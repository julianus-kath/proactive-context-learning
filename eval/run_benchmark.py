"""
Benchmark Runner CLI
Executes the fixed query catalog against the LangGraph service.
Usage: python -m eval.run_benchmark --dataset eval/datasets/cockpit_queries.jsonl --run-name northwind_v1 --target http://localhost:5001
"""

import os
import sys
import json
import time
import re
import argparse
import asyncio
import subprocess
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

from eval.eval_client import EvalClient
from eval.contracts import QueryContract

try:
    import asyncpg
except Exception:  # pragma: no cover - optional runtime dependency
    asyncpg = None


SEMANTIC_CORRECT = "CORRECT"
SEMANTIC_PARTIAL = "PARTIAL"
SEMANTIC_INCORRECT = "INCORRECT"


def _normalize_table_name(name: str) -> str:
    """Normalize table names to schema.table or table lowercase format."""
    if not isinstance(name, str):
        return ""
    cleaned = (
        name.strip()
        .lower()
        .replace('"', "")
        .replace("`", "")
        .replace("[", "")
        .replace("]", "")
    )
    if not cleaned:
        return ""
    parts = [part for part in cleaned.split(".") if part]
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return parts[-1] if parts else ""


def _extract_tables_from_sql(sql: str) -> List[str]:
    if not isinstance(sql, str) or not sql.strip():
        return []
    pattern = r"(?:from|join)\s+([a-zA-Z0-9_\.\"`\[\]]+)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    unique: List[str] = []
    seen = set()
    for raw in matches:
        normalized = _normalize_table_name(raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _table_basename(name: str) -> str:
    normalized = _normalize_table_name(name)
    if not normalized:
        return ""
    return normalized.split(".")[-1]


def _normalize_sql(sql: str) -> str:
    if not isinstance(sql, str):
        return ""
    return " ".join(sql.lower().split())


def _extract_json_payload_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON payload from MCP text wrappers."""
    if not isinstance(text, str) or not text.strip():
        return None

    candidates = [text.strip()]
    marker = "Full response (JSON):"
    if marker in text:
        candidates.append(text.split(marker, 1)[-1].strip())

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1].strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue
    return None


def _extract_payload_from_mcp_result(mcp_result: Any) -> Optional[Dict[str, Any]]:
    """
    Extract structured payload from MCP JSON-RPC result envelope.

    Expected format:
      {"result": [{"type":"text","text":"...Full response (JSON): {...}"}]}
    """
    if isinstance(mcp_result, dict) and isinstance(mcp_result.get("result"), dict):
        return mcp_result.get("result")

    contents = None
    if isinstance(mcp_result, dict):
        contents = mcp_result.get("result")
    if not isinstance(contents, list):
        return None

    for item in contents:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "json" and isinstance(item.get("json"), dict):
            return item["json"]
        if item.get("type") == "text":
            payload = _extract_json_payload_from_text(item.get("text", ""))
            if payload is not None:
                return payload
    return None


def _derive_reference_sql_path_for_dataset(dataset_path: Path) -> Path:
    return dataset_path.with_name(f"{dataset_path.stem}.reference_sql.json")


def load_reference_sql_for_dataset(dataset_path: Path) -> Dict[str, str]:
    """
    Load optional per-query reference SQL mapping.

    Accepted shape:
      { "NW1": "SELECT ...", ... }
    """
    reference_path = _derive_reference_sql_path_for_dataset(dataset_path)
    if not reference_path.exists():
        return {}
    with open(reference_path) as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid reference SQL format in {reference_path}")
    out: Dict[str, str] = {}
    for query_id, sql in payload.items():
        if isinstance(query_id, str) and isinstance(sql, str) and sql.strip():
            out[query_id] = sql
    return out


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


def _derive_contract_path_for_dataset(dataset_path: Path) -> Path:
    """
    Derive the contract file path for a given dataset.

    Example:
        eval/datasets/cockpit_queries_top5.jsonl
        -> eval/datasets/cockpit_queries_top5.contracts.json
    """
    return dataset_path.with_name(f"{dataset_path.stem}.contracts.json")


def load_query_contracts_for_dataset(dataset_path: Path) -> Dict[str, QueryContract]:
    """
    Load per-query semantic contracts for a dataset.

    Returns a mapping {query_id -> QueryContract}.
    Raises FileNotFoundError if the contract file is missing and
    ValueError if any contract fails validation.
    """
    contract_path = _derive_contract_path_for_dataset(dataset_path)
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract file not found: {contract_path}")

    with open(contract_path) as f:
        raw = json.load(f)

    entries: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        entries = [e for e in raw if isinstance(e, dict)]
    elif isinstance(raw, dict):
        # Support either a dict keyed by query_id or a single contract object.
        if "query_id" in raw:
            entries = [raw]
        else:
            for qid, payload in raw.items():
                if not isinstance(payload, dict):
                    continue
                # Ensure query_id is set, defaulting to the dict key.
                entry = dict(payload)
                entry.setdefault("query_id", qid)
                entries.append(entry)
    else:
        raise ValueError(f"Unsupported contract file format: {type(raw).__name__}")

    contracts: Dict[str, QueryContract] = {}
    errors: List[str] = []
    for entry in entries:
        try:
            contract = QueryContract.model_validate(entry)
        except Exception as exc:  # pragma: no cover - defensive
            qid = entry.get("query_id") or "<missing>"
            errors.append(f"{qid}: {exc}")
            continue
        contracts[contract.query_id] = contract

    if errors:
        raise ValueError("Contract validation failed:\n" + "\n".join(errors))

    return contracts


def _postgres_connection_settings_from_env() -> Dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DATABASE") or os.getenv("POSTGRES_DB") or "postgres",
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "timeout": float(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10")),
    }


async def _open_postgres_connection():
    if asyncpg is None:
        raise RuntimeError("asyncpg is not installed; cannot run PostgreSQL-based semantic checks")
    settings = _postgres_connection_settings_from_env()
    timeout = settings.pop("timeout", 10.0)
    return await asyncpg.connect(**settings, timeout=timeout)


async def _mcp_tool_call(
    client: httpx.AsyncClient,
    mcp_server_url: str,
    mcp_api_key: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    response = await client.post(
        f"{mcp_server_url.rstrip('/')}/mcp",
        json=payload,
        headers={"X-API-Key": mcp_api_key, "Content-Type": "application/json"},
    )
    response.raise_for_status()
    raw = response.json()
    parsed = _extract_payload_from_mcp_result(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected MCP response for tool {tool_name}: {raw}")
    return parsed


async def _fetch_catalog_snapshot_from_mcp(
    mcp_server_url: str,
    mcp_api_key: str,
) -> Dict[str, Any]:
    """
    Build discovered catalog snapshot via MCP tools.

    Uses:
      - list_tables (paged)
      - get_column_index (batched)
    """
    discovered_tables: Dict[str, Dict[str, Any]] = {}
    table_names: List[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        page = 1
        while True:
            payload = await _mcp_tool_call(
                client,
                mcp_server_url,
                mcp_api_key,
                "list_tables",
                {"page": page, "page_size": 100, "include_empty": True, "min_rows": 0},
            )
            if not payload.get("ok", False):
                raise RuntimeError(f"list_tables failed: {payload.get('error')}")
            data = payload.get("data") or {}
            page_info = payload.get("page_info") or {}
            rows = data.get("tables") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                full_name = _normalize_table_name(row.get("full_name", ""))
                if not full_name:
                    continue
                table_names.append(full_name)
                discovered_tables[full_name] = {
                    "schema": row.get("schema"),
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "estimated_rows": row.get("estimated_rows"),
                    "columns": [],
                    "primary_keys": [],
                    "foreign_keys": [],
                }
            if not page_info.get("has_next"):
                break
            page += 1

        unique_table_names = sorted(set(table_names))
        batch_size = 25
        for idx in range(0, len(unique_table_names), batch_size):
            batch = unique_table_names[idx: idx + batch_size]
            payload = await _mcp_tool_call(
                client,
                mcp_server_url,
                mcp_api_key,
                "get_column_index",
                {"table_names": batch},
            )
            if not payload.get("ok", False):
                continue
            for full_name, details in (payload.get("data") or {}).items():
                normalized_name = _normalize_table_name(full_name)
                if normalized_name not in discovered_tables:
                    continue
                column_details = details.get("column_details") if isinstance(details, dict) else None
                if not column_details and isinstance(details, dict):
                    column_details = [{"name": col} for col in details.get("columns", [])]
                columns = []
                pks = []
                fks = []
                for col in column_details or []:
                    if not isinstance(col, dict):
                        continue
                    col_name = col.get("name")
                    if not col_name:
                        continue
                    col_record = {
                        "name": str(col_name),
                        "type": col.get("type"),
                        "nullable": col.get("nullable"),
                        "is_primary_key": bool(col.get("is_primary_key")),
                        "is_foreign_key": bool(col.get("is_foreign_key")),
                    }
                    columns.append(col_record)
                    if col_record["is_primary_key"]:
                        pks.append(col_record["name"])
                    if col_record["is_foreign_key"]:
                        fks.append({"column": col_record["name"]})
                discovered_tables[normalized_name]["columns"] = columns
                discovered_tables[normalized_name]["primary_keys"] = sorted(set(pks))
                discovered_tables[normalized_name]["foreign_keys"] = fks

    return {
        "source": "mcp_catalog",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tables": discovered_tables,
    }


def _load_catalog_snapshot_from_cache(cache_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load discovered catalog from local SchemaCatalog cache file.

    This is the most faithful "catalog build" artifact in postgres mode.
    """
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            payload = json.load(f)
    except Exception:
        return None

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        return None

    normalized_tables: Dict[str, Dict[str, Any]] = {}
    for full_name, table in tables.items():
        if not isinstance(table, dict):
            continue
        normalized_name = _normalize_table_name(full_name)
        if not normalized_name:
            continue
        normalized_tables[normalized_name] = {
            "schema": table.get("schema"),
            "name": table.get("name"),
            "type": table.get("type"),
            "estimated_rows": table.get("estimated_rows"),
            "columns": table.get("columns", []),
            "primary_keys": table.get("primary_keys", []),
            "foreign_keys": table.get("foreign_keys", []),
        }

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "source": "catalog_cache",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cache_path": str(cache_path),
        "cache_metadata": metadata,
        "tables": normalized_tables,
    }


