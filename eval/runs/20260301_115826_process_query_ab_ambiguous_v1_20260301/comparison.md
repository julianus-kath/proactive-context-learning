# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_115155_ambiguous_v1_process_query_scout_on_r1` (eval/runs/20260301_115155_ambiguous_v1_process_query_scout_on_r1)
- OFF run: `20260301_115425_ambiguous_v1_process_query_scout_off_aligned_r1` (eval/runs/20260301_115425_ambiguous_v1_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4106.5 | 3764.7 | 341.8000000000002 |
| p95_latency_ms | 10070.0 | 6910.0 | 3160.0 |
| expert_strict_equal_count | 0 | 0 | 0 |
| expert_same_cols_set_equal_count | 0 | 0 | 0 |
| expert_positional_set_equal_count | 0 | 0 | 0 |
| expert_common_cols_set_equal_count | 3 | 4 | -1 |
| expert_required_tables_ok_count | 10 | 10 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NW1 | success | success | 10070 | 2964 | False | False |
| NW10 | success | success | 4008 | 3737 | False | False |
| NW2 | success | success | 4511 | 3715 | False | False |
| NW3 | success | success | 4083 | 3279 | False | False |
| NW4 | success | success | 3259 | 2713 | False | False |
| NW5 | success | success | 2752 | 3333 | False | False |
| NW6 | success | success | 2307 | 2898 | False | False |
| NW7 | success | success | 4015 | 6910 | False | False |
| NW8 | success | success | 3821 | 5075 | False | False |
| NW9 | success | success | 2239 | 3023 | False | False |
