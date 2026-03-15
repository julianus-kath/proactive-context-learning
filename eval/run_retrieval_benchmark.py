"""
Contract-free retrieval benchmark for Scout ON/OFF comparisons.

For each natural-language query, this script calls MCP `search_tables` and
measures retrieval quality against required tables inferred from reference SQL.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


SQL_TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:(?:public|dbo)\.)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
SEARCH_RESULT_TABLE_PATTERN = re.compile(
    r"^\s*(?:[•*-]|\d+\.)\s+((?:public|dbo)\.[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
K_VALUES = (1, 3, 5, 10)


def _normalize_table_name(name: str) -> str:
    value = (name or "").strip().replace('"', "").replace("[", "").replace("]", "")
    if not value:
        return value
    parts = value.split(".")
    if len(parts) == 1:
        return parts[0].lower()
    return parts[-1].lower()


def _extract_required_tables(reference_sql: str) -> List[str]:
    tables: List[str] = []
    for match in SQL_TABLE_PATTERN.findall(reference_sql or ""):
        table = _normalize_table_name(match)
        if table and table not in tables:
            tables.append(table)
    return tables


def _extract_ranked_tables_from_search_text(text: str) -> List[str]:
    # Preferred path: parse the structured JSON payload included by MCP tool responses.
    marker = "Full response (JSON):"
    if marker in (text or ""):
        json_blob = text.split(marker, 1)[1].strip()
        try:
            payload = json.loads(json_blob)
            results = (((payload or {}).get("data") or {}).get("results")) or []
            ranked_from_json: List[str] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                full_name = item.get("full_name")
                if isinstance(full_name, str) and full_name.strip():
                    table = _normalize_table_name(full_name)
                else:
                    schema = (item.get("schema") or "").strip()
                    name = (item.get("name") or "").strip()
                    full = f"{schema}.{name}" if schema and name else name
                    table = _normalize_table_name(full)
                if table and table not in ranked_from_json:
                    ranked_from_json.append(table)
            if ranked_from_json:
                return ranked_from_json
        except Exception:
            # Fall back to text parsing below if JSON extraction fails.
            pass

    ranked: List[str] = []
    for full_name in SEARCH_RESULT_TABLE_PATTERN.findall(text or ""):
        table = _normalize_table_name(full_name)
        if table and table not in ranked:
            ranked.append(table)
    return ranked


async def _search_tables(
    client: httpx.AsyncClient,
    mcp_url: str,
    api_key: str,
    query: str,
    limit: int = 10,
) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_tables",
            "arguments": {"query": query, "limit": limit},
        },
        "id": 1,
    }
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    response = await client.post(f"{mcp_url.rstrip('/')}/mcp", json=payload, headers=headers, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    result = data.get("result")
    text = ""
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                break
    return {"raw": data, "text": text, "ranked_tables": _extract_ranked_tables_from_search_text(text)}


def _compute_query_metrics(required_tables: List[str], ranked_tables: List[str]) -> Dict[str, Any]:
    required = list(dict.fromkeys(required_tables))
    req_set = set(required)

    recalls: Dict[str, float] = {}
    all_hit: Dict[str, bool] = {}
    any_hit: Dict[str, bool] = {}
    for k in K_VALUES:
        topk = ranked_tables[:k]
        inter = req_set.intersection(topk)
        recalls[f"recall_at_{k}"] = (len(inter) / len(req_set)) if req_set else 0.0
        all_hit[f"all_required_in_top_{k}"] = req_set.issubset(set(topk)) if req_set else False
        any_hit[f"any_required_in_top_{k}"] = len(inter) > 0

    first_rank: Optional[int] = None
    for idx, table in enumerate(ranked_tables, start=1):
        if table in req_set:
            first_rank = idx
            break
    reciprocal_rank = (1.0 / first_rank) if first_rank else 0.0

    return {
        **recalls,
        **all_hit,
        **any_hit,
        "first_required_rank": first_rank,
        "reciprocal_rank": reciprocal_rank,
        "required_tables": required,
        "retrieved_tables_ranked": ranked_tables,
    }


def _aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(records)
    if total == 0:
        return {"total_queries": 0}

    agg: Dict[str, Any] = {"total_queries": total}
    for k in K_VALUES:
        agg[f"mean_recall_at_{k}"] = round(sum(r[f"recall_at_{k}"] for r in records) / total, 4)
        agg[f"all_required_hit_rate_at_{k}"] = round(
            sum(1 for r in records if r[f"all_required_in_top_{k}"]) / total, 4
        )
        agg[f"any_required_hit_rate_at_{k}"] = round(
            sum(1 for r in records if r[f"any_required_in_top_{k}"]) / total, 4
        )
    agg["mrr"] = round(sum(r["reciprocal_rank"] for r in records) / total, 4)
    return agg


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _render_summary_md(run_id: str, mode: str, aggregate: Dict[str, Any], per_query: List[Dict[str, Any]]) -> str:
    lines = [
        f"# Retrieval Benchmark Summary ({mode})",
        "",
        f"- Run ID: `{run_id}`",
        f"- Total queries: `{aggregate.get('total_queries', 0)}`",
        f"- Mean Recall@1/3/5/10: `{aggregate.get('mean_recall_at_1')}` / `{aggregate.get('mean_recall_at_3')}` / `{aggregate.get('mean_recall_at_5')}` / `{aggregate.get('mean_recall_at_10')}`",
        f"- All-required hit@1/3/5/10: `{aggregate.get('all_required_hit_rate_at_1')}` / `{aggregate.get('all_required_hit_rate_at_3')}` / `{aggregate.get('all_required_hit_rate_at_5')}` / `{aggregate.get('all_required_hit_rate_at_10')}`",
        f"- MRR: `{aggregate.get('mrr')}`",
        "",
        "| Query | Required Tables | Top-5 Retrieved | Recall@5 |",
        "|---|---|---|---|",
    ]
    for row in per_query:
        lines.append(
            f"| {row['query_id']} | {', '.join(row['required_tables'])} | {', '.join(row['retrieved_tables_ranked'][:5])} | {row['recall_at_5']:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


async def run_benchmark(
    dataset_path: Path,
    reference_sql_path: Path,
    run_name: str,
    mode: str,
    mcp_url: str,
    mcp_api_key: str,
) -> Path:
    queries = _load_dataset(dataset_path)
    reference_sql = json.loads(reference_sql_path.read_text())

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{run_name}"
    run_dir = Path(__file__).parent / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    per_query: List[Dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for query in queries:
            qid = query["id"]
            question = query["question"]
            ref_sql = reference_sql.get(qid, "")
            required_tables = _extract_required_tables(ref_sql)
            retrieval = await _search_tables(
                client=client,
                mcp_url=mcp_url,
                api_key=mcp_api_key,
                query=question,
                limit=max(K_VALUES),
            )
            metrics = _compute_query_metrics(required_tables, retrieval["ranked_tables"])
            per_query.append(
                {
                    "query_id": qid,
                    "question": question,
                    **metrics,
                    "search_text": retrieval["text"],
                }
            )

    aggregate = _aggregate(per_query)
    payload = {
        "run_id": run_id,
        "run_name": run_name,
        "mode": mode,
        "dataset_path": str(dataset_path),
        "reference_sql_path": str(reference_sql_path),
        "mcp_url": mcp_url,
        "aggregate": aggregate,
        "per_query": per_query,
    }
    (run_dir / "retrieval_results.json").write_text(json.dumps(payload, indent=2))
    (run_dir / "summary.json").write_text(json.dumps({"run_id": run_id, "aggregate": aggregate}, indent=2))
    (run_dir / "retrieval_summary.md").write_text(_render_summary_md(run_id, mode, aggregate, per_query))

    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print(f"Mean Recall@10: {aggregate.get('mean_recall_at_10')}")
    print(f"MRR: {aggregate.get('mrr')}")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run contract-free retrieval benchmark via MCP search_tables.")
    parser.add_argument("--dataset", required=True, help="Path to dataset JSONL.")
    parser.add_argument("--reference-sql", required=True, help="Path to reference SQL JSON.")
    parser.add_argument("--run-name", required=True, help="Run name suffix.")
    parser.add_argument("--mode", required=True, help="Label (e.g., scout_on / scout_off).")
    parser.add_argument("--mcp-url", default="http://localhost:8000", help="MCP server URL.")
    parser.add_argument("--mcp-api-key", default="supersecretapikey", help="MCP API key.")
    args = parser.parse_args()

    asyncio_run = __import__("asyncio").run
    asyncio_run(
        run_benchmark(
            dataset_path=Path(args.dataset),
            reference_sql_path=Path(args.reference_sql),
            run_name=args.run_name,
            mode=args.mode,
            mcp_url=args.mcp_url,
            mcp_api_key=args.mcp_api_key,
        )
    )


if __name__ == "__main__":
    main()
