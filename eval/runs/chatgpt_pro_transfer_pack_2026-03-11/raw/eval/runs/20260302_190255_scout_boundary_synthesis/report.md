# Scout Boundary Synthesis (No-Architecture-Change Eval)

## Scout Mode Definitions (as executed)
- Scout ON: `SCOUT_DISABLE=false` -> MCP discovery backend `ScoutRunner` (catalog source: `scout_runner_catalog`).
- Scout OFF aligned control: `SCOUT_DISABLE=true`, `SCOUT_OFF_CONTROL_MODE=aligned_table_ranker` -> backend `SchemaCatalog` with the same `TableRanker` logic.
- Therefore ON/OFF differ by catalog source backend, not by ranker implementation.

## Positive Regime Already Verified
Source: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_143236_scout_gain_segment_cl2_cl6_cl10_r1_r6/report.md`
- Paired instances: 18 (6 ON/OFF pairs x 3 queries)
- Required tables ok: ON 12/18 vs OFF 7/18 (delta +0.278 rate)
- SQL present: ON 14/18 vs OFF 10/18 (delta +0.222 rate)
- Strict equal: ON 3/18 vs OFF 2/18 (delta +0.056 rate)

Interpretation: Scout ON has a measurable retrieval/coverage advantage on this crosslingual hard segment.

## Limit Regime Deep Probe (v2)
Source aggregate: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_190154_scout_limit_probe_v2_r1_r3_analysis/report.md`
- Dataset: 18 queries (3 intents x 6 abstraction levels)
- Replicates: r1, r2, r3 -> 54 paired query-cases
- Strict equal: ON 6 vs OFF 9 (delta -3)
- Positional set equal: ON 18 vs OFF 18 (delta 0)
- Required tables ok: ON 11 vs OFF 17 (delta -6)
- SQL present: ON 28 vs OFF 32 (delta -4)

Per-level signals (delta ON-OFF):
- L1: ON clearly worse (strict -2, req -3, sql -2)
- L2/L3: near parity to slightly worse for ON
- L4: ON better in coverage proxies (pos +1, sql +1), strict tie
- L5: ON slightly better in required tables (+1), strict tie
- L6: ON mixed (pos +1, but req -2, sql -1)

Per-cluster signals (delta ON-OFF):
- CL2: ON better for positional (+2) and sql (+1), strict near tie (-1)
- CL10: ON worse across strict/pos/required (-2 each)
- CL6: ON much worse for required/sql (-4 each)

## Boundary Hypothesis (Evidence-Consistent)
Scout ON appears to help most when the query stays schema-grounded but uses paraphrased/semantic phrasing (observed in the crosslingual gain segment). It degrades when prompts introduce abstractions that are weakly anchored to actual schema fields (e.g., "customer segment/profile group/cluster" style wording), where ON more often fails SQL coverage or required-table inclusion.

## 429 / Rate-Limit Check
Across all new v2 runs (`r1-r3`, ON+OFF), no `429`/`insufficient_quota` occurrences were found in run artifacts.
