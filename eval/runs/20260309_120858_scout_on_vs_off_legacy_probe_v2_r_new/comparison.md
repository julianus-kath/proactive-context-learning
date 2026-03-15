# /process_query Scout ON vs OFF Comparison

- ON run: `20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new` (eval/runs/20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new)
- OFF run: `20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new` (eval/runs/20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 5939.4 | 10679.9 | -4740.5 |
| p95_latency_ms | 17885.0 | 25377.0 | -7492.0 |
| expert_strict_equal_count | 3 | 6 | -3 |
| expert_same_cols_set_equal_count | 3 | 6 | -3 |
| expert_positional_set_equal_count | 4 | 7 | -3 |
| expert_common_cols_set_equal_count | 1 | 2 | -1 |
| expert_required_tables_ok_count | 5 | 12 | -7 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| P_CL10_L1 | success | success | 7645 | 10852 | None | False |
| P_CL10_L2 | success | success | 4426 | 7336 | True | True |
| P_CL10_L3 | success | success | 8154 | 8506 | True | True |
| P_CL10_L4 | success | success | 4785 | 25377 | None | True |
| P_CL10_L5 | success | success | 4695 | 15019 | True | True |
| P_CL10_L6 | success | success | 12463 | 17551 | False | True |
| P_CL2_L1 | success | success | 17885 | 6738 | False | True |
| P_CL2_L2 | success | success | 3989 | 6494 | False | False |
| P_CL2_L3 | success | success | 5297 | 9421 | False | False |
| P_CL2_L4 | success | success | 4521 | 5420 | False | None |
| P_CL2_L5 | success | success | 4193 | 7772 | False | False |
| P_CL2_L6 | success | success | 4787 | 7562 | None | False |
| P_CL6_L1 | success | success | 3145 | 12056 | False | False |
| P_CL6_L2 | success | success | 2249 | 7403 | None | False |
| P_CL6_L3 | success | success | 3654 | 15809 | None | False |
| P_CL6_L4 | success | success | 2603 | 5155 | None | None |
| P_CL6_L5 | success | success | 3878 | 6172 | None | None |
| P_CL6_L6 | success | success | 8541 | 17595 | None | False |
