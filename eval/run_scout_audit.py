"""
Scout Catalog Audit CLI

Runs a production-facing Scout catalog audit via MCP without changing architecture.
It reuses the same catalog coverage computation used in eval.run_benchmark.

Outputs are written to eval/runs/<timestamp>_<run-name>/ and include:
- scout_manifest.json
- scout_catalog_discovered.json
- scout_ground_truth.json
- scout_catalog_coverage.json
- scout_catalog_quality.json
- scout_catalog_diagnostics.json
- scout_health.json
- scout_summary.json
- scout_report.md
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.run_benchmark import (  # Reuse exact benchmark coverage logic.
    _compute_catalog_coverage,
    _extract_payload_from_mcp_result,
    _load_catalog_snapshot_from_cache,
    _normalize_table_name,
)


PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _as_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _safe_pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _maybe_parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None
    return None


def _age_hours(value: Any) -> Optional[float]:
    parsed = _maybe_parse_datetime(value)
    if parsed is None:
        return None
    return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0, 3)


def _to_table_records(tables_raw: Any) -> List[Dict[str, Any]]:
    if isinstance(tables_raw, dict):
        return [t for t in tables_raw.values() if isinstance(t, dict)]
    if isinstance(tables_raw, list):
        return [t for t in tables_raw if isinstance(t, dict)]
    return []


def _normalize_column(col: Any, fallback_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if isinstance(col, dict):
        name = _first_non_empty(col.get("name"), col.get("column_name"), fallback_name)
        if not name:
            return None
        return {
            "name": name,
            "type": col.get("type", col.get("data_type")),
            "nullable": _as_bool(col.get("nullable")),
            "is_primary_key": _as_bool(col.get("is_primary_key")) is True,
            "is_foreign_key": _as_bool(col.get("is_foreign_key")),
        }
    if isinstance(col, str):
        name = col.strip()
        if not name:
            return None
        return {
            "name": name,
            "type": None,
            "nullable": None,
            "is_primary_key": False,
            "is_foreign_key": None,
        }
    if fallback_name:
        return {
            "name": fallback_name,
            "type": None,
            "nullable": None,
            "is_primary_key": False,
            "is_foreign_key": None,
        }
    return None


def _normalize_discovered_snapshot_from_scout(payload: Dict[str, Any]) -> Dict[str, Any]:
    catalog = payload.get("catalog") if isinstance(payload.get("catalog"), dict) else {}
    tables = {}

    for table in _to_table_records(catalog.get("tables")):
        schema = _first_non_empty(table.get("schema"), "dbo")
        name = _first_non_empty(table.get("name"))
        full_name = _normalize_table_name(
            _first_non_empty(table.get("full_name"), f"{schema}.{name}" if name else "")
        )
        if not full_name or not name:
            continue

        columns: List[Dict[str, Any]] = []
        for col in table.get("columns") or []:
            normalized = _normalize_column(col)
            if normalized:
                columns.append(normalized)

        fk_columns = []
        for col in columns:
            if col.get("is_foreign_key") is True:
                fk_columns.append({"column": col["name"]})

        tables[full_name] = {
            "schema": schema,
            "name": name,
            "type": table.get("type"),
            "estimated_rows": _as_int(table.get("estimated_rows")),
            "fk_count": _as_int(table.get("fk_count")),
            "columns": columns,
            "primary_keys": sorted(
                {
                    col["name"]
                    for col in columns
                    if col.get("is_primary_key") is True
                }
            ),
            "foreign_keys": fk_columns,
        }

    return {
        "source": "scout_catalog_get",
        "timestamp": _utc_now(),
        "scout_catalog_metadata": payload.get("metadata"),
        "tables": tables,
    }


def _normalize_discovered_snapshot_from_scout_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    # File export shape: {"version": "...", "built_at": "...", "tables": [...], ...}
    if isinstance(payload.get("tables"), (list, dict)):
        wrapped = {
            "catalog": {"tables": payload.get("tables")},
            "metadata": {
                "built_at": payload.get("built_at"),
                "version": payload.get("version"),
                "source": "scout_catalog_file",
            },
        }
        snapshot = _normalize_discovered_snapshot_from_scout(wrapped)
        snapshot["source"] = "scout_catalog_file"
        snapshot["scout_file_metadata"] = {
            "built_at": payload.get("built_at"),
            "version": payload.get("version"),
        }
        return snapshot

    # Fallback: maybe this is already a MCP-style payload.
    snapshot = _normalize_discovered_snapshot_from_scout(payload)
    snapshot["source"] = "scout_catalog_file"
    return snapshot


def _normalize_discovered_snapshot_from_list_tables(
    table_rows: List[Dict[str, Any]],
    column_index: Dict[str, Any],
) -> Dict[str, Any]:
    tables: Dict[str, Dict[str, Any]] = {}

    for row in table_rows:
        full_name = _normalize_table_name(row.get("full_name", ""))
        if not full_name:
            continue
        schema = _first_non_empty(row.get("schema"), full_name.split(".")[0] if "." in full_name else "dbo")
        name = _first_non_empty(row.get("name"), full_name.split(".")[-1])
        column_names = column_index.get(full_name) or column_index.get(name) or []
        columns: List[Dict[str, Any]] = []
        for col_name in column_names:
            normalized = _normalize_column(col_name)
            if normalized:
                columns.append(normalized)

        tables[full_name] = {
            "schema": schema,
            "name": name,
            "type": row.get("type"),
            "estimated_rows": _as_int(row.get("estimated_rows")),
            "fk_count": None,
            "columns": columns,
            "primary_keys": [],
            "foreign_keys": [],
        }

    return {
        "source": "list_tables_plus_column_index",
        "timestamp": _utc_now(),
        "tables": tables,
    }


def _compute_catalog_quality(discovered_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    tables = list((discovered_snapshot.get("tables") or {}).values())
    total_tables = len(tables)
    if total_tables == 0:
        return {
            "total_tables": 0,
            "tables_with_columns_pct": None,
            "tables_with_row_estimates_pct": None,
            "tables_with_fk_metadata_pct": None,
            "tables_missing_columns": [],
            "tables_missing_row_estimates": [],
            "tables_missing_fk_metadata": [],
        }

    def has_columns(table: Dict[str, Any]) -> bool:
        return bool(table.get("columns"))

    def has_row_estimate(table: Dict[str, Any]) -> bool:
        return table.get("estimated_rows") is not None

    def has_fk_metadata(table: Dict[str, Any]) -> bool:
        fk_count = table.get("fk_count")
        if fk_count is not None:
            return True
        for col in table.get("columns") or []:
            if isinstance(col, dict) and col.get("is_foreign_key") is not None:
                return True
        return False

    with_columns = [t for t in tables if has_columns(t)]
    with_row_estimates = [t for t in tables if has_row_estimate(t)]
    with_fk_metadata = [t for t in tables if has_fk_metadata(t)]

    def full_name(table: Dict[str, Any]) -> str:
        return _normalize_table_name(_first_non_empty(table.get("full_name"), f"{table.get('schema')}.{table.get('name')}"))

    missing_columns = sorted(
        full_name(t) for t in tables if not has_columns(t)
    )
    missing_row_estimates = sorted(
        full_name(t) for t in tables if not has_row_estimate(t)
    )
    missing_fk_metadata = sorted(
        full_name(t) for t in tables if not has_fk_metadata(t)
    )

    return {
        "total_tables": total_tables,
        "tables_with_columns_pct": _safe_pct(len(with_columns), total_tables),
        "tables_with_row_estimates_pct": _safe_pct(len(with_row_estimates), total_tables),
        "tables_with_fk_metadata_pct": _safe_pct(len(with_fk_metadata), total_tables),
        "tables_missing_columns": missing_columns[:25],
        "tables_missing_row_estimates": missing_row_estimates[:25],
        "tables_missing_fk_metadata": missing_fk_metadata[:25],
    }


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


async def _query_rows(
    client: httpx.AsyncClient,
    mcp_server_url: str,
    mcp_api_key: str,
    sql: str,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    payload = await _mcp_tool_call(
        client,
        mcp_server_url,
        mcp_api_key,
        "run_query",
        {"sql": sql, "limit": int(limit)},
    )
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "run_query failed")
    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


async def _fetch_discovered_snapshot(
    client: httpx.AsyncClient,
    mcp_server_url: str,
    mcp_api_key: str,
    max_tables: Optional[int],
) -> Dict[str, Any]:
    scout_payload = await _mcp_tool_call(
        client,
        mcp_server_url,
        mcp_api_key,
        "scout_catalog_get",
        {
            "include_tables": True,
            "include_views": False,
            "include_relationships": False,
            **({"max_tables": int(max_tables)} if isinstance(max_tables, int) and max_tables > 0 else {}),
        },
    )

    if scout_payload.get("ok") and isinstance(scout_payload.get("catalog"), dict):
        normalized = _normalize_discovered_snapshot_from_scout(scout_payload)
        if normalized.get("tables"):
            return normalized

    # Fallback path if Scout catalog endpoint is unavailable.
    table_rows: List[Dict[str, Any]] = []
    page = 1
    while True:
        page_payload = await _mcp_tool_call(
            client,
            mcp_server_url,
            mcp_api_key,
            "list_tables",
            {"page": page, "page_size": 100, "include_empty": True, "min_rows": 0},
        )
        if not page_payload.get("ok"):
            raise RuntimeError(page_payload.get("error") or "list_tables failed")
        data = page_payload.get("data") or {}
        page_rows = data.get("tables") or []
        table_rows.extend([row for row in page_rows if isinstance(row, dict)])
        page_info = page_payload.get("page_info") or {}
        if not page_info.get("has_next"):
            break
        page += 1

    table_names = sorted(
        {
            _normalize_table_name(row.get("full_name", ""))
            for row in table_rows
            if _normalize_table_name(row.get("full_name", ""))
        }
    )
    column_index: Dict[str, Any] = {}
    batch_size = 50
    for start in range(0, len(table_names), batch_size):
        batch = table_names[start:start + batch_size]
        column_payload = await _mcp_tool_call(
            client,
            mcp_server_url,
            mcp_api_key,
            "get_column_index",
            {"table_names": batch},
        )
        if column_payload.get("ok"):
            data = column_payload.get("data") or {}
            if isinstance(data, dict):
                for key, val in data.items():
                    column_index[_normalize_table_name(key)] = val

    return _normalize_discovered_snapshot_from_list_tables(table_rows, column_index)


async def _fetch_ground_truth_snapshot(
    client: httpx.AsyncClient,
    mcp_server_url: str,
    mcp_api_key: str,
    fk_batch_size: int = 500,
) -> Dict[str, Any]:
    schema_payload = await _mcp_tool_call(
        client,
        mcp_server_url,
        mcp_api_key,
        "get_schema",
        {},
    )

    if not schema_payload.get("ok"):
        raise RuntimeError(schema_payload.get("error") or "get_schema failed")

    raw_tables = schema_payload.get("tables")
    if not isinstance(raw_tables, list):
        raw_tables = []

    tables: Dict[str, Dict[str, Any]] = {}
    for row in raw_tables:
        if not isinstance(row, dict):
            continue
        schema = _first_non_empty(row.get("schema"), row.get("table_schema"), "dbo")
        name = _first_non_empty(row.get("name"), row.get("table_name"))
        full_name = _normalize_table_name(_first_non_empty(row.get("full_name"), f"{schema}.{name}" if name else ""))
        if not full_name or not name:
            continue

        columns: List[Dict[str, Any]] = []
        for col in row.get("columns") or []:
            normalized = _normalize_column(col)
            if normalized:
                # get_schema doesn't return FK flags; set unknown until augmented.
                normalized["is_foreign_key"] = None
                columns.append(normalized)

        tables[full_name] = {
            "schema": schema,
            "name": name,
            "type": row.get("type"),
            "estimated_rows": None,
            "columns": columns,
            "primary_keys": [],
            "foreign_keys": [],
        }

    fk_rows: List[Dict[str, Any]] = []
    offset = 0
    max_rows = 100000
    while offset < max_rows:
        sql = f"""
        SELECT
          s.name AS table_schema,
          t.name AS table_name,
          c.name AS column_name
        FROM sys.foreign_key_columns fkc
        INNER JOIN sys.tables t ON fkc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.columns c
          ON c.object_id = t.object_id
         AND c.column_id = fkc.parent_column_id
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY s.name, t.name, c.name
        OFFSET {offset} ROWS FETCH NEXT {fk_batch_size} ROWS ONLY
        """
        batch = await _query_rows(
            client,
            mcp_server_url,
            mcp_api_key,
            sql=sql,
            limit=fk_batch_size,
        )
        if not batch:
            break
        fk_rows.extend(batch)
        if len(batch) < fk_batch_size:
            break
        offset += fk_batch_size

    for fk in fk_rows:
        schema = _first_non_empty(fk.get("table_schema"), fk.get("TABLE_SCHEMA"), "dbo")
        name = _first_non_empty(fk.get("table_name"), fk.get("TABLE_NAME"))
        column_name = _first_non_empty(fk.get("column_name"), fk.get("COLUMN_NAME"))
        full_name = _normalize_table_name(f"{schema}.{name}")
        if not full_name or not column_name:
            continue
        table = tables.get(full_name)
        if not table:
            continue

        table["foreign_keys"].append({"column": column_name})

        matched = False
        for col in table.get("columns") or []:
            if str(col.get("name", "")).lower() == column_name.lower():
                col["is_foreign_key"] = True
                matched = True
                break
        if not matched:
            table["columns"].append(
                {
                    "name": column_name,
                    "type": None,
                    "nullable": None,
                    "is_primary_key": False,
                    "is_foreign_key": True,
                }
            )

    # Fill unknown FK flags as False for non-FK columns.
    for table in tables.values():
        seen = set()
        deduped_fks = []
        for fk in table.get("foreign_keys") or []:
            key = str(fk.get("column", "")).lower()
            if key and key not in seen:
                seen.add(key)
                deduped_fks.append({"column": fk.get("column")})
        table["foreign_keys"] = deduped_fks

        for col in table.get("columns") or []:
            if col.get("is_foreign_key") is None:
                col["is_foreign_key"] = False

    return {
        "source": "get_schema_plus_sys_foreign_key_columns",
        "timestamp": _utc_now(),
        "tables": tables,
    }


def _load_json_file(path: Path) -> Dict[str, Any]:
    with open(path) as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_discovered_snapshot_from_file(path: Path) -> Dict[str, Any]:
    payload = _load_json_file(path)
    snapshot = _normalize_discovered_snapshot_from_scout_file(payload)
    snapshot["file_path"] = str(path)
    return snapshot


def _load_ground_truth_snapshot_from_file(path: Path) -> Dict[str, Any]:
    snapshot = _load_catalog_snapshot_from_cache(path)
    if not snapshot:
        raise ValueError(f"Failed to parse ground-truth catalog file: {path}")
    snapshot["source"] = "catalog_cache_file"
    snapshot["file_path"] = str(path)
    return snapshot


def _render_report(
    run_id: str,
    summary: Dict[str, Any],
    diagnostics: Optional[Dict[str, Any]],
) -> str:
    coverage = summary.get("catalog_coverage") or {}
    quality = summary.get("catalog_quality") or {}
    freshness = summary.get("freshness") or {}
    lines = [
        f"# Scout Production Audit ({run_id})",
        "",
        "## H1 Catalog Indexing Completeness",
        f"- Table coverage: {coverage.get('table_coverage_pct')}% ({coverage.get('discovered_tables')}/{coverage.get('ground_truth_tables')})",
        f"- Column coverage: {coverage.get('column_coverage_pct')}% ({coverage.get('discovered_columns')}/{coverage.get('ground_truth_columns')})",
        f"- FK coverage: {coverage.get('fk_coverage_pct')}% ({coverage.get('discovered_fk_columns')}/{coverage.get('ground_truth_fk_columns')})",
        "",
        "## Catalog Quality Diagnostics",
        f"- Tables with columns present: {quality.get('tables_with_columns_pct')}%",
        f"- Tables with row estimates: {quality.get('tables_with_row_estimates_pct')}%",
        f"- Tables with FK metadata: {quality.get('tables_with_fk_metadata_pct')}%",
        "",
        "## Freshness",
        f"- Catalog valid: {freshness.get('catalog_valid')}",
        f"- Catalog age (hours): {freshness.get('catalog_age_hours')}",
        f"- Catalog TTL (hours): {freshness.get('catalog_ttl_hours')}",
        "",
        "## Caveats",
        "- Retrieval usefulness on production requires a production-grounded query contract set.",
        "- Existing cockpit contracts are Northwind-oriented and should not be used as L&D truth labels.",
    ]

    if diagnostics:
        issues = diagnostics.get("issues") or []
        recommendations = diagnostics.get("recommendations") or []
        lines.extend(["", "## Diagnostics Issues"])
        if issues:
            lines.extend([f"- {issue}" for issue in issues])
        else:
            lines.append("- None reported by scout_catalog_diagnostics.")
        lines.extend(["", "## Diagnostics Recommendations"])
        if recommendations:
            lines.extend([f"- {item}" for item in recommendations])
        else:
            lines.append("- None reported.")

    return "\n".join(lines) + "\n"


async def run_scout_audit(
    run_name: str,
    mcp_server_url: str,
    mcp_api_key: str,
    output_root: Path,
    fk_batch_size: int = 500,
    max_tables: Optional[int] = None,
    refresh_scout: bool = False,
    wait_refresh: bool = False,
) -> Path:
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_name}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "run_name": run_name,
        "timestamp": _utc_now(),
        "mcp_server_url": mcp_server_url,
        "db_dialect_env": os.getenv("DB_DIALECT"),
        "mcp_api_key_configured": bool(mcp_api_key),
        "fk_batch_size": fk_batch_size,
        "max_tables": max_tables,
        "refresh_scout": refresh_scout,
        "wait_refresh": wait_refresh,
    }

    health_payload: Optional[Dict[str, Any]] = None
    diagnostics_payload: Optional[Dict[str, Any]] = None

    async with httpx.AsyncClient(timeout=180.0) as client:
        headers = {"X-API-Key": mcp_api_key} if mcp_api_key else {}
        health_resp = await client.get(f"{mcp_server_url.rstrip('/')}/health", headers=headers)
        health_resp.raise_for_status()
        health_payload = health_resp.json()

        if refresh_scout:
            await _mcp_tool_call(
                client,
                mcp_server_url,
                mcp_api_key,
                "scout_catalog_refresh",
                {"wait_for_completion": bool(wait_refresh)},
            )

        try:
            diagnostics_payload = await _mcp_tool_call(
                client,
                mcp_server_url,
                mcp_api_key,
                "scout_catalog_diagnostics",
                {},
            )
        except Exception:
            diagnostics_payload = None

        discovered_snapshot = await _fetch_discovered_snapshot(
            client=client,
            mcp_server_url=mcp_server_url,
            mcp_api_key=mcp_api_key,
            max_tables=max_tables,
        )
        ground_truth_snapshot = await _fetch_ground_truth_snapshot(
            client=client,
            mcp_server_url=mcp_server_url,
            mcp_api_key=mcp_api_key,
            fk_batch_size=fk_batch_size,
        )

    catalog_coverage = _compute_catalog_coverage(discovered_snapshot, ground_truth_snapshot)
    catalog_quality = _compute_catalog_quality(discovered_snapshot)

    stats = {}
    if isinstance(diagnostics_payload, dict):
        stats = (diagnostics_payload.get("stats") or {}) if diagnostics_payload.get("ok") else {}

    freshness = {
        "catalog_valid": stats.get("valid"),
        "catalog_age_hours": stats.get("age_hours"),
        "catalog_ttl_hours": stats.get("ttl_hours"),
        "catalog_timestamp": stats.get("timestamp"),
    }

    summary = {
        "run_id": run_id,
        "timestamp": _utc_now(),
        "mcp_server_url": mcp_server_url,
        "db_dialect_env": os.getenv("DB_DIALECT"),
        "catalog_coverage": catalog_coverage,
        "catalog_quality": catalog_quality,
        "freshness": freshness,
        "discovered_source": discovered_snapshot.get("source"),
        "ground_truth_source": ground_truth_snapshot.get("source"),
        "notes": [
            "Coverage logic is shared with eval.run_benchmark (_compute_catalog_coverage).",
            "Ground truth is sourced from live MCP-backed schema plus SQL Server FK metadata query.",
        ],
    }

    (run_dir / "scout_manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "scout_health.json").write_text(json.dumps(health_payload, indent=2))
    if diagnostics_payload is not None:
        (run_dir / "scout_catalog_diagnostics.json").write_text(json.dumps(diagnostics_payload, indent=2))
    (run_dir / "scout_catalog_discovered.json").write_text(json.dumps(discovered_snapshot, indent=2))
    (run_dir / "scout_ground_truth.json").write_text(json.dumps(ground_truth_snapshot, indent=2))
    (run_dir / "scout_catalog_coverage.json").write_text(json.dumps(catalog_coverage, indent=2))
    (run_dir / "scout_catalog_quality.json").write_text(json.dumps(catalog_quality, indent=2))
    (run_dir / "scout_summary.json").write_text(json.dumps(summary, indent=2))

    report_md = _render_report(
        run_id=run_id,
        summary=summary,
        diagnostics=diagnostics_payload if isinstance(diagnostics_payload, dict) else None,
    )
    (run_dir / "scout_report.md").write_text(report_md)

    print("=" * 64)
    print("Scout Production Audit Complete")
    print("=" * 64)
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print(f"Table coverage: {catalog_coverage.get('table_coverage_pct')}%")
    print(f"Column coverage: {catalog_coverage.get('column_coverage_pct')}%")
    print(f"FK coverage: {catalog_coverage.get('fk_coverage_pct')}%")
    print("=" * 64)
    return run_dir


def run_scout_audit_from_files(
    run_name: str,
    output_root: Path,
    discovered_catalog_file: Path,
    ground_truth_catalog_file: Path,
    scout_index_file: Optional[Path] = None,
) -> Path:
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_name}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    discovered_snapshot = _load_discovered_snapshot_from_file(discovered_catalog_file)
    ground_truth_snapshot = _load_ground_truth_snapshot_from_file(ground_truth_catalog_file)

    discovered_raw = _load_json_file(discovered_catalog_file)
    ground_truth_raw = _load_json_file(ground_truth_catalog_file)
    index_payload: Optional[Dict[str, Any]] = None
    if scout_index_file and scout_index_file.exists():
        index_payload = _load_json_file(scout_index_file)

    catalog_coverage = _compute_catalog_coverage(discovered_snapshot, ground_truth_snapshot)
    catalog_quality = _compute_catalog_quality(discovered_snapshot)

    gt_meta = ground_truth_raw.get("metadata") if isinstance(ground_truth_raw.get("metadata"), dict) else {}
    scout_built_at = discovered_raw.get("built_at")
    catalog_timestamp = gt_meta.get("timestamp")
    ttl_seconds = gt_meta.get("ttl")
    ttl_hours = None
    if isinstance(ttl_seconds, (int, float)):
        ttl_hours = round(float(ttl_seconds) / 3600.0, 4)

    freshness = {
        "catalog_valid": None if ttl_hours is None else (_age_hours(catalog_timestamp) is not None and _age_hours(catalog_timestamp) <= ttl_hours),
        "catalog_age_hours": _age_hours(catalog_timestamp),
        "catalog_ttl_hours": ttl_hours,
        "catalog_timestamp": catalog_timestamp,
        "scout_built_at": scout_built_at,
        "scout_built_age_hours": _age_hours(scout_built_at),
    }

    health_payload = {
        "status": "offline_file_audit",
        "timestamp": _utc_now(),
        "components": {
            "source": "exported_files",
            "discovered_catalog_file": str(discovered_catalog_file),
            "ground_truth_catalog_file": str(ground_truth_catalog_file),
            "scout_index_file": str(scout_index_file) if scout_index_file else None,
        },
    }

    diagnostics_payload = {
        "ok": True,
        "source": "offline_file_audit",
        "overview": {
            "tables": len((discovered_snapshot.get("tables") or {})),
            "index_available": index_payload is not None,
        },
        "index_keys": sorted(list(index_payload.keys())) if isinstance(index_payload, dict) else [],
    }

    summary = {
        "run_id": run_id,
        "timestamp": _utc_now(),
        "mode": "offline_export_audit",
        "catalog_coverage": catalog_coverage,
        "catalog_quality": catalog_quality,
        "freshness": freshness,
        "discovered_source": discovered_snapshot.get("source"),
        "ground_truth_source": ground_truth_snapshot.get("source"),
        "notes": [
            "Offline audit computed from exported remote files (no live MCP call).",
            "Coverage logic is shared with eval.run_benchmark (_compute_catalog_coverage).",
        ],
    }

    manifest = {
        "run_id": run_id,
        "run_name": run_name,
        "timestamp": _utc_now(),
        "mode": "offline_export_audit",
        "discovered_catalog_file": str(discovered_catalog_file),
        "ground_truth_catalog_file": str(ground_truth_catalog_file),
        "scout_index_file": str(scout_index_file) if scout_index_file else None,
    }

    (run_dir / "scout_manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "scout_health.json").write_text(json.dumps(health_payload, indent=2))
    (run_dir / "scout_catalog_diagnostics.json").write_text(json.dumps(diagnostics_payload, indent=2))
    (run_dir / "scout_catalog_discovered.json").write_text(json.dumps(discovered_snapshot, indent=2))
    (run_dir / "scout_ground_truth.json").write_text(json.dumps(ground_truth_snapshot, indent=2))
    (run_dir / "scout_catalog_coverage.json").write_text(json.dumps(catalog_coverage, indent=2))
    (run_dir / "scout_catalog_quality.json").write_text(json.dumps(catalog_quality, indent=2))
    (run_dir / "scout_summary.json").write_text(json.dumps(summary, indent=2))
    if index_payload is not None:
        (run_dir / "scout_index_snapshot.json").write_text(json.dumps(index_payload, indent=2))

    report_md = _render_report(
        run_id=run_id,
        summary=summary,
        diagnostics=diagnostics_payload,
    )
    (run_dir / "scout_report.md").write_text(report_md)

    print("=" * 64)
    print("Scout Offline Export Audit Complete")
    print("=" * 64)
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print(f"Table coverage: {catalog_coverage.get('table_coverage_pct')}%")
    print(f"Column coverage: {catalog_coverage.get('column_coverage_pct')}%")
    print(f"FK coverage: {catalog_coverage.get('fk_coverage_pct')}%")
    print("=" * 64)
    return run_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Scout catalog analytics against production MCP/MSSQL."
    )
    parser.add_argument(
        "--run-name",
        default="scout_prod_audit",
        help="Run name suffix for eval/runs output directory.",
    )
    parser.add_argument(
        "--mcp-server-url",
        default=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
        help="MCP server base URL.",
    )
    parser.add_argument(
        "--mcp-api-key",
        default=os.getenv("MCP_API_KEY", "supersecretapikey"),
        help="MCP API key.",
    )
    parser.add_argument(
        "--output-root",
        default=str(PROJECT_ROOT / "eval" / "runs"),
        help="Directory where run artifacts are created.",
    )
    parser.add_argument(
        "--fk-batch-size",
        type=int,
        default=500,
        help="Batch size for paginated FK metadata query.",
    )
    parser.add_argument(
        "--max-tables",
        type=int,
        default=None,
        help="Optional cap for discovered catalog table extraction.",
    )
    parser.add_argument(
        "--refresh-scout",
        action="store_true",
        help="Trigger scout_catalog_refresh before auditing.",
    )
    parser.add_argument(
        "--wait-refresh",
        action="store_true",
        help="Wait for scout_catalog_refresh completion (only with --refresh-scout).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and exit without calling MCP.",
    )
    parser.add_argument(
        "--discovered-catalog-file",
        default=None,
        help="Offline mode: path to exported Scout discovered catalog JSON (e.g., scout_catalog.json).",
    )
    parser.add_argument(
        "--ground-truth-catalog-file",
        default=None,
        help="Offline mode: path to exported ground-truth catalog cache JSON (e.g., catalog_mssql.json).",
    )
    parser.add_argument(
        "--scout-index-file",
        default=None,
        help="Offline mode: optional path to scout_index.json for traceability.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.dry_run:
        print("Scout audit dry-run configuration:")
        print(f"  MCP_SERVER_URL={args.mcp_server_url}")
        print(f"  DB_DIALECT={os.getenv('DB_DIALECT')}")
        print(f"  OUTPUT_ROOT={args.output_root}")
        print(f"  DISCOVERED_CATALOG_FILE={args.discovered_catalog_file}")
        print(f"  GROUND_TRUTH_CATALOG_FILE={args.ground_truth_catalog_file}")
        return

    output_root = Path(args.output_root)
    if bool(args.discovered_catalog_file) != bool(args.ground_truth_catalog_file):
        print(
            "Offline mode requires both --discovered-catalog-file and --ground-truth-catalog-file."
        )
        raise SystemExit(1)

    if args.discovered_catalog_file and args.ground_truth_catalog_file:
        discovered_file = Path(args.discovered_catalog_file)
        ground_truth_file = Path(args.ground_truth_catalog_file)
        index_file = Path(args.scout_index_file) if args.scout_index_file else None
        if not discovered_file.exists():
            print(f"Discovered catalog file not found: {discovered_file}")
            raise SystemExit(1)
        if not ground_truth_file.exists():
            print(f"Ground-truth catalog file not found: {ground_truth_file}")
            raise SystemExit(1)
        if index_file and not index_file.exists():
            print(f"Scout index file not found: {index_file}")
            raise SystemExit(1)

        run_scout_audit_from_files(
            run_name=args.run_name,
            output_root=output_root,
            discovered_catalog_file=discovered_file,
            ground_truth_catalog_file=ground_truth_file,
            scout_index_file=index_file,
        )
        return

    try:
        asyncio.run(
            run_scout_audit(
                run_name=args.run_name,
                mcp_server_url=args.mcp_server_url,
                mcp_api_key=args.mcp_api_key,
                output_root=output_root,
                fk_batch_size=max(50, int(args.fk_batch_size)),
                max_tables=args.max_tables,
                refresh_scout=bool(args.refresh_scout),
                wait_refresh=bool(args.wait_refresh),
            )
        )
    except Exception as exc:
        print("Scout audit failed.")
        print(f"Error: {exc}")
        print(
            "Check MCP_SERVER_URL / MCP_API_KEY and ensure the remote MCP server is reachable."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
