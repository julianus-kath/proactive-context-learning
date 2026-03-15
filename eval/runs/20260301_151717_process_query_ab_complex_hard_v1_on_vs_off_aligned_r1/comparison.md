# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_151227_complex_hard_v1_process_query_scout_on_r1` (eval/runs/20260301_151227_complex_hard_v1_process_query_scout_on_r1)
- OFF run: `20260301_151456_complex_hard_v1_process_query_scout_off_aligned_r1` (eval/runs/20260301_151456_complex_hard_v1_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 8121.7 | 8354.5 | -232.80000000000018 |
| p95_latency_ms | 18454.0 | 16174.0 | 2280.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 5 | 7 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 18454 | 16174 | False | False |
| HX10 | success | success | 4068 | 6679 | True | True |
| HX11 | success | success | 4574 | 5218 | False | False |
| HX12 | success | success | 11502 | 9484 | False | False |
| HX13 | success | success | 8919 | 11416 | False | False |
| HX14 | success | success | 8923 | 8419 | False | False |
| HX15 | success | success | 6575 | 9542 | None | None |
| HX2 | success | success | 14459 | 9878 | False | False |
| HX3 | success | success | 4379 | 4426 | None | None |
| HX4 | success | success | 6474 | 4549 | True | True |
| HX5 | success | success | 6233 | 10178 | False | False |
| HX6 | success | success | 8363 | 10793 | False | False |
| HX7 | success | success | 9512 | 9536 | False | False |
| HX8 | success | success | 4651 | 4487 | None | None |
| HX9 | success | success | 4740 | 4539 | False | False |
