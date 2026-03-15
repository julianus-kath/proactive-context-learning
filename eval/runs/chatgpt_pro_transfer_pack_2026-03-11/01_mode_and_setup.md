# 01 Mode and Setup Guide

This pack documents three retrieval modes used in the ablation studies:

- Scout ON: `SCOUT_DISABLE=false`
- Scout OFF aligned: `SCOUT_DISABLE=true`, `SCOUT_OFF_CONTROL_MODE=aligned_table_ranker`
- Scout OFF legacy: `SCOUT_DISABLE=true`, `SCOUT_OFF_CONTROL_MODE=legacy_lexical_schema_linking`

Controlled Northwind studies used `/process_query` and retrieval scripts in `code/eval`.
Production-style cockpit studies used MCP `search_tables` with partner table labels.

Important runtime checks used in the latest cockpit runs:
- `/health` backend check (`ScoutRunner` vs `SchemaCatalog`)
- `/health` off_control_mode check
- `search_tables` response checks (`source`, `ranking_backend`, `source_details`)

This ensured each run matched the intended mode.
