# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_185226_scout_limit_probe_v2_process_query_scout_on_r2` (eval/runs/20260302_185226_scout_limit_probe_v2_process_query_scout_on_r2)
- OFF run: `20260302_184950_scout_limit_probe_v2_process_query_scout_off_aligned_r2` (eval/runs/20260302_184950_scout_limit_probe_v2_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7003.4 | 7523.9 | -520.5 |
| p95_latency_ms | 24738.0 | 20243.0 | 4495.0 |
| expert_strict_equal_count | 2 | 3 | -1 |
| expert_same_cols_set_equal_count | 2 | 3 | -1 |
| expert_positional_set_equal_count | 6 | 7 | -1 |
| expert_common_cols_set_equal_count | 0 | 2 | -2 |
| expert_required_tables_ok_count | 4 | 6 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| P_CL10_L1 | success | success | 3924 | 6402 | None | None |
| P_CL10_L2 | success | success | 10318 | 14761 | None | True |
| P_CL10_L3 | success | success | 7767 | 11398 | True | True |
| P_CL10_L4 | success | success | 5012 | 8159 | False | None |
| P_CL10_L5 | success | success | 4686 | 4786 | True | True |
| P_CL10_L6 | success | success | 24738 | 3584 | False | None |
| P_CL2_L1 | success | success | 5513 | 4957 | False | False |
| P_CL2_L2 | success | success | 4462 | 5026 | False | False |
| P_CL2_L3 | success | success | 7069 | 6697 | False | False |
| P_CL2_L4 | success | success | 4976 | 4728 | False | False |
| P_CL2_L5 | success | success | 6862 | 5044 | False | None |
| P_CL2_L6 | success | success | 9110 | 7635 | False | None |
| P_CL6_L1 | success | success | 6093 | 5505 | None | False |
| P_CL6_L2 | success | success | 3154 | 3163 | None | None |
| P_CL6_L3 | success | success | 3653 | 6853 | None | None |
| P_CL6_L4 | success | success | 5743 | 5071 | None | None |
| P_CL6_L5 | success | success | 6373 | 11419 | None | None |
| P_CL6_L6 | success | success | 6609 | 20243 | None | False |
