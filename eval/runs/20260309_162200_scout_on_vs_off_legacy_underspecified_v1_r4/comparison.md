# /process_query Scout ON vs OFF Comparison

- ON run: `20260309_161731_underspecified_v1_process_query_scout_on_r4` (eval/runs/20260309_161731_underspecified_v1_process_query_scout_on_r4)
- OFF run: `20260309_161941_underspecified_v1_process_query_scout_off_legacy_r4` (eval/runs/20260309_161941_underspecified_v1_process_query_scout_off_legacy_r4)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 10490.2 | 10349.2 | 141.0 |
| p95_latency_ms | 20623.0 | 16301.0 | 4322.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 1 | 4 | -3 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| US_CL10_U1 | success | success | 17963 | 10293 | True | True |
| US_CL10_U2 | success | success | 11945 | 15842 | True | False |
| US_CL10_U3 | success | success | 12956 | 8029 | False | True |
| US_CL2_U1 | success | success | 6158 | 16301 | False | False |
| US_CL2_U2 | success | success | 8807 | 11237 | False | None |
| US_CL2_U3 | success | success | 9103 | 4375 | False | False |
| US_CL3_U1 | success | success | 5659 | 5295 | None | None |
| US_CL3_U2 | success | success | 20623 | 13379 | None | False |
| US_CL3_U3 | success | success | 11946 | 11097 | None | False |
| US_CL6_U1 | success | success | 6027 | 14553 | None | False |
| US_CL6_U2 | success | success | 6779 | 7474 | None | None |
| US_CL6_U3 | success | success | 7917 | 6316 | None | None |
