# H2a Semantic Labels — Scout-off vs Scout-on (2026-04-14 runs)

One-pass semantic labelling of the 128 SQL-agent outputs from the April 14
Northwind N=64 evaluation. Labels are assigned per the rubric in the task
briefing: `CORRECT` / `PARTIAL` / `INCORRECT` / `ERROR`.

## Inputs

- Dataset: `eval/datasets/northwind_extended_difficulty_v1.jsonl` (64 queries, 6 difficulty levels × de/en).
- Contracts: `eval/datasets/northwind_extended_difficulty_v1.contracts.json`.
- SDG-off run: `eval/runs/20260414_095357_h2a_full64_scout_structural/` (mean recall 0.573).
- SDG-on run: `eval/runs/20260414_144359_h2a_full64_scout_enriched_ranked/` (mean recall 0.720).
- Reference SQL for L5 / L6: pre-existing `.reference_sql.json` files next to the dataset.
- Reference SQL for L1 / L2 / L3 / L4: authored here, `reference_sql_l1_l4.json`.
- Database: Postgres 16 Northwind fork at `localhost:55432/northwind` (container
  `b7122f1ad695`), connected read-only with 15 s `statement_timeout`.

## What this directory contains

| File | Content |
|------|---------|
| `label_pipeline.py` | The one-shot pipeline used to produce every output below. |
| `reference_sql_l1_l4.json` | Canonical reference SQL for the 40 queries not covered by existing files (NW1–NW10, NL1–NL10, CL1–CL12, HX1/3/4/5/7/8/9/12). |
| `reference_results.jsonl` | 64 rows. Reference SQL text, column list, full reference rowset (canonicalised), rowcount, elapsed time. |
| `semantic_labels.jsonl` | 128 rows (64 queries × 2 conditions). Fields: `query_id`, `condition`, `category`, `language`, `label`, `label_reason`, `sql_present`, `generated_rowcount`, `reference_rowcount`, `generated_rowset` (truncated to 50 rows), `generated_rowset_truncated`, `run_error`. |
| `semantic_summary.json` | Label distribution, acceptable-answer rate (CORRECT + PARTIAL), per-category / per-language breakdowns, ON–OFF delta. |

## Label distribution — full headline table

Acceptable-answer rate = (CORRECT + PARTIAL) / 64.

| Condition | CORRECT | PARTIAL | INCORRECT | ERROR | Acceptable rate |
|---|---:|---:|---:|---:|---:|
| SDG-off (`scout_structural`)       | 19 | 8 | 37 | 0 | **42.19 %** |
| SDG-on  (`scout_enriched_ranked`)  | 24 | 8 | 32 | 0 | **50.00 %** |
| **Δ (ON − OFF)**                   | +5 | 0 | −5 | 0 | **+7.81 pp** |

Compare to mean recall: SDG-off 0.573 → SDG-on 0.720 (Δ +14.7 pp). Semantic
accuracy moves less than half as far, which is expected: retrieving the right
tables is necessary but not sufficient for generating a correct query.

### Per-category breakdown

| Category (n) | SDG-off C / P / I | SDG-on C / P / I |
|---|---|---|
| direct (L1, n=10)             | 9 / 0 / 1  | 9 / 0 / 1  |
| paraphrase (L2, n=10)         | 2 / 4 / 4  | 2 / 4 / 4  |
| crosslingual (L3, n=12)       | 2 / 3 / 7  | 4 / 3 / 5  |
| complex (L4, n=8)             | 1 / 0 / 7  | 1 / 0 / 7  |
| underspecified (L5, n=12)     | 2 / 0 / 10 | 3 / 0 / 9  |
| lexical_breakpoint / schema-opaque (L6, n=12) | 3 / 1 / 8 | 5 / 1 / 6 |

ON improves L3, L5 and L6 (the German and underspecified categories, which had
the most SQL-generation failures under OFF). L1, L2 and L4 labels are unchanged
between conditions.

