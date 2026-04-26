# H2b Evidence — Production Transfer to Sage / Luisi & Diener

H2b hypothesis: *The system remains operationally usable in production, generating SQL and maintaining stable answerability.*

**Benchmark size: N = 9 partner queries** (CP1–CP9), authored by the Luisi & Diener domain expert and held constant across all H2b runs. **Conditions: SDG-off and SDG-on**, the same SDG ablation used in H2a.

Two pieces of evidence drive the H2b discussion in the thesis: the full-pipeline ablation against the live Sage MSSQL ERP, and a follow-up retrieval-only study that isolates the ranker from the agent to explain the headline finding.

> **Naming note for examiners.** The thesis reports **one ablation: SDG-off vs SDG-on**. Inside the `20260415_101033_h2b_sage_sdg_label_normalization/` run below, the framework wrote the two conditions to disk under their legacy labels `scout_structural` (≡ SDG-off) and `scout_enriched_ranked` (≡ SDG-on). Directory names, JSON `mode_label` fields, and the run report use those legacy strings. They denote the same two conditions; there is no separate "Scout on/off" ablation in the thesis.

## 1) Full-pipeline ablation (the headline H2b experiment)

Single end-to-end run of the `/process_query` pipeline against Sage, against nine partner-supplied questions (CP1–CP9), under SDG-off and SDG-on. The Sage catalog was generated once on 2026-04-15 and reused in both arms.

`20260415_101033_h2b_sage_sdg_label_normalization/` — the parent run directory containing six chronologically nested phases:

| Inner subdirectory | Phase |
|---|---|
| `20260415_100955_h2b_sage_sdg/` | Service boot, mode toggling, health probes |
| `20260415_101009_h2b_sage_sdg_probe/` | `/process_query` feasibility probe |
| `20260415_101033_h2b_sage_sdg_label_normalization/` | Partner-label → live-catalog normalization (5 labels normalised, 8 exact matches, 0 unresolved) |
| `20260415_101039_h2b_cockpit_process_query_scout_structural_r1/` | **SDG-off run** (legacy directory label `scout_structural`): 9 queries through the full pipeline |
| `20260415_101220_h2b_cockpit_process_query_scout_enriched_ranked_r1/` | **SDG-on run** (legacy directory label `scout_enriched_ranked`): same 9 queries, identical pipeline |
| `20260415_101337_h2b_sage_sdg_report/` | Combined report (`report.md`, `report.json`) |

Headline finding: **required-table recall = 0/9 under both conditions**. The H2b positive signal lives in operational stability (boot, query, return, no crashes, +1 SQL-generation in SDG-ON) rather than in retrieval accuracy. The thesis frames H2b accordingly.

## 2) Retrieval-only study (follow-up investigation)

After the 0/9 result, the retrieval layer was probed in isolation to disambiguate "did the ranker fail or did the agent fail?" — by removing the agent entirely and scoring all candidate tables directly with the ranker. Two pairs of runs:

**Sage side (this directory):**
| Subdirectory | Mode | N | Top-K |
|---|---|---:|---:|
| `20260422_193658_h2b_sdg_off_sage/` | `sdg_off` | 9 (CP1–CP9) | 10 |
| `20260422_195205_h2b_sdg_on_sage/` | `sdg_on`  | 9 (CP1–CP9) | 10 |

**Northwind side (control, lives under `../H2a/`):**
| Subdirectory in `../H2a/` | Top-K |
|---|---:|
| `20260422_retrieval_only_sdg_northwind/` | 5 |
| `20260422_retrieval_only_sdg_northwind_top10/` | 10 |

The Northwind side is the validation control: if the ranker recovered acceptable recall on Northwind under retrieval-only conditions, the H2b zero is attributable to schema opacity rather than to a ranker bug. Each retrieval-only run holds `config.json`, `summary.json`, `results_raw.jsonl`, `statistical_tests.json`, `comparison_table.md`, `comparison_by_level.md`.

## Inputs and ground truth

| File | Role |
|---|---|
| `cockpit_partner_queries_v1.jsonl` | The **9 partner-supplied questions** (CP1–CP9) used in both the full-pipeline ablation and the retrieval-only follow-up. Same questions across all four runs. |
| `cockpit_partner_table_labels_v1.json` | **Partner-mapped table labels** (the "based on Urs" ground truth) — the raw, partner-supplied list of which Sage tables each CP query should hit. `verification_status: "partner_mapped_pending_expert_review"` and the `description` field identifies the partner annotator by first name. |
| `cockpit_partner_table_labels_v1.md` | Human-readable rendering of the same labels for review. |
| `cockpit_partner_table_label_overrides_v1.json` | The **alias / prefix normalisation overrides** applied during the run (5 entries). Maps partner-supplied names to live Sage catalog names: `KHKArtikelLieferanten→KHKArtikelLieferant`, `KHKBelegePositionen→KHKVKBelegePositionen`, `KHKPpsBelege→KHKPpsFaBelege`, `KHKPppsBelegeAGPositionen→KHKPpsFaBelegeAGPositionen`, `KHKPpsStempel→KHKPpsBdeStempel`. |
| `sage_descriptions.json` | Scout SDG description cache for the 943-table Sage catalog (~1 MB, used by the SDG-ON arms). The literal SDG on/off toggle for H2b — same role as `northwind_descriptions.json` in H2a. |

The **normalised** version of the partner labels (i.e. the ground truth as evaluated, after the overrides above are applied) is recorded inside the run itself at `20260415_101033_h2b_sage_sdg_label_normalization/.../cockpit_partner_table_labels_v1.normalized.json`, alongside `label_normalization.json` and `label_normalization_review.md`.

Privacy note: `cockpit_partner_table_labels_v1.json` carries the partner annotator's first name. This is the file to anonymise before any public release; the version that ships in `code/evaluation/H2b/` is intentionally the post-normalisation file (no first name) rather than the raw partner-supplied one.

## Caveats (load-bearing for the defense)

1. The Sage ground truth carries `verification_status: "partner_mapped_pending_expert_review"` — it has not been independently validated.
2. Five of thirteen partner-supplied table names were normalised post hoc to live catalog names; one (CP2: "Bestellung" → VK) is a module-knowledge edit the question itself does not justify.
3. The retrieval-only study is reported descriptively, not inferentially. Its purpose is to explain the headline 0/9, not to establish a separate effect.
