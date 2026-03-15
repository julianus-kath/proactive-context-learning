# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_132329_crosslingual_hard_v1_process_query_scout_on_r2` (eval/runs/20260301_132329_crosslingual_hard_v1_process_query_scout_on_r2)
- OFF run: `20260301_132455_crosslingual_hard_v1_process_query_scout_off_aligned_r2` (eval/runs/20260301_132455_crosslingual_hard_v1_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4668.3 | 4361.8 | 306.5 |
| p95_latency_ms | 7029.0 | 7066.0 | -37.0 |
| expert_strict_equal_count | 1 | 1 | 0 |
| expert_same_cols_set_equal_count | 1 | 1 | 0 |
| expert_positional_set_equal_count | 1 | 1 | 0 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 5 | 5 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 3472 | 4077 | False | False |
| CL10 | success | success | 3358 | 3710 | None | None |
| CL11 | success | success | 4523 | 3447 | False | None |
| CL12 | success | success | 5191 | 4412 | False | False |
| CL2 | success | success | 7029 | 7066 | False | False |
| CL3 | success | success | 4020 | 4688 | None | None |
| CL4 | success | success | 5015 | 4124 | False | False |
| CL5 | success | success | 4496 | 3482 | False | False |
| CL6 | success | success | 5612 | 3349 | None | None |
| CL7 | success | success | 5612 | 5122 | False | False |
| CL8 | success | success | 5131 | 6165 | False | False |
| CL9 | success | success | 2561 | 2700 | True | True |
