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
    Convert a raw table identifier into a canonical `schema.table` string.

    Behaviour:
    - Strip MSSQL-style brackets and generic quoting characters.
    - Collapse multi-part names down to a single schema + table:
      `[dbo].[dbo].[Suppliers]` → `dbo.suppliers`
    - When no schema is present, use the provided default schema.
    - For Postgres, always prefer the configured default schema
      (e.g. `public`) and ignore `dbo`-like prefixes.

    Examples (dialect="postgres", schema="public"):
    - "[dbo].[Order Details]"   → "public.order_details"
    - "dbo.Products"            → "public.products"
    - "Products"                → "public.products"

    Examples (dialect="mssql", schema="dbo"):
    - "[dbo].[Order Details]"   → "dbo.order_details"
    - "sales.Orders"            → "sales.orders"
    - "Orders"                  → "dbo.orders"
    """
    if not raw_name:
        return raw_name

    # Normalise to string and strip whitespace
    name = str(raw_name).strip()

    # Fast path: avoid accidental "[dbo].[dbo." duplication when already canonical
    if "[" not in name and "]" not in name and " " not in name and name.count(".") == 1:
        # Already looks like schema.table, just normalise casing/whitespace
        schema_part, table_part = [p.strip() for p in name.split(".", 1)]
        table_clean = re.sub(r"\s+", "_", table_part).lower()
        schema_clean = schema_part.lower() or (schema or "").lower()
        if dialect == "postgres":
            schema_clean = (schema or "public").lower()
        if not schema_clean:
            return table_clean
        return f"{schema_clean}.{table_clean}"

    # Strip brackets and generic quoting
    name = name.replace("[", "").replace("]", "").replace("`", "").replace('"', "")
    name = name.strip()

    if not name:
        return name

    parts = [p for p in name.split(".") if p]
    if len(parts) >= 2:
        # Take the last element as the table name and the one before as schema.
        # This collapses things like "dbo.dbo.Suppliers" safely.
        schema_part = parts[-2]
        table_part = parts[-1]
    else:
        schema_part = schema or ("dbo" if dialect == "mssql" else "public")
        table_part = parts[0]

    table_clean = re.sub(r"\s+", "_", table_part.strip()).lower()
    schema_clean = (schema_part or "").strip().lower()

    # For Postgres, always normalise to the configured default schema.
    if dialect == "postgres":
        schema_clean = (schema or "public").lower()

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

