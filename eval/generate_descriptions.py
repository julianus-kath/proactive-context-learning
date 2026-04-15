#!/usr/bin/env python3
"""
Pre-run Semantic Description Generator (SDG v2) CLI.

Reads the already-built Scout catalog from disk, runs the LLM description
generator against each table, and writes the results to a JSON cache keyed by
`full_name`. Later `ScoutRunner` runs with `SCOUT_DESCRIPTIONS_ENABLED=true`
and the same `SCOUT_DESCRIPTIONS_CACHE_PATH` read straight from this cache, so
experimental runs don't pay for generation and are deterministic.

Usage:
    # Northwind (controlled benchmark)
    SCOUT_DESCRIPTIONS_ENABLED=true \
    SCOUT_DESCRIPTIONS_DATABASE_TYPE=northwind \
    SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/northwind_descriptions.json \
    ANTHROPIC_API_KEY=... \
    python eval/generate_descriptions.py --catalog-dir data/catalog

    # Sage (production)
    SCOUT_DESCRIPTIONS_ENABLED=true \
    SCOUT_DESCRIPTIONS_DATABASE_TYPE=sage \
    SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/sage_descriptions.json \
    ANTHROPIC_API_KEY=... \
    python eval/generate_descriptions.py --catalog-dir data/catalog

The script does NOT rebuild the catalog. Boot the server once with Scout
enabled and description toggle OFF so the catalog builds, stop it, then run
this script against the persisted catalog. Subsequent runs with the toggle ON
will pick up the cached descriptions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from mcp_server.catalog.store import CatalogStore  # noqa: E402
from mcp_server.scout.description_generator import (  # noqa: E402
    DiskCachedDescriptionGenerator,
    LLMDescriptionGenerator,
    NullDescriptionGenerator,
    OpenAIDescriptionGenerator,
    build_description_generator_from_env,
)


def _unwrap_inner(gen) -> Any:
    """Return the innermost generator (strip DiskCachedDescriptionGenerator)."""
    inner = getattr(gen, "inner", None)
    return inner if inner is not None else gen


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-generate SDG descriptions for a Scout catalog")
    parser.add_argument(
        "--catalog-dir",
        default="data/catalog",
        help="Catalog directory used by CatalogStore (default: data/catalog)",
    )
    parser.add_argument(
        "--cache-path",
        default=None,
        help="Override SCOUT_DESCRIPTIONS_CACHE_PATH (default: env var)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate descriptions for tables that already have a cache entry",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on the number of tables generated (debugging)",
    )
    args = parser.parse_args()

    # Prefer the CLI flag over the env var, but default to the env var.
    cache_path = args.cache_path or os.environ.get("SCOUT_DESCRIPTIONS_CACHE_PATH")
    if not cache_path:
        print("ERROR: --cache-path or SCOUT_DESCRIPTIONS_CACHE_PATH is required", file=sys.stderr)
        return 2
    os.environ["SCOUT_DESCRIPTIONS_CACHE_PATH"] = cache_path

    if os.environ.get("SCOUT_DESCRIPTIONS_ENABLED", "").strip().lower() not in {"true", "1", "yes", "on"}:
        print("ERROR: SCOUT_DESCRIPTIONS_ENABLED must be truthy to run this script", file=sys.stderr)
        return 2

    # Load catalog — must already exist (boot the server once to build it).
    store = CatalogStore(catalog_dir=args.catalog_dir)
    catalog = store.load_catalog()
    if not catalog or not catalog.get("tables"):
        print(f"ERROR: no catalog found at {args.catalog_dir}. Build the catalog first.", file=sys.stderr)
        return 1

    tables: List[Dict[str, Any]] = catalog["tables"]
    if args.limit is not None:
        tables = tables[: args.limit]

    # Build the generator from env. This gives us: LLM → DiskCache wrapper.
    gen = build_description_generator_from_env()
    inner = _unwrap_inner(gen)
    if isinstance(gen, NullDescriptionGenerator) or isinstance(inner, NullDescriptionGenerator):
        print(
            "ERROR: description generator resolved to Null. "
            "Check SCOUT_DESCRIPTIONS_ENABLED and ANTHROPIC_API_KEY.",
            file=sys.stderr,
        )
        return 1
    if not isinstance(gen, DiskCachedDescriptionGenerator):
        print(
            "ERROR: generator is not disk-cached. Set SCOUT_DESCRIPTIONS_CACHE_PATH "
            "so results persist across runs.",
            file=sys.stderr,
        )
        return 1
    if not isinstance(inner, (LLMDescriptionGenerator, OpenAIDescriptionGenerator)):
        print(f"WARNING: inner generator is {type(inner).__name__}, expected LLM/OpenAI generator")

    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"Catalog:         {args.catalog_dir} ({len(catalog['tables'])} tables total)")
    print(f"Cache path:      {cache_path}")
    print(f"Model:           {getattr(inner, 'model', '?')}")
    print(f"Database type:   {getattr(inner, 'database_type', '?')}")
    print(f"Processing:      {len(tables)} tables (overwrite={args.overwrite})")
    print("-" * 60)

    generated = 0
    cached = 0
    empty = 0
    start = time.time()

    for idx, table in enumerate(tables, start=1):
        full_name = table.get("full_name") or table.get("name") or f"table_{idx}"

        # Respect the existing cache unless --overwrite.
        already_cached = full_name in getattr(gen, "_cache", {}) if hasattr(gen, "_cache") else False
        if already_cached and not args.overwrite:
            cached += 1
            print(f"[{idx:>3}/{len(tables)}] {full_name:<50} CACHED")
            continue

        # If overwriting, temporarily drop the entry so DiskCache delegates
        # through to the LLM again.
        if args.overwrite and already_cached and hasattr(gen, "_cache"):
            gen._cache.pop(full_name, None)  # type: ignore[attr-defined]

        desc = gen.generate(table)
        if desc:
            generated += 1
            print(f"[{idx:>3}/{len(tables)}] {full_name:<50} OK  ({len(desc)} chars)")
        else:
            empty += 1
            print(f"[{idx:>3}/{len(tables)}] {full_name:<50} EMPTY (fallback / API error)")

    elapsed = time.time() - start
    print("-" * 60)
    print(f"Generated: {generated}   Cached: {cached}   Empty: {empty}   Elapsed: {elapsed:.1f}s")

    # Sanity check: the disk cache should now contain at least `generated` entries.
    try:
        persisted = json.loads(Path(cache_path).read_text()) if Path(cache_path).exists() else {}
        print(f"Cache file now holds {len(persisted)} entries.")
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"(could not read back cache file: {exc})")

    return 0 if empty == 0 else 0  # empty rows don't fail the run


if __name__ == "__main__":
    sys.exit(main())
