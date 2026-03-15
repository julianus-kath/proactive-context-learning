# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_124203_nonlexical_v2_process_query_scout_on_r1` (eval/runs/20260301_124203_nonlexical_v2_process_query_scout_on_r1)
- OFF run: `20260301_124351_nonlexical_v2_process_query_scout_off_aligned_r1` (eval/runs/20260301_124351_nonlexical_v2_process_query_scout_off_aligned_r1)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4038.1 | 4590.7 | -552.5999999999999 |
| p95_latency_ms | 5893.0 | 8826.0 | -2933.0 |
| expert_strict_equal_count | 1 | 1 | 0 |
| expert_same_cols_set_equal_count | 1 | 1 | 0 |
| expert_positional_set_equal_count | 1 | 1 | 0 |
| expert_common_cols_set_equal_count | 3 | 3 | 0 |
| expert_required_tables_ok_count | 9 | 13 | -4 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NL1 | success | success | 4404 | 4445 | False | False |
| NL10 | success | success | 3574 | 3943 | False | False |
| NL11 | success | success | 7021 | 4529 | False | False |
| NL12 | success | success | 3792 | 3809 | False | False |
| NL13 | success | success | 3027 | 3203 | None | None |
| NL14 | success | success | 2772 | 3347 | False | False |
| NL15 | success | success | 4230 | 4820 | False | False |
| NL16 | success | success | 5526 | 4894 | True | True |
| NL17 | success | success | 2881 | 3187 | None | None |
| NL18 | success | success | 3335 | 4205 | False | False |
| NL19 | success | success | 4194 | 8960 | None | None |
| NL2 | success | success | 5893 | 4672 | False | False |
| NL20 | success | success | 3214 | 8826 | None | False |
| NL3 | success | success | 3022 | 2925 | False | False |
| NL4 | success | success | 3085 | 2737 | False | False |
| NL5 | success | success | 4440 | 7602 | False | False |
| NL6 | success | success | 5147 | 4032 | False | False |
| NL7 | success | success | 3970 | 3721 | False | False |
| NL8 | success | success | 4820 | 5168 | False | False |
| NL9 | success | success | 2414 | 2789 | False | False |
