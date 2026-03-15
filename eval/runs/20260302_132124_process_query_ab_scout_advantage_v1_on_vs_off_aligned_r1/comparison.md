# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_131956_scout_advantage_v1_process_query_scout_on_r1` (eval/runs/20260302_131956_scout_advantage_v1_process_query_scout_on_r1)
- OFF run: `20260302_131715_scout_advantage_v1_process_query_scout_off_aligned_r1` (eval/runs/20260302_131715_scout_advantage_v1_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7785.7 | 10600.4 | -2814.7 |
| p95_latency_ms | 16218.0 | 23452.0 | -7234.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 1 | 2 | -1 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 3 | 3 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| SA1 | success | success | 4033 | 6865 | None | None |
| SA2 | success | success | 4598 | 5433 | False | False |
| SA3 | success | success | 4333 | 10210 | False | False |
| SA4 | success | success | 9533 | 13307 | None | False |
| SA5 | success | success | 16218 | 7610 | False | None |
| SA6 | success | success | 3186 | 9138 | None | False |
| SA7 | success | success | 16175 | 14807 | None | True |
| SA8 | success | success | 7176 | 23452 | True | True |
| SA9 | success | success | 4819 | 4582 | False | False |
