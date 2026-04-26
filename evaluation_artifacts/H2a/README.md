# H2a Evidence — Controlled SDG Ablation on Northwind

H2a hypothesis: *Proactive schema grounding via Scout Mode delivers semantic correctness under controlled benchmark conditions.*

**Benchmark size: N = 84 Northwind queries** (20 English + 64 German), spread over six difficulty levels L1–L6, with English and German arms at L1 and L2 only (L3–L6 are German-only). The benchmark was extended on 2026-04-18 from the original 64 queries by adding 20 German L1/L2 queries to disentangle language from difficulty (see [`20260418_extension_report.md`](20260418_extension_report.md) §1).

**Conditions: SDG-OFF and SDG-ON.** SDG (Semantic Description Generation) is the independent variable. The on/off toggle is the literal presence of `northwind_descriptions.json` in the Scout catalog at runtime — everything else (dataset, prompt, model, retrieval depth) is held constant.

## The two headline results (cited in the thesis)

| Result | Subdirectory | Role |
|---|---|---|
| **Table recall** — retrieval-only ablation, agent removed from the loop | [`20260422_retrieval_only_sdg_northwind/`](20260422_retrieval_only_sdg_northwind/) | top-5 retrieval cutoff |
| | [`20260422_retrieval_only_sdg_northwind_top10/`](20260422_retrieval_only_sdg_northwind_top10/) | top-10 retrieval cutoff |
| **Semantic accuracy** — single-coder rubric pass against expert reference SQL | [`20260416_h2a_semantic_labels/`](20260416_h2a_semantic_labels/) | SDG-off vs SDG-on answer-correctness comparison |

> **Naming note for examiners.** The thesis reports **one ablation: SDG-off vs SDG-on**. Some preserved framework artefacts inside `20260416_h2a_semantic_labels/` use the legacy strings `scout_structural` (≡ SDG-off) and `scout_enriched_ranked` (≡ SDG-on) in the per-row `condition` field. These are the same two conditions under different labels — there is no separate "Scout on/off" ablation in this thesis. Earlier framework runs that compared Scout-vs-no-Scout are not reported and are kept only under `code/eval/runs/archived/` for traceability.

Why retrieval-only for table recall: the ranker is scored directly against the required-table contracts without any agent in the loop, so the recall delta reflects the ranker (and SDG-cache) signal cleanly, with no LLM-side decoding variance.

Each retrieval-only run holds:
- `config.json` — experiment settings (mode, top_k, query_ids)
- `summary.json` and `summary_by_level.json` — aggregate + per-difficulty-level recall
- `results_raw.jsonl` — one line per query: candidate ranking, required tables, hit/miss
- `statistical_tests.json` — paired test on per-query recall
- `comparison_table.md`, `comparison_by_level.md` — human-readable rollups

The semantic-labels run additionally holds `label_pipeline.py`, `reference_results.jsonl`, `semantic_labels.jsonl`, `semantic_summary.json`, `reference_sql_l1_l4.json`, and a README documenting the rubric and spot-check log.

Statistical companion (top-level): [`h2a_wilcoxon_recall.json`](h2a_wilcoxon_recall.json) — paired Wilcoxon test on per-query recall for the headline contrast.

## Supplementary — L1/L2-DE extension

Working directory for the German-translation extension of the L1 and L2 categories. The extension was added to disambiguate the "harder queries benefit more" narrative: the original difficulty levels conflate language with difficulty (L1/L2 are English; L3–L6 are German), so translating L1/L2 to German isolates the language effect from the difficulty effect.

| File / dir | Role |
|---|---|
| [`20260418_de_l1l2_drafts/`](20260418_de_l1l2_drafts/) | Scripts (`filter_to_de_l1l2.py`, `append_canonical.py`, `label_delta.py`, `combined_analysis.py`), the extracted `de_l1l2_only.{jsonl,contracts.json}` subset, `combined_summary.json`, and pre-extension backups of the canonical files |
| [`20260418_extension_report.md`](20260418_extension_report.md) | Combined report on the extension (numbers + commentary) |

## Inputs and ground truth

The SDG-OFF and SDG-ON conditions share **identical** dataset and contracts; the only thing that changes between them is whether `northwind_descriptions.json` is loaded into the Scout catalog at runtime. That cache file is therefore the literal SDG on/off toggle.

| File | Role |
|---|---|
| [`northwind_extended_difficulty_v1.jsonl`](northwind_extended_difficulty_v1.jsonl) | The N=84 benchmark dataset (six difficulty levels: L1 direct, L2 paraphrase, L3 crosslingual, L4 complex, L5 underspecified, L6 schema-opaque; L1 and L2 split into English and German arms). Same dataset for **all** N=84 H2a runs. The 2026-04-16 semantic-labels run used the pre-extension N=64 subset (no L1/L2 German); the L1/L2-DE delta cohort was added on 2026-04-18 — see the extension report. |
| [`northwind_extended_difficulty_v1.contracts.json`](northwind_extended_difficulty_v1.contracts.json) | Required tables per query, derived from the reference SQL. Same for both conditions. |
| [`northwind_descriptions.json`](northwind_descriptions.json) | **The SDG cache.** Present in the catalog → SDG ON; absent → SDG OFF. The 14 LLM-generated table descriptions, with bilingual (German + English) first lines, used in the SDG-ON arms. |
| [`northwind_queries_underspecified_v1.jsonl`](northwind_queries_underspecified_v1.jsonl) (+ `.contracts.json`, `.reference_sql.json`) | Source for the L5 category (12 queries). The `.reference_sql.json` is the expert-written ground-truth SQL the semantic-accuracy rubric pass scores answers against. |
| [`northwind_queries_lexical_breakpoint_v1.jsonl`](northwind_queries_lexical_breakpoint_v1.jsonl) (+ `.contracts.json`, `.reference_sql.json`) | Source for the L6 (schema-opaque / `lexical_breakpoint`) category (12 queries). Same role as L5. |

Naming note: dataset filenames use the historical category label `lexical_breakpoint`; thesis prose uses the synonym **schema-opaque**. Filenames not renamed because the contracts files reference them.

## Cross-reference to H2b

A parallel retrieval-only study was run on Sage to investigate the H2b zero-recall finding. That sibling study lives in [`../H2b/`](../H2b/) — see `H2b/README.md` for the cross-link. The Northwind retrieval-only runs in this directory are the H2a-side of that paired methodology.