### Per-language breakdown

| Language | SDG-off C / P / I | SDG-on C / P / I |
|---|---|---|
| en (n=20) | 11 / 4 / 5  | 11 / 4 / 5  |
| de (n=44) | 8 / 4 / 32  | 13 / 4 / 27 |

All of ON's gain is on German queries.

### Query-level label changes (OFF → ON)

| Query         | OFF        | ON         | What changed |
|---------------|------------|------------|--------------|
| CL3           | INCORRECT  | CORRECT    | OFF failed to produce SQL; ON produced correct one. |
| CL6           | INCORRECT  | CORRECT    | Same. |
| LB_CL6_LX1    | INCORRECT  | CORRECT    | Same. |
| LB_CL6_LX2    | INCORRECT  | CORRECT    | Same. |
| US_CL3_U2     | INCORRECT  | CORRECT    | Same. |
| US_CL10_U3    | INCORRECT  | CORRECT    | Same (demographics empty → both empty). |
| US_CL10_U2    | **CORRECT** | **INCORRECT** | ON regressed — agent produced no SQL on this underspecified variant. |

Net +5 queries improved under ON.

## Labelling methodology

Labels are produced in one pass by `label_pipeline.py`, which:

1. Loads the 64-query dataset, contracts, and both agent runs.
2. Executes all 64 reference SQLs once; stores rowsets to `reference_results.jsonl`.
3. For each of 128 agent outputs, executes the generated SQL (if `sql_present=True` and `error` is not recorded).
4. Compares rowsets using the projection-based rubric below.

### Value canonicalisation

Before any comparison, each cell is canonicalised:

- Numbers rounded to 6 decimals (2 decimals inside the fingerprint).
- `date` objects rendered as `YYYY-MM-DD` ISO.
- `datetime` objects whose time component is exactly midnight collapse to date-only.
- Strings stripped. Strings of the form `YYYY-MM-DDT00:00:00…` also collapse
  to the date — handles agents that return `TO_CHAR(...)` or timestamps for
  date groupings.

### Row matching with subset tolerance

Row-level equality is judged on two multisets per row:

- `text_ms(r)` = multiset of non-empty string values (lower-cased).
- `num_ms(r)` = multiset of numeric values rounded to 2 dp.

A generated row is considered to match a reference row when **both**
`text_ms(gen) ⊆ text_ms(ref)` (or vice versa) **and** `num_ms(gen) ⊆ num_ms(ref)`
(or vice versa), with at least one side carrying signal. This absorbs the
two most common column-level differences:

- Agent omits an ID column that reference carries (`(name, revenue)` vs `(id, name, revenue)`).
- Agent returns only IDs, reference carries IDs plus names (`(id, revenue)` vs `(id, name, revenue)`).

It does not absorb off-by-one COUNTs, different SUMs, or repeated-value tricks
(e.g. an agent that projects the same aggregate into two columns).

### Rowset labelling

Given greedy pairwise row matching (each ref row consumed at most once):

- All rows matched bidirectionally, all pairs `exact` → **CORRECT**. If reference query is ordered and the matched indices are not `[0, 1, 2, …]`, downgrade to PARTIAL ("ordering differs / tie-breaking").
- All rows matched bidirectionally with subset differences (column projection only) → **CORRECT** (rubric permits column-selection differences).
- All agent rows matched but some reference rows unmatched and agent is smaller → **PARTIAL** ("top-N subset" or "filtered subset").
- All reference rows matched but agent has extras → **PARTIAL** ("agent broader").
- ≥80 % row coverage on both sides → **PARTIAL**.
- ≥50 % row coverage on both sides → **PARTIAL** (weak).
- Single-row aggregate: numeric/text multisets equal or within 0.5 % tolerance → CORRECT; half-overlap → PARTIAL; otherwise INCORRECT.
- Agent emitted no SQL → **INCORRECT** (rubric).
- Agent SQL raises a DB error → **INCORRECT** with the error quoted.
- Source run artifact carries `error` → **ERROR**.
- Otherwise → **INCORRECT** with counts printed.

