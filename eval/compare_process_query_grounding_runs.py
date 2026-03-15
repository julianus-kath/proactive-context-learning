"""
Compare two stage-aware /process_query grounding evaluation runs.
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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object in {path}")
    return data


def _load_eval(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "grounding_eval.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing grounding_eval.json: {path}")
    payload = _load_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    per_query = payload.get("per_query") if isinstance(payload.get("per_query"), list) else []
    return {
        "run_dir": str(run_dir),
        "run_id": payload.get("run_id"),
        "mode_label": payload.get("mode_label"),
        "summary": summary,
        "per_query": [row for row in per_query if isinstance(row, dict)],
    }


def _safe_num(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _delta(a: Any, b: Any) -> Optional[float]:
    left = _safe_num(a)
    right = _safe_num(b)
    if left is None or right is None:
        return None
    return round(left - right, 4)


def _build_summary(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "total_queries",
        "mean_required_table_recall",
        "queries_with_all_required_tables_surfaced",
        "required_tables_ok_rate",
        "sql_present_count",
        "sql_execution_success_count",
        "median_latency_ms",
        "policy_violations",
        "trace_complete_count",
    ]
    out: Dict[str, Any] = {}
    for key in keys:
        l_val = (left.get("summary") or {}).get(key)
        r_val = (right.get("summary") or {}).get(key)
        out[key] = {
            "left": l_val,
            "right": r_val,
            "delta_left_minus_right": _delta(l_val, r_val),
        }
    return out


def _build_per_query(left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    left_by_id = {str(row.get("query_id")): row for row in left_rows if row.get("query_id") is not None}
    right_by_id = {str(row.get("query_id")): row for row in right_rows if row.get("query_id") is not None}
    query_ids = sorted(set(left_by_id.keys()) | set(right_by_id.keys()))

    rows: List[Dict[str, Any]] = []
    for query_id in query_ids:
        left = left_by_id.get(query_id) or {}
        right = right_by_id.get(query_id) or {}
        rows.append(
            {
                "query_id": query_id,
                "question": left.get("question") or right.get("question"),
                "left_required_table_recall": left.get("required_table_recall"),
                "right_required_table_recall": right.get("required_table_recall"),
                "delta_required_table_recall": _delta(
                    left.get("required_table_recall"),
                    right.get("required_table_recall"),
                ),
                "left_required_tables_ok": left.get("required_tables_ok"),
                "right_required_tables_ok": right.get("required_tables_ok"),
                "left_sql_present": left.get("sql_present"),
                "right_sql_present": right.get("sql_present"),
                "left_sql_execution_success": left.get("sql_execution_success"),
                "right_sql_execution_success": right.get("sql_execution_success"),
                "left_latency_ms": left.get("latency_ms"),
                "right_latency_ms": right.get("latency_ms"),
                "left_missing_required_tables": left.get("missing_required_tables") or [],
                "right_missing_required_tables": right.get("missing_required_tables") or [],
            }
        )
    return rows


def _render_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# /process_query Grounding Comparison",
        "",
        f"- Left run: `{payload.get('left', {}).get('run_id')}` ({payload.get('left', {}).get('run_dir')})",
        f"- Right run: `{payload.get('right', {}).get('run_id')}` ({payload.get('right', {}).get('run_dir')})",
        "",
        "| Metric | Left | Right | Delta (Left-Right) |",
        "|---|---:|---:|---:|",
    ]
    for key, row in (payload.get("summary_metrics") or {}).items():
        lines.append(
            f"| {key} | {row.get('left')} | {row.get('right')} | {row.get('delta_left_minus_right')} |"
        )

    lines.extend(
        [
            "",
            "| Query | Left recall | Right recall | Delta | Left ok | Right ok | Left sql | Right sql |",
            "|---|---:|---:|---:|---|---|---|---|",
        ]
    )
    for row in payload.get("per_query") or []:
        lines.append(
            "| {qid} | {l} | {r} | {d} | {lok} | {rok} | {ls} | {rs} |".format(
                qid=row.get("query_id"),
                l=row.get("left_required_table_recall"),
                r=row.get("right_required_table_recall"),
                d=row.get("delta_required_table_recall"),
                lok=row.get("left_required_tables_ok"),
                rok=row.get("right_required_tables_ok"),
                ls=row.get("left_sql_present"),
                rs=row.get("right_sql_present"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two /process_query grounding eval runs.")
    parser.add_argument("--left-run-dir", required=True)
    parser.add_argument("--right-run-dir", required=True)
    parser.add_argument("--out-name", default="process_query_grounding_compare")
    args = parser.parse_args()

    left_dir = Path(args.left_run_dir).resolve()
    right_dir = Path(args.right_run_dir).resolve()
    left = _load_eval(left_dir)
    right = _load_eval(right_dir)

    payload = {
        "generated_at_utc": _utc_now(),
        "left": {
            "run_dir": left.get("run_dir"),
            "run_id": left.get("run_id"),
            "mode_label": left.get("mode_label"),
        },
        "right": {
            "run_dir": right.get("run_dir"),
            "run_id": right.get("run_id"),
            "mode_label": right.get("mode_label"),
        },
        "summary_metrics": _build_summary(left, right),
        "per_query": _build_per_query(left.get("per_query") or [], right.get("per_query") or []),
    }

    out_dir = Path(__file__).resolve().parent / "runs" / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "comparison.md").write_text(_render_md(payload), encoding="utf-8")

    print(f"Output: {out_dir}")
    print(f"Left run: {payload['left'].get('run_id')}")
    print(f"Right run: {payload['right'].get('run_id')}")


if __name__ == "__main__":
    main()