async def _fetch_information_schema_snapshot(conn) -> Dict[str, Any]:
    """
    Build ground-truth schema snapshot from information_schema.
    """
    tables_sql = """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    """
    columns_sql = """
        SELECT table_schema, table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position
    """
    pk_sql = """
        SELECT tc.table_schema, tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
    """
    fk_sql = """
        SELECT
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY tc.table_schema, tc.table_name, kcu.column_name
    """

    tables_rows = await conn.fetch(tables_sql)
    columns_rows = await conn.fetch(columns_sql)
    pk_rows = await conn.fetch(pk_sql)
    fk_rows = await conn.fetch(fk_sql)

    tables: Dict[str, Dict[str, Any]] = {}
    for row in tables_rows:
        schema = row["table_schema"]
        name = row["table_name"]
        full_name = f"{schema}.{name}".lower()
        tables[full_name] = {
            "schema": schema,
            "name": name,
            "type": row["table_type"],
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
        }

    for row in columns_rows:
        full_name = f"{row['table_schema']}.{row['table_name']}".lower()
        if full_name not in tables:
            continue
        tables[full_name]["columns"].append(
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
            }
        )

    for row in pk_rows:
        full_name = f"{row['table_schema']}.{row['table_name']}".lower()
        if full_name in tables:
            tables[full_name]["primary_keys"].append(row["column_name"])

    for row in fk_rows:
        full_name = f"{row['table_schema']}.{row['table_name']}".lower()
        if full_name in tables:
            tables[full_name]["foreign_keys"].append(
                {
                    "column": row["column_name"],
                    "foreign_table": f"{row['foreign_table_schema']}.{row['foreign_table_name']}".lower(),
                    "foreign_column": row["foreign_column_name"],
                }
            )

    for full_name, table in tables.items():
        pk_set = set(table["primary_keys"])
        fk_set = {fk["column"] for fk in table["foreign_keys"]}
        for col in table["columns"]:
            col["is_primary_key"] = col["name"] in pk_set
            col["is_foreign_key"] = col["name"] in fk_set

    return {
        "source": "information_schema",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tables": tables,
    }


