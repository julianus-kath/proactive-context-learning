# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_074307_complex_hard_v1_process_query_scout_on_r4` (eval/runs/20260302_074307_complex_hard_v1_process_query_scout_on_r4)
- OFF run: `20260302_075221_complex_hard_v1_process_query_scout_off_aligned_r4_recover2` (eval/runs/20260302_075221_complex_hard_v1_process_query_scout_off_aligned_r4_recover2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7749.1 | 7635.1 | 114.0 |
| p95_latency_ms | 17394.0 | 15460.0 | 1934.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 6 | 6 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 17394 | 11427 | False | False |
| HX10 | success | success | 8749 | 11282 | True | True |
| HX11 | success | success | 5138 | 6675 | False | False |
| HX12 | success | success | 9979 | 6599 | False | False |
| HX13 | success | success | 14414 | 7808 | False | False |
| HX14 | success | success | 9154 | 7516 | False | False |
| HX15 | success | success | 6568 | 4009 | None | None |
| HX2 | success | success | 6565 | 8176 | False | False |
| HX3 | success | success | 4909 | 4557 | None | None |
| HX4 | success | success | 3634 | 5751 | True | True |
| HX5 | success | success | 6645 | 6420 | False | False |
| HX6 | success | success | 6818 | 5946 | False | False |
| HX7 | success | success | 6113 | 15460 | False | False |
| HX8 | success | success | 4650 | 8630 | None | None |
| HX9 | success | success | 5507 | 4271 | False | False |
