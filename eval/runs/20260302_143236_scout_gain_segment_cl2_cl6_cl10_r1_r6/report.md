# Scout Gain Segment Analysis (CL2, CL6, CL10)

- Generated at (UTC): `2026-03-02T13:32:36.092506+00:00`
- Segment source: `eval/datasets/northwind_queries_crosslingual_hard_v1.jsonl`
- OFF mode: `SchemaCatalog + aligned TableRanker`
- ON mode: `ScoutRunner catalog + TableRanker`
- Total paired instances: `18` (6 pairs x 3 queries)

| Metric (segment-level) | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| Required tables ok | 12 (0.667) | 7 (0.389) | 0.278 |
| Strict equal | 3 (0.167) | 2 (0.111) | 0.056 |
| SQL present | 14 (0.778) | 10 (0.556) | 0.222 |

Interpretation:
- This segment shows a substantial ON advantage in retrieval/coverage proxies (`required_tables_ok`, `sql_present`).
- Strict equality gain is positive but smaller, indicating SQL formulation remains a shared bottleneck.

Pair references:
- ON `20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1` vs OFF `20260301_131954_crosslingual_hard_v1_process_query_scout_off_aligned_r1` (comparison `20260301_132255_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r1`)
- ON `20260301_132329_crosslingual_hard_v1_process_query_scout_on_r2` vs OFF `20260301_132455_crosslingual_hard_v1_process_query_scout_off_aligned_r2` (comparison `20260301_132557_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r2`)
- ON `20260301_132643_crosslingual_hard_v1_process_query_scout_on_r3` vs OFF `20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3` (comparison `20260301_133013_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r3`)
- ON `20260302_071150_crosslingual_hard_v1_process_query_scout_on_r4` vs OFF `20260302_071346_crosslingual_hard_v1_process_query_scout_off_aligned_r4` (comparison `20260302_080208_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r4`)
- ON `20260302_071600_crosslingual_hard_v1_process_query_scout_on_r5` vs OFF `20260302_071708_crosslingual_hard_v1_process_query_scout_off_aligned_r5` (comparison `20260302_080208_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r5`)
- ON `20260302_132718_crosslingual_hard_v1_process_query_scout_on_r6` vs OFF `20260302_132916_crosslingual_hard_v1_process_query_scout_off_aligned_r6` (comparison `20260302_133109_process_query_ab_crosslingual_hard_v1_on_vs_off_aligned_r6`)