# /process_query Scout ON vs OFF Comparison

- ON run: `20260302_132546_on_edge_v1_process_query_scout_on_r1` (eval/runs/20260302_132546_on_edge_v1_process_query_scout_on_r1)
- OFF run: `20260302_132445_on_edge_v1_process_query_scout_off_aligned_r1` (eval/runs/20260302_132445_on_edge_v1_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 11064.7 | 8054.3 | 3010.4000000000005 |
| p95_latency_ms | 14919.0 | 9978.0 | 4941.0 |
| expert_strict_equal_count | 1 | 1 | 0 |
| expert_same_cols_set_equal_count | 1 | 1 | 0 |
| expert_positional_set_equal_count | 1 | 1 | 0 |
| expert_common_cols_set_equal_count | 0 | 0 | 0 |
| expert_required_tables_ok_count | 2 | 2 | 0 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| OE1 | success | success | 14919 | 9978 | False | False |
| OE2 | success | success | 9177 | 7156 | False | None |
| OE3 | success | success | 9098 | 7029 | True | True |