def _compute_catalog_coverage(
    discovered_snapshot: Dict[str, Any],
    ground_truth_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    discovered_tables = discovered_snapshot.get("tables") or {}
    ground_truth_tables = ground_truth_snapshot.get("tables") or {}

    discovered_table_set = set(discovered_tables.keys())
    gt_table_set = set(ground_truth_tables.keys())
    table_intersection = discovered_table_set.intersection(gt_table_set)

    discovered_columns = set()
    gt_columns = set()
    discovered_fk_cols = set()
    gt_fk_cols = set()

    for table_name, table in discovered_tables.items():
        for col in table.get("columns", []):
            col_name = str(col.get("name", "")).lower()
            if not col_name:
                continue
            discovered_columns.add((table_name, col_name))
            if col.get("is_foreign_key"):
                discovered_fk_cols.add((table_name, col_name))

    for table_name, table in ground_truth_tables.items():
        for col in table.get("columns", []):
            col_name = str(col.get("name", "")).lower()
            if not col_name:
                continue
            gt_columns.add((table_name, col_name))
            if col.get("is_foreign_key"):
                gt_fk_cols.add((table_name, col_name))

    column_intersection = discovered_columns.intersection(gt_columns)
    fk_intersection = discovered_fk_cols.intersection(gt_fk_cols)

    def _pct(numerator: int, denominator: int) -> Optional[float]:
        if denominator <= 0:
            return None
        return round((numerator / denominator) * 100.0, 2)

    return {
        "discovered_tables": len(discovered_table_set),
        "ground_truth_tables": len(gt_table_set),
        "table_coverage_pct": _pct(len(table_intersection), len(gt_table_set)),
        "discovered_columns": len(discovered_columns),
        "ground_truth_columns": len(gt_columns),
        "column_coverage_pct": _pct(len(column_intersection), len(gt_columns)),
        "discovered_fk_columns": len(discovered_fk_cols),
        "ground_truth_fk_columns": len(gt_fk_cols),
        "fk_coverage_pct": _pct(len(fk_intersection), len(gt_fk_cols)),
        "missing_tables": sorted(gt_table_set - discovered_table_set),
        "missing_columns_count": len(gt_columns - discovered_columns),
        "missing_fk_columns_count": len(gt_fk_cols - discovered_fk_cols),
    }


def _as_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return round(float(value), 8)
    if isinstance(value, float):
        return round(float(value), 8)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _normalized_result_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        record = {str(k).lower(): _normalize_cell(v) for k, v in row.items()}
        normalized.append(record)
    normalized.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str))
    return normalized


