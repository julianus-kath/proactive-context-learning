# Ablation Study Master Summary (as of 2026-03-11)

This file consolidates the ablation work done so far across controlled Northwind studies and production-oriented cockpit studies.

## 1. Purpose and Scope

The ablation work was designed to answer one central question: **what exactly changes when Scout mode is ON vs OFF, and when do those changes help or hurt retrieval and end-to-end behavior?**

The work was split into:

- **H1-oriented controlled retrieval tests** (table retrieval quality).
- **H2a-oriented controlled end-to-end tests** via `/process_query` on Northwind (SQL generation + result correctness proxies).
- **H2b-oriented production-style retrieval tests** on cockpit questions with partner-provided required tables (no full SQL ground truth yet).

H3 (user value/acceptance) was not re-run in these ablation loops; only supporting context was gathered.

---

## 2. Mode Definitions Used in Ablations

### 2.1 ON vs OFF aligned (catalog-source ablation)

- **Scout ON**:
  - `SCOUT_DISABLE=false`
  - Catalog source: `ScoutRunner` / `scout_runner_catalog`
  - Ranking strategy: `TableRanker`
- **Scout OFF aligned**:
  - `SCOUT_DISABLE=true`
  - `SCOUT_OFF_CONTROL_MODE=aligned_table_ranker`
  - Catalog source: `SchemaCatalog` / `schema_catalog`
  - Ranking strategy: `TableRanker`

Interpretation: this isolates catalog source more than ranker logic.

### 2.2 OFF legacy (lexical baseline)

- **Scout OFF legacy**:
  - `SCOUT_DISABLE=true`
  - `SCOUT_OFF_CONTROL_MODE=legacy_lexical_schema_linking`
  - Catalog source: `SchemaCatalog` / `schema_catalog`
  - Ranking strategy: `LexicalSchemaLinkingBaseline` (rule-based lexical linker)

Interpretation: this changes both retrieval strategy and ranking behavior compared with ON.

---

## 3. Datasets Used (Controlled + Production)

### 3.1 Northwind controlled datasets

- `northwind_queries.jsonl` (n=10)
- `northwind_queries_more_v1.jsonl` (n=30)
- `northwind_queries_ambiguous_v1.jsonl` (n=10)
- `northwind_queries_nonlexical_v1.jsonl` (n=20)
- `northwind_queries_crosslingual_hard_v1.jsonl` (n=12)
- `northwind_queries_complex_hard_v1.jsonl` (n=15)
- `northwind_queries_scout_gain_segment_v1.jsonl` (n=3)
- `northwind_queries_scout_limit_ladder_v1.jsonl` (n=15)
- `northwind_queries_scout_limit_probe_v2.jsonl` (n=18)
- `northwind_queries_lexical_breakpoint_v1.jsonl` (n=12)
- `northwind_queries_underspecified_v1.jsonl` (n=12)
- `northwind_queries_scout_advantage_v1.jsonl` (n=9)
- `northwind_queries_on_edge_v1.jsonl` (n=3)

### 3.2 Production-oriented cockpit dataset

- `cockpit_partner_queries_v1.jsonl` (n=9)
- `cockpit_partner_table_labels_v1.json` (n=9 query labels)

Label summary:
- Unique labeled required tables: 13
- Required tables per query: 1 to 4

---

## 4. H1: Controlled Retrieval Results

## 4.1 Early ambiguous retrieval ablation (before full alignment)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260222_214600_ambiguous_v1_scout_ablation/comparison.md`

Runs:
- ON: `20260222_214527_ambiguous_v1_retrieval_scout_on_pg_v2`
- OFF: `20260222_214536_ambiguous_v1_retrieval_scout_off_pg_v2`

Aggregate:
- Mean Recall@5: ON 0.7083 vs OFF 0.8950 (OFF +0.1867)
- Mean Recall@10: ON 0.7083 vs OFF 0.9350 (OFF +0.2267)
- MRR: ON 0.8000 vs OFF 0.9200 (OFF +0.1200)

This was the first strong sign that ON and OFF were not using equivalent ranking paths.

## 4.2 Alignment audit (ranker-aligned ON/OFF retrieval)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_054125_scout_alignment_audit_v4/comparison.md`

Key result (ambiguous v1 retrieval, aligned ranker):
- ON and OFF became identical on aggregate retrieval metrics:
  - Mean Recall@5: 0.8950 vs 0.8950
  - Mean Recall@10: 0.9350 vs 0.9350
  - MRR: 0.8033 vs 0.8033

Interpretation:
- A large part of earlier divergence came from ranking path differences, not only from catalog source.

---

## 5. H2a: Controlled End-to-End `/process_query` Results (Northwind)

