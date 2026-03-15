# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_074307_complex_hard_v1_process_query_scout_on_r4` (eval/runs/20260302_074307_complex_hard_v1_process_query_scout_on_r4)
- OFF run: `20260302_074648_complex_hard_v1_process_query_scout_off_aligned_r4` (eval/runs/20260302_074648_complex_hard_v1_process_query_scout_off_aligned_r4)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `None` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7749.1 | 2684.5 | 5064.6 |
| p95_latency_ms | 17394.0 | 8860.0 | 8534.0 |
| expert_strict_equal_count | 2 | 0 | 2 |
| expert_same_cols_set_equal_count | 2 | 0 | 2 |
| expert_positional_set_equal_count | 2 | 0 | 2 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 6 | 0 | 6 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 17394 | 1788 | False | None |
| HX10 | success | success | 8749 | 1986 | True | None |
| HX11 | success | success | 5138 | 8860 | False | None |
| HX12 | success | success | 9979 | 1711 | False | None |
| HX13 | success | success | 14414 | 3312 | False | None |
| HX14 | success | success | 9154 | 1741 | False | None |
| HX15 | success | success | 6568 | 1839 | None | None |
| HX2 | success | success | 6565 | 2023 | False | None |
| HX3 | success | success | 4909 | 2179 | None | None |
| HX4 | success | success | 3634 | 2158 | True | None |
| HX5 | success | success | 6645 | 2690 | False | None |
| HX6 | success | success | 6818 | 2667 | False | None |
| HX7 | success | success | 6113 | 2572 | False | None |
| HX8 | success | success | 4650 | 2733 | None | None |
| HX9 | success | success | 5507 | 2008 | False | None |
