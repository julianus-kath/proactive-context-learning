# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_184710_scout_limit_probe_v2_process_query_scout_on_r1` (eval/runs/20260302_184710_scout_limit_probe_v2_process_query_scout_on_r1)
- OFF run: `20260302_184403_scout_limit_probe_v2_process_query_scout_off_aligned_r1_recover` (eval/runs/20260302_184403_scout_limit_probe_v2_process_query_scout_off_aligned_r1_recover)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 6235.4 | 7986.1 | -1750.7000000000007 |
| p95_latency_ms | 13287.0 | 18651.0 | -5364.0 |
| expert_strict_equal_count | 2 | 4 | -2 |
| expert_same_cols_set_equal_count | 2 | 4 | -2 |
| expert_positional_set_equal_count | 6 | 5 | 1 |
| expert_common_cols_set_equal_count | 1 | 2 | -1 |
| expert_required_tables_ok_count | 4 | 7 | -3 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| P_CL10_L1 | success | success | 8081 | 7861 | None | True |
| P_CL10_L2 | success | success | 13287 | 10053 | False | None |
| P_CL10_L3 | success | success | 10531 | 13267 | True | True |
| P_CL10_L4 | success | success | 7534 | 3771 | None | None |
| P_CL10_L5 | success | success | 4719 | 5206 | True | True |
| P_CL10_L6 | success | success | 4740 | 3089 | None | None |
| P_CL2_L1 | success | success | 4229 | 6973 | False | True |
| P_CL2_L2 | success | success | 5492 | 5575 | False | False |
| P_CL2_L3 | success | success | 5965 | 5582 | False | None |
| P_CL2_L4 | success | success | 6632 | 10096 | False | False |
| P_CL2_L5 | success | success | 6087 | 6493 | None | False |
| P_CL2_L6 | success | success | 6086 | 8839 | None | False |
| P_CL6_L1 | success | success | 5623 | 18347 | False | False |
| P_CL6_L2 | success | success | 2547 | 2881 | None | None |
| P_CL6_L3 | success | success | 2602 | 3960 | None | None |
| P_CL6_L4 | success | success | 2934 | 6628 | None | None |
| P_CL6_L5 | success | success | 6290 | 6477 | None | None |
| P_CL6_L6 | success | success | 8858 | 18651 | None | False |
