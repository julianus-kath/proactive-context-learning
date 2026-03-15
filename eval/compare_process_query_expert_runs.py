"""
Compare two /process_query Northwind runs (typically Scout ON vs OFF).

Expected inputs:
- run_dir_on: produced by eval/start_northwind_process_query.py
- run_dir_off: produced by eval/start_northwind_process_query.py

If expert_async_eval.json exists in both runs, semantic comparison metrics
are included automatically.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_get(dct: Dict[str, Any], *keys: str) -> Any:
    current: Any = dct
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _collect_run_payload(run_dir: Path) -> Dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "summary.json"
    results_path = run_dir / "process_query_results.json"
    expert_path = run_dir / "expert_async_eval.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {manifest_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing {summary_path}")
    if not results_path.exists():
        raise FileNotFoundError(f"Missing {results_path}")

    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    results = _load_json(results_path)
    expert_eval = _load_json(expert_path) if expert_path.exists() else None

    return {
        "run_dir": str(run_dir),
        "manifest": manifest,
        "summary": summary,
        "results": results,
        "expert_eval": expert_eval,
    }


def _expert_summary(expert_eval: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(expert_eval, dict):
        return {}
    summary = expert_eval.get("summary")
    return summary if isinstance(summary, dict) else {}


def _build_comparison(on_payload: Dict[str, Any], off_payload: Dict[str, Any]) -> Dict[str, Any]:
    on_summary = on_payload["summary"]
    off_summary = off_payload["summary"]

    on_expert = _expert_summary(on_payload.get("expert_eval"))
    off_expert = _expert_summary(off_payload.get("expert_eval"))

    metrics = {
        "success_rate_pct": {
            "on": on_summary.get("success_rate"),
            "off": off_summary.get("success_rate"),
            "delta_on_minus_off": (
                (on_summary.get("success_rate") - off_summary.get("success_rate"))
                if isinstance(on_summary.get("success_rate"), (int, float))
                and isinstance(off_summary.get("success_rate"), (int, float))
                else None
            ),
        },
        "avg_latency_ms": {
            "on": on_summary.get("avg_latency_ms"),
            "off": off_summary.get("avg_latency_ms"),
            "delta_on_minus_off": (
                (on_summary.get("avg_latency_ms") - off_summary.get("avg_latency_ms"))
                if isinstance(on_summary.get("avg_latency_ms"), (int, float))
                and isinstance(off_summary.get("avg_latency_ms"), (int, float))
                else None
            ),
        },
        "p95_latency_ms": {
            "on": on_summary.get("p95_latency_ms"),
            "off": off_summary.get("p95_latency_ms"),
            "delta_on_minus_off": (
                (on_summary.get("p95_latency_ms") - off_summary.get("p95_latency_ms"))
                if isinstance(on_summary.get("p95_latency_ms"), (int, float))
                and isinstance(off_summary.get("p95_latency_ms"), (int, float))
                else None
            ),
        },
        "expert_strict_equal_count": {
            "on": on_expert.get("strict_equal_count"),
            "off": off_expert.get("strict_equal_count"),
            "delta_on_minus_off": (
                (on_expert.get("strict_equal_count") - off_expert.get("strict_equal_count"))
                if isinstance(on_expert.get("strict_equal_count"), int)
                and isinstance(off_expert.get("strict_equal_count"), int)
                else None
            ),
        },
        "expert_same_cols_set_equal_count": {
            "on": on_expert.get("same_cols_set_equal_count"),
            "off": off_expert.get("same_cols_set_equal_count"),
            "delta_on_minus_off": (
                (on_expert.get("same_cols_set_equal_count") - off_expert.get("same_cols_set_equal_count"))
                if isinstance(on_expert.get("same_cols_set_equal_count"), int)
                and isinstance(off_expert.get("same_cols_set_equal_count"), int)
                else None
            ),
        },
        "expert_positional_set_equal_count": {
            "on": on_expert.get("positional_set_equal_count"),
            "off": off_expert.get("positional_set_equal_count"),
            "delta_on_minus_off": (
                (on_expert.get("positional_set_equal_count") - off_expert.get("positional_set_equal_count"))
                if isinstance(on_expert.get("positional_set_equal_count"), int)
                and isinstance(off_expert.get("positional_set_equal_count"), int)
                else None
            ),
        },
        "expert_common_cols_set_equal_count": {
            "on": on_expert.get("common_cols_set_equal_count"),
            "off": off_expert.get("common_cols_set_equal_count"),
            "delta_on_minus_off": (
                (on_expert.get("common_cols_set_equal_count") - off_expert.get("common_cols_set_equal_count"))
                if isinstance(on_expert.get("common_cols_set_equal_count"), int)
                and isinstance(off_expert.get("common_cols_set_equal_count"), int)
                else None
            ),
        },
        "expert_required_tables_ok_count": {
            "on": on_expert.get("required_tables_ok_count"),
            "off": off_expert.get("required_tables_ok_count"),
            "delta_on_minus_off": (
                (on_expert.get("required_tables_ok_count") - off_expert.get("required_tables_ok_count"))
                if isinstance(on_expert.get("required_tables_ok_count"), int)
                and isinstance(off_expert.get("required_tables_ok_count"), int)
                else None
            ),
        },
    }

    on_results = on_payload["results"]
    off_results = off_payload["results"]
    all_query_ids = sorted(set(on_results.keys()) | set(off_results.keys()))
    per_query: List[Dict[str, Any]] = []

    on_expert_rows = {
        row.get("query_id"): row
        for row in (_safe_get(on_payload.get("expert_eval") or {}, "per_query") or [])
        if isinstance(row, dict) and row.get("query_id")
    }
    off_expert_rows = {
        row.get("query_id"): row
        for row in (_safe_get(off_payload.get("expert_eval") or {}, "per_query") or [])
        if isinstance(row, dict) and row.get("query_id")
    }

    for query_id in all_query_ids:
        on_row = on_results.get(query_id) or {}
        off_row = off_results.get(query_id) or {}
        on_cmp = (on_expert_rows.get(query_id) or {}).get("comparison") or {}
        off_cmp = (off_expert_rows.get(query_id) or {}).get("comparison") or {}
        per_query.append(
            {
                "query_id": query_id,
                "on_status": on_row.get("status"),
                "off_status": off_row.get("status"),
                "on_latency_ms": on_row.get("latency_ms_total"),
                "off_latency_ms": off_row.get("latency_ms_total"),
                "on_sql_present": bool((on_row.get("sql_query") or "").strip()),
                "off_sql_present": bool((off_row.get("sql_query") or "").strip()),
                "on_strict_equal": on_cmp.get("strict_equal"),
                "off_strict_equal": off_cmp.get("strict_equal"),
                "on_positional_set_equal": on_cmp.get("positional_set_equal"),
                "off_positional_set_equal": off_cmp.get("positional_set_equal"),
            }
        )

    return {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "on": {
            "run_dir": on_payload["run_dir"],
            "run_id": _safe_get(on_payload, "summary", "run_id"),
            "mode_label": _safe_get(on_payload, "summary", "mode_label"),
            "scout_mode": _safe_get(on_payload, "summary", "scout_mode_start"),
        },
        "off": {
            "run_dir": off_payload["run_dir"],
            "run_id": _safe_get(off_payload, "summary", "run_id"),
            "mode_label": _safe_get(off_payload, "summary", "mode_label"),
            "scout_mode": _safe_get(off_payload, "summary", "scout_mode_start"),
        },
        "metrics": metrics,
        "per_query": per_query,
    }


def _render_md(comparison: Dict[str, Any]) -> str:
    on = comparison.get("on") or {}
    off = comparison.get("off") or {}
    metrics = comparison.get("metrics") or {}
    per_query = comparison.get("per_query") or []

    lines = [
        "# /process_query Scout ON vs OFF Comparison",
        "",
        f"- ON run: `{on.get('run_id')}` ({on.get('run_dir')})",
        f"- OFF run: `{off.get('run_id')}` ({off.get('run_dir')})",
        f"- ON scout mode: `{_safe_get(on, 'scout_mode', 'backend')}` active=`{_safe_get(on, 'scout_mode', 'active')}`",
        f"- OFF scout mode: `{_safe_get(off, 'scout_mode', 'backend')}` active=`{_safe_get(off, 'scout_mode', 'active')}`",
        "",
        "| Metric | ON | OFF | Delta (ON-OFF) |",
        "|---|---:|---:|---:|",
    ]
    for metric_name in [
        "success_rate_pct",
        "avg_latency_ms",
        "p95_latency_ms",
        "expert_strict_equal_count",
        "expert_same_cols_set_equal_count",
        "expert_positional_set_equal_count",
        "expert_common_cols_set_equal_count",
        "expert_required_tables_ok_count",
    ]:
        metric = metrics.get(metric_name) or {}
        lines.append(
            f"| {metric_name} | {metric.get('on')} | {metric.get('off')} | {metric.get('delta_on_minus_off')} |"
        )

    lines += [
        "",
        "| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in per_query:
        lines.append(
            f"| {row.get('query_id')} | {row.get('on_status')} | {row.get('off_status')} | "
            f"{row.get('on_latency_ms')} | {row.get('off_latency_ms')} | "
            f"{row.get('on_strict_equal')} | {row.get('off_strict_equal')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two /process_query Northwind run directories.")
    parser.add_argument("--on-run-dir", required=True, help="Run directory for Scout ON.")
    parser.add_argument("--off-run-dir", required=True, help="Run directory for Scout OFF.")
    parser.add_argument(
        "--out-name",
        default="process_query_scout_ab_compare",
        help="Output folder name suffix under eval/runs.",
    )
    args = parser.parse_args()

    on_dir = Path(args.on_run_dir)
    off_dir = Path(args.off_run_dir)
    if not on_dir.exists():
        raise FileNotFoundError(f"ON run dir not found: {on_dir}")
    if not off_dir.exists():
        raise FileNotFoundError(f"OFF run dir not found: {off_dir}")

    on_payload = _collect_run_payload(on_dir)
    off_payload = _collect_run_payload(off_dir)
    comparison = _build_comparison(on_payload=on_payload, off_payload=off_payload)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).parent / "runs" / f"{timestamp}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    (out_dir / "comparison.md").write_text(_render_md(comparison), encoding="utf-8")

    print(f"Comparison saved to: {out_dir}")
    print(f"ON run: {comparison['on']['run_id']}")
    print(f"OFF run: {comparison['off']['run_id']}")


if __name__ == "__main__":
    main()