def _compare_row_values(left: Any, right: Any, numeric_tolerance: float) -> bool:
    left_dec = _as_decimal(left)
    right_dec = _as_decimal(right)
    if left_dec is not None and right_dec is not None:
        return abs(float(left_dec - right_dec)) <= numeric_tolerance
    return left == right


def _rows_equivalent(
    expected_rows: List[Dict[str, Any]],
    actual_rows: List[Dict[str, Any]],
    numeric_tolerance: float = 1e-5,
) -> bool:
    if len(expected_rows) != len(actual_rows):
        return False
    for expected, actual in zip(expected_rows, actual_rows):
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        if expected_keys != actual_keys:
            return False
        for key in expected_keys:
            if not _compare_row_values(expected.get(key), actual.get(key), numeric_tolerance):
                return False
    return True


async def _execute_sql(conn, sql: str, row_limit: int = 5000) -> List[Dict[str, Any]]:
    wrapped_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS benchmark_subquery LIMIT {int(row_limit)}"
    records = await conn.fetch(wrapped_sql)
    rows: List[Dict[str, Any]] = []
    for record in records:
        rows.append(dict(record.items()))
    return rows


async def _compare_query_to_reference(
    conn,
    candidate_sql: str,
    reference_sql: str,
    numeric_tolerance: float = 1e-5,
) -> Dict[str, Any]:
    try:
        candidate_rows = await _execute_sql(conn, candidate_sql)
        reference_rows = await _execute_sql(conn, reference_sql)
    except Exception as exc:
        return {
            "checked": False,
            "match": False,
            "error": str(exc),
        }

    normalized_candidate = _normalized_result_rows(candidate_rows)
    normalized_reference = _normalized_result_rows(reference_rows)
    match = _rows_equivalent(
        normalized_reference,
        normalized_candidate,
        numeric_tolerance=numeric_tolerance,
    )
    return {
        "checked": True,
        "match": match,
        "candidate_row_count": len(normalized_candidate),
        "reference_row_count": len(normalized_reference),
    }


def _contains_discount_factor(sql_normalized: str) -> bool:
    return "discount" in sql_normalized and (
        "(1 - " in sql_normalized
        or "(1- " in sql_normalized
        or "(1-" in sql_normalized
        or "1 - discount" in sql_normalized
        or "1-discount" in sql_normalized
    )


def _contains_count_distinct_order(sql_normalized: str) -> bool:
    return "count(distinct" in sql_normalized and "order_id" in sql_normalized


