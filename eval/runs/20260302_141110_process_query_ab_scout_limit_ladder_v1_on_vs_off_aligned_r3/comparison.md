# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_140859_scout_limit_ladder_v1_process_query_scout_on_r3` (eval/runs/20260302_140859_scout_limit_ladder_v1_process_query_scout_on_r3)
- OFF run: `20260302_140659_scout_limit_ladder_v1_process_query_scout_off_aligned_r3` (eval/runs/20260302_140659_scout_limit_ladder_v1_process_query_scout_off_aligned_r3)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 6650.3 | 4889.7 | 1760.6000000000004 |
| p95_latency_ms | 19841.0 | 10792.0 | 9049.0 |
| expert_strict_equal_count | 1 | 3 | -2 |
| expert_same_cols_set_equal_count | 1 | 3 | -2 |
| expert_positional_set_equal_count | 2 | 3 | -1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 2 | 4 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| LT1_CL10 | success | success | 8763 | 4342 | False | True |
| LT1_CL2 | success | success | 4188 | 3926 | False | True |
| LT1_CL6 | success | success | 4550 | 4025 | False | False |
| LT2_CL10 | success | success | 19841 | 6625 | True | None |
| LT2_CL2 | success | success | 4602 | 2926 | False | False |
| LT2_CL6 | success | success | 19712 | 4918 | False | None |
| LT3_CL10 | success | success | 4635 | 7530 | None | True |
| LT3_CL2 | success | success | 5403 | 10792 | False | False |
| LT3_CL6 | success | success | 2685 | 2174 | None | None |
| LT4_CL10 | success | success | 4822 | 5854 | None | None |
| LT4_CL2 | success | success | 4612 | 4227 | False | False |
| LT4_CL6 | success | success | 2914 | 4267 | None | None |
| LT5_CL10 | success | success | 4809 | 3348 | False | False |
| LT5_CL2 | success | success | 4881 | 6055 | False | False |
| LT5_CL6 | success | success | 3338 | 2337 | None | None |
