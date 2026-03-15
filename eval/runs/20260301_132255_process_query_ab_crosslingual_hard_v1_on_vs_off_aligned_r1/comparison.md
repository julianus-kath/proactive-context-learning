# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1` (eval/runs/20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1)
- OFF run: `20260301_131954_crosslingual_hard_v1_process_query_scout_off_aligned_r1` (eval/runs/20260301_131954_crosslingual_hard_v1_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4599.8 | 4315.2 | 284.60000000000036 |
| p95_latency_ms | 8719.0 | 6399.0 | 2320.0 |
| expert_strict_equal_count | 2 | 1 | 1 |
| expert_same_cols_set_equal_count | 2 | 1 | 1 |
| expert_positional_set_equal_count | 2 | 1 | 1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 7 | 6 | 1 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 3623 | 3499 | False | False |
| CL10 | success | success | 5094 | 3873 | True | None |
| CL11 | success | success | 3803 | 3923 | None | None |
| CL12 | success | success | 4709 | 4417 | False | False |
| CL2 | success | success | 8719 | 3726 | False | False |
| CL3 | success | success | 4041 | 4820 | None | None |
| CL4 | success | success | 3881 | 3503 | False | False |
| CL5 | success | success | 3330 | 3551 | False | False |
| CL6 | success | success | 4936 | 5446 | False | False |
| CL7 | success | success | 4928 | 6399 | False | False |
| CL8 | success | success | 5035 | 5453 | False | False |
| CL9 | success | success | 3098 | 3172 | True | True |
