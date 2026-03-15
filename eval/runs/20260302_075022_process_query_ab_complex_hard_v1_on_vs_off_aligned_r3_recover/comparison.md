# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_072425_complex_hard_v1_process_query_scout_on_r3` (eval/runs/20260302_072425_complex_hard_v1_process_query_scout_on_r3)
- OFF run: `20260302_073947_complex_hard_v1_process_query_scout_off_aligned_r3_recover` (eval/runs/20260302_073947_complex_hard_v1_process_query_scout_off_aligned_r3_recover)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 8801.2 | 10653.7 | -1852.5 |
| p95_latency_ms | 19810.0 | 21304.0 | -1494.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 5 | 7 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 19810 | 20702 | False | False |
| HX10 | success | success | 6939 | 6370 | True | True |
| HX11 | success | success | 5825 | 12779 | False | False |
| HX12 | success | success | 17689 | 19300 | False | False |
| HX13 | success | success | 9662 | 9703 | False | False |
| HX14 | success | success | 10131 | 10398 | False | False |
| HX15 | success | success | 5207 | 12273 | None | None |
| HX2 | success | success | 6562 | 8692 | False | False |
| HX3 | success | success | 4212 | 3507 | None | None |
| HX4 | success | success | 8199 | 6482 | True | True |
| HX5 | success | success | 6683 | 8567 | False | False |
| HX6 | success | success | 6180 | 10214 | False | False |
| HX7 | success | success | 10373 | 21304 | False | False |
| HX8 | success | success | 8669 | 5120 | None | None |
| HX9 | success | success | 5877 | 4395 | False | False |
