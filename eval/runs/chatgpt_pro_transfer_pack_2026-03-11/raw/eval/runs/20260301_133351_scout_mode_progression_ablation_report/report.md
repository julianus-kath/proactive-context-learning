# Scout Mode Progression Ablation (Process Query)

Generated: 2026-03-01T13:33:51.338876Z

## Mode Definitions
- Scout ON: `SCOUT_DISABLE=false; discovery source=scout_runner_catalog; ranking=TableRanker`
- Scout OFF aligned: `SCOUT_DISABLE=true; SCOUT_OFF_CONTROL_MODE=aligned_table_ranker; discovery source=schema_catalog; ranking=TableRanker`

## Tier Results (ON vs OFF-aligned)

| Tier | Comparison Run ID | strict Δ | same-cols Δ | positional Δ | required-tables Δ | success Δ | avg-latency Δ ms |
|---|---|---:|---:|---:|---:|---:|---:|
| T1_ambiguous | 20260301_123510_process_query_ab_ambiguous_v1_r2_on_vs_off_aligned | 0 | 0 | 0 | 0 | 0.0 | 1316.0000000000005 |
| T2_nonlexical | 20260301_124534_process_query_ab_nonlexical_v2_r1_on_vs_off_aligned | 0 | 0 | 0 | -4 | 0.0 | -552.5999999999999 |

## Hard Tier (Cross-lingual, r1-r3)

| Replicate | Comparison Run ID | strict Δ | same-cols Δ | positional Δ | required-tables Δ | avg-latency Δ ms | p95-latency Δ ms |
|---|---|---:|---:|---:|---:|---:|---:|
| r1 | 20260301_132255_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r1 | 1 | 1 | 1 | 1 | 284.60000000000036 | 2320.0 |
| r2 | 20260301_132557_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r2 | 0 | 0 | 0 | 0 | 306.5 | -37.0 |
| r3 | 20260301_133013_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r3 | 1 | 1 | 1 | 0 | -49.69999999999982 | 1423.0 |

Mean delta across r1-r3 (ON-OFF):
strict=0.6666666666666666, same-cols=0.6666666666666666, positional=0.6666666666666666, required-tables=0.3333333333333333, avg-latency-ms=180.46666666666684

## Example (ON advantage)
- Query `CL10`: Welche Kundensegmente erzeugen den höchsten Erlös nach Rabatt?
- ON has SQL: `True`; OFF has SQL: `False`
- ON tables: `['public.orders', 'public.customers', 'public.customer_customer_demo', 'public.customer_demographics']`
- OFF tables: `[]`
- OFF response excerpt: `Es scheint, dass die Datenbank keine direkten Tabellen oder Spalten für "Kundensegmente", "Erlös" oder "Rabatt" enthält. Möglicherweise sind diese Informationen in anderen Tabellen oder unter anderen Bezeichnungen gespei`

## Quota / 429 Check

- `20260301_122640_ambiguous_v1_process_query_scout_on_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_122935_ambiguous_v1_process_query_scout_off_aligned_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_124203_nonlexical_v2_process_query_scout_on_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_124351_nonlexical_v2_process_query_scout_off_aligned_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_131954_crosslingual_hard_v1_process_query_scout_off_aligned_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_132329_crosslingual_hard_v1_process_query_scout_on_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_132455_crosslingual_hard_v1_process_query_scout_off_aligned_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_132643_crosslingual_hard_v1_process_query_scout_on_r3` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