def _evaluate_contract_semantics(
    query_id: str,
    sql_query: str,
    tables_used: List[str],
    contract: Optional[QueryContract],
    reference_check: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Contract + SQL expert aligned semantic evaluator.

    Status definitions:
      - CORRECT: no hard or soft violations
      - PARTIAL: no hard violations, but soft quality/reasoning gaps
      - INCORRECT: at least one hard semantic violation
    """
    if contract is None:
        return {
            "semantic_status": None,
            "semantic_failure_reasons": ["CONTRACT_MISSING"],
        }

    sql_normalized = _normalize_sql(sql_query)
    table_candidates = set(
        _table_basename(name)
        for name in merge_unique_strings(tables_used, _extract_tables_from_sql(sql_query))
    )
    table_candidates.discard("")
    required_tables = set(_table_basename(name) for name in contract.required_tables)
    required_tables.discard("")

    hard_reasons: List[str] = []
    soft_reasons: List[str] = []

    missing_tables = sorted(required_tables - table_candidates)
    if missing_tables:
        hard_reasons.append("REQUIRED_TABLES_MISSING:" + ",".join(missing_tables))

    metric_expr = (contract.metric_expression_sql or "").lower()
    needs_discount = "discount" in metric_expr or query_id in {"NW2", "NW5", "NW10"}
    if needs_discount and not _contains_discount_factor(sql_normalized):
        hard_reasons.append("MISSING_DISCOUNT_FACTOR")

    needs_distinct_order_count = (
        "count(distinct orders.order_id)" in metric_expr
        or query_id in {"NW3", "NW9"}
    )
    if needs_distinct_order_count and not _contains_count_distinct_order(sql_normalized):
        hard_reasons.append("COUNT_NOT_DISTINCT_ORDER_ID")

    if query_id == "NW4":
        if not ("shipped_date" in sql_normalized and "required_date" in sql_normalized and ">" in sql_normalized):
            hard_reasons.append("LATE_SHIPMENT_LOGIC_MISSING")

    if query_id == "NW8":
        has_avg = "avg(" in sql_normalized
        has_order_total_alias = "order_total" in sql_normalized
        has_multiple_group_by = sql_normalized.count("group by") >= 2
        has_group_by_order = "group by" in sql_normalized and "order_id" in sql_normalized
        if not (has_avg and (has_order_total_alias or (has_group_by_order and has_multiple_group_by))):
            hard_reasons.append("AVG_NOT_OVER_ORDER_TOTAL")

    if query_id == "NW7":
        has_pair_logic = (
            "join public.order_details od2" in sql_normalized
            or "join order_details od2" in sql_normalized
            or ("od1." in sql_normalized and "od2." in sql_normalized)
        )
        if not has_pair_logic:
            hard_reasons.append("CO_OCCURRENCE_PAIRING_MISSING")
        has_supplier_pair_output = (
            ("s1." in sql_normalized and "s2." in sql_normalized)
            or ("supplier_1" in sql_normalized and "supplier_2" in sql_normalized)
        )
        if not has_supplier_pair_output:
            soft_reasons.append("PAIRWISE_SUPPLIER_OUTPUT_MISSING")
        has_frequency = "count(" in sql_normalized and "order by" in sql_normalized
        if not has_frequency:
            soft_reasons.append("FREQUENCY_NOT_OPERATIONALIZED")

    if contract.top_k:
        top_k = int(contract.top_k)
        if f"limit {top_k}" not in sql_normalized and f"top {top_k}" not in sql_normalized:
            soft_reasons.append(f"TOP_K_LIMIT_MISSING:{top_k}")

    if query_id == "NW10":
        has_month_grouping = ("date_trunc('month'" in sql_normalized) or ("extract(month" in sql_normalized)
        if not has_month_grouping:
            hard_reasons.append("MONTHLY_GROUPING_MISSING")

    if reference_check:
        if reference_check.get("checked"):
            if not reference_check.get("match"):
                soft_reasons.append("REFERENCE_RESULT_MISMATCH")
        else:
            soft_reasons.append("REFERENCE_CHECK_UNAVAILABLE")

    if hard_reasons:
        semantic_status = SEMANTIC_INCORRECT
    elif soft_reasons:
        semantic_status = SEMANTIC_PARTIAL
    else:
        semantic_status = SEMANTIC_CORRECT

    return {
        "semantic_status": semantic_status,
        "semantic_failure_reasons": hard_reasons + soft_reasons,
    }


def _evaluate_retrieval_recall(
    retrieved_tables: List[str],
    required_tables: List[str],
) -> Dict[str, Any]:
    retrieved = []
    seen_retrieved = set()
    for table in retrieved_tables:
        name = _table_basename(table)
        if name and name not in seen_retrieved:
            seen_retrieved.add(name)
            retrieved.append(name)

    required = []
    seen_required = set()
    for table in required_tables:
        name = _table_basename(table)
        if name and name not in seen_required:
            seen_required.add(name)
            required.append(name)
    required_set = set(required)

    def recall_at_k(k: int) -> Optional[float]:
        if not required_set:
            return None
        top_k = set(retrieved[:k])
        return round(len(required_set.intersection(top_k)) / len(required_set), 4)

    recall_3 = recall_at_k(3)
    recall_5 = recall_at_k(5)
    top3 = set(retrieved[:3])
    top5 = set(retrieved[:5])

    return {
        "required_tables": required,
        "retrieved_tables": retrieved,
        "recall_at_3": recall_3,
        "recall_at_5": recall_5,
        "all_required_in_top_3": bool(required_set) and required_set.issubset(top3),
        "all_required_in_top_5": bool(required_set) and required_set.issubset(top5),
    }


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
            "retrieved_tables_topk": artifact.get("retrieved_tables_topk", []),
            "retrieval_eval": artifact.get("retrieval_eval"),
            "reference_result_match": artifact.get("reference_result_match"),
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

    # Load per-dataset semantic contracts when available.
    try:
        query_contracts = load_query_contracts_for_dataset(dataset_path)
        print(
            f"🧾 Loaded {len(query_contracts)} semantic contracts from "
            f"{_derive_contract_path_for_dataset(dataset_path)}"
        )
    except FileNotFoundError:
        query_contracts = {}
        print(
            f"⚠️  No semantic contract file found for dataset {dataset_path.name}; "
            "semantic correctness scoring will be disabled for this run."
        )
    except Exception as exc:
        query_contracts = {}
        print(f"⚠️  Failed to load semantic contracts: {exc}")

    # Optional reference SQLs for strong semantic equivalence checks.
    try:
        reference_sql_map = load_reference_sql_for_dataset(dataset_path)
        if reference_sql_map:
            print(
                f"🧠 Loaded {len(reference_sql_map)} reference SQL queries from "
                f"{_derive_reference_sql_path_for_dataset(dataset_path)}"
            )
    except Exception as exc:
        reference_sql_map = {}
        print(f"⚠️  Failed to load reference SQL file: {exc}")

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
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "prompt_versions": {},
        "environment": get_environment_info(),
        "total_queries": len(queries),
        "completed_queries": 0,
        "failed_queries": 0,
    }

    print(f"🚀 Starting run: {run_id}")
    print(f"📁 Results will be saved to: {run_dir}")

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
    observed_models = set()

    # Prepare DB/MCP resources for H1 and H2a deep evaluation.
    postgres_conn = None
    catalog_snapshot = None
    catalog_coverage = None
    ground_truth_snapshot = None
    discovered_snapshot = None
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    mcp_api_key = os.getenv("MCP_API_KEY", "supersecretapikey")

    try:
        postgres_conn = await _open_postgres_connection()
        ground_truth_snapshot = await _fetch_information_schema_snapshot(postgres_conn)
        print("✅ Connected to PostgreSQL for semantic/reference evaluation")
    except Exception as exc:
        postgres_conn = None
        print(f"⚠️  PostgreSQL direct connection unavailable: {exc}")

    cache_file = project_root / "mcp_server" / "cache" / f"catalog_{os.getenv('DB_DIALECT', 'postgres')}.json"
    discovered_snapshot = _load_catalog_snapshot_from_cache(cache_file)
    if discovered_snapshot:
        print(f"✅ Loaded discovered catalog snapshot from cache: {cache_file}")
    else:
        try:
            discovered_snapshot = await _fetch_catalog_snapshot_from_mcp(
                mcp_server_url=mcp_server_url,
                mcp_api_key=mcp_api_key,
            )
            print("✅ Loaded discovered catalog snapshot from MCP tools")
        except Exception as exc:
            print(f"⚠️  Failed to build discovered catalog snapshot: {exc}")
            discovered_snapshot = None

    if discovered_snapshot and ground_truth_snapshot:
        catalog_coverage = _compute_catalog_coverage(discovered_snapshot, ground_truth_snapshot)

    catalog_snapshot = {
        "discovered_catalog": discovered_snapshot,
        "ground_truth_catalog": ground_truth_snapshot,
        "coverage": catalog_coverage,
    }
    if not discovered_snapshot:
        catalog_snapshot["error"] = "discovered_catalog_unavailable"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, query in enumerate(queries, 1):
            query_id = query["id"]
            question = query["question"]
            print(f"\n[{i}/{len(queries)}] {query_id}: {question[:60]}...")

            # Select the QueryContract (if any) for this benchmark query.
            contract_payload: Optional[Dict[str, Any]] = None
            contract = query_contracts.get(query_id)
            if isinstance(contract, QueryContract):
                contract_payload = contract.model_dump(exclude_none=True)

            start_time = time.time()
            try:
                api_key = os.getenv("API_KEY", "supersecretapikey")
                response = await client.post(
                    f"{target_url}/process_query",
                    json={
                        "user_input": question,
                        "api_key": api_key,  # Legacy field; ignored by LangGraph API but preserved for compatibility
                        # Per-query semantic contract is passed through to the
                        # LangGraph service, which forwards it via metadata.
                        "query_contract": contract_payload,
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
                    "retrieval_log": [],
                    "retrieved_tables_topk": [],
                    "retrieval_eval": None,
                    "reference_result_match": None,
                    "reference_result_info": None,
                    "semantic_review_method": None,
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
                artifact["retrieval_log"] = result.get("retrieval_log") or []

                retrieved_tables = result.get("retrieved_tables_topk") or []
                if not retrieved_tables and artifact["tables_used"]:
                    retrieved_tables = artifact["tables_used"][:5]
                artifact["retrieved_tables_topk"] = [
                    _normalize_table_name(name) for name in retrieved_tables if _normalize_table_name(name)
                ]

                # Phase 1 instrumentation: persist LLM/node usage and loop diagnostics per query
                artifact["llm_usage"] = result.get("llm_usage") or {
                    "total": result.get("total_llm_calls"),
                    "intent": 0,
                    "discovery": 0,
                    "join": 0,
                    "repair": 0,
                    "answer": 0,
                }
                artifact["node_entry_counts"] = result.get("node_entry_counts") or {}
                artifact["loop_events"] = result.get("loop_events") or {}
                artifact["total_llm_calls"] = result.get("total_llm_calls") or artifact["llm_usage"].get("total")
                artifact["total_graph_cycles"] = result.get("total_graph_cycles")

                model_name = first_non_empty_str(result.get("model_name"), manifest.get("model"))
                if model_name:
                    observed_models.add(model_name)
                    artifact["model"] = model_name

                reference_check = None
                if (
                    postgres_conn
                    and sql_query
                    and query_id in reference_sql_map
                ):
                    reference_check = await _compare_query_to_reference(
                        postgres_conn,
                        candidate_sql=sql_query,
                        reference_sql=reference_sql_map[query_id],
                    )
                    artifact["reference_result_match"] = reference_check.get("match")
                    artifact["reference_result_info"] = reference_check

                if isinstance(contract, QueryContract):
                    artifact["contract_id"] = contract.query_id
                    retrieval_eval = _evaluate_retrieval_recall(
                        artifact.get("retrieved_tables_topk", []),
                        contract.required_tables,
                    )
                    artifact["retrieval_eval"] = retrieval_eval

                    if sql_query:
                        semantic_eval = _evaluate_contract_semantics(
                            query_id=query_id,
                            sql_query=sql_query or "",
                            tables_used=artifact.get("tables_used", []),
                            contract=contract,
                            reference_check=reference_check,
                        )
                        artifact["semantic_status"] = semantic_eval["semantic_status"]
                        artifact["semantic_failure_reasons"] = semantic_eval["semantic_failure_reasons"]
                        artifact["semantic_review_method"] = "contract_rules_plus_reference_sql"
                    else:
                        artifact["semantic_status"] = None
                        artifact["semantic_failure_reasons"] = ["EVALUATION_SKIPPED_NO_SQL"]
                        artifact["semantic_review_method"] = "skipped_no_sql"

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
                    "retrieval_log": [],
                    "retrieved_tables_topk": [],
                    "retrieval_eval": None,
                    "reference_result_match": None,
                    "reference_result_info": None,
                    "semantic_review_method": None,
                }
                results[query_id] = artifact
                failed += 1
                print(f"   ❌ Failed: {e}")

                if eval_client:
                    await eval_client.save_query_artifact(run_id, query_id, artifact)

    if postgres_conn:
        await postgres_conn.close()

    if observed_models:
        if len(observed_models) == 1:
            manifest["model"] = list(observed_models)[0]
        else:
            manifest["model"] = ", ".join(sorted(observed_models))

    manifest["completed_queries"] = completed
    manifest["failed_queries"] = failed

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

    # H1/H2a aggregate evidence
    semantic_labeled = [
        artifact
        for artifact in results.values()
        if artifact.get("contract_id")
        and artifact.get("semantic_status") in {SEMANTIC_CORRECT, SEMANTIC_PARTIAL, SEMANTIC_INCORRECT}
    ]
    strict_correct = sum(1 for artifact in semantic_labeled if artifact.get("semantic_status") == SEMANTIC_CORRECT)
    acceptable = sum(
        1 for artifact in semantic_labeled
        if artifact.get("semantic_status") in {SEMANTIC_CORRECT, SEMANTIC_PARTIAL}
    )
    semantic_total = len(semantic_labeled)

    retrieval_evals = [artifact.get("retrieval_eval") for artifact in semantic_labeled if artifact.get("retrieval_eval")]
    recall3_values = [entry.get("recall_at_3") for entry in retrieval_evals if isinstance(entry.get("recall_at_3"), (int, float))]
    recall5_values = [entry.get("recall_at_5") for entry in retrieval_evals if isinstance(entry.get("recall_at_5"), (int, float))]
    full_top5_hits = sum(1 for entry in retrieval_evals if entry.get("all_required_in_top_5"))

    reference_checks = [artifact.get("reference_result_info") for artifact in results.values() if artifact.get("reference_result_info")]
    reference_checked = [entry for entry in reference_checks if isinstance(entry, dict) and entry.get("checked")]
    reference_matches = sum(1 for entry in reference_checked if entry.get("match"))

    avg_total_calls = 0.0
    call_values = [
        row.get("total_calls") for row in calls_summary
        if isinstance(row.get("total_calls"), (int, float))
    ]
    if call_values:
        avg_total_calls = round(sum(call_values) / len(call_values), 3)

    h1_h2a_evaluation = {
        "run_id": run_id,
        "dataset": str(dataset_path),
        "h1": {
            "catalog_coverage": catalog_coverage,
            "retrieval_quality": {
                "queries_with_contracts": semantic_total,
                "avg_recall_at_3": round(sum(recall3_values) / len(recall3_values), 4) if recall3_values else None,
                "avg_recall_at_5": round(sum(recall5_values) / len(recall5_values), 4) if recall5_values else None,
                "all_required_in_top_5_rate_pct": round((full_top5_hits / semantic_total) * 100.0, 2) if semantic_total else None,
            },
        },
        "h2a": {
            "semantic_counts": {
                "CORRECT": sum(1 for artifact in semantic_labeled if artifact.get("semantic_status") == SEMANTIC_CORRECT),
                "PARTIAL": sum(1 for artifact in semantic_labeled if artifact.get("semantic_status") == SEMANTIC_PARTIAL),
                "INCORRECT": sum(1 for artifact in semantic_labeled if artifact.get("semantic_status") == SEMANTIC_INCORRECT),
            },
            "strict_accuracy_pct": round((strict_correct / semantic_total) * 100.0, 2) if semantic_total else None,
            "acceptable_accuracy_pct": round((acceptable / semantic_total) * 100.0, 2) if semantic_total else None,
            "reference_equivalence": {
                "checked_queries": len(reference_checked),
                "matched_queries": reference_matches,
                "match_rate_pct": round((reference_matches / len(reference_checked)) * 100.0, 2) if reference_checked else None,
            },
        },
        "instrumentation": {
            "avg_total_llm_calls": avg_total_calls,
            "queries_with_missing_total_calls": [
                row.get("query_id")
                for row in calls_summary
                if row.get("total_calls") is None
            ],
        },
    }
    h1_h2a_file = run_dir / "h1_h2a_evaluation.json"
    h1_h2a_file.write_text(json.dumps(h1_h2a_evaluation, indent=2))

    if catalog_snapshot:
        catalog_snapshot_file = run_dir / "catalog_snapshot.json"
        catalog_snapshot_file.write_text(json.dumps(catalog_snapshot, indent=2))

    summary = {
        "run_id": run_id,
        "total_queries": len(queries),
        "successful": completed,
        "failed": failed,
        "success_rate": f"{(completed/len(queries)*100):.1f}%",
        "semantic_strict_accuracy_pct": h1_h2a_evaluation["h2a"]["strict_accuracy_pct"],
        "semantic_acceptable_accuracy_pct": h1_h2a_evaluation["h2a"]["acceptable_accuracy_pct"],
        "catalog_table_coverage_pct": (catalog_coverage or {}).get("table_coverage_pct"),
        "catalog_column_coverage_pct": (catalog_coverage or {}).get("column_coverage_pct"),
        "retrieval_avg_recall_at_5": h1_h2a_evaluation["h1"]["retrieval_quality"]["avg_recall_at_5"],
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
    print(f"  🧪 h1_h2a_evaluation.json - H1/H2a deep evaluation")
    if catalog_snapshot:
        print(f"  🗂️ catalog_snapshot.json - Catalog completeness evidence")
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
