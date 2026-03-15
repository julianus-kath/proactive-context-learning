# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_132718_crosslingual_hard_v1_process_query_scout_on_r6` (eval/runs/20260302_132718_crosslingual_hard_v1_process_query_scout_on_r6)
- OFF run: `20260302_132916_crosslingual_hard_v1_process_query_scout_off_aligned_r6` (eval/runs/20260302_132916_crosslingual_hard_v1_process_query_scout_off_aligned_r6)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 6976.8 | 7770.6 | -793.8000000000002 |
| p95_latency_ms | 12784.0 | 24784.0 | -12000.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 1 | 2 | -1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 6 | 6 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 4875 | 4761 | False | False |
| CL10 | success | success | 5232 | 8125 | None | True |
| CL11 | success | success | 12784 | 6158 | False | None |
| CL12 | success | success | 7639 | 6390 | False | False |
| CL2 | success | success | 9317 | 9072 | False | False |
| CL3 | success | success | 5373 | 5053 | None | None |
| CL4 | success | success | 5422 | 24784 | False | False |
| CL5 | success | success | 4125 | 5133 | False | False |
| CL6 | success | success | 10990 | 5501 | False | None |
| CL7 | success | success | 6072 | 6630 | False | False |
| CL8 | success | success | 8345 | 6623 | False | False |
| CL9 | success | success | 3548 | 5017 | True | True |
