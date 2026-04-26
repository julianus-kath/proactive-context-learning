# Evaluation Framework

A standalone, non-intrusive evaluation harness for the SQL Agent + Scout Mode + MCP system. Drives the four thesis hypotheses end-to-end.

> **The single ablation reported in the thesis is SDG-off vs SDG-on.** The toggle is whether the Scout catalog loads `cache/northwind_descriptions.json` (or `cache/sage_descriptions.json` for H2b) at runtime — when present, the 14 (Northwind) or 943 (Sage) LLM-generated table descriptions are used by the ranker; when absent, the ranker falls back to structural signals only.
>
> Earlier framework artefacts compared "Scout on" against "no Scout at all" or had a three-mode framing (`scout_structural` / `scout_enriched` / `scout_enriched_ranked`). **Those framings are not reported in the thesis.** Pre-SDG runs are kept under `runs/archived/` and `archived_scripts/` for traceability and reproducibility, but they are deprecated and not the headline evidence. Where SDG-era runs use the legacy strings `scout_structural` and `scout_enriched_ranked` in their on-disk labels, those map 1:1 to **SDG-off** and **SDG-on** respectively.

---

## Post-consolidation layout (as of 2026-04-14)

On 2026-04-14 the eval directory was consolidated. Pre-SDG scripts, datasets, runs, and docs were moved into `archived_*` / `runs/archived/`; only the artefacts driving the current SDG ablation remain at the top level.

```
eval/
├── README.md                            # this file
├── SDG_ABLATION_EXPERIMENTAL_SETUP.md   # canonical experimental design
├── SDG_EVALUATION_RUNBOOK.md            # how to run SDG-era evaluations
├── contracts.py                         # ground-truth contract definitions
├── eval_client.py                       # instrumentation client
├── service.py                           # eval tracking service
├── run_h2a_full_pipeline.py             # H2a (Northwind) runner
├── run_h2b_process_query_grounding.py   # H2b (Cockpit/Sage) runner
├── run_retrieval_only_ablation.py       # retrieval-only probe (Northwind + Sage)
├── generate_descriptions.py             # SDG description generation
├── datasets/
│   ├── northwind_extended_difficulty_v1.{jsonl,contracts.json}     # H2a, N=84 after the L1/L2-DE extension
│   ├── northwind_queries_underspecified_v1.*                       # L5 source
│   ├── northwind_queries_lexical_breakpoint_v1.*                   # L6 source — see naming note below
│   ├── northwind_pilot_n10_v1.jsonl                                # SDG pilot, N=10
│   ├── cockpit_partner_queries_v1.jsonl                            # H2b, N=9
│   ├── cockpit_partner_table_labels_v1.{json,md}                   # H2b ground truth (partner-mapped)
│   ├── cockpit_partner_table_label_overrides_v1.json               # 5-entry alias / prefix normalisation
│   └── archived/                        # 58 superseded datasets — DEPRECATED, not reported
├── runs/
│   ├── 20260414_*_h2a_full64_scout_*               # H2a SDG ablation runs (full pipeline, 64-query) — see naming note below
│   ├── 20260416_h2a_semantic_labels                # H2a semantic accuracy
│   ├── 20260418_*_h2a_de_l1l2_scout_*              # H2a German L1/L2 extension (20 queries)
│   ├── 20260415_101033_h2b_sage_sdg_label_normalization     # H2b full-pipeline ablation
│   ├── 20260422_*_retrieval_only_sdg_northwind*    # H2a retrieval-only (top-5, top-10)
│   ├── 20260422_*_h2b_sdg_*_sage                   # H2b retrieval-only follow-up
│   └── archived/                        # 302 pre-SDG runs — DEPRECATED, not reported in the thesis
├── cache/                               # SDG description cache (generated; not in git)
├── archived_scripts/                    # retired scripts — DEPRECATED, not reported
└── archived_docs/                       # retired design docs — DEPRECATED, not reported
```

### Naming notes

- **SDG-off / SDG-on terminology.** Some runs in `runs/` were generated before the rename to SDG terminology and label their on-disk artefacts with the legacy strings `scout_structural` and `scout_enriched_ranked`. These are the same conditions the thesis reports as **SDG-off** and **SDG-on** respectively. There is no separate "Scout on/off" ablation in this thesis.
- **`lexical_breakpoint` vs "schema-opaque".** The L6 dataset files and the `category` field inside `northwind_extended_difficulty_v1.jsonl` are named `lexical_breakpoint` for historical reasons. Thesis prose uses the synonym **schema-opaque**. Filenames are not renamed because the contracts files reference them.

### Deprecated content (kept for traceability only)

These directories contain runs and scripts that were superseded by the SDG-era methodology and are **not reported in the thesis**:

- `runs/archived/` — 302 pre-SDG runs (multi-agent orchestration era, March 2026 and earlier, "Scout on vs Scout off" framing).
- `datasets/archived/` — 58 superseded datasets that fed the pre-SDG runs.
- `archived_scripts/` — retired scoring scripts and old runners.
- `archived_docs/` — retired design documents.

A reviewer auditing reproducibility can still execute these, but the headline evidence of the thesis is in the non-archived runs above and in the curated public subset at `evaluation_artifacts/` (master-thesis root) and `code/evaluation_artifacts/` (release-shipping).
