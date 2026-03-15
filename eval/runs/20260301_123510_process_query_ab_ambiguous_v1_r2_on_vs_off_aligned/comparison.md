# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_122640_ambiguous_v1_process_query_scout_on_r2` (eval/runs/20260301_122640_ambiguous_v1_process_query_scout_on_r2)
- OFF run: `20260301_122935_ambiguous_v1_process_query_scout_off_aligned_r2` (eval/runs/20260301_122935_ambiguous_v1_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4674.1 | 3358.1 | 1316.0000000000005 |
| p95_latency_ms | 9357.0 | 4609.0 | 4748.0 |
| expert_strict_equal_count | 0 | 0 | 0 |
| expert_same_cols_set_equal_count | 0 | 0 | 0 |
| expert_positional_set_equal_count | 0 | 0 | 0 |
| expert_common_cols_set_equal_count | 3 | 3 | 0 |
| expert_required_tables_ok_count | 10 | 10 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NW1 | success | success | 5559 | 2853 | False | False |
| NW10 | success | success | 3266 | 3397 | False | False |
| NW2 | success | success | 3630 | 4007 | False | False |
| NW3 | success | success | 4314 | 3062 | False | False |
| NW4 | success | success | 9357 | 2820 | False | False |
| NW5 | success | success | 5120 | 3453 | False | False |
| NW6 | success | success | 3066 | 2330 | False | False |
| NW7 | success | success | 4871 | 4353 | False | False |
| NW8 | success | success | 5257 | 4609 | False | False |
| NW9 | success | success | 2301 | 2697 | False | False |
