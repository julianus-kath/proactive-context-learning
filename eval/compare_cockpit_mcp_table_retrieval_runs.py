"""
Compare two MCP table-retrieval evaluation runs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


K_VALUES = (1, 3, 5, 10, 25)


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_payload(run_dir: Path) -> Dict[str, Any]:
    payload_path = run_dir / "retrieval_table_eval.json"
    if not payload_path.exists():
        raise FileNotFoundError(f"Missing retrieval_table_eval.json in {run_dir}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload in {payload_path}")
    return payload


def _index_queries(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for row in payload.get("per_query", []):
        if not isinstance(row, dict):
            continue
        query_id = str(row.get("query_id") or "").strip()
        if not query_id:
            continue
        index[query_id] = row
    return index


def _safe_num(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _build_comparison(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    left_q = _index_queries(left)
    right_q = _index_queries(right)
    query_ids = sorted(set(left_q.keys()).intersection(set(right_q.keys())))

    aggregate: Dict[str, Any] = {}
    left_agg = left.get("aggregate") or {}
    right_agg = right.get("aggregate") or {}
    for k in K_VALUES:
        for metric in (
            f"mean_recall_at_{k}",
            f"required_tables_ok_count_at_{k}",
            f"required_tables_ok_rate_at_{k}",
            f"any_required_hit_rate_at_{k}",
        ):
            aggregate[metric] = {
                "left": left_agg.get(metric),
                "right": right_agg.get(metric),
                "delta_left_minus_right": round(_safe_num(left_agg.get(metric)) - _safe_num(right_agg.get(metric)), 4),
            }
    aggregate["mrr"] = {
        "left": left_agg.get("mrr"),
        "right": right_agg.get("mrr"),
        "delta_left_minus_right": round(_safe_num(left_agg.get("mrr")) - _safe_num(right_agg.get("mrr")), 4),
    }

    per_query: List[Dict[str, Any]] = []
    for query_id in query_ids:
        l = left_q[query_id]
        r = right_q[query_id]
        per_query.append(
            {
                "query_id": query_id,
                "left_recall_at_5": l.get("recall_at_5"),
                "right_recall_at_5": r.get("recall_at_5"),
                "delta_recall_at_5": round(_safe_num(l.get("recall_at_5")) - _safe_num(r.get("recall_at_5")), 4),
                "left_recall_at_10": l.get("recall_at_10"),
                "right_recall_at_10": r.get("recall_at_10"),
                "delta_recall_at_10": round(_safe_num(l.get("recall_at_10")) - _safe_num(r.get("recall_at_10")), 4),
                "left_required_ok_at_10": l.get("required_tables_ok_at_10"),
                "right_required_ok_at_10": r.get("required_tables_ok_at_10"),
                "left_top10": (l.get("retrieved_tables_ranked") or [])[:10],
                "right_top10": (r.get("retrieved_tables_ranked") or [])[:10],
                "required_tables": l.get("required_tables") or r.get("required_tables") or [],
            }
        )
    per_query.sort(key=lambda x: (x["delta_recall_at_10"], x["query_id"]), reverse=True)

    return {
        "generated_at_utc": _utc_now(),
        "left": {
            "run_dir": str(Path(left.get("run_id", "")).parent) if "/" in str(left.get("run_id", "")) else None,
            "run_id": left.get("run_id"),
            "mode_label": left.get("mode_label"),
        },
        "right": {
            "run_dir": str(Path(right.get("run_id", "")).parent) if "/" in str(right.get("run_id", "")) else None,
            "run_id": right.get("run_id"),
            "mode_label": right.get("mode_label"),
        },
        "aggregate": aggregate,
        "per_query": per_query,
        "query_count_compared": len(query_ids),
    }


def _render_md(comp: Dict[str, Any], left_dir: Path, right_dir: Path) -> str:
    lines = [
        "# Cockpit MCP Table-Retrieval Comparison",
        "",
        f"- Left run: `{comp.get('left', {}).get('run_id')}` ({left_dir})",
        f"- Right run: `{comp.get('right', {}).get('run_id')}` ({right_dir})",
        f"- Query count compared: `{comp.get('query_count_compared')}`",
        "",
        "## Aggregate (left minus right)",
        "",
        "| Metric | Left | Right | Delta |",
        "|---|---:|---:|---:|",
    ]
    aggregate = comp.get("aggregate") or {}
    for metric in (
        "mean_recall_at_5",
        "required_tables_ok_count_at_5",
        "required_tables_ok_rate_at_5",
        "mean_recall_at_10",
        "required_tables_ok_count_at_10",
        "required_tables_ok_rate_at_10",
        "mrr",
    ):
        row = aggregate.get(metric) or {}
        lines.append(
            f"| {metric} | {row.get('left')} | {row.get('right')} | {row.get('delta_left_minus_right')} |"
        )

    lines.extend(
        [
            "",
            "## Per-query delta (Recall@10)",
            "",
            "| Query | Left Recall@10 | Right Recall@10 | Delta | Required ok@10 (L/R) |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in comp.get("per_query", []):
        lines.append(
            "| {qid} | {l} | {r} | {d} | {lok}/{rok} |".format(
                qid=row.get("query_id"),
                l=row.get("left_recall_at_10"),
                r=row.get("right_recall_at_10"),
                d=row.get("delta_recall_at_10"),
                lok=row.get("left_required_ok_at_10"),
                rok=row.get("right_required_ok_at_10"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two cockpit MCP retrieval runs.")
    parser.add_argument("--left-run-dir", required=True)
    parser.add_argument("--right-run-dir", required=True)
    parser.add_argument("--out-name", default="cockpit_mcp_table_retrieval_compare")
    args = parser.parse_args()

    left_dir = Path(args.left_run_dir).resolve()
    right_dir = Path(args.right_run_dir).resolve()
    left = _load_payload(left_dir)
    right = _load_payload(right_dir)
    comp = _build_comparison(left, right)

    out_dir = Path(__file__).resolve().parent / "runs" / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(comp, indent=2), encoding="utf-8")
    (out_dir / "comparison.md").write_text(_render_md(comp, left_dir, right_dir), encoding="utf-8")

    print(f"Output: {out_dir}")
    print(f"Compared queries: {comp.get('query_count_compared')}")


if __name__ == "__main__":
    main()
