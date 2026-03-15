# Northwind A/B Comparison (Scout ON vs OFF)

Generated: 2026-02-22T18:49:05.398675Z
Dataset: `eval/datasets/northwind_queries.jsonl`

## Run IDs
- Scout ON: `20260222_194637_northwind_ab_scout_on`
- Scout OFF: `20260222_194750_northwind_ab_scout_off`

## Backend Evidence
- Scout ON backend (start/end): `ScoutRunner` / `ScoutRunner`
- Scout OFF backend (start/end): `SchemaCatalog` / `SchemaCatalog`

## Aggregate Metrics
| Metric | Scout ON | Scout OFF | Delta (OFF-ON) |
|---|---:|---:|---:|
| Success rate | 100.0% | 100.0% | 0.0 pp |
| SQL executed rate | 100.0% | 100.0% | 0.0 pp |
| Non-empty results rate | 100.0% | 100.0% | 0.0 pp |
| Avg latency (ms) | 4081.9 | 3782.8 | -299.1 |

## Per-query Latency
| Query | Scout ON (ms) | Scout OFF (ms) | Delta (OFF-ON) | Row count equal |
|---|---:|---:|---:|:---:|
| NW1 | 3419 | 3434 | 15 | yes |
| NW10 | 5532 | 6958 | 1426 | yes |
| NW2 | 3179 | 2540 | -639 | yes |
| NW3 | 4055 | 3117 | -938 | yes |
| NW4 | 3383 | 3367 | -16 | yes |
| NW5 | 4707 | 3728 | -979 | yes |
| NW6 | 2829 | 3373 | 544 | yes |
| NW7 | 6787 | 4175 | -2612 | yes |
| NW8 | 3603 | 4173 | 570 | yes |
| NW9 | 3325 | 2963 | -362 | yes |
