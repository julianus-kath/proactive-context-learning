# /process_query Scout ON vs OFF Comparison

- ON run: `20260223_143212_northwind_more_v1_scout_on` (eval/runs/20260223_143212_northwind_more_v1_scout_on)
- OFF run: `20260223_143759_northwind_more_v1_scout_off` (eval/runs/20260223_143759_northwind_more_v1_scout_off)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 7893.8 | 12379.9 | -4486.099999999999 |
| p95_latency_ms | 14351.0 | 29296.0 | -14945.0 |
| expert_strict_equal_count | 2 | 2 | 0 |
| expert_same_cols_set_equal_count | 2 | 2 | 0 |
| expert_positional_set_equal_count | 2 | 2 | 0 |
| expert_common_cols_set_equal_count | 7 | 7 | 0 |
| expert_required_tables_ok_count | 22 | 23 | -1 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NW11 | success | success | 11376 | 11627 | False | False |
| NW12 | success | success | 5839 | 6542 | False | False |
| NW13 | success | success | 11453 | 12434 | False | False |
| NW14 | success | success | 14351 | 8332 | False | False |
| NW15 | success | success | 7734 | 7077 | False | False |
| NW16 | success | success | 6744 | 5284 | False | False |
| NW17 | success | success | 4198 | 2965 | False | False |
| NW18 | success | success | 6620 | 7240 | False | False |
| NW19 | success | success | 12063 | 20354 | False | False |
| NW20 | success | success | 7923 | 4977 | False | False |
| NW21 | success | success | 3546 | 4444 | False | False |
| NW22 | success | success | 4642 | 4489 | False | False |
| NW23 | success | success | 4766 | 6935 | False | False |
| NW24 | success | success | 12340 | 5204 | False | False |
| NW25 | success | success | 7803 | 6245 | False | False |
| NW26 | success | success | 5436 | 8012 | False | False |
| NW27 | success | success | 10498 | 5749 | False | False |
| NW28 | success | success | 15107 | 12637 | False | False |
| NW29 | success | success | 7833 | 6981 | False | False |
| NW30 | success | success | 4165 | 5423 | True | True |
| NW31 | success | success | 7394 | 12440 | False | False |
| NW32 | success | success | 7952 | 19520 | True | True |
| NW33 | success | success | 6399 | 25519 | False | False |
| NW34 | success | success | 4535 | 20951 | False | False |
| NW35 | success | success | 7665 | 28412 | False | False |
| NW36 | success | success | 14331 | 5213 | False | False |
| NW37 | success | success | 7868 | 29296 | False | False |
| NW38 | success | success | 7022 | 22631 | False | False |
| NW39 | success | success | 5635 | 24487 | False | False |
| NW40 | success | success | 3576 | 29978 | False | False |
