"""
Stage-aware H2b grounding evaluation for /process_query run artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SQL_TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:(?:public|dbo)\.)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
SQL_CTE_NAME_PATTERN = re.compile(
    r"(?:\bWITH\b|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(",
    re.IGNORECASE,
)
STAGE_ORDER = ("final_sql", "ranked", "discovery")
SUPPORTED_STAGES = ("discovery", "ranked", "final_sql")


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _normalize_table_name(name: str) -> str:
    value = (name or "").strip().replace('"', "").replace("[", "").replace("]", "")
    value = value.rstrip(",")
    if not value:
        return value
    parts = [part for part in value.split(".") if part]
    return parts[-1].lower() if parts else value.lower()


def _dedupe_keep_order(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _extract_tables_from_sql(sql: str) -> List[str]:
    cte_names = {_normalize_table_name(match) for match in SQL_CTE_NAME_PATTERN.findall(sql or "")}
    out: List[str] = []
    for match in SQL_TABLE_PATTERN.findall(sql or ""):
        table = _normalize_table_name(match)
        if table in cte_names:
            continue
        if table and table not in out:
            out.append(table)
    return out


def _parse_stage_list(raw: str) -> List[str]:
    items = [part.strip().lower() for part in (raw or "").split(",") if part.strip()]
    out: List[str] = []
    for item in items:
        if item not in SUPPORTED_STAGES:
            raise ValueError(
                f"Unsupported stage '{item}'. Supported stages: {', '.join(SUPPORTED_STAGES)}"
            )
        if item not in out:
            out.append(item)
    return out


def _load_labels(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = _load_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        labels = [row for row in raw["labels"] if isinstance(row, dict)]
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    elif isinstance(raw, list):
        labels = [row for row in raw if isinstance(row, dict)]
        meta = {}
    else:
        raise ValueError("labels must be list or object with labels[]")

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in labels:
        qid = str(row.get("query_id") or row.get("id") or "").strip()
        if qid:
            by_id[qid] = row
    return by_id, meta


def _derive_sql_execution_success(process_row: Dict[str, Any], sql_present: bool) -> Optional[bool]:
    if isinstance(process_row.get("sql_execution_success"), bool):
        return process_row.get("sql_execution_success")
    if not sql_present:
        return None
    exec_result = process_row.get("exec_result")
    if not isinstance(exec_result, dict) or not exec_result:
        return None
    if isinstance(exec_result.get("ok"), bool):
        return exec_result.get("ok")
    if exec_result.get("error") or exec_result.get("error_message"):
        return False
    row_count = exec_result.get("row_count")
    rows = exec_result.get("data")
    if not isinstance(rows, list):
        rows = exec_result.get("rows")
    if row_count is not None or isinstance(rows, list):
        return True
    return None


def _extract_stage_tables(process_row: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Dict[str, bool], List[str]]:
    notes: List[str] = []
    stage_tables: Dict[str, List[str]] = {stage: [] for stage in SUPPORTED_STAGES}
    stage_presence: Dict[str, bool] = {stage: False for stage in SUPPORTED_STAGES}

    raw_stage = process_row.get("stage_tables")
    if isinstance(raw_stage, dict):
        for stage in SUPPORTED_STAGES:
            values = raw_stage.get(stage)
            if isinstance(values, list):
                stage_tables[stage] = _dedupe_keep_order(
                    [_normalize_table_name(str(v)) for v in values if str(v).strip()]
                )
                stage_presence[stage] = True
        notes.append("stage_tables present in process artifact")

    raw_presence = process_row.get("trace_stage_presence")
    if isinstance(raw_presence, dict):
        for stage in SUPPORTED_STAGES:
            if stage in raw_presence:
                stage_presence[stage] = bool(raw_presence.get(stage))
        notes.append("trace_stage_presence present in process artifact")

    sql_query = str(process_row.get("sql_query") or "").strip()
    if sql_query:
        sql_tables = _extract_tables_from_sql(sql_query)
        stage_tables["final_sql"] = _dedupe_keep_order(stage_tables["final_sql"] + sql_tables)
        stage_presence["final_sql"] = True
        notes.append("final_sql inferred from sql_query")

    exec_result = process_row.get("exec_result")
    if isinstance(exec_result, dict):
        exec_tables = []
        for value in (exec_result.get("tables_used") or []) + (exec_result.get("tables") or []):
            text = str(value).strip()
            if text:
                exec_tables.append(_normalize_table_name(text))
        if exec_tables:
            stage_tables["final_sql"] = _dedupe_keep_order(stage_tables["final_sql"] + exec_tables)
            stage_presence["final_sql"] = True
            notes.append("final_sql inferred from exec_result tables")

    # Backward-compatible fallback: treat legacy tables_used as ranked evidence when missing.
    if not stage_tables["ranked"]:
        legacy_ranked = [_normalize_table_name(str(v)) for v in (process_row.get("tables_used") or []) if str(v).strip()]
        if legacy_ranked:
            stage_tables["ranked"] = _dedupe_keep_order(legacy_ranked)
            if not stage_presence["ranked"]:
                stage_presence["ranked"] = False
            notes.append("ranked fallback inferred from tables_used (legacy artifact)")

    return stage_tables, stage_presence, notes


def _eval_query(
    query_id: str,
    label_row: Dict[str, Any],
    process_row: Optional[Dict[str, Any]],
    required_stage_traces: Sequence[str],
) -> Dict[str, Any]:
    process_row = process_row if isinstance(process_row, dict) else {}
    response_found = bool(process_row)

    required_original = [str(x).strip() for x in (label_row.get("required_tables_original") or label_row.get("required_tables") or []) if str(x).strip()]
    required_resolved_raw = [
        str(x).strip()
        for x in (
            label_row.get("required_tables_resolved")
            or label_row.get("required_tables")
            or []
        )
        if str(x).strip()
    ]
    required_resolved = _dedupe_keep_order([_normalize_table_name(x) for x in required_resolved_raw])
    unresolved = [str(x).strip() for x in (label_row.get("unresolved_required_labels") or []) if str(x).strip()]

    stage_tables, stage_presence, stage_notes = _extract_stage_tables(process_row)
    required_set = set(required_resolved)
    stage_sets = {stage: set(stage_tables.get(stage) or []) for stage in SUPPORTED_STAGES}

    surfaced_stage_by_table: Dict[str, Optional[str]] = {}
    for table in required_resolved:
        surfaced_stage_by_table[table] = None
        for stage in STAGE_ORDER:
            if table in stage_sets.get(stage, set()):
                surfaced_stage_by_table[table] = stage
                break

    surfaced_required = [table for table in required_resolved if surfaced_stage_by_table.get(table)]
    missing_required = [table for table in required_resolved if not surfaced_stage_by_table.get(table)]
    surfaced_tables_union = _dedupe_keep_order(
        stage_tables["final_sql"] + stage_tables["ranked"] + stage_tables["discovery"]
    )

    required_count = len(required_resolved)
    matched_count = len(surfaced_required)
    required_table_recall = (matched_count / required_count) if required_count else None
    required_tables_ok = (matched_count == required_count) if required_count else None

    def _stage_recall(stage: str) -> Optional[float]:
        if not required_count:
            return None
        return len(required_set.intersection(stage_sets.get(stage, set()))) / required_count

    sql_query = str(process_row.get("sql_query") or "").strip()
    sql_present = bool(sql_query)
    sql_execution_success = _derive_sql_execution_success(process_row, sql_present)
    policy_violation = bool(process_row.get("policy_violation"))
    error_type = process_row.get("error_type")
    if error_type is None and process_row.get("status") == "failed":
        error_type = "failed_without_error_type"

    missing_required_stage_traces = [stage for stage in required_stage_traces if not bool(stage_presence.get(stage))]
    trace_complete = len(missing_required_stage_traces) == 0

    return {
        "query_id": query_id,
        "question": label_row.get("question") or process_row.get("question"),
        "response_found": response_found,
        "status": process_row.get("status"),
        "latency_ms": process_row.get("latency_ms_total"),
        "error": process_row.get("error"),
        "required_tables_original": required_original,
        "required_tables": required_resolved,
        "unresolved_required_labels": unresolved,
        "required_table_count": required_count,
        "matched_required_table_count": matched_count,
        "required_tables_ok": required_tables_ok,
        "required_table_recall": required_table_recall,
        "surfaced_tables": surfaced_tables_union,
        "surfaced_stage_by_required_table": surfaced_stage_by_table,
        "missing_required_tables": missing_required,
        "stage_tables": stage_tables,
        "trace_stage_presence": stage_presence,
        "missing_required_stage_traces": missing_required_stage_traces,
        "trace_complete": trace_complete,
        "discovery_stage_required_recall": _stage_recall("discovery"),
        "ranked_stage_required_recall": _stage_recall("ranked"),
        "final_sql_required_recall": _stage_recall("final_sql"),
        "sql_present": sql_present,
        "sql_execution_success": sql_execution_success,
        "policy_violation": policy_violation,
        "error_type": error_type,
        "notes": _dedupe_keep_order(stage_notes + [str(x) for x in (process_row.get("trace_extraction_notes") or []) if str(x).strip()]),
    }


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    recalls = [_safe_float(row.get("required_table_recall")) for row in rows]
    recalls = [value for value in recalls if value is not None]
    latencies = [_safe_float(row.get("latency_ms")) for row in rows]
    latencies = [value for value in latencies if value is not None]

    return {
        "total_queries": total,
        "mean_required_table_recall": statistics.mean(recalls) if recalls else None,
        "queries_with_all_required_tables_surfaced": sum(1 for row in rows if row.get("required_tables_ok") is True),
        "required_tables_ok_rate": (
            sum(1 for row in rows if row.get("required_tables_ok") is True) / total
            if total
            else None
        ),
        "sql_present_count": sum(1 for row in rows if row.get("sql_present") is True),
        "sql_execution_success_count": sum(1 for row in rows if row.get("sql_execution_success") is True),
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "policy_violations": sum(1 for row in rows if row.get("policy_violation") is True),
        "trace_complete_count": sum(1 for row in rows if row.get("trace_complete") is True),
        "queries_with_unresolved_required_labels": sum(
            1 for row in rows if (row.get("unresolved_required_labels") or [])
        ),
    }


def _render_md(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    rows = payload.get("per_query") or []

    lines = [
        "# H2b /process_query Grounding Evaluation",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Run dir: `{payload.get('run_dir')}`",
        f"- Labels: `{payload.get('labels_path')}`",
        f"- Required stage traces: `{', '.join(payload.get('required_stage_traces') or [])}`",
        "",
        "## Summary",
        "",
        f"- Number of queries: `{summary.get('total_queries')}`",
        f"- Mean required-table recall: `{summary.get('mean_required_table_recall')}`",
        f"- Queries with all required tables surfaced: `{summary.get('queries_with_all_required_tables_surfaced')}`",
        f"- SQL present count: `{summary.get('sql_present_count')}`",
        f"- SQL execution success count: `{summary.get('sql_execution_success_count')}`",
        f"- Median latency: `{summary.get('median_latency_ms')}`",
        f"- Policy violations: `{summary.get('policy_violations')}`",
        "",
        "| Query | Required recall | All required ok | SQL present | SQL exec ok | Trace complete | Missing required |",
        "|---|---:|---|---|---|---|---|",
    ]

    for row in rows:
        recall = row.get("required_table_recall")
        lines.append(
            "| {qid} | {recall} | {ok} | {sql} | {exec_ok} | {trace} | {missing} |".format(
                qid=row.get("query_id"),
                recall=(f"{recall:.3f}" if isinstance(recall, (int, float)) else "None"),
                ok=row.get("required_tables_ok"),
                sql=row.get("sql_present"),
                exec_ok=row.get("sql_execution_success"),
                trace=row.get("trace_complete"),
                missing=", ".join(row.get("missing_required_tables") or []),
            )
        )

    lines.append("")
    lines.append("## Scoring Rule")
    lines.append("")
    lines.append(
        "A required table is counted as surfaced with precedence: `final_sql` -> `ranked` -> `discovery`."
    )
    lines.append("")
    return "\n".join(lines)


def _write_trace_failure_report(
    run_dir: Path,
    labels_path: Path,
    required_stage_traces: Sequence[str],
    failures: List[Dict[str, Any]],
) -> Path:
    report = {
        "generated_at_utc": _utc_now(),
        "run_dir": str(run_dir),
        "labels_path": str(labels_path),
        "required_stage_traces": list(required_stage_traces),
        "failure_count": len(failures),
        "failures": failures,
        "message": (
            "Strict stage-trace requirement failed. "
            "Primary H2b grounding scoring must not proceed for this run."
        ),
    }
    out_path = run_dir / "trace_failure_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate /process_query runs with stage-aware H2b grounding.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--table-labels", required=True, help="Normalized labels artifact path.")
    parser.add_argument("--required-stage-traces", default="discovery,ranked")
    parser.add_argument(
        "--strict-stage-traces",
        action="store_true",
        default=True,
        help="Fail if required stage traces are missing on any query.",
    )
    parser.add_argument(
        "--no-strict-stage-traces",
        action="store_true",
        default=False,
        help="Disable strict trace failure behavior.",
    )
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    labels_path = Path(args.table_labels).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"run dir not found: {run_dir}")
    if not labels_path.exists():
        raise FileNotFoundError(f"labels file not found: {labels_path}")

    strict_stage_traces = bool(args.strict_stage_traces and not args.no_strict_stage_traces)
    required_stage_traces = _parse_stage_list(args.required_stage_traces)

    process_results_path = run_dir / "process_query_results.json"
    if not process_results_path.exists():
        raise FileNotFoundError(f"Missing process results: {process_results_path}")

    process_results = _load_json(process_results_path)
    if not isinstance(process_results, dict):
        raise ValueError("process_query_results.json must be an object keyed by query_id")

    labels_by_id, labels_meta = _load_labels(labels_path)
    per_query: List[Dict[str, Any]] = []
    for query_id, label_row in labels_by_id.items():
        row = _eval_query(
            query_id=query_id,
            label_row=label_row,
            process_row=process_results.get(query_id),
            required_stage_traces=required_stage_traces,
        )
        per_query.append(row)
    per_query.sort(key=lambda x: str(x.get("query_id") or ""))

    strict_failures = [
        {
            "query_id": row.get("query_id"),
            "missing_required_stage_traces": row.get("missing_required_stage_traces"),
            "trace_stage_presence": row.get("trace_stage_presence"),
        }
        for row in per_query
        if row.get("trace_complete") is False
    ]

    if strict_stage_traces and strict_failures:
        report_path = _write_trace_failure_report(
            run_dir=run_dir,
            labels_path=labels_path,
            required_stage_traces=required_stage_traces,
            failures=strict_failures,
        )
        print(f"Trace failure report: {report_path}")
        print("Strict stage-trace requirement failed.")
        sys.exit(2)

    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = _load_json(run_manifest_path) if run_manifest_path.exists() else {}
    if not isinstance(run_manifest, dict):
        run_manifest = {}

    payload = {
        "generated_at_utc": _utc_now(),
        "run_dir": str(run_dir),
        "run_id": run_manifest.get("run_id"),
        "mode_label": run_manifest.get("mode_label"),
        "scout_mode_start": run_manifest.get("scout_mode_start"),
        "scout_mode_end": run_manifest.get("scout_mode_end"),
        "labels_path": str(labels_path),
        "labels_meta": labels_meta,
        "required_stage_traces": required_stage_traces,
        "strict_stage_traces": strict_stage_traces,
        "summary": _summarize(per_query),
        "per_query": per_query,
    }

    out_json = Path(args.out_json).resolve() if args.out_json else (run_dir / "grounding_eval.json")
    out_md = Path(args.out_md).resolve() if args.out_md else (run_dir / "grounding_eval.md")

    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")

    print(f"Grounding eval JSON: {out_json}")
    print(f"Grounding eval MD: {out_md}")


if __name__ == "__main__":
    main()
