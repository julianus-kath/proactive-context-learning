"""
Start script for Northwind /process_query experiments (benchmark-free path).

What this script does:
1) Sends each natural-language Northwind query to the agent service /process_query.
2) Stores raw per-query responses and run metadata.
3) Optionally performs async expert-reference evaluation by executing:
   - candidate SQL (from /process_query response)
   - reference SQL (expert baseline)
   through MCP run_query, then comparing result sets.

This script is intentionally separate from eval/run_benchmark.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx


SQL_TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:(?:public|dbo)\.)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
SQL_CTE_NAME_PATTERN = re.compile(
    r"(?:\bWITH\b|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(",
    re.IGNORECASE,
)
EXPERT_REASON_CODES = [
    "MISSING_DISCOUNT_FACTOR",
    "COUNT_NOT_DISTINCT",
    "WRONG_AGGREGATION_GRAIN",
    "MISSING_REQUIRED_TABLE",
    "JOIN_PATH_VIOLATION",
    "MISSING_TIME_GROUPING",
    "TOP_K_NOT_APPLIED",
]

STAGE_NAMES: Tuple[str, ...] = ("discovery", "ranked", "final_sql")
DISCOVERY_STAGE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("discovery_log",),
    ("discovery",),
    ("discovered_tables",),
    ("discovery_tables",),
    ("state", "discovery_log"),
    ("state", "discovery"),
    ("state", "discovered_tables"),
    ("state", "discovery_tables"),
    ("trace", "discovery"),
    ("trace", "discovery_log"),
    ("debug", "discovery"),
    ("debug", "discovery_log"),
)
RANKED_STAGE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("sources",),
    ("relevant_tables",),
    ("ranked_tables",),
    ("selected_tables",),
    ("candidate_tables",),
    ("state", "sources"),
    ("state", "relevant_tables"),
    ("state", "ranked_tables"),
    ("state", "selected_tables"),
    ("state", "candidate_tables"),
    ("trace", "ranked_tables"),
    ("debug", "ranked_tables"),
)
FINAL_STAGE_TABLE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("final_sql_tables",),
    ("state", "final_sql_tables"),
    ("exec_result", "tables_used"),
    ("exec_result", "tables"),
)
POLICY_FLAG_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("policy_violation",),
    ("safety_violation",),
    ("guardrail_violation",),
    ("policy_blocked",),
    ("blocked_by_policy",),
    ("exec_result", "policy_violation"),
    ("exec_result", "safety_violation"),
    ("state", "policy_violation"),
)
TABLE_TOKEN_PATTERN = re.compile(
    r"\b(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)\b"
)


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _normalize_table_name(name: str) -> str:
    value = (name or "").strip().replace('"', "").replace("[", "").replace("]", "")
    if not value:
        return value
    parts = value.split(".")
    return parts[-1].lower()


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


def _merge_unique_strings(*sources: Any) -> List[str]:
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


def _get_nested(data: Dict[str, Any], path: Sequence[str]) -> Tuple[bool, Any]:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current.get(key)
    return True, current


def _looks_like_table_name(value: str) -> bool:
    token = (value or "").strip()
    if not token:
        return False
    if " " in token:
        return False
    if token.lower().startswith(("select", "with")):
        return False
    if "." in token:
        left, right = token.split(".", 1)
        if not left or not right:
            return False
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", left)) and bool(
            re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", right)
        )
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token))


def _extract_table_candidates_from_text(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []

    if " from " in f" {raw.lower()} " or " join " in f" {raw.lower()} ":
        return _extract_tables_from_sql(raw)

    out: List[str] = []
    for match in TABLE_TOKEN_PATTERN.findall(raw):
        table = _normalize_table_name(match)
        if table and table not in out:
            out.append(table)
    return out


def _extract_tables_from_object(value: Any) -> List[str]:
    if value is None:
        return []

    out: List[str] = []

    def _append_table(candidate: str) -> None:
        if not candidate:
            return
        cleaned = candidate.strip().rstrip(",")
        if not cleaned:
            return
        if not _looks_like_table_name(cleaned):
            return
        normalized = _normalize_table_name(cleaned)
        if normalized and normalized not in out:
            out.append(normalized)

    if isinstance(value, str):
        for candidate in _extract_table_candidates_from_text(value):
            _append_table(candidate)
        return out

    if isinstance(value, list):
        for item in value:
            for table in _extract_tables_from_object(item):
                _append_table(table)
        return out

    if isinstance(value, dict):
        name_keys = ("full_name", "table_name", "table", "name")
        schema = str(value.get("schema") or "").strip()
        for key in name_keys:
            name_value = value.get(key)
            if isinstance(name_value, str) and name_value.strip():
                if schema and "." not in name_value:
                    _append_table(f"{schema}.{name_value}")
                _append_table(name_value)

        list_like_keys = (
            "tables",
            "tables_used",
            "results",
            "candidates",
            "ranked_tables",
            "selected_tables",
            "discovered_tables",
            "relevant_tables",
            "sources",
            "data",
        )
        for key in list_like_keys:
            if key in value:
                for table in _extract_tables_from_object(value.get(key)):
                    _append_table(table)
        return out

    return out


def _extract_stage_tables(
    response_payload: Dict[str, Any],
    sql_query: Optional[str],
    exec_result: Dict[str, Any],
) -> Tuple[Dict[str, List[str]], Dict[str, bool], List[str]]:
    stage_tables: Dict[str, List[str]] = {stage: [] for stage in STAGE_NAMES}
    stage_presence: Dict[str, bool] = {stage: False for stage in STAGE_NAMES}
    notes: List[str] = []

    for path in DISCOVERY_STAGE_PATHS:
        exists, value = _get_nested(response_payload, path)
        if not exists:
            continue
        stage_presence["discovery"] = True
        extracted = _extract_tables_from_object(value)
        stage_tables["discovery"] = _merge_unique_strings(stage_tables["discovery"], extracted)
        notes.append(f"discovery path found: {'.'.join(path)} ({len(extracted)} tables)")

    for path in RANKED_STAGE_PATHS:
        exists, value = _get_nested(response_payload, path)
        if not exists:
            continue
        stage_presence["ranked"] = True
        extracted = _extract_tables_from_object(value)
        stage_tables["ranked"] = _merge_unique_strings(stage_tables["ranked"], extracted)
        notes.append(f"ranked path found: {'.'.join(path)} ({len(extracted)} tables)")

    final_tables = _extract_tables_from_sql(sql_query or "")
    if isinstance(sql_query, str):
        stage_presence["final_sql"] = True
    for path in FINAL_STAGE_TABLE_PATHS:
        exists, value = _get_nested(response_payload, path)
        if not exists:
            continue
        stage_presence["final_sql"] = True
        extracted = _extract_tables_from_object(value)
        final_tables = _merge_unique_strings(final_tables, extracted)
        notes.append(f"final_sql path found: {'.'.join(path)} ({len(extracted)} tables)")

    if exec_result:
        exec_tables = _merge_unique_strings(
            exec_result.get("tables_used"),
            exec_result.get("tables"),
        )
        if exec_tables:
            stage_presence["final_sql"] = True
            final_tables = _merge_unique_strings(final_tables, exec_tables)
            notes.append(f"final_sql exec_result tables inferred ({len(exec_tables)} tables)")

    stage_tables["final_sql"] = _merge_unique_strings(final_tables)
    return stage_tables, stage_presence, notes


def _derive_policy_violation(response_payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    for path in POLICY_FLAG_PATHS:
        exists, value = _get_nested(response_payload, path)
        if not exists:
            continue
        if isinstance(value, bool):
            if value:
                return True, ".".join(path)
            continue
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered and lowered not in ("false", "none", "no"):
                return True, f"{'.'.join(path)}={value}"
            continue
        if value is not None:
            return True, f"{'.'.join(path)} present"
    return False, None


def _derive_sql_execution_success(
    status: str,
    sql_query: Optional[str],
    exec_result: Dict[str, Any],
) -> Optional[bool]:
    sql_present = isinstance(sql_query, str) and bool(sql_query.strip())
    if not sql_present:
        return None
    if not isinstance(exec_result, dict) or not exec_result:
        return None
    if isinstance(exec_result.get("ok"), bool):
        return exec_result.get("ok")
    if exec_result.get("error") or exec_result.get("error_message"):
        return False
    row_count = exec_result.get("row_count")
    data_rows = exec_result.get("data")
    if not isinstance(data_rows, list):
        data_rows = exec_result.get("rows")
    if row_count is not None or isinstance(data_rows, list):
        return True
    if status == "success":
        return True
    return None


def _classify_error_type(
    status: str,
    http_status: Optional[int],
    error: Optional[str],
    sql_present: bool,
    policy_violation: bool,
) -> Optional[str]:
    if policy_violation:
        return "policy_violation"
    if http_status is not None and http_status != 200:
        return f"http_{http_status}"
    if status == "success":
        return None
    message = (error or "").lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "connection" in message or "connect" in message:
        return "connection_error"
    if not sql_present:
        return "no_sql_generated"
    return "agent_failure"


def _load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _percentile_95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return float(ordered[idx])


def _extract_payload_from_jsonrpc_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    result = raw.get("result")
    if isinstance(result, dict):
        return result

    # MCP tool responses can be a list envelope, including typed JSON chunks:
    # [{"type":"json","json": {...}}]
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "json":
                payload = item.get("json")
                if isinstance(payload, dict):
                    return payload

    text_parts: List[str] = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                text_parts.append(item)

    text = "\n".join(part for part in text_parts if part).strip()
    marker = "Full response (JSON):"
    if marker in text:
        json_blob = text.split(marker, 1)[1].strip()
        try:
            payload = json.loads(json_blob)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    if text.startswith("{") and text.endswith("}"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    return {"ok": False, "error": "Could not parse MCP payload", "raw_text": text}


async def _fetch_mcp_health_snapshot(mcp_url: str, api_key: Optional[str]) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {"url": mcp_url, "reachable": False}
    target = (mcp_url or "").strip().rstrip("/")
    if not target:
        snapshot["error"] = "MCP URL is empty"
        return snapshot

    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{target}/health", headers=headers)
        snapshot["status_code"] = response.status_code
        snapshot["reachable"] = response.status_code == 200

        payload: Any
        if "application/json" in response.headers.get("content-type", "").lower():
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
                    snapshot["off_control_mode"] = scout_component.get("off_control_mode")
    except Exception as exc:
        snapshot["error"] = str(exc)
    return snapshot


def _derive_scout_mode(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    backend = snapshot.get("discovery_backend")
    status = snapshot.get("discovery_status")
    catalog_valid = snapshot.get("catalog_valid")
    off_control_mode = snapshot.get("off_control_mode")
    active = backend == "ScoutRunner"

    if active:
        meaning = (
            "Scout mode ACTIVE: MCP discovery backend is ScoutRunner. "
            "Catalog source is scout_runner_catalog."
        )
    elif backend == "SchemaCatalog":
        if off_control_mode == "legacy_lexical_schema_linking":
            meaning = (
                "Scout mode INACTIVE: MCP discovery backend is SchemaCatalog "
                "with legacy lexical schema-linking baseline."
            )
        else:
            meaning = (
                "Scout mode INACTIVE: MCP discovery backend is SchemaCatalog "
                "with aligned TableRanker baseline."
            )
    else:
        meaning = (
            "Scout mode UNKNOWN: discovery backend not clearly reported. "
            "Verify MCP /health before using results for A/B claims."
        )

    return {
        "active": active,
        "backend": backend,
        "status": status,
        "catalog_valid": catalog_valid,
        "off_control_mode": off_control_mode,
        "meaning": meaning,
    }


async def _call_process_query(
    client: httpx.AsyncClient,
    target_url: str,
    api_key: str,
    query_id: str,
    question: str,
    timeout_s: float,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    endpoint = f"{target_url.rstrip('/')}/process_query"
    payload = {"user_input": question, "api_key": api_key}

    try:
        response = await client.post(endpoint, json=payload, timeout=timeout_s)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if response.status_code != 200:
            base_error = f"HTTP {response.status_code}: {response.text}"
            return {
                "query_id": query_id,
                "question": question,
                "status": "failed",
                "http_status": response.status_code,
                "latency_ms_total": latency_ms,
                "error": base_error,
                "final_response_text": "",
                "sql_query": None,
                "exec_result": None,
                "tables_used": [],
                "raw_response_keys": [],
                "trace_stage_presence": {
                    "discovery": False,
                    "ranked": False,
                    "final_sql": False,
                },
                "stage_tables": {
                    "discovery": [],
                    "ranked": [],
                    "final_sql": [],
                },
                "trace_extraction_notes": ["non-200 response; trace extraction skipped"],
                "sql_execution_success": None,
                "policy_violation": False,
                "policy_violation_detail": None,
                "error_type": _classify_error_type(
                    status="failed",
                    http_status=response.status_code,
                    error=base_error,
                    sql_present=False,
                    policy_violation=False,
                ),
            }

        data = response.json()
        exec_result = data.get("exec_result") if isinstance(data.get("exec_result"), dict) else {}
        sql_query = data.get("sql_query")
        tables_used = _merge_unique_strings(
            data.get("sources"),
            data.get("relevant_tables"),
            exec_result.get("tables_used"),
            exec_result.get("tables"),
        )
        stage_tables, trace_stage_presence, trace_notes = _extract_stage_tables(
            response_payload=data,
            sql_query=sql_query if isinstance(sql_query, str) else None,
            exec_result=exec_result,
        )
        tables_used = _merge_unique_strings(
            tables_used,
            stage_tables.get("final_sql"),
            stage_tables.get("ranked"),
            stage_tables.get("discovery"),
        )
        policy_violation, policy_violation_detail = _derive_policy_violation(data)

        result_rows = exec_result.get("data")
        if not isinstance(result_rows, list):
            result_rows = exec_result.get("rows")
        if not isinstance(result_rows, list):
            result_rows = []

        row_count = exec_result.get("row_count")
        if row_count is None and result_rows:
            row_count = len(result_rows)

        success_flag = bool(data.get("success", False))
        status = "success" if success_flag else "failed"
        sql_execution_success = _derive_sql_execution_success(
            status=status,
            sql_query=sql_query if isinstance(sql_query, str) else None,
            exec_result=exec_result,
        )
        error = data.get("error")
        sql_present = isinstance(sql_query, str) and bool(sql_query.strip())

        return {
            "query_id": query_id,
            "question": question,
            "status": status,
            "http_status": response.status_code,
            "latency_ms_total": latency_ms,
            "error": error,
            "final_response_text": data.get("final_response", ""),
            "sql_query": sql_query,
            "exec_result": exec_result,
            "tables_used": tables_used,
            "row_count": row_count,
            "result_preview": result_rows[:20],
            "raw_response_keys": sorted(data.keys()) if isinstance(data, dict) else [],
            "trace_stage_presence": trace_stage_presence,
            "stage_tables": stage_tables,
            "trace_extraction_notes": trace_notes,
            "sql_execution_success": sql_execution_success,
            "policy_violation": policy_violation,
            "policy_violation_detail": policy_violation_detail,
            "error_type": _classify_error_type(
                status=status,
                http_status=response.status_code,
                error=str(error) if error is not None else None,
                sql_present=sql_present,
                policy_violation=policy_violation,
            ),
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        error_text = str(exc)
        return {
            "query_id": query_id,
            "question": question,
            "status": "failed",
            "http_status": None,
            "latency_ms_total": latency_ms,
            "error": error_text,
            "final_response_text": "",
            "sql_query": None,
            "exec_result": None,
            "tables_used": [],
            "row_count": None,
            "result_preview": [],
            "raw_response_keys": [],
            "trace_stage_presence": {
                "discovery": False,
                "ranked": False,
                "final_sql": False,
            },
            "stage_tables": {
                "discovery": [],
                "ranked": [],
                "final_sql": [],
            },
            "trace_extraction_notes": ["exception before trace extraction"],
            "sql_execution_success": None,
            "policy_violation": False,
            "policy_violation_detail": None,
            "error_type": _classify_error_type(
                status="failed",
                http_status=None,
                error=error_text,
                sql_present=False,
                policy_violation=False,
            ),
        }


def _normalize_required_stage_traces(stages: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for stage in stages:
        name = str(stage or "").strip().lower()
        if not name:
            continue
        if name not in STAGE_NAMES:
            raise ValueError(
                f"Unsupported stage trace requirement '{stage}'. "
                f"Supported: {', '.join(STAGE_NAMES)}"
            )
        if name not in normalized:
            normalized.append(name)
    return normalized


def _apply_stage_trace_requirements(
    result: Dict[str, Any],
    required_stage_traces: Sequence[str],
) -> Dict[str, Any]:
    required = _normalize_required_stage_traces(required_stage_traces)
    presence = result.get("trace_stage_presence")
    if not isinstance(presence, dict):
        presence = {}
    missing = [stage for stage in required if not bool(presence.get(stage))]
    result["required_stage_traces"] = required
    result["missing_required_stage_traces"] = missing
    result["trace_requirements_met"] = len(missing) == 0
    return result


async def _run_process_query_batch(
    dataset: List[Dict[str, Any]],
    target_url: str,
    api_key: str,
    timeout_s: float,
    concurrency: int,
    required_stage_traces: Sequence[str],
    abort_on_missing_stage_trace: bool,
) -> Tuple[Dict[str, Dict[str, Any]], Optional[Dict[str, Any]]]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _run_one(row: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        query_id = str(row.get("id"))
        question = str(row.get("question") or "").strip()
        async with semaphore:
            result = await _call_process_query(
                client=client,
                target_url=target_url,
                api_key=api_key,
                query_id=query_id,
                question=question,
                timeout_s=timeout_s,
            )
        result = _apply_stage_trace_requirements(result, required_stage_traces)
        return query_id, result

    results: Dict[str, Dict[str, Any]] = {}
    aborted: Optional[Dict[str, Any]] = None
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        if abort_on_missing_stage_trace or max(1, concurrency) == 1:
            for row in dataset:
                query_id, result = await _run_one(row)
                results[query_id] = result
                status = result.get("status")
                latency = result.get("latency_ms_total")
                print(f"[{query_id}] {status} ({latency}ms)")
                missing = result.get("missing_required_stage_traces") or []
                if abort_on_missing_stage_trace and missing:
                    aborted = {
                        "query_id": query_id,
                        "missing_required_stage_traces": missing,
                        "message": (
                            "Aborted run because required stage traces were missing "
                            f"for query {query_id}: {', '.join(missing)}"
                        ),
                    }
                    print(f"[ABORT] {aborted['message']}")
                    break
        else:
            tasks = [asyncio.create_task(_run_one(row)) for row in dataset]
            for task in asyncio.as_completed(tasks):
                query_id, result = await task
                results[query_id] = result
                status = result.get("status")
                latency = result.get("latency_ms_total")
                print(f"[{query_id}] {status} ({latency}ms)")
    return results, aborted


def _normalize_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        # Stabilize tiny floating differences from DB/json serialization.
        return round(value, 10)
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _normalize_query_result(payload: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    data = payload.get("data")
    if not isinstance(data, list):
        data = payload.get("rows")
    if not isinstance(data, list):
        data = []

    columns = payload.get("columns")
    if not isinstance(columns, list):
        columns = []

    normalized_rows: List[Dict[str, Any]] = []

    if data and isinstance(data[0], dict):
        if not columns:
            # Preserve first-row key order and then append unseen keys from later rows.
            seen: List[str] = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                for key in row.keys():
                    if key not in seen:
                        seen.append(key)
            columns = seen

        for row in data:
            if not isinstance(row, dict):
                continue
            normalized_rows.append({col: _normalize_scalar(row.get(col)) for col in columns})
        return [str(c) for c in columns], normalized_rows

    if data and isinstance(data[0], (list, tuple)):
        if not columns:
            columns = [f"col_{idx+1}" for idx in range(len(data[0]))]
        for raw_row in data:
            row_values = list(raw_row) if isinstance(raw_row, (list, tuple)) else []
            normalized_rows.append(
                {
                    str(columns[idx]): _normalize_scalar(row_values[idx] if idx < len(row_values) else None)
                    for idx in range(len(columns))
                }
            )
        return [str(c) for c in columns], normalized_rows

    return [str(c) for c in columns], normalized_rows


def _row_sequence(rows: List[Dict[str, Any]], columns: List[str]) -> List[Tuple[Any, ...]]:
    return [tuple(_normalize_scalar(row.get(col)) for col in columns) for row in rows]


def _row_multiset(rows: List[Dict[str, Any]], columns: List[str]) -> Counter:
    return Counter(_row_sequence(rows, columns))


def _compare_result_sets(
    ref_payload: Dict[str, Any],
    cand_payload: Dict[str, Any],
) -> Dict[str, Any]:
    ref_cols, ref_rows = _normalize_query_result(ref_payload)
    cand_cols, cand_rows = _normalize_query_result(cand_payload)

    strict_equal = ref_cols == cand_cols and _row_sequence(ref_rows, ref_cols) == _row_sequence(cand_rows, cand_cols)

    same_cols_set_equal = False
    if set(ref_cols) == set(cand_cols):
        common_sorted = sorted(set(ref_cols))
        same_cols_set_equal = _row_multiset(ref_rows, common_sorted) == _row_multiset(cand_rows, common_sorted)

    positional_set_equal = False
    if len(ref_cols) == len(cand_cols):
        positional_set_equal = _row_multiset(ref_rows, ref_cols) == _row_multiset(cand_rows, cand_cols)

    common_cols = [col for col in ref_cols if col in set(cand_cols)]
    common_cols_set_equal: Optional[bool]
    if not common_cols:
        common_cols_set_equal = None
    else:
        common_cols_set_equal = _row_multiset(ref_rows, common_cols) == _row_multiset(cand_rows, common_cols)

    return {
        "ref_cols": ref_cols,
        "cand_cols": cand_cols,
        "ref_row_count": len(ref_rows),
        "cand_row_count": len(cand_rows),
        "strict_equal": strict_equal,
        "same_cols_set_equal": same_cols_set_equal,
        "positional_set_equal": positional_set_equal,
        "common_cols": common_cols,
        "common_cols_set_equal": common_cols_set_equal,
    }


async def _call_mcp_run_query(
    client: httpx.AsyncClient,
    mcp_url: str,
    mcp_api_key: str,
    sql: str,
    limit: int,
) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "run_query", "arguments": {"sql": sql, "limit": limit}},
        "id": 1,
    }
    headers = {"X-API-Key": mcp_api_key, "Content-Type": "application/json"}
    response = await client.post(f"{mcp_url.rstrip('/')}/mcp", json=payload, headers=headers, timeout=120.0)
    response.raise_for_status()
    raw = response.json()
    return _extract_payload_from_jsonrpc_result(raw)


async def _evaluate_single_query(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    query_id: str,
    query_artifact: Dict[str, Any],
    reference_sql: Dict[str, str],
    mcp_url: str,
    mcp_api_key: str,
    mcp_query_limit: int,
) -> Dict[str, Any]:
    candidate_sql = query_artifact.get("sql_query")
    reference_query = reference_sql.get(query_id, "")

    required_tables = _extract_tables_from_sql(reference_query)
    candidate_tables = _extract_tables_from_sql(candidate_sql or "")
    required_tables_ok = set(required_tables).issubset(set(candidate_tables)) if required_tables else False

    entry: Dict[str, Any] = {
        "query_id": query_id,
        "question": query_artifact.get("question"),
        "required_tables": required_tables,
        "candidate_tables": candidate_tables,
        "required_tables_ok": required_tables_ok,
        "candidate_sql": candidate_sql,
        "reference_sql": reference_query,
        "candidate_sql_exec_error": None,
        "reference_sql_exec_error": None,
        "comparison": None,
    }

    if not candidate_sql:
        entry["candidate_sql_exec_error"] = "No candidate SQL in /process_query response"
        return entry
    if not reference_query:
        entry["reference_sql_exec_error"] = "No reference SQL for query_id"
        return entry

    async with semaphore:
        cand_task = _call_mcp_run_query(
            client=client,
            mcp_url=mcp_url,
            mcp_api_key=mcp_api_key,
            sql=candidate_sql,
            limit=mcp_query_limit,
        )
        ref_task = _call_mcp_run_query(
            client=client,
            mcp_url=mcp_url,
            mcp_api_key=mcp_api_key,
            sql=reference_query,
            limit=mcp_query_limit,
        )
        cand_payload, ref_payload = await asyncio.gather(cand_task, ref_task, return_exceptions=True)

    if isinstance(cand_payload, Exception):
        entry["candidate_sql_exec_error"] = str(cand_payload)
        return entry
    if isinstance(ref_payload, Exception):
        entry["reference_sql_exec_error"] = str(ref_payload)
        return entry

    if not isinstance(cand_payload, dict):
        entry["candidate_sql_exec_error"] = "Candidate payload is not a dict"
        return entry
    if not isinstance(ref_payload, dict):
        entry["reference_sql_exec_error"] = "Reference payload is not a dict"
        return entry

    if cand_payload.get("ok") is False:
        entry["candidate_sql_exec_error"] = cand_payload.get("error") or "Candidate query failed"
    if ref_payload.get("ok") is False:
        entry["reference_sql_exec_error"] = ref_payload.get("error") or "Reference query failed"

    if entry["candidate_sql_exec_error"] or entry["reference_sql_exec_error"]:
        return entry

    entry["comparison"] = _compare_result_sets(ref_payload=ref_payload, cand_payload=cand_payload)
    return entry


async def _evaluate_expert_async(
    process_results: Dict[str, Dict[str, Any]],
    reference_sql_path: Path,
    mcp_url: str,
    mcp_api_key: str,
    mcp_query_limit: int,
    eval_concurrency: int,
) -> Dict[str, Any]:
    reference_sql = json.loads(reference_sql_path.read_text(encoding="utf-8"))
    semaphore = asyncio.Semaphore(max(1, eval_concurrency))
    per_query: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        tasks = [
            asyncio.create_task(
                _evaluate_single_query(
                    semaphore=semaphore,
                    client=client,
                    query_id=query_id,
                    query_artifact=artifact,
                    reference_sql=reference_sql,
                    mcp_url=mcp_url,
                    mcp_api_key=mcp_api_key,
                    mcp_query_limit=mcp_query_limit,
                )
            )
            for query_id, artifact in process_results.items()
        ]
        for task in asyncio.as_completed(tasks):
            per_query.append(await task)

    per_query.sort(key=lambda row: row.get("query_id", ""))
    total = len(per_query)
    strict = sum(1 for row in per_query if (row.get("comparison") or {}).get("strict_equal") is True)
    same_cols = sum(1 for row in per_query if (row.get("comparison") or {}).get("same_cols_set_equal") is True)
    positional = sum(1 for row in per_query if (row.get("comparison") or {}).get("positional_set_equal") is True)
    common_cols = sum(1 for row in per_query if (row.get("comparison") or {}).get("common_cols_set_equal") is True)
    required_ok = sum(1 for row in per_query if row.get("required_tables_ok") is True)
    sql_exec_errors = sum(
        1
        for row in per_query
        if row.get("candidate_sql_exec_error") or row.get("reference_sql_exec_error")
    )

    summary = {
        "total": total,
        "strict_equal_count": strict,
        "same_cols_set_equal_count": same_cols,
        "positional_set_equal_count": positional,
        "common_cols_set_equal_count": common_cols,
        "required_tables_ok_count": required_ok,
        "sql_exec_errors_count": sql_exec_errors,
    }

    manual_template = {
        "instructions": {
            "labels": ["CORRECT", "PARTIAL", "INCORRECT"],
            "reason_codes": EXPERT_REASON_CODES,
        },
        "per_query": [
            {
                "query_id": row.get("query_id"),
                "label": None,
                "reason_codes": [],
                "reviewer_notes": "",
                "auto_summary": {
                    "required_tables_ok": row.get("required_tables_ok"),
                    "strict_equal": (row.get("comparison") or {}).get("strict_equal"),
                    "same_cols_set_equal": (row.get("comparison") or {}).get("same_cols_set_equal"),
                    "positional_set_equal": (row.get("comparison") or {}).get("positional_set_equal"),
                    "common_cols_set_equal": (row.get("comparison") or {}).get("common_cols_set_equal"),
                    "candidate_sql_exec_error": row.get("candidate_sql_exec_error"),
                    "reference_sql_exec_error": row.get("reference_sql_exec_error"),
                },
            }
            for row in per_query
        ],
    }

    return {
        "generated_at_utc": _utc_now(),
        "reference_sql_path": str(reference_sql_path),
        "summary": summary,
        "per_query": per_query,
        "manual_review_template": manual_template,
    }


def _render_run_summary_md(
    run_id: str,
    run_name: str,
    mode_label: str,
    scout_mode_start: Dict[str, Any],
    scout_mode_end: Dict[str, Any],
    process_results: Dict[str, Dict[str, Any]],
    required_stage_traces: Sequence[str],
    aborted: Optional[Dict[str, Any]],
) -> str:
    rows = list(process_results.values())
    total = len(rows)
    successes = sum(1 for row in rows if row.get("status") == "success")
    failures = total - successes
    trace_complete = sum(1 for row in rows if row.get("trace_requirements_met") is True)
    latencies = [
        _safe_float(row.get("latency_ms_total"))
        for row in rows
        if _safe_float(row.get("latency_ms_total")) is not None
    ]
    avg_latency = round(statistics.mean(latencies), 1) if latencies else None
    p95_latency = round(_percentile_95(latencies), 1) if latencies else None

    lines = [
        f"# /process_query Northwind Run ({mode_label})",
        "",
        f"- Run ID: `{run_id}`",
        f"- Run name: `{run_name}`",
        f"- Scout start: `{scout_mode_start.get('backend')}` | active=`{scout_mode_start.get('active')}`",
        f"- Scout end: `{scout_mode_end.get('backend')}` | active=`{scout_mode_end.get('active')}`",
        f"- Meaning: {scout_mode_start.get('meaning')}",
        f"- Total queries: `{total}`",
        f"- Successes: `{successes}`",
        f"- Failures: `{failures}`",
        f"- Avg latency ms: `{avg_latency}`",
        f"- P95 latency ms: `{p95_latency}`",
        f"- Required stage traces: `{', '.join(required_stage_traces) if required_stage_traces else '<none>'}`",
        f"- Trace requirements met: `{trace_complete}/{total}`",
    ]
    if aborted:
        lines.append(f"- Aborted early: `{aborted.get('message')}`")
    lines.extend(
        [
            "",
            "| Query | Status | Latency (ms) | SQL present | Trace OK | Missing trace stages | Tables used |",
            "|---|---|---:|---|---|---|---|",
        ]
    )
    for query_id in sorted(process_results.keys()):
        row = process_results[query_id]
        sql_present = bool((row.get("sql_query") or "").strip())
        tables = ", ".join(row.get("tables_used") or [])
        missing = ", ".join(row.get("missing_required_stage_traces") or [])
        lines.append(
            f"| {query_id} | {row.get('status')} | {row.get('latency_ms_total')} | "
            f"{sql_present} | {row.get('trace_requirements_met')} | {missing} | {tables} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_expert_eval_md(run_id: str, eval_payload: Dict[str, Any]) -> str:
    summary = eval_payload.get("summary") or {}
    per_query = eval_payload.get("per_query") or []

    lines = [
        f"# Async Expert Evaluation ({run_id})",
        "",
        f"- Reference SQL: `{eval_payload.get('reference_sql_path')}`",
        f"- Total queries: `{summary.get('total')}`",
        f"- Strict equal: `{summary.get('strict_equal_count')}`",
        f"- Same-column set equal: `{summary.get('same_cols_set_equal_count')}`",
        f"- Positional set equal: `{summary.get('positional_set_equal_count')}`",
        f"- Common-column set equal: `{summary.get('common_cols_set_equal_count')}`",
        f"- Required table coverage: `{summary.get('required_tables_ok_count')}`",
        f"- SQL execution errors: `{summary.get('sql_exec_errors_count')}`",
        "",
        "| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in per_query:
        cmp = row.get("comparison") or {}
        lines.append(
            "| {query} | {req} | {strict} | {same_cols} | {pos} | {common} | {err} |".format(
                query=row.get("query_id"),
                req=row.get("required_tables_ok"),
                strict=cmp.get("strict_equal"),
                same_cols=cmp.get("same_cols_set_equal"),
                pos=cmp.get("positional_set_equal"),
                common=cmp.get("common_cols_set_equal"),
                err=row.get("candidate_sql_exec_error"),
            )
        )
    lines.append("")
    return "\n".join(lines)


async def run(
    dataset_path: Path,
    run_name: str,
    mode_label: str,
    target_url: str,
    api_key: str,
    request_timeout_s: float,
    concurrency: int,
    mcp_url: str,
    mcp_api_key: str,
    evaluate_expert: bool,
    reference_sql_path: Path,
    expert_sheet_path: Path,
    mcp_query_limit: int,
    eval_concurrency: int,
    required_stage_traces: Sequence[str],
    abort_on_missing_stage_trace: bool,
) -> Path:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if evaluate_expert and not reference_sql_path.exists():
        raise FileNotFoundError(f"Reference SQL not found: {reference_sql_path}")

    dataset = _load_dataset(dataset_path)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{run_name}"
    run_dir = Path(__file__).parent / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Run ID: {run_id}")
    print(f"Run dir: {run_dir}")
    print(f"Target: {target_url.rstrip('/')}/process_query")
    print(f"Queries: {len(dataset)}")
    print(
        "Required stage traces: "
        f"{', '.join(required_stage_traces) if required_stage_traces else '<none>'}"
    )
    print(f"Abort on missing stage trace: {abort_on_missing_stage_trace}")

    mcp_health_start = await _fetch_mcp_health_snapshot(mcp_url=mcp_url, api_key=mcp_api_key)
    scout_mode_start = _derive_scout_mode(mcp_health_start)
    print(f"Scout start backend: {scout_mode_start.get('backend')} (active={scout_mode_start.get('active')})")

    if abort_on_missing_stage_trace and max(1, concurrency) != 1:
        print("Abort-on-missing-stage-trace requires sequential mode; forcing concurrency=1.")
        concurrency = 1

    process_results, aborted = await _run_process_query_batch(
        dataset=dataset,
        target_url=target_url,
        api_key=api_key,
        timeout_s=request_timeout_s,
        concurrency=concurrency,
        required_stage_traces=required_stage_traces,
        abort_on_missing_stage_trace=abort_on_missing_stage_trace,
    )

    mcp_health_end = await _fetch_mcp_health_snapshot(mcp_url=mcp_url, api_key=mcp_api_key)
    scout_mode_end = _derive_scout_mode(mcp_health_end)
    print(f"Scout end backend: {scout_mode_end.get('backend')} (active={scout_mode_end.get('active')})")

    rows = list(process_results.values())
    total = len(rows)
    successes = sum(1 for row in rows if row.get("status") == "success")
    failures = total - successes
    latencies = [
        _safe_float(row.get("latency_ms_total"))
        for row in rows
        if _safe_float(row.get("latency_ms_total")) is not None
    ]
    avg_latency = round(statistics.mean(latencies), 1) if latencies else None
    p95_latency = round(_percentile_95(latencies), 1) if latencies else None
    trace_complete_count = sum(1 for row in rows if row.get("trace_requirements_met") is True)
    sql_execution_success_count = sum(1 for row in rows if row.get("sql_execution_success") is True)
    policy_violations_count = sum(1 for row in rows if row.get("policy_violation") is True)

    summary = {
        "run_id": run_id,
        "run_name": run_name,
        "mode_label": mode_label,
        "total_queries": total,
        "successes": successes,
        "failures": failures,
        "success_rate": round((successes / total) * 100.0, 2) if total else 0.0,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "trace_complete_count": trace_complete_count,
        "trace_complete_rate": (trace_complete_count / total) if total else None,
        "sql_execution_success_count": sql_execution_success_count,
        "policy_violations_count": policy_violations_count,
        "required_stage_traces": list(required_stage_traces),
        "aborted_on_missing_stage_trace": bool(aborted),
        "abort_details": aborted,
        "scout_mode_start": scout_mode_start,
        "scout_mode_end": scout_mode_end,
        "results_dir": str(run_dir),
    }

    manifest = {
        "run_id": run_id,
        "run_name": run_name,
        "mode_label": mode_label,
        "generated_at_utc": _utc_now(),
        "dataset_path": str(dataset_path),
        "reference_sql_path": str(reference_sql_path),
        "expert_sheet_path": str(expert_sheet_path),
        "target_url": target_url,
        "mcp_url": mcp_url,
        "request_timeout_s": request_timeout_s,
        "request_concurrency": concurrency,
        "required_stage_traces": list(required_stage_traces),
        "abort_on_missing_stage_trace": bool(abort_on_missing_stage_trace),
        "abort_details": aborted,
        "evaluate_expert": evaluate_expert,
        "eval_concurrency": eval_concurrency,
        "mcp_query_limit": mcp_query_limit,
        "mcp_health_start": mcp_health_start,
        "mcp_health_end": mcp_health_end,
        "scout_mode_start": scout_mode_start,
        "scout_mode_end": scout_mode_end,
    }

    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "process_query_results.json").write_text(json.dumps(process_results, indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "run_summary.md").write_text(
        _render_run_summary_md(
            run_id=run_id,
            run_name=run_name,
            mode_label=mode_label,
            scout_mode_start=scout_mode_start,
            scout_mode_end=scout_mode_end,
            process_results=process_results,
            required_stage_traces=required_stage_traces,
            aborted=aborted,
        ),
        encoding="utf-8",
    )

    if evaluate_expert:
        print("Running async expert evaluation...")
        expert_eval = await _evaluate_expert_async(
            process_results=process_results,
            reference_sql_path=reference_sql_path,
            mcp_url=mcp_url,
            mcp_api_key=mcp_api_key,
            mcp_query_limit=mcp_query_limit,
            eval_concurrency=eval_concurrency,
        )
        (run_dir / "expert_async_eval.json").write_text(json.dumps(expert_eval, indent=2), encoding="utf-8")
        (run_dir / "expert_async_eval.md").write_text(
            _render_expert_eval_md(run_id=run_id, eval_payload=expert_eval),
            encoding="utf-8",
        )
        (run_dir / "expert_manual_review_template.json").write_text(
            json.dumps(expert_eval.get("manual_review_template") or {}, indent=2),
            encoding="utf-8",
        )

    print("\n/process_query run complete")
    print(f"Success rate: {summary['success_rate']}%")
    print(f"Avg latency: {summary['avg_latency_ms']}ms")
    print(f"P95 latency: {summary['p95_latency_ms']}ms")
    print(
        "Trace completeness: "
        f"{summary['trace_complete_count']}/{summary['total_queries']}"
    )
    print(f"Artifacts: {run_dir}")
    return run_dir


def _parse_stage_trace_arg(raw: str) -> List[str]:
    if not raw:
        return []
    items = [part.strip() for part in raw.split(",") if part.strip()]
    return _normalize_required_stage_traces(items)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Northwind /process_query startup runner with optional async expert evaluation."
    )
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).parent / "datasets" / "northwind_queries.jsonl"),
        help="Dataset JSONL path with {id, question}.",
    )
    parser.add_argument(
        "--run-name",
        default="northwind_process_query",
        help="Run name suffix.",
    )
    parser.add_argument(
        "--mode-label",
        default="unset_mode",
        help="Free-form label (e.g., scout_on / scout_off).",
    )
    parser.add_argument(
        "--target",
        default="http://localhost:5001",
        help="Agent service base URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY", "supersecretapikey"),
        help="Agent API key payload field.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=180.0,
        help="Per-query /process_query timeout seconds.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Concurrent /process_query calls. Use 1 for fully sequential awaits.",
    )
    parser.add_argument(
        "--mcp-url",
        default=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
        help="MCP server URL (for health + expert eval re-execution).",
    )
    parser.add_argument(
        "--mcp-api-key",
        default=os.getenv("MCP_API_KEY", "supersecretapikey"),
        help="MCP API key.",
    )
    parser.add_argument(
        "--evaluate-expert",
        action="store_true",
        help="Run async candidate-vs-reference evaluation using MCP run_query.",
    )
    parser.add_argument(
        "--reference-sql",
        default=str(Path(__file__).parent / "datasets" / "northwind_queries.reference_sql.json"),
        help="Reference SQL JSON path keyed by query_id.",
    )
    parser.add_argument(
        "--expert-sheet",
        default=str(Path(__file__).parent / "datasets" / "northwind_expert_review_sheet.md"),
        help="Expert review sheet path (recorded in manifest for traceability).",
    )
    parser.add_argument(
        "--mcp-query-limit",
        type=int,
        default=1000,
        help="Row limit for MCP run_query during expert evaluation.",
    )
    parser.add_argument(
        "--eval-concurrency",
        type=int,
        default=4,
        help="Concurrent expert-eval query executions.",
    )
    parser.add_argument(
        "--require-stage-traces",
        default="discovery,ranked",
        help=(
            "Comma-separated stage traces required for each query. "
            "Supported: discovery, ranked, final_sql."
        ),
    )
    parser.add_argument(
        "--abort-on-missing-stage-trace",
        action="store_true",
        help="Abort the run at the first query missing any required stage trace.",
    )
    args = parser.parse_args()
    required_stage_traces = _parse_stage_trace_arg(args.require_stage_traces)

    asyncio.run(
        run(
            dataset_path=Path(args.dataset),
            run_name=args.run_name,
            mode_label=args.mode_label,
            target_url=args.target,
            api_key=args.api_key,
            request_timeout_s=args.request_timeout,
            concurrency=args.concurrency,
            mcp_url=args.mcp_url,
            mcp_api_key=args.mcp_api_key,
            evaluate_expert=args.evaluate_expert,
            reference_sql_path=Path(args.reference_sql),
            expert_sheet_path=Path(args.expert_sheet),
            mcp_query_limit=args.mcp_query_limit,
            eval_concurrency=args.eval_concurrency,
            required_stage_traces=required_stage_traces,
            abort_on_missing_stage_trace=bool(args.abort_on_missing_stage_trace),
        )
    )


if __name__ == "__main__":
    main()
