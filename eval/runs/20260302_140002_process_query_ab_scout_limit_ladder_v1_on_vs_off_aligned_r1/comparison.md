# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_135751_scout_limit_ladder_v1_process_query_scout_on_r1` (eval/runs/20260302_135751_scout_limit_ladder_v1_process_query_scout_on_r1)
- OFF run: `20260302_135320_scout_limit_ladder_v1_process_query_scout_off_aligned_r1_recover` (eval/runs/20260302_135320_scout_limit_ladder_v1_process_query_scout_off_aligned_r1_recover)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7351.5 | 15454.3 | -8102.799999999999 |
| p95_latency_ms | 15146.0 | 34182.0 | -19036.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 1 | -1 |
| expert_required_tables_ok_count | 4 | 3 | 1 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| LT1_CL10 | success | success | 8913 | 33584 | None | None |
| LT1_CL2 | success | success | 5498 | 34182 | False | True |
| LT1_CL6 | success | success | 6217 | 31047 | False | False |
| LT2_CL10 | success | success | 6945 | 16394 | None | False |
| LT2_CL2 | success | success | 4720 | 4944 | False | False |
| LT2_CL6 | success | success | 10382 | 9349 | False | None |
| LT3_CL10 | success | success | 10372 | 11834 | True | True |
| LT3_CL2 | success | success | 11275 | 8269 | False | None |
| LT3_CL6 | success | success | 3342 | 5821 | None | None |
| LT4_CL10 | success | success | 8671 | 29893 | False | None |
| LT4_CL2 | success | success | 4717 | 6142 | False | None |
| LT4_CL6 | success | success | 3706 | 14873 | None | None |
| LT5_CL10 | success | success | 4025 | 4642 | False | False |
| LT5_CL2 | success | success | 6344 | 16862 | False | False |
| LT5_CL6 | success | success | 15146 | 3979 | False | None |
