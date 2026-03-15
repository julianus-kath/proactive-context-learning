# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_122640_ambiguous_v1_process_query_scout_on_r2` (eval/runs/20260301_122640_ambiguous_v1_process_query_scout_on_r2)
- OFF run: `20260301_123213_ambiguous_v1_process_query_scout_off_legacy_r2` (eval/runs/20260301_123213_ambiguous_v1_process_query_scout_off_legacy_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4674.1 | 4570.5 | 103.60000000000036 |
| p95_latency_ms | 9357.0 | 8589.0 | 768.0 |
| expert_strict_equal_count | 0 | 0 | 0 |
| expert_same_cols_set_equal_count | 0 | 0 | 0 |
| expert_positional_set_equal_count | 0 | 1 | -1 |
| expert_common_cols_set_equal_count | 3 | 2 | 1 |
| expert_required_tables_ok_count | 10 | 8 | 2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NW1 | success | success | 5559 | 3823 | False | False |
| NW10 | success | success | 3266 | 8589 | False | False |
| NW2 | success | success | 3630 | 3039 | False | False |
| NW3 | success | success | 4314 | 3474 | False | False |
| NW4 | success | success | 9357 | 3885 | False | False |
| NW5 | success | success | 5120 | 5676 | False | False |
| NW6 | success | success | 3066 | 5646 | False | False |
| NW7 | success | success | 4871 | 4564 | False | False |
| NW8 | success | success | 5257 | 3256 | False | False |
| NW9 | success | success | 2301 | 3753 | False | False |
