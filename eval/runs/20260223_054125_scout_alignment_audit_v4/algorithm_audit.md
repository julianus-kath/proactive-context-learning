# Algorithmic Path Audit (Scout ON vs OFF)

## Pre-alignment behavior (root cause of mismatch)

### Search path split in MCP tool
- `mcp_server/tools/__init__.py` (`MCPTools._search_tables`) had two different ranking engines:
  - Scout ON path: `ScoutRunner.search(...)`
  - Scout OFF path: `DiscoveryTools.search_tables(...)` (internally `TableRanker`)

### ON ranking engine (ScoutRunner.search)
- Implemented in `mcp_server/scout/runner.py` (`ScoutRunner.search`).
- Used custom token/fuzzy scoring (`TableNameNormalizer.safe_fuzzy_match`, token match ratios, manual thresholds, row bonus, empty-table filtering).
- Did **not** use the `TableRanker` stack used by OFF mode.

### OFF ranking engine (Discovery + TableRanker)
- Implemented in `mcp_server/tools/discovery_tools.py` (`DiscoveryTools.search_tables`).
- Called `TableRanker.rank_tables(...)` from `mcp_server/tools/table_ranker.py`.
- Included synonym expansion and multiple boosts/penalties in `TableRanker`.

### Control-plane issue
- `SCOUT_DISABLE` was not enforced in the live `search_tables` code path.
- Startup in `mcp_server/server/app.py` skipped ScoutRunner in postgres mode, so backend attribution could drift from actual runtime retrieval path.

## Post-alignment behavior (implemented)

### Single ranking engine for both ON/OFF
- `mcp_server/tools/__init__.py` now routes both modes through shared helper `_rank_entities_with_table_ranker(...)`.
- Ranking backend is always `TableRanker` for this experiment.

### Only backend source differs
- Scout ON source: `scout_runner_catalog` (from `ScoutRunner.get_catalog()`).
- Scout OFF source: `schema_catalog` (from `db_manager.catalog.get_table_list()`).
- Response JSON now includes explicit metadata:
  - `source`
  - `ranking_backend`
  - `source_details`
  - `ranking_input`

### Deterministic mode control
- `SCOUT_DISABLE` is now explicitly enforced in `_search_tables`.
- `SCOUT_REQUIRE_READY=true` now fails fast with `SCOUT_NOT_READY` instead of silently falling back.

### Startup/backend attribution fix
- `mcp_server/server/app.py` now initializes ScoutRunner for enabled modes on postgres as well.
- Health backend now correctly reports `ScoutRunner` for ON runs and `SchemaCatalog` for OFF runs from run start.

## ScoutRunner vs Scout Catalog vs SchemaCatalog

- **ScoutRunner** (`mcp_server/scout/runner.py`): runtime manager (TTL, refresh, health) + builder orchestration. Persists compressed catalog in `data/catalog/scout_catalog.json.gz` via `CatalogStore`.
- **Scout catalog (legacy)** (`mcp_server/scout/mode.py`): older `SemanticCatalogBuilder` path that writes `mcp_server/cache/scout_catalog.json`. Kept as fallback for MSSQL startup path only.
- **SchemaCatalog** (`mcp_server/catalog/__init__.py`): database adapter cache used by OFF baseline; persisted as `mcp_server/cache/catalog_postgres.json` for postgres.

## Recommendation for thesis experiments
- Use **ScoutRunner** as the ON implementation.
- Use **SchemaCatalog + same TableRanker** as OFF baseline.
- Keep `SCOUT_REQUIRE_READY=true` in ON runs to prevent accidental source fallback.
