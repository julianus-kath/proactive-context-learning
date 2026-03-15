# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_140029_scout_limit_ladder_v1_process_query_scout_on_r2` (eval/runs/20260302_140029_scout_limit_ladder_v1_process_query_scout_on_r2)
- OFF run: `20260302_140259_scout_limit_ladder_v1_process_query_scout_off_aligned_r2` (eval/runs/20260302_140259_scout_limit_ladder_v1_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 8129.8 | 7501.7 | 628.1000000000004 |
| p95_latency_ms | 18630.0 | 25833.0 | -7203.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 2 | 3 | -1 |
| expert_common_cols_set_equal_count | 0 | 1 | -1 |
| expert_required_tables_ok_count | 2 | 3 | -1 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| LT1_CL10 | success | success | 7754 | 6729 | None | True |
| LT1_CL2 | success | success | 5304 | 4974 | False | False |
| LT1_CL6 | success | success | 5213 | 5408 | False | False |
| LT2_CL10 | success | success | 9706 | 4216 | False | None |
| LT2_CL2 | success | success | 3646 | 3265 | False | False |
| LT2_CL6 | success | success | 6674 | 5851 | None | None |
| LT3_CL10 | success | success | 18630 | 10156 | True | True |
| LT3_CL2 | success | success | 6348 | 11762 | False | None |
| LT3_CL6 | success | success | 11081 | 25833 | None | False |
| LT4_CL10 | success | success | 14316 | 3736 | None | None |
| LT4_CL2 | success | success | 6462 | 8004 | False | False |
| LT4_CL6 | success | success | 5144 | 4752 | None | None |
| LT5_CL10 | success | success | 8613 | 4688 | False | False |
| LT5_CL2 | success | success | 5899 | 6061 | False | False |
| LT5_CL6 | success | success | 7157 | 7091 | None | None |
