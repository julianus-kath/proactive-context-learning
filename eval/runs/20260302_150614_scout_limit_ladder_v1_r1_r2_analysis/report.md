# Scout ON vs OFF Limit Analysis (Ladder v1, r1+r2)

- Generated (UTC): `2026-03-02T14:06:14.683330+00:00`
- Dataset: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/northwind_queries_scout_limit_ladder_v1.jsonl`
- OFF mode: `SchemaCatalog + aligned TableRanker`
- ON mode: `ScoutRunner + TableRanker`

| Tier | N | Req ON | Req OFF | Delta Req Rate | SQL ON | SQL OFF | Delta SQL Rate | Strict ON | Strict OFF | Delta Strict Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 6 | 2 | 3 | -0.167 | 4 | 5 | -0.167 | 0 | 2 | -0.333 |
| T2 | 6 | 1 | 0 | 0.167 | 5 | 3 | 0.333 | 0 | 0 | 0.000 |
| T3 | 6 | 2 | 3 | -0.167 | 4 | 3 | 0.167 | 2 | 2 | 0.000 |
| T4 | 6 | 0 | 0 | 0.000 | 3 | 1 | 0.333 | 0 | 0 | 0.000 |
| T5 | 6 | 1 | 0 | 0.167 | 5 | 4 | 0.167 | 0 | 0 | 0.000 |

- Breakpoint (req+sql heuristic): `T5`
- Interpretation:
  - `T1` is lexical/direct; OFF is competitive or slightly better here.
  - `T2+` shifts toward paraphrase/implicit framing; ON gains on retrieval/SQL coverage in this run set.
  - Strict exact-result parity remains noisy and low in higher tiers for both modes.