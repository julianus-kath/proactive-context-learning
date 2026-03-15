# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_075448_complex_hard_v1_process_query_scout_on_r5_recover2` (eval/runs/20260302_075448_complex_hard_v1_process_query_scout_on_r5_recover2)
- OFF run: `20260302_075712_complex_hard_v1_process_query_scout_off_aligned_r5_recover2` (eval/runs/20260302_075712_complex_hard_v1_process_query_scout_off_aligned_r5_recover2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 93.33 | 6.670000000000002 |
| avg_latency_ms | 7466.7 | 12570.0 | -5103.3 |
| p95_latency_ms | 19679.0 | 72001.0 | -52322.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 7 | 5 | 2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | failed | 19679 | 72001 | False | None |
| HX10 | success | success | 6381 | 4668 | True | True |
| HX11 | success | success | 6098 | 5529 | False | False |
| HX12 | success | success | 8541 | 5816 | False | False |
| HX13 | success | success | 9556 | 11592 | False | False |
| HX14 | success | success | 8949 | 11559 | False | False |
| HX15 | success | success | 5774 | 4572 | None | None |
| HX2 | success | success | 5996 | 18569 | False | False |
| HX3 | success | success | 4264 | 4419 | None | None |
| HX4 | success | success | 4326 | 4402 | True | True |
| HX5 | success | success | 8515 | 6681 | False | False |
| HX6 | success | success | 5095 | 12143 | False | False |
| HX7 | success | success | 9522 | 12917 | False | False |
| HX8 | success | success | 5606 | 4811 | None | None |
| HX9 | success | success | 3698 | 8871 | False | False |
