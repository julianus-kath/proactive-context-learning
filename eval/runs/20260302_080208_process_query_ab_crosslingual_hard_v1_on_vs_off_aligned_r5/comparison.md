# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_071600_crosslingual_hard_v1_process_query_scout_on_r5` (eval/runs/20260302_071600_crosslingual_hard_v1_process_query_scout_on_r5)
- OFF run: `20260302_071708_crosslingual_hard_v1_process_query_scout_off_aligned_r5` (eval/runs/20260302_071708_crosslingual_hard_v1_process_query_scout_off_aligned_r5)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 5482.8 | 5482.2 | 0.6000000000003638 |
| p95_latency_ms | 8408.0 | 7409.0 | 999.0 |
| expert_strict_equal_count | 2 | 1 | 1 |
| expert_same_cols_set_equal_count | 2 | 1 | 1 |
| expert_positional_set_equal_count | 2 | 1 | 1 |
| expert_common_cols_set_equal_count | 1 | 1 | 0 |
| expert_required_tables_ok_count | 8 | 5 | 3 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| CL1 | success | success | 3472 | 6720 | False | False |
| CL10 | success | success | 8408 | 3960 | True | None |
| CL11 | success | success | 5597 | 4682 | None | None |
| CL12 | success | success | 4426 | 5007 | False | False |
| CL2 | success | success | 7814 | 7409 | False | False |
| CL3 | success | success | 4087 | 6359 | None | None |
| CL4 | success | success | 5185 | 5623 | False | False |
| CL5 | success | success | 3780 | 2690 | False | False |
| CL6 | success | success | 5861 | 4840 | False | None |
| CL7 | success | success | 6729 | 6740 | False | False |
| CL8 | success | success | 7468 | 5609 | False | False |
| CL9 | success | success | 2966 | 6148 | True | True |
