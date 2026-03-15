# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1` (eval/runs/20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1)
- OFF run: `20260301_132133_crosslingual_hard_v1_process_query_scout_off_legacy_r1` (eval/runs/20260301_132133_crosslingual_hard_v1_process_query_scout_off_legacy_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4599.8 | 5859.2 | -1259.3999999999996 |
| p95_latency_ms | 8719.0 | 11772.0 | -3053.0 |
| expert_strict_equal_count | 2 | 3 | -1 |
| expert_same_cols_set_equal_count | 2 | 3 | -1 |
| expert_positional_set_equal_count | 2 | 3 | -1 |
| expert_common_cols_set_equal_count | 1 | 2 | -1 |
| expert_required_tables_ok_count | 7 | 9 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 3623 | 4043 | False | False |
| CL10 | success | success | 5094 | 4728 | True | True |
| CL11 | success | success | 3803 | 6095 | None | False |
| CL12 | success | success | 4709 | 5806 | False | False |
| CL2 | success | success | 8719 | 10031 | False | True |
| CL3 | success | success | 4041 | 6602 | None | False |
| CL4 | success | success | 3881 | 3465 | False | False |
| CL5 | success | success | 3330 | 3096 | False | False |
| CL6 | success | success | 4936 | 7667 | False | False |
| CL7 | success | success | 4928 | 11772 | False | False |
| CL8 | success | success | 5035 | 3295 | False | False |
| CL9 | success | success | 3098 | 3710 | True | True |