## 5.1 Progression report (ON vs OFF aligned)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260301_133351_scout_mode_progression_ablation_report/report.md`

Tier summary:
- `T1_ambiguous`: near parity on strict/same-cols/positional/required-tables
- `T2_nonlexical`: ON worse on required-tables (delta -4)

Hard tier (`crosslingual_hard_v1`, r1-r3 mean deltas ON-OFF):
- strict +0.67
- same-cols +0.67
- positional +0.67
- required-tables +0.33

## 5.2 Aggregate across controlled hard sets (ON vs OFF aligned, r1-r5)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_090413_process_query_on_off_aligned_r1_r5_aggregate/report.md`

`crosslingual_hard_v1` (5 pairs):
- Strict equal rate: ON 0.133 vs OFF 0.100
- Required tables ok rate: ON 0.533 vs OFF 0.467

`complex_hard_v1` (5 pairs):
- Strict equal rate: ON 0.133 vs OFF 0.133 (tie)
- Required tables ok rate: ON 0.373 vs OFF 0.400 (OFF slightly better)

## 5.3 Focused gain segment (CL2/CL6/CL10, 6 pairs x 3 prompts = 18 cases)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_143236_scout_gain_segment_cl2_cl6_cl10_r1_r6/report.md`

Result:
- Required tables ok: ON 12/18 vs OFF 7/18 (delta +0.278)
- SQL present: ON 14/18 vs OFF 10/18 (delta +0.222)
- Strict equal: ON 3/18 vs OFF 2/18 (delta +0.056)

This is the clearest controlled segment where ON outperformed OFF aligned.

## 5.4 Limit probe and boundary synthesis (54 paired cases)

Artifacts:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_190154_scout_limit_probe_v2_r1_r3_analysis/report.md`
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_190255_scout_boundary_synthesis/report.md`

Result (54 paired cases):
- Strict equal: ON 6 vs OFF 9
- Positional set equal: ON 18 vs OFF 18 (tie)
- Required tables ok: ON 11 vs OFF 17
- SQL present: ON 28 vs OFF 32

Interpretation:
- ON advantage is not global.
- ON helps in some schema-grounded paraphrase regimes.
- OFF aligned can be better in weaker abstraction / harder temporal-dialect conditions.

## 5.5 Regime split framing

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260303_071247_scout_regime_split_claims/report.md`

Combined regime-level evidence:
- `schema_grounded_paraphrase`: ON slightly better on required/sql coverage
- `schema_weak_abstraction`: OFF slightly better overall
- `temporal_dialect_sensitive`: OFF slightly better overall

---

## 6. OFF Legacy (Lexical) Stress Tests on Northwind

## 6.1 Limit probe v2: ON vs OFF legacy

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_lexical_breakdown_probe_v2_on_vs_off_legacy_analysis/report.md`

Result:
- strict_equal_count: ON 3 vs OFF legacy 6
- positional_set_equal_count: ON 4 vs OFF 7
- required_tables_ok_count: ON 5 vs OFF 12
- sql_exec_errors_count: ON 8 vs OFF 3

## 6.2 Lexical breakpoint v1

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_scout_on_vs_off_legacy_northwind_lexical_synthesis/report.md`

Result:
- strict_equal_count: ON 1 vs OFF 2
- positional_set_equal_count: ON 2 vs OFF 3
- required_tables_ok_count: ON 4 vs OFF 7
- sql_exec_errors_count: ON 7 vs OFF 1

## 6.3 Underspecified v1 (r2-r4 summary)

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_172250_underspecified_v1_on_vs_off_legacy_r2_r4_summary/report.md`

Aggregate (36 paired queries):
- strict_equal: ON 5/36 vs OFF 5/36 (tie)
- positional_set_equal: ON 5/36 vs OFF 5/36 (tie)
- required_tables_ok: ON 2/36 vs OFF 10/36 (OFF better)
- sql_present: ON 16/36 vs OFF 24/36 (OFF better)

Interpretation of legacy stress tests:
- In these Northwind lexical/underspecified settings, OFF legacy was often stronger on coverage and execution stability.

---

## 7. H2b: Production-Oriented Cockpit Retrieval Ablation (MCP)

## 7.1 Why this protocol was used

The production network did not expose a usable `/process_query` endpoint from this machine during setup windows, so H2b was evaluated via MCP `search_tables` table coverage against partner labels.

This supports retrieval/grounding analysis, not full semantic SQL correctness claims.

## 7.2 Deployment readiness checks performed

