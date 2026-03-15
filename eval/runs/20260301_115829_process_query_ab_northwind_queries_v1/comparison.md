# /process_query Scout ON vs OFF Comparison

- ON run: `20260223_063000_northwind_process_query_scout_on` (eval/runs/20260223_063000_northwind_process_query_scout_on)
- OFF run: `20260223_063107_northwind_process_query_scout_off` (eval/runs/20260223_063107_northwind_process_query_scout_off)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4234.3 | 3968.9 | 265.4000000000001 |
| p95_latency_ms | 5438.0 | 8214.0 | -2776.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 4 | 4 | 0 |
| expert_common_cols_set_equal_count | 8 | 6 | 2 |
| expert_required_tables_ok_count | 8 | 8 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NW1 | success | success | 5438 | 2915 | False | False |
| NW10 | success | success | 5116 | 5180 | False | False |
| NW2 | success | success | 3527 | 3956 | True | True |
| NW3 | success | success | 4462 | 3712 | False | False |
| NW4 | success | success | 3595 | 3667 | False | False |
| NW5 | success | success | 3965 | 8214 | True | True |
| NW6 | success | success | 3169 | 2473 | False | False |
| NW7 | success | success | 5246 | 3446 | False | False |
| NW8 | success | success | 4960 | 3258 | False | False |
| NW9 | success | success | 2865 | 2868 | False | False |
