# Scout Mode A/B (Northwind) - Thesis Integration Notes

## Objective
Validate that Northwind controlled evaluation can be aligned with the same Scout-enabled architecture used in production/user-study mode, while also reporting a SchemaCatalog ablation.

## Conditions
- Dataset: `eval/datasets/northwind_queries.jsonl` (10 fixed queries)
- Target agent: `http://localhost:5001`
- MCP backend: `http://localhost:8000`

### Run A (Scout ON)
- Run ID: `20260222_195813_northwind_ab_scout_on_clean_v2`
- MCP backend evidence: `ScoutRunner` at start and end (`run_manifest.json`)
- Flags: `SCOUT_DISABLE=false`, `SCOUT_REQUIRE_READY=true`

### Run B (Scout OFF)
- Run ID: `20260222_195526_northwind_ab_scout_off_clean`
- MCP backend evidence: `SchemaCatalog` at start and end (`run_manifest.json`)
- Flags: `SCOUT_DISABLE=true`

## Headline results
- Success rate: ON 100% (10/10), OFF 100% (10/10)
- SQL-executed rate: ON 100%, OFF 100%
- Non-empty-result rate: ON 100%, OFF 100%
- Average latency: ON 3553.4 ms, OFF 3730.9 ms (OFF-ON: +177.5 ms)

## Interpretation
- Controlled Northwind evaluation is now architecture-consistent with the production-style Scout path when Scout is enabled.
- The SchemaCatalog configuration can be presented as an explicit ablation baseline, not an accidental mismatch.
- In this 10-query sample, both backends are equally reliable on task completion; Scout shows a modest average latency advantage.

## Reproducibility artifacts
- Comparison JSON: `eval/runs/20260222_northwind_ab_comparison_clean_v2.json`
- Comparison Markdown: `eval/runs/20260222_northwind_ab_comparison_clean_v2.md`

## Important note
- An earlier run (`20260222_195322_northwind_ab_scout_on_clean`) is invalid for comparison due a temporary tool-path bug fixed afterward.
