# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_122737_nonlexical_v1_process_query_scout_on_r2` (eval/runs/20260301_122737_nonlexical_v1_process_query_scout_on_r2)
- OFF run: `20260301_123020_nonlexical_v1_process_query_scout_off_aligned_r2` (eval/runs/20260301_123020_nonlexical_v1_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4344.2 | 4372.8 | -28.600000000000364 |
| p95_latency_ms | 6341.0 | 6513.0 | -172.0 |
| expert_strict_equal_count | 1 | 1 | 0 |
| expert_same_cols_set_equal_count | 1 | 1 | 0 |
| expert_positional_set_equal_count | 1 | 1 | 0 |
| expert_common_cols_set_equal_count | 1 | 4 | -3 |
| expert_required_tables_ok_count | 9 | 9 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NL1 | success | success | 2752 | 3213 | False | False |
| NL10 | success | success | 4152 | 5995 | False | False |
| NL11 | success | success | 4162 | 3389 | False | False |
| NL12 | success | success | 6341 | 4170 | False | False |
| NL13 | success | success | 3374 | 3698 | None | None |
| NL14 | success | success | 3763 | 3719 | False | False |
| NL15 | success | success | 5164 | 4931 | False | False |
| NL16 | success | success | 6957 | 8247 | True | True |
| NL17 | success | success | 4884 | 2948 | False | None |
| NL18 | success | success | 3860 | 2966 | False | False |
| NL19 | success | success | 2795 | 5636 | None | False |
| NL2 | success | success | 3763 | 4641 | False | False |
| NL20 | success | success | 3518 | 2752 | None | None |
| NL3 | success | success | 3893 | 6513 | None | False |
| NL4 | success | success | 4796 | 3848 | False | None |
| NL5 | success | success | 4396 | 5031 | False | False |
| NL6 | success | success | 6295 | 4330 | False | False |
| NL7 | success | success | 3674 | 4028 | False | False |
| NL8 | success | success | 5410 | 4621 | False | False |
| NL9 | success | success | 2936 | 2779 | False | False |
