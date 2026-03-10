"""
Benchmark Runner CLI
Executes the fixed query catalog against the LangGraph service.
Usage: python -m eval.run_benchmark --dataset eval/datasets/cockpit_queries.jsonl --run-name northwind_v1 --target http://localhost:5001
"""

import os
import sys
import json
import time
import argparse
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

from eval.eval_client import EvalClient
def first_non_empty_str(*candidates: Optional[str]) -> str:
    for candidate in candidates:
        if isinstance(candidate, str):
            trimmed = candidate.strip()
            if trimmed:
                return trimmed
    return ""


def merge_unique_strings(*sources: Any) -> List[str]:
    merged: List[str] = []
    for source in sources:
        if not source:
            continue
        values = source if isinstance(source, list) else [source]
        for value in values:
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed and trimmed not in merged:
                    merged.append(trimmed)
    return merged


def artifact_validation_errors(artifact: Dict[str, Any]) -> List[str]:
    """
    Validate that a query artifact meets success criteria.
    
    A query is FAILED if ANY of these conditions are true:
    1. final_answer contains error phrases
    2. No SQL was executed (sql_executed is empty or only contains empty strings)
    3. No tables were used (indicates discovery failure or fallback to sample data)
    4. No results returned (row_count is None AND no result_preview)
    5. Grounding gate was activated (UNGROUNDED_RESPONSE_PREVENTED in error)
    
    This ensures we catch silent failures where the system continues but produces garbage.
    """
    reasons = []
    
    final_answer = (artifact.get("final_answer_text") or "").lower()
    
    # Check 1: Error phrases in response (explicit failure signals)
    failure_phrases = (
        "internal error",
        "please provide correct data",
        "please execute a relevant query",
        "wasn't able to retrieve",
        "too vague",
        "ungrounded",
        "retrieval failed",
    )
    if any(phrase in final_answer for phrase in failure_phrases):
        reasons.append("invalid_final_answer")
    
    # Check 2: No valid SQL executed (empty string or empty list)
    sql_entries = artifact.get("sql_executed") or []
    has_sql = any(
        isinstance(entry, str) and entry.strip() and entry.strip() != ""
        for entry in sql_entries
    )
    if not has_sql:
        reasons.append("missing_sql")
    
    # Check 3: No tables were used (indicates discovery failure or fallback)
    tables_used = artifact.get("tables_used") or []
    if not tables_used:
        reasons.append("missing_tables")
    
    # Check 4: No results returned
    row_count = artifact.get("row_count")
    preview = artifact.get("result_preview") or []
    if row_count is None and not preview:
        reasons.append("missing_results")
    
    # Check 5: Grounding gate was activated
    error_info = artifact.get("error_info")
    if isinstance(error_info, dict):
        error_type = error_info.get("type", "")
        if "UNGROUNDED" in error_type or "NO_SQL" in error_type:
            reasons.append("grounding_gate_activated")
    
    return reasons


def get_git_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_environment_info() -> Dict[str, str]:
    """Collect environment metadata."""
    return {
        "python_version": sys.version.split()[0],
        "machine": os.uname().nodename,
        "platform": sys.platform,
        "cwd": os.getcwd(),
    }


