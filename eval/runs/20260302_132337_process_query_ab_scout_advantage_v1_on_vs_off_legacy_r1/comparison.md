# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_131956_scout_advantage_v1_process_query_scout_on_r1` (eval/runs/20260302_131956_scout_advantage_v1_process_query_scout_on_r1)
- OFF run: `20260302_132202_scout_advantage_v1_process_query_scout_off_legacy_r1` (eval/runs/20260302_132202_scout_advantage_v1_process_query_scout_off_legacy_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7785.7 | 8593.8 | -808.0999999999995 |
| p95_latency_ms | 16218.0 | 13452.0 | 2766.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 1 | 2 | -1 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 3 | 5 | -2 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| SA1 | success | success | 4033 | 7723 | None | False |
| SA2 | success | success | 4598 | 5890 | False | False |
| SA3 | success | success | 4333 | 13452 | False | False |
| SA4 | success | success | 9533 | 12015 | None | False |
| SA5 | success | success | 16218 | 8599 | False | False |
| SA6 | success | success | 3186 | 10936 | None | False |
| SA7 | success | success | 16175 | 7218 | None | True |
| SA8 | success | success | 7176 | 4867 | True | True |
| SA9 | success | success | 4819 | 6644 | False | False |
