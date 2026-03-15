# Scout ON vs OFF Limit Analysis (Ladder v1, r1-r3)

- Generated (UTC): `2026-03-02T14:11:40.137470+00:00`
- Dataset: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/northwind_queries_scout_limit_ladder_v1.jsonl`
- OFF mode: `SchemaCatalog + aligned TableRanker`
- ON mode: `ScoutRunner + TableRanker`
- Pair count: `3`

| Tier | N | dReq rate | dSQL rate | dStrict rate | Coverage ON | Coverage OFF | Coverage delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 9 | -0.333 | -0.111 | -0.444 | 0.556 | 0.778 | -0.222 |
| T2 | 9 | 0.222 | 0.444 | 0.111 | 0.556 | 0.222 | 0.333 |
| T3 | 9 | -0.222 | 0.000 | -0.111 | 0.389 | 0.500 | -0.111 |
| T4 | 9 | 0.000 | 0.222 | 0.000 | 0.222 | 0.111 | 0.111 |
| T5 | 9 | 0.111 | 0.111 | 0.000 | 0.444 | 0.333 | 0.111 |

- Estimated boundary: `starts at T2 but unstable across later tiers`

Source-level notes:
- `CL2`: T1(dReq=-0.67, dSQL=0.00), T2(dReq=0.00, dSQL=0.00), T3(dReq=0.00, dSQL=0.67), T4(dReq=0.00, dSQL=0.33), T5(dReq=0.00, dSQL=0.00)
- `CL6`: T1(dReq=0.00, dSQL=0.00), T2(dReq=0.67, dSQL=0.67), T3(dReq=-0.33, dSQL=-0.33), T4(dReq=0.00, dSQL=0.00), T5(dReq=0.33, dSQL=0.33)
- `CL10`: T1(dReq=-0.33, dSQL=-0.33), T2(dReq=0.00, dSQL=0.67), T3(dReq=-0.33, dSQL=-0.33), T4(dReq=0.00, dSQL=0.33), T5(dReq=0.00, dSQL=0.00)