#!/usr/bin/env python3
"""
H2a Full-Pipeline Ablation: Scout ON vs OFF through the LLM agent.

Runs each query through create_sql_agent() → MCP tools → SQL generation,
then compares generated SQL tables against ground-truth required tables.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def extract_tables_from_sql(sql: str) -> set:
    """Extract table names from SQL FROM/JOIN clauses."""
    if not sql:
        return set()
    sql_upper = sql.upper()
    # Match FROM/JOIN followed by optional schema prefix and table name
    pattern = r'(?:FROM|JOIN)\s+(?:public\.|dbo\.)?["\']?(\w+)["\']?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return {m.lower() for m in matches}


def normalize_table(name: str) -> str:
    """Normalize table name for comparison."""
    parts = name.strip().split(".")
    return parts[-1].lower().strip()


def compute_recall(retrieved: set, required: set) -> float:
    """Compute recall of required tables in retrieved set."""
    if not required:
        return 1.0
    required_norm = {normalize_table(t) for t in required}
    retrieved_norm = {normalize_table(t) for t in retrieved}
    hits = required_norm & retrieved_norm
    return len(hits) / len(required_norm)


def load_contracts(contracts_path, label_overrides_path=None):
    """Load H2a ground-truth contracts as {query_id: [required_tables]}.

    Supported on-disk JSON formats:
      - List:             [{"query_id": str, "required_tables": [str, ...]}, ...]
      - Dict-with-labels: {"labels": [{"query_id": ..., "required_tables": [...]}]}
      - Map:              {"query_id": [str, ...], ...}

    If label_overrides_path points to an existing file, its
    {"overrides": [{"partner_label": ..., "live_catalog_name": ...}, ...]}
    entries are applied to each required_tables list (Cockpit partner labels
    → live catalog names).
    """
    with open(contracts_path) as f:
        contracts_data = json.load(f)

    if isinstance(contracts_data, list):
        contracts = {c["query_id"]: c["required_tables"] for c in contracts_data}
    elif isinstance(contracts_data, dict) and "labels" in contracts_data:
        contracts = {c["query_id"]: c["required_tables"] for c in contracts_data["labels"]}
    else:
        contracts = dict(contracts_data)

    if label_overrides_path and Path(label_overrides_path).exists():
        with open(label_overrides_path) as f:
            overrides_doc = json.load(f)
        override_map = {
            e["partner_label"]: e["live_catalog_name"]
            for e in overrides_doc.get("overrides", [])
        }
        for qid in contracts:
            contracts[qid] = [override_map.get(t, t) for t in contracts[qid]]

    return contracts


async def run_single_query(agent, question: str, query_id: str, category: str = "", language: str = "") -> dict:
    """Run a single query through the agent and capture results."""
    start = time.time()
    try:
        result = await agent.arun(question)
        elapsed = (time.time() - start) * 1000

        generated_sql = result.get("sql_query", "") or ""
        answer = result.get("answer", "") or ""

        return {
            "query_id": query_id,
            "question": question,
            "category": category,
            "language": language,
            "generated_sql": generated_sql,
            "sql_present": bool(generated_sql.strip()),
            "tables_used": sorted(extract_tables_from_sql(generated_sql)),
            "latency_ms": round(elapsed, 1),
            "error": result.get("error", None),
            "response_preview": answer[:500],
        }
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {
            "query_id": query_id,
            "question": question,
            "category": category,
            "language": language,
            "generated_sql": "",
            "sql_present": False,
            "tables_used": [],
            "latency_ms": round(elapsed, 1),
            "error": str(e),
            "response_preview": "",
        }


async def main():
    parser = argparse.ArgumentParser(description="H2a full-pipeline ablation")
    parser.add_argument("--dataset", required=True, help="Path to queries JSONL")
    parser.add_argument("--contracts", required=True, help="Path to contracts JSON")
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    parser.add_argument(
        "--mode",
        default="scout_on",
        choices=[
            "scout_on",
            "scout_off_aligned",
            "scout_enriched",          # SDG descriptions in agent payload only
            "scout_enriched_ranked",   # SDG in agent payload AND ranker
            "scout_structural",         # No descriptions at all (baseline)
        ],
    )
    parser.add_argument("--run-tag", default="h2a_full_pipeline")
    parser.add_argument("--label-overrides", default=None)
    args = parser.parse_args()

    # Load queries
    queries = {}
    with open(args.dataset) as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                queries[q["id"]] = q

    # Load contracts/ground truth (with optional Cockpit label overrides)
    contracts = load_contracts(args.contracts, args.label_overrides)

    # Set environment for mode
    os.environ["MCP_SERVER_URL"] = args.mcp_url
    os.environ["MCP_API_KEY"] = os.getenv("API_KEY", "supersecretapikey")

    # Import agent (after env is set)
    from simple_sql_agent.agent import create_sql_agent
    agent = create_sql_agent()

    # Create output directory
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(__file__).parent / "runs" / f"{timestamp}_{args.run_tag}_{args.mode}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot the env vars that determine the experimental condition.
    # Without this, future-you cannot tell from disk which condition ran.
    env_snapshot_keys = [
        "SCOUT_DISABLE",
        "SCOUT_DESCRIPTIONS_ENABLED",
        "SCOUT_DESCRIPTIONS_RANKING",
        "SCOUT_DESCRIPTIONS_MODEL",
        "SCOUT_DESCRIPTIONS_DATABASE_TYPE",
        "SCOUT_DESCRIPTIONS_CACHE_PATH",
        "DB_DIALECT",
        "DB_NAME",
        "DB_HOST",
        "DB_PORT",
    ]
    env_snapshot = {k: os.environ.get(k) for k in env_snapshot_keys}

    # Save config
    config = {
        "dataset": args.dataset,
        "contracts": args.contracts,
        "mcp_url": args.mcp_url,
        "mode": args.mode,
        "n_queries": len(queries),
        "timestamp": timestamp,
        "env_snapshot": env_snapshot,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))

    # Run all queries
    results = []
    for qid in sorted(queries.keys()):
        q = queries[qid]
        question = q["question"]
        required = contracts.get(qid, [])

        print(f"\n[{qid}] {question[:80]}...")
        print(f"  Required: {required}")

        result = await run_single_query(
            agent,
            question,
            qid,
            category=str(q.get("category", "") or ""),
            language=str(q.get("language", "") or ""),
        )
        tables_used = set(result["tables_used"])
        recall = compute_recall(tables_used, required)
        result["required_tables"] = required
        result["recall"] = round(recall, 4)
        result["missing_tables"] = [t for t in required if normalize_table(t) not in {normalize_table(x) for x in tables_used}]

        status = "PERFECT" if recall == 1.0 else ("PARTIAL" if recall > 0 else "MISS")
        print(f"  {status}: recall={recall:.2f}, tables={result['tables_used']}, sql={'YES' if result['sql_present'] else 'NO'}")
        if result["missing_tables"]:
            print(f"  Missing: {result['missing_tables']}")
        if result["error"]:
            print(f"  ERROR: {result['error']}")

        results.append(result)

        # Rate limit protection
        time.sleep(1)

    # Save raw results
    with open(run_dir / "results_raw.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Compute summary
    recalls = [r["recall"] for r in results]
    sql_rates = [1 if r["sql_present"] else 0 for r in results]

    # Per-category breakdown — central to the H2a analysis plan.
    per_category: dict = {}
    for r in results:
        cat = r.get("category") or "uncategorized"
        bucket = per_category.setdefault(cat, {"n": 0, "_recall_sum": 0.0})
        bucket["n"] += 1
        bucket["_recall_sum"] += float(r["recall"])
    per_category_out = {
        cat: {
            "n": b["n"],
            "mean_recall": round(b["_recall_sum"] / b["n"], 4) if b["n"] else 0.0,
        }
        for cat, b in per_category.items()
    }

    # Per-language breakdown (en/de split for crosslingual analysis).
    per_language: dict = {}
    for r in results:
        lang = r.get("language") or "unknown"
        bucket = per_language.setdefault(lang, {"n": 0, "_recall_sum": 0.0})
        bucket["n"] += 1
        bucket["_recall_sum"] += float(r["recall"])
    per_language_out = {
        lang: {
            "n": b["n"],
            "mean_recall": round(b["_recall_sum"] / b["n"], 4) if b["n"] else 0.0,
        }
        for lang, b in per_language.items()
    }

    summary = {
        "mode": args.mode,
        "n_queries": len(results),
        "mean_recall": round(sum(recalls) / len(recalls), 4) if recalls else 0,
        "sql_generation_rate": round(sum(sql_rates) / len(sql_rates), 4) if sql_rates else 0,
        "perfect_recall_count": sum(1 for r in recalls if r == 1.0),
        "zero_recall_count": sum(1 for r in recalls if r == 0.0),
        "errors": sum(1 for r in results if r["error"]),
        "per_category": per_category_out,
        "per_language": per_language_out,
        "env_snapshot": env_snapshot,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}")
    print(f"SUMMARY ({args.mode})")
    print(f"{'='*60}")
    print(f"  Mean Recall:       {summary['mean_recall']:.4f}")
    print(f"  SQL Generation:    {summary['sql_generation_rate']:.4f}")
    print(f"  Perfect Recall:    {summary['perfect_recall_count']}/{len(results)}")
    print(f"  Zero Recall:       {summary['zero_recall_count']}/{len(results)}")
    print(f"  Errors:            {summary['errors']}")
    if per_category_out:
        print("\n  Per-category:")
        for cat, stats in sorted(per_category_out.items()):
            print(f"    {cat:<22} n={stats['n']:>3}  mean_recall={stats['mean_recall']:.4f}")
    if per_language_out:
        print("\n  Per-language:")
        for lang, stats in sorted(per_language_out.items()):
            print(f"    {lang:<10} n={stats['n']:>3}  mean_recall={stats['mean_recall']:.4f}")
    print(f"\nResults saved to: {run_dir}")


if __name__ == "__main__":
    asyncio.run(main())
