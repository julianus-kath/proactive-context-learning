"""
Compare two /process_query runs using table-label evaluation artifacts.

Expected input artifact in each run dir:
- table_label_eval.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_get(d: Any, key: str, default: Any = None) -> Any:
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def _load_run_eval(run_dir: Path) -> Dict[str, Any]:
    eval_path = run_dir / "table_label_eval.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"Missing table-label eval artifact: {eval_path}")
    payload = _load_json(eval_path)

    summary = payload.get("summary") if isinstance(payload, dict) else {}
    per_query = payload.get("per_query") if isinstance(payload, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(per_query, list):
        per_query = []

    return {
        "run_dir": str(run_dir),
        "run_id": payload.get("run_id"),
        "mode_label": payload.get("mode_label"),
        "scout_mode_start": payload.get("scout_mode_start"),
        "summary": summary,
        "per_query": per_query,
    }


def _delta(a: Any, b: Any) -> Optional[float]:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) - float(b)
    return None


def _build_metrics(on_summary: Dict[str, Any], off_summary: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "responses_found_count",
        "responses_found_rate",
        "sql_present_count",
        "sql_present_rate",
        "required_tables_ok_count",
        "required_tables_ok_rate_all_queries",
        "required_tables_ok_rate_labeled_queries",
        "mean_required_table_recall",
        "median_required_table_recall",
    ]
    metrics: Dict[str, Any] = {}
    for key in keys:
        on_val = on_summary.get(key)
        off_val = off_summary.get(key)
        metrics[key] = {
            "on": on_val,
            "off": off_val,
            "delta_on_minus_off": _delta(on_val, off_val),
        }
    return metrics


def _build_per_query(on_rows: List[Dict[str, Any]], off_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    on_map = {
        str(row.get("query_id")): row
        for row in on_rows
        if isinstance(row, dict) and row.get("query_id") is not None
    }
    off_map = {
        str(row.get("query_id")): row
        for row in off_rows
        if isinstance(row, dict) and row.get("query_id") is not None
    }
    query_ids = sorted(set(on_map.keys()) | set(off_map.keys()))

    rows: List[Dict[str, Any]] = []
    for query_id in query_ids:
        on_row = on_map.get(query_id) or {}
        off_row = off_map.get(query_id) or {}
        rows.append(
            {
                "query_id": query_id,
                "question": on_row.get("question") or off_row.get("question"),
                "on_required_tables_ok": on_row.get("required_tables_ok"),
                "off_required_tables_ok": off_row.get("required_tables_ok"),
                "on_required_table_recall": on_row.get("required_table_recall"),
                "off_required_table_recall": off_row.get("required_table_recall"),
                "on_sql_present": on_row.get("sql_present"),
                "off_sql_present": off_row.get("sql_present"),
                "on_missing_required_tables": on_row.get("missing_required_tables"),
                "off_missing_required_tables": off_row.get("missing_required_tables"),
            }
        )
    return rows


def _render_md(payload: Dict[str, Any]) -> str:
    on = payload.get("on") or {}
    off = payload.get("off") or {}
    metrics = payload.get("metrics") or {}
    per_query = payload.get("per_query") or []

    lines = [
        "# /process_query Table-Label ON vs OFF Comparison",
        "",
        f"- ON run: `{_safe_get(on, 'run_id')}` ({_safe_get(on, 'run_dir')})",
        f"- OFF run: `{_safe_get(off, 'run_id')}` ({_safe_get(off, 'run_dir')})",
        f"- ON scout mode: `{_safe_get(_safe_get(on, 'scout_mode_start', {}), 'backend')}` active=`{_safe_get(_safe_get(on, 'scout_mode_start', {}), 'active')}`",
        f"- OFF scout mode: `{_safe_get(_safe_get(off, 'scout_mode_start', {}), 'backend')}` active=`{_safe_get(_safe_get(off, 'scout_mode_start', {}), 'active')}`",
        "",
        "| Metric | ON | OFF | Delta (ON-OFF) |",
        "|---|---:|---:|---:|",
    ]
    for key, metric in metrics.items():
        lines.append(
            f"| {key} | {metric.get('on')} | {metric.get('off')} | {metric.get('delta_on_minus_off')} |"
        )

    lines.extend(
        [
            "",
            "| Query | ON required ok | OFF required ok | ON recall | OFF recall | ON sql | OFF sql |",
            "|---|---|---|---:|---:|---|---|",
        ]
    )
    for row in per_query:
        lines.append(
            "| {query_id} | {on_ok} | {off_ok} | {on_recall} | {off_recall} | {on_sql} | {off_sql} |".format(
                query_id=row.get("query_id"),
                on_ok=row.get("on_required_tables_ok"),
                off_ok=row.get("off_required_tables_ok"),
                on_recall=(
                    f"{row.get('on_required_table_recall'):.3f}"
                    if isinstance(row.get("on_required_table_recall"), (int, float))
                    else "None"
                ),
                off_recall=(
                    f"{row.get('off_required_table_recall'):.3f}"
                    if isinstance(row.get("off_required_table_recall"), (int, float))
                    else "None"
                ),
                on_sql=row.get("on_sql_present"),
                off_sql=row.get("off_sql_present"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two /process_query table-label evaluation runs.")
    parser.add_argument("--on-run-dir", required=True, help="Run directory for Scout ON.")
    parser.add_argument("--off-run-dir", required=True, help="Run directory for Scout OFF.")
    parser.add_argument(
        "--out-name",
        default="process_query_table_label_ab_compare",
        help="Output folder name suffix under eval/runs.",
    )
    args = parser.parse_args()

    on_run_dir = Path(args.on_run_dir).resolve()
    off_run_dir = Path(args.off_run_dir).resolve()
    on_eval = _load_run_eval(on_run_dir)
    off_eval = _load_run_eval(off_run_dir)

    comparison = {
        "generated_at_utc": _utc_now(),
        "on": {
            "run_dir": on_eval["run_dir"],
            "run_id": on_eval.get("run_id"),
            "mode_label": on_eval.get("mode_label"),
            "scout_mode_start": on_eval.get("scout_mode_start"),
        },
        "off": {
            "run_dir": off_eval["run_dir"],
            "run_id": off_eval.get("run_id"),
            "mode_label": off_eval.get("mode_label"),
            "scout_mode_start": off_eval.get("scout_mode_start"),
        },
        "metrics": _build_metrics(on_eval.get("summary") or {}, off_eval.get("summary") or {}),
        "per_query": _build_per_query(on_eval.get("per_query") or [], off_eval.get("per_query") or []),
    }

    out_dir = Path(__file__).parent / "runs" / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    (out_dir / "comparison.md").write_text(_render_md(comparison), encoding="utf-8")

    print(f"Comparison saved to: {out_dir}")
    print(f"ON run: {comparison['on'].get('run_id')}")
    print(f"OFF run: {comparison['off'].get('run_id')}")


if __name__ == "__main__":
    main()

