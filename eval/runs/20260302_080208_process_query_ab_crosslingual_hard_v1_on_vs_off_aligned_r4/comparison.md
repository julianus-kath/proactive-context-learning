# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_071150_crosslingual_hard_v1_process_query_scout_on_r4` (eval/runs/20260302_071150_crosslingual_hard_v1_process_query_scout_on_r4)
- OFF run: `20260302_071346_crosslingual_hard_v1_process_query_scout_off_aligned_r4` (eval/runs/20260302_071346_crosslingual_hard_v1_process_query_scout_off_aligned_r4)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7309.6 | 5497.4 | 1812.2000000000007 |
| p95_latency_ms | 14187.0 | 8722.0 | 5465.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 1 | 2 | -1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 5 | 5 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 7610 | 3813 | False | False |
| CL10 | success | success | 4262 | 5965 | None | True |
| CL11 | success | success | 4220 | 4419 | None | None |
| CL12 | success | success | 5545 | 5035 | False | False |
| CL2 | success | success | 13138 | 7245 | False | False |
| CL3 | success | success | 7088 | 5218 | None | None |
| CL4 | success | success | 6824 | 4672 | False | False |
| CL5 | success | success | 6177 | 5221 | False | False |
| CL6 | success | success | 14187 | 4024 | False | None |
| CL7 | success | success | 5304 | 7037 | False | False |
| CL8 | success | success | 9687 | 8722 | False | False |
| CL9 | success | success | 3673 | 4598 | True | True |