async def fetch_mcp_health_snapshot(
    mcp_server_url: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture MCP health and discovery backend metadata for run reproducibility.
    """
    snapshot: Dict[str, Any] = {
        "url": mcp_server_url,
        "reachable": False,
    }

    target = (mcp_server_url or "").strip().rstrip("/")
    if not target:
        snapshot["error"] = "MCP_SERVER_URL is empty"
        return snapshot

    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{target}/health", headers=headers)

        snapshot["status_code"] = response.status_code
        snapshot["reachable"] = response.status_code == 200

        payload: Any = None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            payload = response.json()
        else:
            payload = {"raw": response.text}
        snapshot["payload"] = payload

        if isinstance(payload, dict):
            components = payload.get("components") or {}
            if isinstance(components, dict):
                db_component = components.get("database") or {}
                scout_component = components.get("scout_catalog") or {}
                if isinstance(db_component, dict):
                    snapshot["database_dialect"] = db_component.get("dialect")
                if isinstance(scout_component, dict):
                    snapshot["discovery_backend"] = scout_component.get("backend")
                    snapshot["discovery_status"] = scout_component.get("status")
                    snapshot["catalog_valid"] = scout_component.get("catalog_valid")
    except Exception as exc:
        snapshot["error"] = str(exc)

    return snapshot


def _build_detailed_results(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a user-friendly detailed results summary highlighting SQL queries,
    final outputs, and agent execution steps for each query.
    """
    detailed_queries = []
    success_count = 0
    failed_count = 0

    for query_id, artifact in results.items():
        status = artifact.get("status", "unknown")
        if status == "success":
            success_count += 1
        else:
            failed_count += 1

        sql_query = None
        if artifact.get("sql_generated"):
            sql_query = artifact["sql_generated"][0]
        elif artifact.get("sql_executed"):
            sql_query = artifact["sql_executed"][0]

        llm_usage = artifact.get("llm_usage") or {}
        node_counts = artifact.get("node_entry_counts") or {}
        loop_events = artifact.get("loop_events") or {}

        agent_execution = {
            "llm_calls": {
                "total": llm_usage.get("total", artifact.get("total_llm_calls")),
                "by_stage": {
                    "intent": llm_usage.get("intent", 0),
                    "discovery": llm_usage.get("discovery", 0),
                    "join": llm_usage.get("join", 0),
                    "repair": llm_usage.get("repair", 0),
                    "answer": llm_usage.get("answer", 0),
                },
            },
            "node_executions": {
                "discovery": node_counts.get("discovery", 0),
                "join": node_counts.get("join_sql", node_counts.get("join", 0)),
            },
            "loop_suppressions": {
                "same_tables_suppressed": loop_events.get("discovery_reentered_same_tables", 0),
                "same_sql_suppressed": loop_events.get("join_sql_regenerated_same_sql", 0),
            },
            "graph_cycles": artifact.get("total_graph_cycles"),
        }

        query_result = {
            "query_id": query_id,
            "question": artifact.get("question"),
            "status": status,
            "latency_ms": artifact.get("latency_ms_total"),
            "sql_query": sql_query,
            "tables_used": artifact.get("tables_used", []),
            "final_answer": artifact.get("final_answer_text"),
            "row_count": artifact.get("row_count"),
            "result_preview": artifact.get("result_preview", [])[:5],
            "agent_execution": agent_execution,
            "semantic_status": artifact.get("semantic_status"),
            "semantic_failure_reasons": artifact.get("semantic_failure_reasons", []),
        }

        if status == "failed":
            failure_reasons = artifact.get("failure_reasons", [])
            error = artifact.get("error")
            error_info = artifact.get("error_info")
            query_result["failure_reasons"] = failure_reasons
            if error:
                query_result["error"] = error
            if error_info:
                query_result["error_info"] = error_info

        detailed_queries.append(query_result)

    return {
        "summary": {
            "total_queries": len(results),
            "successful": success_count,
            "failed": failed_count,
            "success_rate": f"{(success_count/len(results)*100):.1f}%" if results else "0%",
        },
        "queries": detailed_queries,
    }


async def run_benchmark(
    dataset_path: str,
    run_name: str,
    target_url: str,
    eval_service_url: Optional[str] = None,
):
    """Execute benchmark against LangGraph service."""
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return

    print(f"📊 Loading benchmark dataset: {dataset_path}")
    queries = []
    with open(dataset_path) as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    print(f"✅ Loaded {len(queries)} queries")

    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_name}"
    run_dir = Path(__file__).parent / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "run_name": run_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": get_git_commit(),
        "dataset_path": str(dataset_path),
        "mcp_server_url": os.getenv("MCP_SERVER_URL", "unknown"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4"),
        "prompt_versions": {},
        "environment": get_environment_info(),
        "total_queries": len(queries),
        "completed_queries": 0,
        "failed_queries": 0,
    }

    # Record MCP backend state up-front so runs are reproducible and auditable.
    mcp_server_url = os.getenv("MCP_SERVER_URL", "unknown")
    mcp_api_key = os.getenv("MCP_API_KEY")
    manifest["mcp_health_start"] = await fetch_mcp_health_snapshot(
        mcp_server_url=mcp_server_url,
        api_key=mcp_api_key,
    )

    print(f"🚀 Starting run: {run_id}")
    print(f"📁 Results will be saved to: {run_dir}")
    backend = manifest["mcp_health_start"].get("discovery_backend")
    backend_status = manifest["mcp_health_start"].get("discovery_status")
    if backend:
        print(f"🧭 MCP discovery backend at start: {backend} ({backend_status or 'unknown'})")
    else:
        print("🧭 MCP discovery backend at start: unavailable")

    if eval_service_url:
        eval_client = EvalClient(eval_service_url)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{eval_service_url}/runs",
                    json=manifest,
                )
                if response.status_code != 200:
                    print(f"⚠️  Could not register run with eval service: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Eval service unavailable: {e}")
            eval_client = None
    else:
        eval_client = None

    results = {}
    completed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, query in enumerate(queries, 1):
            query_id = query["id"]
            question = query["question"]
            print(f"\n[{i}/{len(queries)}] {query_id}: {question[:60]}...")

            start_time = time.time()
            try:
                api_key = os.getenv("API_KEY", "supersecretapikey")
                response = await client.post(
                    f"{target_url}/process_query",
                    json={
                        "user_input": question,
                        "api_key": api_key,  # Legacy field; ignored by LangGraph API but preserved for compatibility
                    },
                    headers={"X-Eval-Run-Id": run_id, "X-Eval-Query-Id": query_id},
                )

                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")

                result = response.json()
                latency_ms = int((time.time() - start_time) * 1000)

                # Base artifact structure (backward compatible with Phase 1/2).
                artifact = {
                    "query_id": query_id,
                    "question": question,
                    "status": "success",
                    "final_answer_text": result.get("final_response", ""),
                    "sql_generated": [],
                    "sql_executed": [],
                    "tables_used": [],
                    "row_count": None,
                    "latency_ms_total": latency_ms,
                    "retries": 0,
                    "result_preview": [],
                    "error_info": None,
                    "discovery_log": None,
                    # Semantic correctness fields (populated by result_validator in benchmark mode).
                    # These are optional for legacy runs and remain internal to eval artifacts.
                    "semantic_status": None,
                    "semantic_failure_reasons": [],
                    "semantic_retry_count": None,
                    "semantic_retry_action": None,
                    "contract_id": None,
                }

                # Semantic metadata comes from the orchestrator's validation_result + state.
                validation = result.get("validation_result") or {}
                if isinstance(validation, dict):
                    artifact["semantic_status"] = validation.get("semantic_status")
                    reasons = validation.get("semantic_failure_reasons") or []
                    if isinstance(reasons, list):
                        artifact["semantic_failure_reasons"] = list(reasons)
                    artifact["semantic_retry_action"] = validation.get("semantic_retry_action")
                    artifact["contract_id"] = validation.get("contract_id")

                if "semantic_retry_count" in result:
                    artifact["semantic_retry_count"] = result.get("semantic_retry_count")

                exec_result_payload = result.get("exec_result")
                rows: List[Dict[str, Any]] = []
                row_count = None
                metadata: Dict[str, Any] = {}
                metadata_tables: Any = []
                if isinstance(exec_result_payload, dict) and exec_result_payload:
                    data_rows = exec_result_payload.get("data")
                    if not isinstance(data_rows, list):
                        data_rows = exec_result_payload.get("rows") or []
                    rows = data_rows if isinstance(data_rows, list) else []
                    row_count = exec_result_payload.get("row_count")
                    raw_metadata = exec_result_payload.get("metadata")
                    if isinstance(raw_metadata, dict):
                        metadata = raw_metadata
                        metadata_tables = metadata.get("tables_used") or metadata.get("tables") or []
                else:
                    metadata_tables = []

                if row_count is None and rows:
                    row_count = len(rows)

                if rows:
                    artifact["result_preview"] = rows[:20]
                artifact["row_count"] = row_count

                sources = result.get("sources") or result.get("relevant_tables")
                exec_tables = None
                if isinstance(exec_result_payload, dict):
                    exec_tables = exec_result_payload.get("tables_used") or exec_result_payload.get("tables")
                artifact["tables_used"] = merge_unique_strings(sources, exec_tables, metadata_tables)

                sql_query = first_non_empty_str(
                    result.get("sql_query"),
                    result.get("state", {}).get("sql_query") if isinstance(result.get("state"), dict) else None,
                    exec_result_payload.get("sql_query") if isinstance(exec_result_payload, dict) else None,
                    exec_result_payload.get("query") if isinstance(exec_result_payload, dict) else None,
                    metadata.get("sql_query") if isinstance(exec_result_payload, dict) and isinstance(exec_result_payload.get("metadata"), dict) else None,
                )
                if sql_query:
                    artifact["sql_generated"] = [sql_query]
                    artifact["sql_executed"] = [sql_query]

                error_info_payload = result.get("error_info")
                if not error_info_payload and isinstance(exec_result_payload, dict):
                    error_info_payload = exec_result_payload.get("error_info")
                artifact["error_info"] = error_info_payload
                artifact["discovery_log"] = result.get("discovery_log")

                # Phase 1 instrumentation: persist LLM/node usage and loop diagnostics per query
                artifact["llm_usage"] = result.get("llm_usage")
                artifact["node_entry_counts"] = result.get("node_entry_counts")
                artifact["loop_events"] = result.get("loop_events")
                artifact["total_llm_calls"] = result.get("total_llm_calls")
                artifact["total_graph_cycles"] = result.get("total_graph_cycles")

                validation_errors = artifact_validation_errors(artifact)
                if validation_errors:
                    artifact["status"] = "failed"
                    artifact["failure_reasons"] = validation_errors
                    failed += 1
                    print(f"   ❌ Failed validation: {', '.join(validation_errors)}")
                else:
                    completed += 1
                    print(f"   ✅ Success ({latency_ms}ms)")

                results[query_id] = artifact

                if eval_client:
                    await eval_client.save_query_artifact(run_id, query_id, artifact)

            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                # Even on client-side failures, emit a consistent artifact shape
                # so downstream scoring and analysis remain robust.
                artifact = {
                    "query_id": query_id,
                    "question": question,
                    "status": "failed",
                    "error": str(e),
                    "latency_ms_total": latency_ms,
                    "sql_executed": [],
                    "tables_used": [],
                    "error_info": {"type": "CLIENT_EXCEPTION", "message": str(e)},
                    "discovery_log": None,
                    "semantic_status": None,
                    "semantic_failure_reasons": [],
                    "semantic_retry_count": None,
                    "semantic_retry_action": None,
                    "contract_id": None,
                }
                results[query_id] = artifact
                failed += 1
                print(f"   ❌ Failed: {e}")

                if eval_client:
                    await eval_client.save_query_artifact(run_id, query_id, artifact)

    manifest["completed_queries"] = completed
    manifest["failed_queries"] = failed
    manifest["mcp_health_end"] = await fetch_mcp_health_snapshot(
        mcp_server_url=mcp_server_url,
        api_key=mcp_api_key,
    )

    manifest_file = run_dir / "run_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))

    results_file = run_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2))

    detailed_results = _build_detailed_results(results)
    detailed_results_file = run_dir / "results_detailed.json"
    detailed_results_file.write_text(json.dumps(detailed_results, indent=2))

    # Phase 1 instrumentation: emit per-query LLM usage summary for quick inspection
    calls_summary: List[Dict[str, Any]] = []
    for qid, artifact in results.items():
        usage = artifact.get("llm_usage") or {}
        node_counts = artifact.get("node_entry_counts") or {}
        loop_events = artifact.get("loop_events") or {}
        row = {
            "query_id": qid,
            "total_calls": usage.get("total", artifact.get("total_llm_calls")),
            "intent": usage.get("intent", 0),
            "discovery": usage.get("discovery", 0),
            "join": usage.get("join", 0),
            "repair": usage.get("repair", 0),
            "answer": usage.get("answer", 0),
            "discovery_entries": node_counts.get("discovery", 0),
            "join_entries": node_counts.get("join_sql", node_counts.get("join", 0)),
            "same_tables_suppressed": loop_events.get("discovery_reentered_same_tables", 0),
            "same_sql_suppressed": loop_events.get("join_sql_regenerated_same_sql", 0),
        }
        calls_summary.append(row)

    calls_summary_file = run_dir / "llm_calls_per_query.json"
    calls_summary_file.write_text(json.dumps(calls_summary, indent=2))

    summary = {
        "run_id": run_id,
        "total_queries": len(queries),
        "successful": completed,
        "failed": failed,
        "success_rate": f"{(completed/len(queries)*100):.1f}%",
        "results_dir": str(run_dir),
    }

    summary_file = run_dir / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}")
    print(f"📋 BENCHMARK COMPLETE")
    print(f"{'='*60}")
    print(f"Run ID: {run_id}")
    print(f"Total Queries: {len(queries)}")
    print(f"Successful: {completed} ({(completed/len(queries)*100):.1f}%)")
    print(f"Failed: {failed}")
    print(f"Results saved to: {run_dir}")
    print(f"  📄 results.json - Full artifact data")
    print(f"  📊 results_detailed.json - User-friendly summary with SQL & agent steps")
    print(f"  📈 llm_calls_per_query.json - LLM usage breakdown")
    print(f"  📋 summary.json - Run summary")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Execute benchmark queries against LangGraph service"
    )
    parser.add_argument(
        "--dataset",
        default="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_queries.jsonl",
        help="Path to benchmark dataset (JSONL format). Default runs 5 representative queries; use cockpit_queries.jsonl for full 12.",
    )
    parser.add_argument(
        "--run-name",
        default="benchmark_run",
        help="Name for this benchmark run",
    )
    parser.add_argument(
        "--target",
        default="http://localhost:5001",
        help="LangGraph service URL",
    )
    parser.add_argument(
        "--eval-service",
        default=None,
        help="Evaluation service URL (optional, e.g., http://localhost:7001)",
    )

    args = parser.parse_args()

    asyncio.run(
        run_benchmark(
            dataset_path=args.dataset,
            run_name=args.run_name,
            target_url=args.target,
            eval_service_url=args.eval_service,
        )
    )


if __name__ == "__main__":
    main()
