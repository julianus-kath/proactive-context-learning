"""
Create compact thesis-ready report for H2b /process_query grounding runs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object in {path}")
    return payload


def _parse_mode_runs(values: List[str]) -> Dict[str, Path]:
    mode_runs: Dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("Each --mode-run must be formatted as mode=/abs/or/rel/path")
        mode, path = value.split("=", 1)
        mode = mode.strip()
        if not mode:
            raise ValueError("Mode name cannot be empty in --mode-run")
        mode_runs[mode] = Path(path).resolve()
    return mode_runs


def _load_mode_payload(run_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    eval_path = run_dir / "grounding_eval.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"Missing grounding_eval.json in {run_dir}")
    eval_payload = _load_json(eval_path)

    manifest_path = run_dir / "run_manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    return eval_payload, manifest


def _aggregate_row(mode: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": mode,
        "number_of_queries": summary.get("total_queries"),
        "mean_required_table_recall": summary.get("mean_required_table_recall"),
        "queries_with_all_required_tables_surfaced": summary.get("queries_with_all_required_tables_surfaced"),
        "sql_present_count": summary.get("sql_present_count"),
        "sql_execution_success_count": summary.get("sql_execution_success_count"),
        "median_latency_ms": summary.get("median_latency_ms"),
        "policy_violations": summary.get("policy_violations"),
    }


def _render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# H2b /process_query Grounding Report",
        "",
        "## Experiment Definition",
        "",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Endpoint(s): `{', '.join(report.get('experiment', {}).get('endpoints') or [])}`",
        f"- Dataset(s): `{', '.join(report.get('experiment', {}).get('datasets') or [])}`",
        f"- Modes: `{', '.join(report.get('experiment', {}).get('modes') or [])}`",
        f"- Scoring logic: `{report.get('experiment', {}).get('scoring_logic')}`",
        "",
        "## Label Normalization Summary",
        "",
    ]

    normalization = report.get("label_normalization_summary")
    if isinstance(normalization, dict):
        lines.append(f"- Source: `{normalization.get('source')}`")
        lines.append(f"- Exact: `{normalization.get('exact')}`")
        lines.append(f"- Alias/prefix-normalized: `{normalization.get('alias_prefix_normalized')}`")
        lines.append(f"- Manual-confirmed: `{normalization.get('manual_confirmed')}`")
        lines.append(f"- Unresolved: `{normalization.get('unresolved')}`")
    else:
        lines.append("- No normalization artifact supplied.")

    lines.extend(
        [
            "",
            "## Aggregate Metrics by Mode",
            "",
            "| Mode | #Queries | Mean required recall | All-required surfaced | SQL present | SQL exec success | Median latency (ms) | Policy violations |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("aggregate_table") or []:
        lines.append(
            "| {mode} | {n} | {recall} | {all_ok} | {sql_present} | {sql_exec} | {latency} | {policy} |".format(
                mode=row.get("mode"),
                n=row.get("number_of_queries"),
                recall=row.get("mean_required_table_recall"),
                all_ok=row.get("queries_with_all_required_tables_surfaced"),
                sql_present=row.get("sql_present_count"),
                sql_exec=row.get("sql_execution_success_count"),
                latency=row.get("median_latency_ms"),
                policy=row.get("policy_violations"),
            )
        )

    lines.extend(["", "## Per-Query Tables", ""])
    for mode, rows in (report.get("per_query_by_mode") or {}).items():
        lines.append(f"### {mode}")
        lines.append("")
        lines.append(
            "| Query ID | Required tables | Surfaced tables | Required recall | All-required-ok | SQL present | Execution success | Latency (ms) | Notes/mismatches |"
        )
        lines.append("|---|---|---|---:|---|---|---|---:|---|")
        for row in rows:
            lines.append(
                "| {qid} | {required} | {surfaced} | {recall} | {ok} | {sql} | {exec_ok} | {latency} | {notes} |".format(
                    qid=row.get("query_id"),
                    required=", ".join(row.get("required_tables") or []),
                    surfaced=", ".join(row.get("surfaced_tables") or []),
                    recall=row.get("required_table_recall"),
                    ok=row.get("required_tables_ok"),
                    sql=row.get("sql_present"),
                    exec_ok=row.get("sql_execution_success"),
                    latency=row.get("latency_ms"),
                    notes="; ".join(row.get("notes") or []),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            report.get("interpretation") or "",
            "",
            "## Methodological Comparability (H2a vs H2b)",
            "",
            "H2a and H2b both use the same `/process_query` full agent pipeline.",
            "H2a is scored on semantic correctness; H2b is scored on production table grounding and operational robustness.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact H2b /process_query grounding report.")
    parser.add_argument(
        "--mode-run",
        action="append",
        required=True,
        help="Mode/run binding formatted as mode=/path/to/run_dir. Repeat for each mode.",
    )
    parser.add_argument(
        "--label-normalization",
        default=None,
        help="Optional label_normalization.json path for summary injection.",
    )
    parser.add_argument("--out-name", default="h2b_process_query_grounding_report")
    args = parser.parse_args()

    mode_runs = _parse_mode_runs(args.mode_run)

    experiment_endpoints: List[str] = []
    experiment_datasets: List[str] = []
    aggregate_table: List[Dict[str, Any]] = []
    per_query_by_mode: Dict[str, List[Dict[str, Any]]] = {}

    for mode, run_dir in mode_runs.items():
        eval_payload, manifest = _load_mode_payload(run_dir)
        summary = eval_payload.get("summary") if isinstance(eval_payload.get("summary"), dict) else {}
        rows = eval_payload.get("per_query") if isinstance(eval_payload.get("per_query"), list) else []

        aggregate_table.append(_aggregate_row(mode, summary))

        condensed_rows: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            notes: List[str] = []
            missing = row.get("missing_required_tables") or []
            unresolved = row.get("unresolved_required_labels") or []
            if missing:
                notes.append("missing_required=" + ",".join(missing))
            if unresolved:
                notes.append("unresolved_labels=" + ",".join(unresolved))
            if row.get("trace_complete") is False:
                notes.append(
                    "missing_traces=" + ",".join(row.get("missing_required_stage_traces") or [])
                )
            condensed_rows.append(
                {
                    "query_id": row.get("query_id"),
                    "required_tables": row.get("required_tables") or [],
                    "surfaced_tables": row.get("surfaced_tables") or [],
                    "required_table_recall": row.get("required_table_recall"),
                    "required_tables_ok": row.get("required_tables_ok"),
                    "sql_present": row.get("sql_present"),
                    "sql_execution_success": row.get("sql_execution_success"),
                    "latency_ms": row.get("latency_ms"),
                    "notes": notes,
                }
            )
        per_query_by_mode[mode] = condensed_rows

        endpoint = manifest.get("target_url")
        if isinstance(endpoint, str) and endpoint not in experiment_endpoints:
            experiment_endpoints.append(endpoint)
        dataset = manifest.get("dataset_path")
        if isinstance(dataset, str) and dataset not in experiment_datasets:
            experiment_datasets.append(dataset)

    normalization_summary = None
    if args.label_normalization:
        normalization_payload = _load_json(Path(args.label_normalization).resolve())
        summary = normalization_payload.get("summary") if isinstance(normalization_payload.get("summary"), dict) else {}
        normalization_summary = {
            "source": args.label_normalization,
            "exact": summary.get("exact"),
            "alias_prefix_normalized": summary.get("alias_prefix_normalized"),
            "manual_confirmed": summary.get("manual_confirmed"),
            "unresolved": summary.get("unresolved"),
        }

    best_mode = None
    if aggregate_table:
        best_mode = sorted(
            aggregate_table,
            key=lambda row: (
                row.get("mean_required_table_recall") if isinstance(row.get("mean_required_table_recall"), (int, float)) else -1
            ),
            reverse=True,
        )[0].get("mode")

    interpretation = (
        "Primary signal: required-table grounding under full `/process_query` pipeline. "
        + (f"Best mean required-table recall in this run set: `{best_mode}`." if best_mode else "")
    )

    report_payload = {
        "generated_at_utc": _utc_now(),
        "experiment": {
            "endpoints": experiment_endpoints,
            "datasets": experiment_datasets,
            "modes": list(mode_runs.keys()),
            "scoring_logic": "required-table grounding with surfaced precedence final_sql > ranked > discovery",
        },
        "label_normalization_summary": normalization_summary,
        "aggregate_table": aggregate_table,
        "per_query_by_mode": per_query_by_mode,
        "interpretation": interpretation,
    }

    out_dir = Path(__file__).resolve().parent / "runs" / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "report.md").write_text(_render_md(report_payload), encoding="utf-8")

    print(f"Output: {out_dir}")
    print(f"Modes: {', '.join(mode_runs.keys())}")


if __name__ == "__main__":
    main()
