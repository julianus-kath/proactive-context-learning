# Northwind A/B Comparison (clean v2)

- Scout ON run: `20260222_195813_northwind_ab_scout_on_clean_v2`
- Scout OFF run: `20260222_195526_northwind_ab_scout_off_clean`
- ON backend (start/end): `ScoutRunner` / `ScoutRunner`
- OFF backend (start/end): `SchemaCatalog` / `SchemaCatalog`

## Aggregate

| Metric | Scout ON | Scout OFF | Delta (OFF-ON) |
|---|---:|---:|---:|
| Success rate | 100.0% | 100.0% | 0.0 pp |
| Avg latency (ms) | 3553.4 | 3730.9 | 177.5 |
| SQL executed rate | 100.0% | 100.0% | 0.0 pp |
| Non-empty result rate | 100.0% | 100.0% | 0.0 pp |

## Per Query Latency

| Query | ON status | OFF status | ON ms | OFF ms | OFF-ON ms |
|---|---|---|---:|---:|---:|
| NW1 | success | success | 2858 | 4996 | 2138 |
| NW10 | success | success | 5159 | 5648 | 489 |
| NW2 | success | success | 3743 | 2734 | -1009 |
| NW3 | success | success | 3214 | 3851 | 637 |
| NW4 | success | success | 3112 | 3424 | 312 |
| NW5 | success | success | 2912 | 3466 | 554 |
| NW6 | success | success | 2533 | 2575 | 42 |
| NW7 | success | success | 3808 | 3929 | 121 |
| NW8 | success | success | 5347 | 4183 | -1164 |
| NW9 | success | success | 2848 | 2503 | -345 |
