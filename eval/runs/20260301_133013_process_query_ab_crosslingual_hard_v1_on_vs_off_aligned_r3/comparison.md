# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_132643_crosslingual_hard_v1_process_query_scout_on_r3` (eval/runs/20260301_132643_crosslingual_hard_v1_process_query_scout_on_r3)
- OFF run: `20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3` (eval/runs/20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4919.2 | 4968.9 | -49.69999999999982 |
| p95_latency_ms | 10326.0 | 8903.0 | 1423.0 |
| expert_strict_equal_count | 2 | 1 | 1 |
| expert_same_cols_set_equal_count | 2 | 1 | 1 |
| expert_positional_set_equal_count | 2 | 1 | 1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 7 | 7 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 3459 | 4354 | False | False |
| CL10 | success | success | 10326 | 3688 | True | None |
| CL11 | success | success | 3892 | 4782 | None | None |
| CL12 | success | success | 4557 | 3935 | False | False |
| CL2 | success | success | 7124 | 3790 | False | False |
| CL3 | success | success | 3831 | 3927 | None | None |
| CL4 | success | success | 4942 | 6535 | False | False |
| CL5 | success | success | 3388 | 4914 | False | False |
| CL6 | success | success | 4817 | 8903 | False | False |
| CL7 | success | success | 4485 | 5258 | False | False |
| CL8 | success | success | 5575 | 6288 | False | False |
| CL9 | success | success | 2634 | 3253 | True | True |
