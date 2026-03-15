# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_151800_complex_hard_v1_process_query_scout_on_r2` (eval/runs/20260301_151800_complex_hard_v1_process_query_scout_on_r2)
- OFF run: `20260301_152002_complex_hard_v1_process_query_scout_off_aligned_r2` (eval/runs/20260301_152002_complex_hard_v1_process_query_scout_off_aligned_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 6087.3 | 7590.4 | -1503.0999999999995 |
| p95_latency_ms | 9854.0 | 13274.0 | -3420.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 5 | 5 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| HX1 | success | success | 9854 | 13151 | False | False |
| HX10 | success | success | 4130 | 3823 | True | True |
| HX11 | success | success | 5089 | 5921 | False | False |
| HX12 | success | success | 8423 | 9649 | False | False |
| HX13 | success | success | 7191 | 8945 | False | False |
| HX14 | success | success | 7006 | 8139 | False | False |
| HX15 | success | success | 7156 | 9948 | None | None |
| HX2 | success | success | 5117 | 6483 | False | False |
| HX3 | success | success | 3858 | 4333 | None | None |
| HX4 | success | success | 5884 | 4011 | True | True |
| HX5 | success | success | 5482 | 6339 | False | False |
| HX6 | success | success | 6378 | 13274 | False | False |
| HX7 | success | success | 7882 | 10632 | False | False |
| HX8 | success | success | 4179 | 4102 | None | None |
| HX9 | success | success | 3681 | 5106 | False | False |
