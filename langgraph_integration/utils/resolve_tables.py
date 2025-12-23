"""
Catalog-backed table name resolver.

Layer 2 on top of `canonical_table_name`:
- Uses the Scout catalog payload already present in state["catalog"].
- Builds light-weight indices once per catalog payload.
- Resolves raw or canonical names deterministically to a physical
  `schema.table` that exists in the catalog.

This module does **not** perform any semantic guessing (no synonyms,
no pluralisation). Matching is purely based on:
- exact `schema.table`
- case-insensitive variants
- "loose" keys (punctuation/whitespace/underscore insensitive)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .canonical_names import canonical_table_name


def _loose_key(name: str) -> str:
    """
    Build a loose comparison key for a table identifier.

    - Lowercase
    - Remove separators: '.', '_', whitespace, '-', brackets/quotes
    """
    if not name:
        return ""
    text = str(name).lower()
    # Strip common wrappers
    text = text.replace("[", "").replace("]", "").replace("`", "").replace('"', "")
    # Remove separators: dot, underscore, whitespace, hyphen
    return re.sub(r"[.\s_-]+", "", text)


@dataclass
class ResolvedTable:
    canonical_full_name: str
    physical_full_name: str
    physical_schema: str
    physical_name: str
    object_type: str  # "table" | "view" | "unknown"
    match_type: str   # "exact" | "ci" | "loose" | "default_schema" | "ambiguous" | "not_found"
    candidates: List[str]


class TableResolver:
    """
    Resolver built from a Scout catalog payload.

    Expected catalog structure (simplified):
    {
      "tables": {
        "public.orders": {
          "schema": "public",
          "table_name": "orders",
          "type": "BASE TABLE" | "VIEW" | ...,
          ...
        },
        ...
      },
      "views": {
        "public.orders_view": { ... },
        ...
      }
    }
    """

    def __init__(self, catalog: Dict[str, Any], dialect: str, default_schema: str):
        self.dialect = dialect
        self.default_schema = default_schema

        tables = catalog.get("tables") or {}
        views = catalog.get("views") or {}

        # Map: physical_full_name -> meta
        self._entries: Dict[str, Dict[str, Any]] = {}

        def _add_entries(container: Dict[str, Any], object_type: str) -> None:
            for full_name, meta in container.items():
                if not full_name:
                    continue
                key = str(full_name)
                record = dict(meta or {})
                record.setdefault("object_type", object_type)
                self._entries[key] = record

        _add_entries(tables, "table")
        _add_entries(views, "view")

        # Build indices
        self._exact_full: Dict[str, str] = {}   # canonical_full_name -> physical_full_name
        self._ci_full: Dict[str, str] = {}      # lower(canonical_full_name) -> physical_full_name
        self._loose_full: Dict[str, str] = {}   # loose(canonical_full_name) -> physical_full_name
        self._loose_table: Dict[str, List[str]] = {}  # loose(table_name) -> [physical_full_name]

        for physical_full, meta in self._entries.items():
            schema = str(meta.get("schema") or "").strip() or physical_full.split(".")[0]
            table_name = str(meta.get("table_name") or meta.get("name") or physical_full.split(".")[-1])

            # Canonical key from physical name
            canonical = canonical_table_name(
                f"{schema}.{table_name}",
                dialect=self.dialect,
                schema=self.default_schema,
            )

            self._exact_full[canonical] = physical_full
            self._ci_full[canonical.lower()] = physical_full

            loose_full = _loose_key(canonical)
            if loose_full and loose_full not in self._loose_full:
                self._loose_full[loose_full] = physical_full

            loose_table = _loose_key(table_name)
            if loose_table:
                self._loose_table.setdefault(loose_table, []).append(physical_full)

    def resolve(self, raw_name: str) -> ResolvedTable:
        """
        Resolve a raw or canonical table identifier to a physical catalog entry.

        Resolution order:
        1) exact canonical_full_name
        2) case-insensitive canonical_full_name
        3) loose(canonical_full_name)
        4) if no explicit schema: loose(table_name) across schemas
           - if one match → default_schema or only candidate
           - if many → ambiguous
        5) not_found
        """
        # Step 1: canonicalise input
        canonical = canonical_table_name(
            raw_name,
            dialect=self.dialect,
            schema=self.default_schema,
        )
        canonical_lower = canonical.lower()
        candidates: List[str] = []

        # Extract table token to decide whether we can try table-only search
        if "." in canonical:
            canonical_schema, canonical_table = canonical.split(".", 1)
        else:
            canonical_schema, canonical_table = self.default_schema, canonical

        # 1) Exact canonical match
        if canonical in self._exact_full:
            physical_full = self._exact_full[canonical]
            return self._build_result(
                canonical=canonical,
                physical_full=physical_full,
                match_type="exact",
            )

        # 2) Case-insensitive canonical match
        if canonical_lower in self._ci_full:
            physical_full = self._ci_full[canonical_lower]
            return self._build_result(
                canonical=canonical,
                physical_full=physical_full,
                match_type="ci",
            )

        # 3) Loose canonical (schema + table)
        loose_full = _loose_key(canonical)
        if loose_full and loose_full in self._loose_full:
            physical_full = self._loose_full[loose_full]
            return self._build_result(
                canonical=canonical,
                physical_full=physical_full,
                match_type="loose",
            )

        # 4) Table-only loose search (only when schema is effectively "default")
        schema_is_default = (
            not canonical_schema
            or canonical_schema.lower() == self.default_schema.lower()
        )
        loose_table = _loose_key(canonical_table)
        if schema_is_default and loose_table:
            matches = self._loose_table.get(loose_table, [])
            if len(matches) == 1:
                return self._build_result(
                    canonical=canonical,
                    physical_full=matches[0],
                    match_type="default_schema",
                )
            if len(matches) > 1:
                # Prefer default_schema if present
                preferred = [
                    m for m in matches
                    if m.split(".")[0].lower() == self.default_schema.lower()
                ]
                if len(preferred) == 1:
                    return self._build_result(
                        canonical=canonical,
                        physical_full=preferred[0],
                        match_type="default_schema",
                    )
                # Ambiguous across schemas
                return ResolvedTable(
                    canonical_full_name=canonical,
                    physical_full_name="",
                    physical_schema="",
                    physical_name="",
                    object_type="unknown",
                    match_type="ambiguous",
                    candidates=sorted(matches),
                )

        # 5) Not found
        return ResolvedTable(
            canonical_full_name=canonical,
            physical_full_name="",
            physical_schema="",
            physical_name="",
            object_type="unknown",
            match_type="not_found",
            candidates=candidates,
        )

    def _build_result(self, canonical: str, physical_full: str, match_type: str) -> ResolvedTable:
        meta = self._entries.get(physical_full, {})
        if "." in physical_full:
            schema, name = physical_full.split(".", 1)
        else:
            schema, name = self.default_schema, physical_full
        object_type = str(meta.get("object_type") or meta.get("type") or "unknown")
        return ResolvedTable(
            canonical_full_name=canonical,
            physical_full_name=physical_full,
            physical_schema=schema,
            physical_name=name,
            object_type=object_type,
            match_type=match_type,
            candidates=[physical_full],
        )