No REFERENCE_CHECK_UNAVAILABLE bucket is introduced. No `UNCLEAR` /
`UNEVALUATED`. Every row has a non-empty `label_reason`.

## Spot-check log

Five rows were picked with a fixed seed and re-verified by hand. All held.

| # | Query | Condition | Label | Verdict |
|---|-------|-----------|-------|---------|
| 1 | LB_CL3_LX3 | SDG-off | INCORRECT | `sql_present=false`. Agent gave up. ✓ |
| 2 | CL4        | SDG-off | PARTIAL   | Agent `LIMIT 5` on an open-ended ranking query; its 5 rows are the correct top 5, reference returns all 9. ✓ |
| 3 | CL4        | SDG-on  | PARTIAL   | Same as above. Reasonable. ✓ |
| 4 | US_CL6_U2  | SDG-off | INCORRECT | `sql_present=false`. Agent gave up. ✓ |
| 5 | US_CL2_U3  | SDG-off | INCORRECT | Agent grouped by `product_id` instead of `country`; top-5 by revenue, different dimension from the reference reading. ✓ |

## Edge cases, caveats and queries flagged for human review

Empty demographics:
: `customer_demographics` and `customer_customer_demo` are both empty in this
  Northwind build. Any query that depends on them — CL10, US_CL10_U*, LB_CL10_LX* —
  has a reference rowset of 0. An agent that produced a syntactically correct
  demographics-joined query also returns 0 rows and is scored CORRECT under the
  "both empty" clause. An agent that produced no SQL, or chose a fallback
  grouping (e.g. country), is scored INCORRECT.

Ambiguous readings that are labelled INCORRECT but the thesis author may want to review as PARTIAL:
- **NL5 (both conditions)**: "average basket values by buyer location". Reference averages per-order totals by country; SDG-on agent averages per-line-item revenue by country, which is a defensible alternate metric.
- **NL8 (both conditions)**: agent's `AVG(shipped_date - required_date)` includes on-time shipments (producing negative averages). Reference restricts the average to late shipments. Agent's reading is arguably the literal phrase "how late on average".
- **LB_CL3_LX1 (SDG-on)**: agent uses late *rate* (`AVG(CASE ... THEN 1 ELSE 0 END)`) as primary sort; reference uses *avg days late*. German "im Schnitt am häufigsten verspätet" literally asks about frequency, which arguably favours the agent's reading.
- **US_CL2_U2 (SDG-off)**: agent groups by `ship_region` (mostly NULL) instead of customer country. Weakly defensible interpretation of "Märkte" but heavily biased by the NULL bucket.
- **US_CL6_U1 (SDG-on)**: agent reports on-time percentage; reference reports late count. Both are defensible for "Pünktlichkeit".

Methodology bugs that cause NW7 to be INCORRECT in both conditions:
- Agent adds a stricter filter `od1.product_id < od2.product_id` on top of
  `s1.supplier_id < s2.supplier_id`. This drops pairs where product and
  supplier orderings disagree, shaving 1–2 off the correct co-order count for
  most of the top-10 pairs. Per the question's explicit spec (which
  enumerates the join predicates), the agent deviates from the contract and
  the label stands at INCORRECT.

CL12 freight-ratio mismatch:
- Agent (both conditions) sums `freight` after joining with `order_details`,
  inflating freight by the number of line items per order. Reference
  pre-aggregates freight per order before summing. Resulting ratios are ~3×
  off. Interpreted as a methodology bug, not an ambiguity.

## Reproducing

```bash
# Required: Docker postgres:16 Northwind container running on :55432.
cd <repo>/code/eval/runs/20260416_h2a_semantic_labels
python3 label_pipeline.py
```

Runtime: ~20 s wall-clock on the author's machine (all SQL is short; the
15 s `statement_timeout` was not hit on any query).
