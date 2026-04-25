# ADR-0036: Ablation Axis Pivot — from Scout ON/OFF to SDG Description Enrichment

**Status**: Accepted
**Date**: 2026-04-19
**Author**: Julianus Kath
**Related**: ADR-0014, ADR-0015, ADR-0027, ADR-0035

## Context

The thesis's H2a hypothesis originally framed the ablation as *Scout Mode enabled vs. disabled*:

- `SCOUT_DISABLE=false` — Scout catalog + semantic ranking (the "ON" condition)
- `SCOUT_DISABLE=true` — a baseline path with plain lexical matching (the "OFF" condition)

This was the natural comparison when Scout was introduced (ADR-0014, ADR-0015) and it is consistent with the semantic-correctness contracts framework (ADR-0027) that assumed a Scout-vs-no-Scout baseline.

### Why the original framing collapsed

When the OFF condition was refined into an "aligned table ranker" — the same ranker as ON but with the semantic enrichment layer stripped — the two conditions became structurally near-identical on Northwind. Ablation runs produced statistically indistinguishable recall (see `eval/runs/20260328_131450_h2a_CLEAN_scout_on` and `20260328_131936_h2a_CLEAN_scout_off_aligned`).

This is a methodologically useful result — it narrows the research question — but it invalidates the ON/OFF framing as the primary ablation. The *interesting* variable is not "does Scout exist?" but "does the semantic enrichment layer change retrieval?"

This is also consistent with the schema-opacity framing of the thesis: Northwind has transparent table names, so a structural+lexical ranker already performs well; no amount of Scout machinery moves the needle on a benchmark where names leak the schema. The production regime (Sage) is where the story plays out.

## Decision

Pivot the primary H2a ablation from Scout presence to SDG description enrichment (see ADR-0035 for SDG itself). Three conditions along a monotonic exposure axis:

| Condition | Code label | Environment | Description exposure |
|---|---|---|---|
| `sdg_off` | `scout_structural` | `SCOUT_DESCRIPTIONS_ENABLED=false` | None — structural catalog only |
| `sdg_payload` | `scout_enriched` | `ENABLED=true, RANKING=false` | Descriptions in catalog + agent tool-call payload; ranker ignores them |
| `sdg_ranker` | `scout_enriched_ranked` | `ENABLED=true, RANKING=true` | Descriptions in payload AND in ranker scoring |

### Treatment of the pre-pivot ON/OFF modes

- `scout_on`, `scout_off_aligned`, `scout_off_legacy` remain in the code (in `eval/run_h2a_full_pipeline.py` and `eval/run_h2b_process_query_grounding.py`) for **replay of pre-pivot runs only**.
- These modes should be moved into an `ARCHIVED_MODE_SPECS` dict and gated behind an explicit `--include-legacy` flag so accidental invocation is impossible. (Pending implementation.)
- The thesis text refers exclusively to the SDG trio and does not present ON/OFF as an H2a finding.

### Why an ADR (and not just an experimental setup doc)?

This is a scope decision, not just an experimental convention. It changes:
- Which code paths are considered primary vs. archival.
- Which runs in `eval/runs/` are cited in the thesis.
- Which findings the thesis claims (SDG-conditional improvement vs. Scout-conditional improvement).

Those changes ripple across the codebase and the thesis narrative, so they need a durable record.

## Consequences

**Positive:**
- The ablation isolates a single variable (description enrichment) rather than a bundled change.
- Aligns the experimental setup with the actual technical contribution in ADR-0035.
- Makes H2a defensible on a schema-opacity framing: SDG is predicted to be neutral on transparent benchmarks (Northwind) and informative on opaque production schemas (Sage). Both predictions are testable against the existing datasets.
- The collapsed ON≈OFF result becomes a methodological strength when framed as a pivot, not a null finding.

**Negative:**
- Pre-pivot runs (before 2026-03) cannot be interpreted under the new framing. They are retained in `eval/runs/archived/` but not cited.
- `SCOUT_DISABLE` is vestigial for the primary ablation. Retained for replay only.
- Chapter 4 of the thesis requires rewriting to frame H2a around SDG rather than Scout presence.

**Follow-up:**
- Move `scout_on` / `scout_off_*` into `ARCHIVED_MODE_SPECS` in the eval runners (pending).
- Rewrite thesis §4 H2a framing to center SDG (pending).
- Produce retrieval-only Recall@K evidence on both datasets using the SDG trio (see `eval/run_retrieval_only_ablation.py`).
