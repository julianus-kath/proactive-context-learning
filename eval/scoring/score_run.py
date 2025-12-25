"""
Evaluation Scoring Module
Phase 1: Basic scoring (success rate, SQL execution, result population)
Phase 2: Expert SQL comparison (when ground truth is added)
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def score_run(run_dir: Path) -> Dict[str, Any]:
    """
    Score a completed benchmark run.
    Phase 1 scoring: success_rate, sql_executed_present, non_empty_results, failure_categorization
    """
    manifest_path = run_dir / "run_manifest.json"
    results_path = run_dir / "results.json"

    if not manifest_path.exists() or not results_path.exists():
        raise FileNotFoundError(f"Missing manifest or results in {run_dir}")

    manifest = json.loads(manifest_path.read_text())
    results = json.loads(results_path.read_text())

    total_queries = len(results)
    successful = sum(1 for r in results.values() if r.get("status") == "success")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")

    sql_executed_count = sum(
        1 for r in results.values()
        if r.get("sql_executed") and len(r.get("sql_executed", [])) > 0
    )

    non_empty_results_count = sum(
        1 for r in results.values()
        if r.get("row_count") and r["row_count"] > 0
    )

    failure_categories = _categorize_failures(results)

    # Semantic correctness metrics:
    # Count queries where the entity, metric, and join path all match the contract.
    semantic_pass_count = sum(
        1
        for r in results.values()
        if r.get("status") == "success" and r.get("semantic_status") == "OK"
    )

    entity_metric_join_correct_rate = (
        f"{(semantic_pass_count / total_queries * 100):.1f}%"
        if total_queries > 0
        else "0%"
    )

    # Average latency: consider only entries that have a numeric latency value.
    latencies = [
        r.get("latency_ms_total")
        for r in results.values()
        if isinstance(r.get("latency_ms_total"), (int, float))
    ]
    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else 0

    score = {
        "run_id": manifest.get("run_id"),
        "run_name": manifest.get("run_name"),
        "timestamp": manifest.get("timestamp"),
        "metrics": {
            "total_queries": total_queries,
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": f"{(successful/total_queries*100):.1f}%" if total_queries > 0 else "0%",
            "sql_executed_rate": f"{(sql_executed_count/total_queries*100):.1f}%" if total_queries > 0 else "0%",
            "non_empty_results_rate": f"{(non_empty_results_count/total_queries*100):.1f}%" if total_queries > 0 else "0%",
            "entity_metric_join_correct_count": semantic_pass_count,
            "entity_metric_join_correct_rate": entity_metric_join_correct_rate,
            "avg_latency_ms": round(avg_latency_ms, 2),
        },
        "failure_analysis": failure_categories,
        "per_query_status": {
            qid: {
                "status": r.get("status", "unknown"),
                "latency_ms": r.get("latency_ms_total"),
                "row_count": r.get("row_count"),
                "error": r.get("error"),
            }
            for qid, r in results.items()
        },
    }

    return score


def _categorize_failures(results: Dict[str, Any]) -> Dict[str, List[str]]:
    """Categorize failure modes for error analysis."""
    categories = {
        "timeout": [],
        "connection_error": [],
        "sql_syntax_error": [],
        "table_not_found": [],
        "column_not_found": [],
        "permission_denied": [],
        "other": [],
    }

    for query_id, result in results.items():
        if result.get("status") != "failed":
            continue

        error = str(result.get("error", "")).lower()

        if "timeout" in error or "timed out" in error:
            categories["timeout"].append(query_id)
        elif "connection" in error or "refused" in error:
            categories["connection_error"].append(query_id)
        elif "syntax" in error or "invalid" in error:
            categories["sql_syntax_error"].append(query_id)
        elif "table" in error and "not found" in error:
            categories["table_not_found"].append(query_id)
        elif "column" in error and "not found" in error:
            categories["column_not_found"].append(query_id)
        elif "permission" in error or "denied" in error:
            categories["permission_denied"].append(query_id)
        else:
            categories["other"].append(query_id)

    return {k: v for k, v in categories.items() if v}


def save_score(run_dir: Path, score: Dict[str, Any]):
    """Save score to file."""
    score_path = run_dir / "score.json"
    score_path.write_text(json.dumps(score, indent=2))
    return score_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Score a completed benchmark run")
    parser.add_argument("run_dir", help="Path to run directory")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save score to score.json",
    )

    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        return

    try:
        score = score_run(run_dir)
        print("✅ Scoring complete")
        print("\n" + "=" * 60)
        print(f"Run: {score['run_id']}")
        print("=" * 60)
        metrics = score["metrics"]
        print(f"Total Queries: {metrics['total_queries']}")
        print(f"Successful: {metrics['successful_queries']} ({metrics['success_rate']})")
        print(f"Failed: {metrics['failed_queries']}")
        print(f"SQL Execution Rate: {metrics['sql_executed_rate']}")
        print(f"Non-Empty Results Rate: {metrics['non_empty_results_rate']}")
        print(f"Avg Latency: {metrics['avg_latency_ms']}ms")
        print(
            "Semantic Correctness (entity+metric+join): "
            f"{metrics['entity_metric_join_correct_count']} "
            f"({metrics['entity_metric_join_correct_rate']})"
        )
        print("=" * 60)

        if score["failure_analysis"]:
            print("\nFailure Analysis:")
            for category, queries in score["failure_analysis"].items():
                print(f"  {category}: {len(queries)} ({', '.join(queries)})")

        if args.save:
            score_path = save_score(run_dir, score)
            print(f"\n📁 Score saved to: {score_path}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
