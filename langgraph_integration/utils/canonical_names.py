"""
Canonical table identifier utilities.

This module provides a single place to normalise logical table identifiers
so that the rest of the pipeline can reason about a stable
`schema.table` form instead of a mix of:

- `[dbo].[Order Details]`
- `dbo.Order Details`
- `dbo.Orders`
- `Orders`

The goal is consistency for:
- intent/concept mapping
- discovery seed tables and logs
- join planning inputs
- validation metadata

Actual SQL generation remains responsible for dialect‑specific quoting
(`[…]`, `"…"`, etc.).
"""

from __future__ import annotations

import re
from typing import Iterable, List


def canonical_table_name(raw_name: str, dialect: str, schema: str) -> str:
    """
    Convert a raw table identifier into a *syntactically* canonical `schema.table`.

    This function is deliberately conservative: it normalizes representation,
    not meaning. It does **not** attempt to guess dataset-specific names
    (e.g. mapping "Order Details" → "order_details" or "Products" → "product").

    Rules:
    - Strip wrappers: [], ``, double quotes.
    - Trim outer whitespace.
    - Split into parts on '.'; treat the last part as the table token, the
      previous as the schema token (collapsing prefixes such as dbo.dbo.X).
    - If schema is missing, fall back to the provided default schema.
    - Normalize whitespace *inside* the table token to single spaces.
    - Normalize case to lower-case for comparison consistency.
    - For Postgres dialect, always emit the configured logical schema
      (e.g. "public") rather than dbo-style prefixes.

    Any higher-level aliasing (e.g., resolving "Order Details" to an actual
    `order_details` table) must be done by a catalog-backed resolver, not here.
    """
    if not raw_name:
        return raw_name

    # Normalise to string and strip outer whitespace
    name = str(raw_name).strip()

    # Strip MSSQL-style brackets and generic quoting
    name = name.replace("[", "").replace("]", "").replace("`", "").replace('"', "")
    name = name.strip()

    if not name:
        return name

    parts = [p for p in name.split(".") if p]
    if len(parts) >= 2:
        # Take the last element as the table token and the one before as schema.
        # This collapses duplicates like "dbo.dbo.Suppliers" safely.
        schema_part = parts[-2]
        table_part = parts[-1]
    else:
        schema_part = None
        table_part = parts[0]

    # Whitespace-normalized, identifier-safe table token:
    # - collapse internal whitespace to a single space
    # - lowercase
    # - replace spaces with underscore so the result can be safely used as an
    #   unquoted identifier in SQL when needed.
    table_norm = re.sub(r"\s+", " ", table_part.strip())
    table_clean = table_norm.lower().replace(" ", "_")

    # Schema normalisation:
    # - For Postgres, preserve explicit schema tokens from the raw name
    #   (lowercased) when present to avoid collapsing multi-schema usage.
    #   Only when no schema_part is present do we fall back to the configured
    #   default schema.
    # - For MSSQL/others, prefer explicit schema when present, otherwise the
    #   provided default or a sensible dialect-specific fallback.
    if dialect == "postgres":
        if schema_part:
            candidate = schema_part.strip().lower()
            if candidate in {"dbo", "db_owner"}:
                fallback = (schema or "public").strip().lower() or "public"
                schema_clean = fallback
            else:
                schema_clean = candidate
        else:
            schema_clean = (schema or "public").strip().lower()
    else:
        effective_schema = (schema_part or schema or ("dbo" if dialect == "mssql" else "public"))
        schema_clean = str(effective_schema).strip().lower()

    if not schema_clean:
        return table_clean

    return f"{schema_clean}.{table_clean}"


def canonicalize_table_list(
    tables: Iterable[str],
    dialect: str,
    schema: str,
) -> List[str]:
    """
    Canonicalise a sequence of table identifiers.

    Returns a list without preserving duplicates; if the same logical
    table appears under different syntactic forms, only the first
    canonical instance is kept.
    """
    seen: set[str] = set()
    output: List[str] = []
    for raw in tables:
        if not raw:
            continue
        canonical = canonical_table_name(str(raw), dialect=dialect, schema=schema)
        if canonical in seen:
            continue
        seen.add(canonical)
        output.append(canonical)
    return output
