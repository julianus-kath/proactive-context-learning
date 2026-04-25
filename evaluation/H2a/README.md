# H2a Evidence — Controlled Ablation on Northwind

H2a hypothesis: *Proactive schema grounding via Scout Mode delivers semantic correctness under controlled benchmark conditions.*

Independent variable: `SCOUT_DESCRIPTIONS_ENABLED` (and, in the third arm, `SCOUT_DESCRIPTIONS_RANKING`). Everything else is held constant: same dataset, same prompt, same model, same retrieval depth.

Primary evidence: three-mode ablation on the 64-query extended difficulty set, plus a semantic accuracy spot-check, plus a German-only L1/L2 extension, plus a retrieval-only ablation that bypasses the LLM. These figures populate Tables 5.2–5.5 and Figures 5.1–5.3 in Thesis §5.2.

## Three-mode ablation, N=64 (Apr 14)

| Mode | Subdirectory | Mean recall | SQL gen rate | Perfect / 64 | Zero / 64 |
|---|---|---:|---:|---:|---:|
| `scout_structural` (SDG off) | `20260414_h2a_full64_scout_structural/` | 0.5729 | 0.6719 | 28 | 21 |
| `scout_enriched` (SDG payload only) | `20260414_h2a_full64_scout_enriched/` | 0.6372 | 0.7344 | 31 | 17 |
| `scout_enriched_ranked` (SDG payload + ranker) | `20260414_h2a_full64_scout_enriched_ranked/` | 0.7201 | 0.7969 | 37 | 13 |

Total recall lift structural → enriched_ranked: **+14.72 pp**. Wilcoxon paired test on the per-query recall vector is in `h2a_wilcoxon_recall.json`.

The ranker arm contributes the bigger lift on the underspecified (L5) and schema-opaque (L6) German categories; the payload arm contributes most of the crosslingual (L3) lift. Per-category and per-language breakdowns are in each run's `summary.json`.

## Semantic accuracy, N=64 (Apr 16)

Single-coder rubric pass over the same 64 queries comparing SDG-off vs SDG-on agent answers against expert-authored reference SQL.

| Mode | Correct | Partial | Incorrect | Acceptable rate |
|---|---:|---:|---:|---:|
| SDG-off | 19 | 8 | 37 | 0.4219 |
| SDG-on  | 24 | 8 | 32 | 0.5000 |

Acceptable-rate delta: **+7.81 pp**. Spot-check log of borderline cases is in `20260416_h2a_semantic_labels/README.md`. Five queries are flagged as defensible re-codes; the delta survives them but should be read as rubric-sensitive rather than ground-truth.

## German L1/L2 extension, N=20 (Apr 18)

Adds a German translation of the L1 (direct) and L2 (paraphrase) categories to disentangle the language effect from the difficulty effect. Same three-mode design, same model.

| Subdirectory | Role |
|---|---|
| `20260418_h2a_de_l1l2_scout_structural/` | SDG-off baseline on the German L1/L2 extension |
| `20260418_h2a_de_l1l2_scout_enriched_ranked/` | SDG-on (payload + ranker) on the same 20 queries |
| `20260418_h2a_de_l1l2_semantic_labels/` | Single-coder semantic accuracy pass over the extension |
| `20260418_extension_report.md` | Combined report and statistical commentary |

## Retrieval-only ablation, top-5 and top-10 (Apr 22)

Bypasses the LLM agent entirely and measures retrieval quality directly: the ranker scores all candidate tables for each query and we report whether the required tables fall in the top-K. This isolates the SDG signal from any agent-side variance.

| Subdirectory | Cutoff |
|---|---|
| `20260422_retrieval_only_sdg_northwind/` | top-5 |
| `20260422_retrieval_only_sdg_northwind_top10/` | top-10 |

## Inputs and ground truth

| File | Role |
|---|---|
| `northwind_extended_difficulty_v1.jsonl` | The 64-query dataset (six difficulty levels: L1 direct, L2 paraphrase, L3 crosslingual, L4 complex, L5 underspecified, L6 schema-opaque/`lexical_breakpoint`) |
| `northwind_extended_difficulty_v1.contracts.json` | Required tables per query, derived from the reference SQL |
| `northwind_queries_underspecified_v1.reference_sql.json` | Expert-written reference SQL for the L5 set |
| `northwind_queries_lexical_breakpoint_v1.reference_sql.json` | Expert-written reference SQL for the L6 set |
| `northwind_descriptions.json` | The Scout SDG description cache used at runtime |
| `h2a_wilcoxon_recall.json` | Paired Wilcoxon test on per-query recall (structural vs enriched_ranked) |

The `lexical_breakpoint` filename uses the historical category label; the thesis prose uses the synonym **schema-opaque**. Names are never renamed because the contract files reference them.

## Files per run directory

- `config.json` — model, mode flags, dataset path, cache path, run timestamp
- `summary.json` — aggregate recall + per-category + per-language breakdown
- `results_raw.jsonl` — one line per query: predicted tables, required tables, generated SQL, latency

The semantic-labels run directories additionally hold `label_pipeline.py`, `reference_results.jsonl`, `semantic_labels.jsonl`, `semantic_summary.json`, and a README with the rubric and spot-check log.

## Caveats (load-bearing for the defense)

1. **The SDG prompt pre-engineers a German vocabulary bridge.** `description_generator.py` instructs the LLM to produce a "First line: German business name + English translation in parentheses" and to surface "Common German business terms that would refer to this table's data." Most of the H2a recall lift on German queries is therefore at least partly mechanical: SDG rewrites the schema into the query language. The thesis frames the delta as *vocabulary alignment*, not *semantic understanding*.

2. **Ranking is substring containment plus heuristic boosts.** The "description_match" ranker score is a literal substring test (lowercased) of query entities against the description, weighted 0.4. It is not embedding-based semantic similarity. Sage-tuned regex boosts (e.g., +0.5 for "verkauf" / "auftrag" / "umsatz" name tokens) also fire during the Northwind run, contributing a non-SDG floor to the German numbers.

3. **Difficulty and language covary by design.** L1/L2 are English; L3–L6 are German. The "harder queries benefit more" reading conflates the language effect with the difficulty effect. The April 18 L1/L2-DE extension was added specifically to break this conflation; see `20260418_extension_report.md`.

4. **Northwind description cache is linguistically inconsistent.** The 14 generated descriptions all open with the bilingual first line, but the body prose is sometimes German and sometimes English depending on the LLM's choice. The vocabulary bridge it provides is therefore leaky.

5. **The semantic accuracy pass is single-coder.** The +7.81 pp acceptable-rate delta survives the borderline re-codes flagged in the spot-check log, but it has not been independently rubric-validated.
