# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_074810_complex_hard_v1_process_query_scout_on_r5` (eval/runs/20260302_074810_complex_hard_v1_process_query_scout_on_r5)
- OFF run: `20260302_074916_complex_hard_v1_process_query_scout_off_aligned_r5` (eval/runs/20260302_074916_complex_hard_v1_process_query_scout_off_aligned_r5)
- ON scout mode: `None` active=`False`
- OFF scout mode: `None` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 2482.6 | 2456.4 | 26.199999999999818 |
| p95_latency_ms | 3854.0 | 6424.0 | -2570.0 |
| expert_strict_equal_count | 0 | 0 | 0 |
| expert_same_cols_set_equal_count | 0 | 0 | 0 |
| expert_positional_set_equal_count | 0 | 0 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 0 | 0 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 1860 | 6424 | None | None |
| HX10 | success | success | 2083 | 2394 | None | None |
| HX11 | success | success | 2761 | 2439 | None | None |
| HX12 | success | success | 1712 | 2205 | None | None |
| HX13 | success | success | 2202 | 1781 | None | None |
| HX14 | success | success | 2774 | 2770 | None | None |
| HX15 | success | success | 3854 | 1795 | None | None |
| HX2 | success | success | 2870 | 1753 | None | None |
| HX3 | success | success | 3622 | 2008 | None | None |
| HX4 | success | success | 3734 | 1868 | None | None |
| HX5 | success | success | 1874 | 2176 | None | None |
| HX6 | success | success | 2552 | 2648 | None | None |
| HX7 | success | success | 1623 | 2978 | None | None |
| HX8 | success | success | 1753 | 1968 | None | None |
| HX9 | success | success | 1965 | 1639 | None | None |
