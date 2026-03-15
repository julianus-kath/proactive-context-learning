# /process_query Scout ON vs OFF Comparison

- ON run: `20260309_145932_underspecified_v1_process_query_scout_on_r2` (eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2)
- OFF run: `20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2` (eval/runs/20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 10735.6 | 9771.2 | 964.3999999999996 |
| p95_latency_ms | 20312.0 | 16479.0 | 3833.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 1 | 3 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| US_CL10_U1 | success | success | 9907 | 7853 | True | True |
| US_CL10_U2 | success | success | 10441 | 16479 | True | False |
| US_CL10_U3 | success | success | 6047 | 7212 | None | True |
| US_CL2_U1 | success | success | 20312 | 10339 | False | None |
| US_CL2_U2 | success | success | 7951 | 8852 | False | False |
| US_CL2_U3 | success | success | 13328 | 9018 | False | False |
| US_CL3_U1 | success | success | 7789 | 4199 | None | None |
| US_CL3_U2 | success | success | 14839 | 13737 | None | False |
| US_CL3_U3 | success | success | 9836 | 13923 | None | False |
| US_CL6_U1 | success | success | 8765 | 12546 | None | False |
| US_CL6_U2 | success | success | 5775 | 6343 | None | None |
| US_CL6_U3 | success | success | 13837 | 6753 | None | None |
