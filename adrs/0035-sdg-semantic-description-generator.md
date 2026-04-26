# ADR-0035: Semantic Description Generator (SDG) for Scout Catalog

**Status**: Accepted
**Date**: 2026-04-25
**Author**: Julianus Kath
**Related**: ADR-0014, ADR-0015, ADR-0020, ADR-0036

## Context

Scout Mode (ADR-0014) builds a structural catalog of tables, columns, and foreign keys. Semantic table ranking (ADR-0015) ranks tables by name and column fuzzy match. ADR-0020 introduced a first round of semantic catalog enrichment through additional MCP discovery tools (view dependencies, FK cardinality, domain clusters).

Running the system end-to-end revealed that structural and lexical signals work well on transparent schemas (Northwind: English table names like `customers`, `orders`) but fail on opaque production schemas. The Sage/Luisi & Diener ERP has 943 MSSQL tables with German CamelCase names such as `KHKStatVKKunden`, `BSBelege`, `MAArtikel`. Queries like *"which customers have overdue invoices?"* share no lexical tokens with the correct tables, so the ranker cannot surface them.

This is the regime the thesis is about: **schema opacity in production ERPs**.

## Decision

Add a Semantic Description Generator (SDG) to the Scout catalog build pipeline. SDG calls an LLM (Anthropic Claude Sonnet by default; OpenAI GPT-4o optional) to generate a one-paragraph business description for each table, grounded in the table's columns, foreign keys, and database type. Descriptions are embedded in the catalog and cached on disk.

### Components

- `mcp_server/scout/description_generator.py`
  - `DescriptionGenerator` Protocol with two implementations:
    - `NullDescriptionGenerator` — returns `""`, used when SDG is disabled
    - `LLMDescriptionGenerator` — calls Anthropic or OpenAI
  - `DiskCachedDescriptionGenerator` — wraps the LLM generator with per-table cache
  - `build_description_generator_from_env()` — factory resolving provider, model, cache path from env
- `mcp_server/scout/description_enricher.py`
  - `enrich_tables_with_descriptions()` — mutates catalog tables in place, stamping the `description` field

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `SCOUT_DESCRIPTIONS_ENABLED` | Generate descriptions at catalog build | `false` |
| `SCOUT_DESCRIPTIONS_PROVIDER` | `anthropic` or `openai` | `anthropic` |
| `SCOUT_DESCRIPTIONS_MODEL` | Model identifier | `claude-sonnet-4-20250514` |
| `SCOUT_DESCRIPTIONS_DATABASE_TYPE` | Swaps the prompt (`northwind` / `sage`) | `northwind` |
| `SCOUT_DESCRIPTIONS_CACHE_PATH` | Disk cache location | project-local |
| `SCOUT_DESCRIPTIONS_RANKING` | Use descriptions in ranker scoring | `false` |

`SCOUT_DESCRIPTIONS_ENABLED` is independent from `SCOUT_DESCRIPTIONS_RANKING`. This lets the ablation separate "descriptions in the agent's tool-call payload" from "descriptions in the ranker's scoring function." The three resulting conditions are the primary H2a ablation axis; see ADR-0036.

### Wiring

1. At startup, `ScoutRunner` builds the catalog via the dialect-specific builder (Postgres or MSSQL).
2. `enrich_tables_with_descriptions()` is called with the configured generator:
   - `NullDescriptionGenerator` stamps `description=""` on every table (no API cost).
   - `LLMDescriptionGenerator` generates one description per table, cached to disk after first call.
3. The enriched catalog is persisted at `data/catalog/catalog.json.gz`.
4. Descriptions are returned to the agent via `search_tables` responses regardless of whether they're used in ranking — the `discover_tables` tool output always includes them when present.
5. If `SCOUT_DESCRIPTIONS_RANKING=true`, `TableRanker._score_description_match()` in `mcp_server/tools/table_ranker.py` adds a token-coverage term (entities found as substring in lowered description / count of entities with length ≥ 3) to the relevance score. Tables qualify for inclusion on description alone when coverage ≥ 0.5; otherwise descriptions act as a re-rank tiebreaker among already-qualified candidates.

### Scope boundaries

- **Per-table, not per-column.** Column-level descriptions are a natural extension but out of scope for this thesis.
- **One-shot at catalog build.** Descriptions are not refreshed at query time.
- **Generator is replaceable.** Tests inject `NullDescriptionGenerator` or counting stubs; production injects the LLM generator. See `mcp_server/scout/tests/test_runner_toggle.py`.

## Consequences

**Positive:**
- Enables semantic retrieval on opaque schemas — the central technical contribution of the thesis.
- Decouples "generate" from "rank-with", enabling a clean three-condition ablation (see ADR-0036).
- Disk cache amortizes LLM cost across catalog rebuilds.
- Database-aware prompts keep the Northwind demo cheap (~$0.05 per full build).
- Fully replaceable generator (via Protocol) keeps tests deterministic.

**Negative:**
- Adds an LLM dependency to catalog build. First-boot on cold cache takes longer.
- Descriptions are LLM-generated and can hallucinate on exotic table structures. The thesis treats them as a controlled input, not ground truth.
- Adds four environment variables to the configuration surface.

**Follow-up:**
- ADR-0036 documents the shift from "Scout ON/OFF" to "SDG description enrichment" as the primary H2a ablation axis.
- Per-column descriptions and automatic refresh on schema drift are not in scope for this thesis but are natural next steps.
