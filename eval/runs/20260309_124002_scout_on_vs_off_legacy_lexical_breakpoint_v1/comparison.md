# /process_query Scout ON vs OFF Comparison

- ON run: `20260309_121921_lexical_breakpoint_v1_process_query_scout_on_r1` (eval/runs/20260309_121921_lexical_breakpoint_v1_process_query_scout_on_r1)
- OFF run: `20260309_123615_lexical_breakpoint_v1_process_query_scout_off_legacy_r1` (eval/runs/20260309_123615_lexical_breakpoint_v1_process_query_scout_off_legacy_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 6693.8 | 10036.1 | -3342.3 |
| p95_latency_ms | 12379.0 | 16262.0 | -3883.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 2 | 3 | -1 |
| expert_common_cols_set_equal_count | 0 | 1 | -1 |
| expert_required_tables_ok_count | 4 | 7 | -3 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| LB_CL10_LX1 | success | success | 6984 | 16262 | True | True |
| LB_CL10_LX2 | success | success | 5036 | 9703 | None | True |
| LB_CL10_LX3 | success | success | 5300 | 9286 | None | False |
| LB_CL2_LX1 | success | success | 5005 | 13608 | False | False |
| LB_CL2_LX2 | success | success | 8365 | 7731 | False | False |
| LB_CL2_LX3 | success | success | 4089 | 7776 | None | False |
| LB_CL3_LX1 | success | success | 4943 | 4030 | None | None |
| LB_CL3_LX2 | success | success | 4881 | 10610 | None | False |
| LB_CL3_LX3 | success | success | 9352 | 12893 | None | False |
| LB_CL6_LX1 | success | success | 12379 | 10594 | False | False |
| LB_CL6_LX2 | success | success | 10735 | 6545 | False | False |
| LB_CL6_LX3 | success | success | 3256 | 11395 | None | False |
