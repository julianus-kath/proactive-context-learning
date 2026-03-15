"""
Evaluate a /process_query run against partner-provided table labels.

This evaluator does not require reference SQL. It measures whether the
tables used by the generated SQL cover the required table set per query.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SQL_TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:(?:public|dbo)\.)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
SQL_CTE_NAME_PATTERN = re.compile(
    r"(?:\bWITH\b|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_table_name(name: str) -> str:
    value = (name or "").strip().replace('"', "").replace("[", "").replace("]", "")
    value = value.rstrip(",")
    if not value:
        return value
    parts = [p for p in value.split(".") if p]
    return parts[-1].lower() if parts else value.lower()


def _extract_tables_from_sql(sql: str) -> List[str]:
    cte_names = {
        _normalize_table_name(match)
        for match in SQL_CTE_NAME_PATTERN.findall(sql or "")
    }
    tables: List[str] = []
    for match in SQL_TABLE_PATTERN.findall(sql or ""):
        table = _normalize_table_name(match)
        if table in cte_names:
            continue
        if table and table not in tables:
            tables.append(table)
    return tables


def _dedupe_keep_order(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_labels(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = _load_json(path)
    meta: Dict[str, Any] = {}

    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        labels = raw["labels"]
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    elif isinstance(raw, list):
        labels = raw
    else:
        raise ValueError("Table labels must be a JSON list or an object with a 'labels' list.")

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in labels:
        if not isinstance(row, dict):
            continue
        query_id = str(row.get("query_id") or row.get("id") or "").strip()
        if not query_id:
            continue
        by_id[query_id] = row
    return by_id, meta


def _eval_query(
    query_id: str,
    label_row: Dict[str, Any],
    process_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    required_tables_raw = [
        str(x).strip()
        for x in (label_row.get("required_tables") or [])
        if str(x).strip()
    ]
    required_tables = _dedupe_keep_order([_normalize_table_name(x) for x in required_tables_raw])

    external_sources = [
        str(x).strip()
        for x in (label_row.get("external_required_sources") or [])
        if str(x).strip()
    ]

    response_found = isinstance(process_row, dict)
    sql_query = (process_row or {}).get("sql_query")
    sql_present = isinstance(sql_query, str) and sql_query.strip() != ""

    candidate_tables_raw: List[str] = []
    if response_found:
        tables_used = (process_row or {}).get("tables_used") or []
        if isinstance(tables_used, list):
            candidate_tables_raw.extend([str(x) for x in tables_used if str(x).strip()])

        exec_result = (process_row or {}).get("exec_result") or {}
        if isinstance(exec_result, dict):
            exec_tables = exec_result.get("tables_used") or []
            if isinstance(exec_tables, list):
                candidate_tables_raw.extend([str(x) for x in exec_tables if str(x).strip()])

    if sql_present:
        candidate_tables_raw.extend(_extract_tables_from_sql(str(sql_query)))

    candidate_tables_raw = _dedupe_keep_order(candidate_tables_raw)
    candidate_tables = _dedupe_keep_order([_normalize_table_name(x) for x in candidate_tables_raw])

    required_set = set(required_tables)
    candidate_set = set(candidate_tables)
    matched_required = sorted(required_set.intersection(candidate_set))
    missing_required = sorted(required_set.difference(candidate_set))
    extra_tables = sorted(candidate_set.difference(required_set))

    if required_tables:
        table_recall = len(matched_required) / len(required_tables)
        required_tables_ok = len(missing_required) == 0
    else:
        table_recall = None
        required_tables_ok = None

    return {
        "query_id": query_id,
        "question": label_row.get("question"),
        "response_found": response_found,
        "status": (process_row or {}).get("status"),
        "latency_ms_total": (process_row or {}).get("latency_ms_total"),
        "error": (process_row or {}).get("error"),
        "sql_present": sql_present,
        "required_tables_raw": required_tables_raw,
        "required_tables": required_tables,
        "candidate_tables_raw": candidate_tables_raw,
        "candidate_tables": candidate_tables,
        "matched_required_tables": matched_required,
        "missing_required_tables": missing_required,
        "extra_candidate_tables": extra_tables,
        "required_tables_ok": required_tables_ok,
        "required_table_recall": table_recall,
        "external_required_sources": external_sources,
        "notes": label_row.get("notes"),
    }


def _summarize(per_query: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(per_query)
    responses_found = sum(1 for row in per_query if row.get("response_found") is True)
    sql_present_count = sum(1 for row in per_query if row.get("sql_present") is True)
    required_ok_count = sum(1 for row in per_query if row.get("required_tables_ok") is True)
    has_required_labels = sum(1 for row in per_query if row.get("required_tables"))
    external_sources_count = sum(1 for row in per_query if row.get("external_required_sources"))

    recalls = [
        _safe_float(row.get("required_table_recall"))
        for row in per_query
        if _safe_float(row.get("required_table_recall")) is not None
    ]
    avg_recall = statistics.mean(recalls) if recalls else None
    median_recall = statistics.median(recalls) if recalls else None

    return {
        "total_queries": total,
        "responses_found_count": responses_found,
        "responses_found_rate": (responses_found / total) if total else None,
        "sql_present_count": sql_present_count,
        "sql_present_rate": (sql_present_count / total) if total else None,
        "queries_with_required_table_labels": has_required_labels,
        "required_tables_ok_count": required_ok_count,
        "required_tables_ok_rate_all_queries": (required_ok_count / total) if total else None,
        "required_tables_ok_rate_labeled_queries": (
            required_ok_count / has_required_labels if has_required_labels else None
        ),
        "mean_required_table_recall": avg_recall,
        "median_required_table_recall": median_recall,
        "queries_with_external_required_sources": external_sources_count,
    }


def _render_md(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    rows = payload.get("per_query") or []
    lines = [
        "# /process_query Table-Label Evaluation",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Run dir: `{payload.get('run_dir')}`",
        f"- Labels file: `{payload.get('labels_path')}`",
        "",
        "## Summary",
        "",
        f"- Total queries: `{summary.get('total_queries')}`",
        f"- Responses found: `{summary.get('responses_found_count')}`",
        f"- SQL present: `{summary.get('sql_present_count')}`",
        f"- Required tables ok (count): `{summary.get('required_tables_ok_count')}`",
        f"- Mean required-table recall: `{summary.get('mean_required_table_recall')}`",
        "",
        "| Query | Required tables ok | Recall | SQL present | Missing required tables |",
        "|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {qid} | {ok} | {recall} | {sql_present} | {missing} |".format(
                qid=row.get("query_id"),
                ok=row.get("required_tables_ok"),
                recall=(
                    f"{row.get('required_table_recall'):.3f}"
                    if isinstance(row.get("required_table_recall"), (int, float))
                    else "None"
                ),
                sql_present=row.get("sql_present"),
                missing=", ".join(row.get("missing_required_tables") or []),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_manual_template(per_query: List[Dict[str, Any]]) -> Dict[str, Any]:
    reviews: Dict[str, Any] = {}
    for row in per_query:
        qid = row.get("query_id")
        if not qid:
            continue
        reviews[str(qid)] = {
            "query_id": qid,
            "auto_required_tables_ok": row.get("required_tables_ok"),
            "auto_required_table_recall": row.get("required_table_recall"),
            "required_tables": row.get("required_tables"),
            "candidate_tables": row.get("candidate_tables"),
            "reviewed_required_tables_ok": None,
            "reviewed_notes": "",
        }
    return {"generated_at_utc": _utc_now(), "reviews": reviews}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate /process_query run with table-label ground truth.")
    parser.add_argument("--run-dir", required=True, help="Run directory containing process_query_results.json")
    parser.add_argument("--table-labels", required=True, help="Path to table label JSON")
    parser.add_argument(
        "--out-json",
        default=None,
        help="Optional output JSON path (default: <run-dir>/table_label_eval.json)",
    )
    parser.add_argument(
        "--out-md",
        default=None,
        help="Optional output Markdown path (default: <run-dir>/table_label_eval.md)",
    )
    parser.add_argument(
        "--out-manual-template",
        default=None,
        help="Optional manual review template path (default: <run-dir>/table_label_manual_review_template.json)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir not found: {run_dir}")

    results_path = run_dir / "process_query_results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"Missing process results: {results_path}")

    labels_path = Path(args.table_labels).resolve()
    if not labels_path.exists():
        raise FileNotFoundError(f"Table labels not found: {labels_path}")

    process_results = _load_json(results_path)
    if not isinstance(process_results, dict):
        raise ValueError("process_query_results.json must be an object keyed by query_id.")

    labels_by_id, labels_meta = _load_labels(labels_path)
    per_query: List[Dict[str, Any]] = []
    for query_id, label_row in labels_by_id.items():
        row = _eval_query(query_id=query_id, label_row=label_row, process_row=process_results.get(query_id))
        if not row.get("question"):
            row["question"] = (process_results.get(query_id) or {}).get("question")
        per_query.append(row)
    per_query.sort(key=lambda x: str(x.get("query_id") or ""))

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
        "summary": _summarize(per_query),
        "per_query": per_query,
    }

    out_json = Path(args.out_json).resolve() if args.out_json else (run_dir / "table_label_eval.json")
    out_md = Path(args.out_md).resolve() if args.out_md else (run_dir / "table_label_eval.md")
    out_manual = (
        Path(args.out_manual_template).resolve()
        if args.out_manual_template
        else (run_dir / "table_label_manual_review_template.json")
    )

    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")
    out_manual.write_text(json.dumps(_build_manual_template(per_query), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Table-label eval JSON: {out_json}")
    print(f"Table-label eval MD: {out_md}")
    print(f"Manual review template: {out_manual}")


if __name__ == "__main__":
    main()

