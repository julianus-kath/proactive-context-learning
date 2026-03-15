# /process_query Scout ON vs OFF Comparison

- ON run: `20260301_122737_nonlexical_v1_process_query_scout_on_r2` (eval/runs/20260301_122737_nonlexical_v1_process_query_scout_on_r2)
- OFF run: `20260301_123314_nonlexical_v1_process_query_scout_off_legacy_r2` (eval/runs/20260301_123314_nonlexical_v1_process_query_scout_off_legacy_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate_pct | 100.0 | 100.0 | 0.0 |
| avg_latency_ms | 4344.2 | 4930.4 | -586.1999999999998 |
| p95_latency_ms | 6341.0 | 7675.0 | -1334.0 |
| expert_strict_equal_count | 1 | 2 | -1 |
| expert_same_cols_set_equal_count | 1 | 2 | -1 |
| expert_positional_set_equal_count | 1 | 2 | -1 |
| expert_common_cols_set_equal_count | 1 | 2 | -1 |
| expert_required_tables_ok_count | 9 | 13 | -4 |

| Query | ON status | OFF status | ON latency | OFF latency | ON strict | OFF strict |
|---|---|---|---:|---:|---|---|
| NL1 | success | success | 2752 | 3143 | False | False |
| NL10 | success | success | 4152 | 7675 | False | False |
| NL11 | success | success | 4162 | 4165 | False | False |
| NL12 | success | success | 6341 | 3848 | False | False |
| NL13 | success | success | 3374 | 7051 | None | False |
| NL14 | success | success | 3763 | 4036 | False | False |
| NL15 | success | success | 5164 | 5245 | False | False |
| NL16 | success | success | 6957 | 3185 | True | True |
| NL17 | success | success | 4884 | 5971 | False | True |
| NL18 | success | success | 3860 | 2686 | False | False |
| NL19 | success | success | 2795 | 4334 | None | False |
| NL2 | success | success | 3763 | 4344 | False | False |
| NL20 | success | success | 3518 | 5356 | None | False |
| NL3 | success | success | 3893 | 6008 | None | False |
| NL4 | success | success | 4796 | 5843 | False | False |
| NL5 | success | success | 4396 | 4879 | False | False |
| NL6 | success | success | 6295 | 8194 | False | False |
| NL7 | success | success | 3674 | 3625 | False | False |
| NL8 | success | success | 5410 | 5721 | False | False |
| NL9 | success | success | 2936 | 3298 | False | False |
