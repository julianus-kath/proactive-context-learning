# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_185811_scout_limit_probe_v2_process_query_scout_on_r3` (eval/runs/20260302_185811_scout_limit_probe_v2_process_query_scout_on_r3)
- OFF run: `20260302_185506_scout_limit_probe_v2_process_query_scout_off_aligned_r3` (eval/runs/20260302_185506_scout_limit_probe_v2_process_query_scout_off_aligned_r3)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7557.4 | 8605.5 | -1048.1000000000004 |
| p95_latency_ms | 16933.0 | 23595.0 | -6662.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 6 | 6 | 0 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 3 | 4 | -1 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| P_CL10_L1 | success | success | 5825 | 6241 | None | None |
| P_CL10_L2 | success | success | 7369 | 10866 | True | False |
| P_CL10_L3 | success | success | 7377 | 10048 | None | True |
| P_CL10_L4 | success | success | 6615 | 4448 | None | None |
| P_CL10_L5 | success | success | 4980 | 6128 | True | True |
| P_CL10_L6 | success | success | 16933 | 18862 | False | False |
| P_CL2_L1 | success | success | 5783 | 6873 | False | False |
| P_CL2_L2 | success | success | 4629 | 5100 | False | False |
| P_CL2_L3 | success | success | 6985 | 6191 | None | False |
| P_CL2_L4 | success | success | 6535 | 5740 | False | False |
| P_CL2_L5 | success | success | 9272 | 5286 | False | False |
| P_CL2_L6 | success | success | 8609 | 5282 | False | None |
| P_CL6_L1 | success | success | 13813 | 18152 | False | False |
| P_CL6_L2 | success | success | 6900 | 2888 | None | None |
| P_CL6_L3 | success | success | 6860 | 7808 | None | None |
| P_CL6_L4 | success | success | 3928 | 4690 | None | None |
| P_CL6_L5 | success | success | 5075 | 6701 | None | None |
| P_CL6_L6 | success | success | 8545 | 23595 | None | False |
