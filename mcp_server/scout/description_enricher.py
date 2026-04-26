"""
Catalog Description Enrichment
================================================================================
Applies a DescriptionGenerator to every table in a Scout catalog. Safe to call
with a NullDescriptionGenerator (each table ends up with description="").

This keeps the generator and the catalog mutation in separate modules so the
generator can be unit-tested in isolation and so the enrichment step can be
called from different places (ScoutRunner startup, ad-hoc scripts, tests).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp_server.scout.description_generator import DescriptionGenerator

logger = logging.getLogger(__name__)


def enrich_tables_with_descriptions(
    tables: List[Dict[str, Any]],
    generator: DescriptionGenerator,
    overwrite_existing: bool = False,
) -> int:
    """
    Populate the `description` field on each table dict in-place.

    Args:
        tables: Catalog table list; each entry is a dict.
        generator: A DescriptionGenerator (null or real).
        overwrite_existing: If False, preserve non-empty existing descriptions.

    Returns:
        The number of descriptions written.
    """
    if not tables:
        return 0

    # Short-circuit for the null case: stamp empty strings, no iteration over
    # the LLM, no logging noise.
    if not getattr(generator, "enabled", False):
        written = 0
        for table in tables:
            if not isinstance(table, dict):
                continue
            if overwrite_existing or not table.get("description"):
                table["description"] = ""
                written += 1
        return written

    written = 0
    total = len(tables)
    for idx, table in enumerate(tables, start=1):
        if not isinstance(table, dict):
            continue
        if not overwrite_existing and table.get("description"):
            continue
        try:
            description = generator.generate(table) or ""
        except Exception as exc:
            logger.warning(
                "Description generation raised for %s: %s",
                table.get("full_name", "?"),
                exc,
            )
            description = ""
        table["description"] = description
        written += 1
        if idx % 50 == 0 or idx == total:
            logger.info("SDG progress: %d / %d tables", idx, total)
    return written
