# Evaluation Vault — Master Thesis

This directory is the **full evidence base** for the four thesis hypotheses, organised by hypothesis. It is the working vault on disk; a curated public subset is mirrored into the GitHub release at `code/evaluation_artifacts/`.

The single ablation reported in the thesis is **SDG-off vs SDG-on** — whether the Scout catalog loads its LLM-generated table descriptions at runtime. Earlier "Scout on/off" framings and pre-SDG iterations are not reported and are kept only under the framework's `code/eval/runs/archived/` for traceability.

## Layout

| Subdir | Hypothesis | Thesis section | What's inside |
|---|---|---|---|
| [`H1/`](H1/) | Scout Mode autonomously builds a query-useful schema catalog | §5.1 | Catalog completeness on Northwind (14 tables) and Sage (943 tables) |
| [`H2a/`](H2a/) | Proactive schema grounding delivers semantic correctness (controlled) | §5.2 | SDG ablation on Northwind, N=84: table recall (retrieval-only) + semantic accuracy + L1/L2-DE extension |
| [`H2b/`](H2b/) | The system transfers to production conditions | §5.3 | SDG ablation on Sage, N=9: full-pipeline grounding + retrieval-only follow-up |
| [`H3/`](H3/) | Users derive exploratory value from the system | §5.4 | Two-participant user study: session logs, transcripts, screen recording, UTAUT/UEX questionnaire, thematic + cross-reference analysis |

Each subdirectory has its own `README.md` mapping every file to its role.

## Headline numbers, by hypothesis

| Hypothesis | Headline number | Source file |
|---|---|---|
| H1 — Northwind catalog | 14 / 14 tables (100%), 92 / 92 columns (100%), 13 / 13 FK columns (100%) | [`H1/northwind_catalog_coverage/scout_catalog_coverage.json`](H1/northwind_catalog_coverage/scout_catalog_coverage.json) |
| H1 — Sage catalog | 943 / 943 tables (100%), 13 759 / 13 759 columns (100%), 392 / 392 FK columns (100%) | [`H1/sage_catalog_coverage/scout_catalog_coverage.json`](H1/sage_catalog_coverage/scout_catalog_coverage.json) |
| H2a — Mean table recall (N=84) | 0.6052 → 0.7490 (+14.38 pp) | [`H2a/20260418_extension_report.md`](H2a/20260418_extension_report.md) §4.1 |
| H2a — Per-language (N=84) | English +0.00 pp, German +18.88 pp | [`H2a/20260418_extension_report.md`](H2a/20260418_extension_report.md) §4.2 |
| H2a — Paired Wilcoxon (N=84) | W = 163.5, p = 0.00026 (one-sided) | [`H2a/20260418_extension_report.md`](H2a/20260418_extension_report.md) §4.4 |
| H2a — Retrieval-only top-5 / top-10 | per-query candidate-ranking detail | [`H2a/20260422_retrieval_only_sdg_northwind*/summary.json`](H2a/) + `statistical_tests.json` |
| H2a — Acceptable semantic accuracy (N=84) | 47.62% (40/84) → 54.76% (46/84), +7.14 pp | [`H2a/20260418_extension_report.md`](H2a/20260418_extension_report.md) §3.3 + §4 (combined from `20260416_h2a_semantic_labels/semantic_summary.json` for the N=64 base and the L1/L2-DE delta cohort) |
| H2b — Required-table recall | 0 / 9 under both conditions | `H2b/20260415_101033_*/20260415_101039_*/grounding_eval.md` and `…101220_*/grounding_eval.md` |
| H2b — Full-pipeline ablation report | combined SDG-off vs SDG-on | `H2b/20260415_101033_*/20260415_101337_h2b_sage_sdg_report/report.md` |
| H2b — Retrieval-only Sage stats | per-query ranking probe | [`H2b/20260422_193658_h2b_sdg_off_sage/`](H2b/20260422_193658_h2b_sdg_off_sage/), [`H2b/20260422_195205_h2b_sdg_on_sage/`](H2b/20260422_195205_h2b_sdg_on_sage/) |
| H3 — UTAUT / NASA-TLX | questionnaire scores, N=2 | `H3/Results/User Study Artifacts/User Experience Assessment Framework for ERP Chatbot System(1-1).xlsx` |
| H3 — Per-turn Ref+/Ref−/Ref-NA | reconciled ground-truth labels | [`H3/Results/cross_reference_analysis/h3_Complete_Ground_Truth.reconciled.csv`](H3/Results/cross_reference_analysis/h3_Complete_Ground_Truth.reconciled.csv) |

## Datasets and ground truth

| Hypothesis | File(s) | Role |
|---|---|---|
| H2a | [`H2a/northwind_extended_difficulty_v1.jsonl`](H2a/northwind_extended_difficulty_v1.jsonl) (+ `.contracts.json`) | N=84 query benchmark |
| H2a | `H2a/northwind_queries_underspecified_v1.*` | L5 source (12 queries, with reference SQL) |
| H2a | `H2a/northwind_queries_lexical_breakpoint_v1.*` | L6 source (12 queries; thesis name: "schema-opaque", with reference SQL) |
| H2a | [`H2a/northwind_descriptions.json`](H2a/northwind_descriptions.json) | The SDG toggle for Northwind (14 LLM-generated descriptions) |
| H2b | [`H2b/cockpit_partner_queries_v1.jsonl`](H2b/cockpit_partner_queries_v1.jsonl) | The 9 partner questions (CP1–CP9) |
| H2b | [`H2b/cockpit_partner_table_labels_v1.json`](H2b/cockpit_partner_table_labels_v1.json) (+ `.md`) | Partner-mapped table labels (raw, with annotator first name) |
| H2b | [`H2b/cockpit_partner_table_label_overrides_v1.json`](H2b/cockpit_partner_table_label_overrides_v1.json) | 5-entry alias / prefix normalisation |
| H2b | `H2b/20260415_101033_*/20260415_101033_*/cockpit_partner_table_labels_v1.normalized.json` | Ground truth as evaluated (post-normalisation) |
| H2b | [`H2b/sage_descriptions.json`](H2b/sage_descriptions.json) | The SDG toggle for Sage (943 descriptions) |

## Public-release subset (mirrored into GitHub)

Not everything in this vault ships publicly. The GitHub release at `code/evaluation_artifacts/` contains:

- **H1, H2a, H2b** — complete (the runs and supporting data are PII-free).
- **H3** — only the unsigned study-design PDFs and PII-clean analysis output. Raw transcripts, session logs, signed consent form, screen recording, and ground-truth files containing participant identifiers stay private under the consent terms.

See [`H3/README.md`](H3/README.md) and `code/evaluation_artifacts/H3/README.md` for the H3-specific public-release filter and rationale.

## Cross-references

- **Audit trail.** `H2a_H2b_Evidence_Inventory_2026-04-17.md` at the master-thesis root documents every file the thesis relies on, with defense risks called out. (Pre-cleanup snapshot; some paths drifted since.)
- **Framework code.** `code/eval/` — runners (`run_h2a_full_pipeline.py`, `run_h2b_process_query_grounding.py`, `run_retrieval_only_ablation.py`), datasets, contracts, scoring.
- **Public release.** `code/evaluation_artifacts/` — curated subset + per-hypothesis READMEs ready for examiner review.