Capabilities probe after remote update:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260310_151923_mcp_search_capability_probe_remote_after_restart/probe.md`
- Confirmed aligned metadata available:
  - `ranking_backend`
  - `source_details`
  - supports aligned ON/OFF/legacy attribution

## 7.3 Label integrity check

Artifact:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260310_111857_cockpit_partner_label_catalog_check_remote_r1/label_catalog_check.md`

Result:
- 5 of 13 labeled table names were not exact matches in the live catalog.
- This is a known measurement constraint for H2b table-recall evaluation.

## 7.4 Guarded tri-mode results (r1)

ON run:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260310_151931_cockpit_partner_remote_mcp_scout_on_aligned_r1`

OFF aligned run:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_053124_cockpit_partner_remote_mcp_scout_off_aligned_r1`

OFF legacy run:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_075958_cockpit_partner_remote_mcp_scout_off_legacy_r1`

Metrics:

| Mode | Mean Recall@5 | Mean Recall@10 | Required ok@5 | Required ok@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Scout ON (aligned build) | 0.1111 | 0.1481 | 1/9 | 1/9 | 0.0437 |
| Scout OFF aligned | 0.1111 | 0.1481 | 1/9 | 1/9 | 0.0554 |
| Scout OFF legacy | 0.1111 | 0.1111 | 1/9 | 1/9 | 0.1111 |

Comparisons:
- ON vs OFF aligned:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_053138_cockpit_partner_remote_mcp_scout_on_vs_off_aligned_r1/comparison.md`
- OFF aligned vs OFF legacy:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_080031_cockpit_partner_remote_mcp_off_aligned_vs_off_legacy_r1/comparison.md`
- ON vs OFF legacy:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_080031_cockpit_partner_remote_mcp_scout_on_vs_off_legacy_r1/comparison.md`

Per-query note:
- Most cockpit queries had 0 recall@10 across all modes under current labels.
- Main differentiators were CP6/CP7 rank positions (affected MRR more than coverage counts).

## 7.5 Stability checks (replicates)

OFF aligned replicates:
- r1/r2/r3 all identical on aggregate metrics.
- Stability artifacts:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_061011_cockpit_partner_remote_mcp_off_aligned_r1_vs_r2/comparison.md`
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_061011_cockpit_partner_remote_mcp_off_aligned_r1_vs_r3/comparison.md`

OFF legacy replicates:
- r1/r2/r3 all identical on aggregate metrics.
- Stability artifacts:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_080031_cockpit_partner_remote_mcp_off_legacy_r1_vs_r2/comparison.md`
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_080042_cockpit_partner_remote_mcp_off_legacy_r1_vs_r3/comparison.md`

---

## 8. Operational Reliability and 429 Status

Across the latest aligned and legacy cockpit runs (and the key March synthesis runs), no 429/insufficient-quota interruptions were observed in the generated artifacts.

Earlier historical runs in March included some quota-affected experiments; those were explicitly marked as invalid for quality claims in the corresponding report files.

---

## 9. Initial Interpretation (Working)

1. **Scout ON is not universally better.**
   Results are clearly regime-dependent.

2. **Catalog source alone often has small effect when ranker is held constant.**
   ON vs OFF aligned was often close or tied, especially on retrieval metrics.

3. **Ranker choice can dominate outcomes.**
   OFF legacy sometimes outperformed ON/OFF aligned in Northwind lexical-stress settings.

4. **There are still clear controlled segments where ON helps.**
   The CL2/CL6/CL10 gain segment showed ON gains in required-table coverage and SQL presence.

5. **Current cockpit H2b labels likely understate true retrieval for some queries.**
   5/13 required table labels do not exactly match live catalog names.

6. **H2b claims should stay bounded right now.**
   Current cockpit ablation supports table-grounding comparisons, but not full semantic correctness claims without SQL/result ground truth.

---

## 10. Practical Next Steps (for a defensible thesis narrative)

1. **Normalize partner table labels to live catalog names** (with Urs confirmation), then re-run the same tri-mode cockpit retrieval protocol.
2. **Keep two claims separate in writing:**
   - controlled mechanism behavior (H1/H2a ablation)
   - production operational behavior (H2b)
3. **Report regime-conditional findings** instead of global superiority statements.
4. **If production `/process_query` becomes reachable**, add a small labeled H2b-mini end-to-end set for semantic checks.

---

## 11. Key New Tooling Added During This Phase

- MCP retrieval evaluator:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/run_cockpit_mcp_table_retrieval.py`
- MCP run comparator:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/compare_cockpit_mcp_table_retrieval_runs.py`
- Partner label vs catalog checker:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/check_partner_table_labels_against_catalog.py`
- MCP capability probe:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/probe_mcp_search_capabilities.py`
- Updated protocol notes:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/README_cockpit_table_ablation.md`

