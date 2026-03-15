# /process_query Scout ON vs OFF Comparison

- ON run: `20260309_161345_underspecified_v1_process_query_scout_on_r3` (eval/runs/20260309_161345_underspecified_v1_process_query_scout_on_r3)
- OFF run: `20260309_161530_underspecified_v1_process_query_scout_off_legacy_r3` (eval/runs/20260309_161530_underspecified_v1_process_query_scout_off_legacy_r3)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 8350.6 | 9677.3 | -1326.699999999999 |
| p95_latency_ms | 17356.0 | 17183.0 | 173.0 |
| expert_strict_equal_count | 1 | 1 | 0 |
| expert_same_cols_set_equal_count | 1 | 1 | 0 |
| expert_positional_set_equal_count | 1 | 1 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 0 | 3 | -3 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| US_CL10_U1 | success | success | 10506 | 17183 | False | True |
| US_CL10_U2 | success | success | 6250 | 7697 | True | False |
| US_CL10_U3 | success | success | 5155 | 7714 | None | None |
| US_CL2_U1 | success | success | 8800 | 8305 | False | False |
| US_CL2_U2 | success | success | 17356 | 9551 | False | False |
| US_CL2_U3 | success | success | 7799 | 8307 | False | False |
| US_CL3_U1 | success | success | 6052 | 5466 | None | None |
| US_CL3_U2 | success | success | 5040 | 8823 | None | False |
| US_CL3_U3 | success | success | 8208 | 15276 | None | False |
| US_CL6_U1 | success | success | 10791 | 13742 | None | False |
| US_CL6_U2 | success | success | 5496 | 7897 | None | None |
| US_CL6_U3 | success | success | 8754 | 6167 | None | None |
