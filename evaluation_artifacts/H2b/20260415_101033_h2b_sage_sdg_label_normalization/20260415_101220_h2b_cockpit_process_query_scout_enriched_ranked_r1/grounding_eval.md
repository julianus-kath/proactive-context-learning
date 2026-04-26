# H2b /process_query Grounding Evaluation

- Generated: `2026-04-15T10:13:36.570509Z`
- Run dir: `C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\eval\runs\20260415_101220_h2b_cockpit_process_query_scout_enriched_ranked_r1`
- Labels: `C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\eval\runs\20260415_101033_h2b_sage_sdg_label_normalization\cockpit_partner_table_labels_v1.normalized.json`
- Required stage traces: `discovery, ranked`

## Summary

- Number of queries: `9`
- Mean required-table recall: `0.0`
- Queries with all required tables surfaced: `0`
- SQL present count: `7`
- SQL execution success count: `6`
- Median latency: `6876.0`
- Policy violations: `0`

| Query | Required recall | All required ok | SQL present | SQL exec ok | Trace complete | Missing required |
|---|---:|---|---|---|---|---|
| CP1 | 0.000 | False | True | True | True | khkartikel, khkartikellieferant, khkartikelvarianten |
| CP2 | 0.000 | False | True | False | True | khkvkbelege, khkvkbelegepositionen |
| CP3 | 0.000 | False | True | True | True | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel |
| CP4 | 0.000 | False | True | True | True | osemzizzebuchungen |
| CP5 | 0.000 | False | True | True | True | osemzizzebuchungen, khkppsbdestempel |
| CP6 | 0.000 | False | True | True | True | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager |
| CP7 | 0.000 | False | True | True | True | khkbuchungserfassung |
| CP8 | 0.000 | False | False | None | True | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel |
| CP9 | 0.000 | False | False | None | True | osemzizzebuchungen, khkppsbdestempel, khkppsfabelege, khkppsfabelegeagpositionen |

## Scoring Rule

A required table is counted as surfaced with precedence: `final_sql` -> `ranked` -> `discovery`.
