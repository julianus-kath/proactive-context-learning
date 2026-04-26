# H2a / H2b Evaluation — Final Experimental Setup

> **Status:** Final design — pending run execution
> **Date:** 2026-04-14
> **Supersedes:** EXPERIMENTAL_SETUP.md (March 26 two-arm Scout ON/OFF design)

---

## 0. Why This Replaces the Previous Design

The March 2026 evaluation compared Scout ON (structural metadata) vs Scout OFF (aligned
TableRanker). After code audit, these conditions are **functionally identical** from the
LLM's perspective:

- Same `TableRanker` ranking algorithm (same weights, same signals)
- Same metadata content (table names, columns, types, FKs, row counts)
- Same empty `description` field (SDG was not enabled; `SemanticDescriptionGenerator` was dead code)
- Only difference: caching strategy (pre-built snapshot vs live INFORMATION_SCHEMA query)

All reported deltas (+6.1pp overall, +13.9% at L6, p=0.066) were **LLM stochasticity**,
not treatment effects. The Set B reversal (Scout OFF outperforming Scout ON) confirms this.

The SDG v2 implementation creates a **genuine independent variable**: LLM-generated semantic
descriptions that appear in `search_tables` and `describe_table` responses. Descriptions
provide business-level context ("Artikelstamm — master product table with stock levels,
pricing, and supplier links") that structural metadata alone cannot convey.

---

## 1. Research Questions

**H2a (Controlled Benchmark):** Does adding LLM-generated semantic table descriptions to
Scout Mode's catalog improve the SQL agent's table selection accuracy on Northwind, and
does the effect vary by query difficulty?

**H2b (Production Transfer):** Can semantic descriptions bridge the vocabulary gap between
German business language and opaque ERP table names on the 943-table Sage schema, where
structural metadata alone achieves 0% table recall?

---

## 2. Experimental Conditions

Two conditions. One independent variable: **description enrichment**.

| Condition | Label | Env Config | What LLM Sees |
|---|---|---|---|
| **Scout + SDG** | `scout_enriched` | `SCOUT_DISABLE=false`, `SCOUT_DESCRIPTIONS_ENABLED=true` | Structural metadata + LLM-generated business descriptions per table |
| **Scout structural** | `scout_structural` | `SCOUT_DISABLE=false`, `SCOUT_DESCRIPTIONS_ENABLED=false` | Structural metadata only, `description=""` |

**No Scout OFF condition.** Scout OFF (aligned) uses the same TableRanker with the same
data and produces identical LLM-visible output as Scout structural. Including it would
compare a system against itself.

**Relationship to user study (H3):** The user study was conducted on `scout_structural` —
the system as deployed. This evaluation measures the improvement ceiling that description
enrichment provides over the deployment baseline.

### What Differs Between Conditions

The ONLY difference is the `description` field in `search_tables` and `describe_table`
MCP tool responses:

**scout_enriched:**
```json
{
  "name": "KHKArtikel", "full_name": "dbo.KHKArtikel",
  "estimated_rows": 1237, "column_count": 89, "fk_count": 12,
  "relevance_score": 0.95,
  "description": "Artikelstamm (Master Article/Product Table): Contains all
    products/articles with stock levels (LagerMenge), pricing (VKPreis, EKPreis),
    reorder points, supplier links, and item classification. Business terms:
    Artikel, Material, Produkt, Ware, Lagerartikel.",
  "columns": [...], "matched_columns": [...]
}
```

**scout_structural:**
```json
{
  "name": "KHKArtikel", "full_name": "dbo.KHKArtikel",
  "estimated_rows": 1237, "column_count": 89, "fk_count": 12,
  "relevance_score": 0.95,
  "description": "",
  "columns": [...], "matched_columns": [...]
}
```

Ranking scores, table ordering, column lists — all identical. The LLM receives the same
ranked candidates in the same order. The only difference is whether it can *read what the
table is for* before deciding which tables to use in SQL.

### What Does NOT Differ

| Factor | Value (both conditions) |
|---|---|
| Ranking algorithm | TableRanker (identical weights, signals, code path) |
| Ranking input | Same table metadata from same database |
| Relevance scores | Identical (descriptions are NOT used for scoring — verified by unit test) |
| Table ordering | Identical (same scores → same sort order) |
| LLM model | gpt-4o, temperature=0.0 |
| Max iterations | 15 (Northwind), 20 (Sage) |
| MCP server restart | Between conditions (clean state) |

---

## 3. Datasets

### H2a: Northwind (Controlled Benchmark)

**File:** `eval/datasets/northwind_extended_difficulty_v1.jsonl`
**N = 64 queries** across 6 difficulty levels:

| Level | Category | ID Pattern | N | Language | What It Tests |
|---|---|---|---|---|---|
| L1 | Direct | NW1–NW10 | 10 | English | Explicit SQL-style, table names in query |
| L2 | Paraphrase | NL1–NL10 | 10 | English | Business synonyms, no table names |
| L3 | Cross-lingual | CL1–CL12 | 12 | German | German business language vs English schema |
| L4 | Complex | HX subset | 8 | German | Multi-table analytical, complex joins |
| L5 | Underspecified | US_* | 12 | German | Vague business questions, no domain terms |
| L6 | Schema-opaque | LB_* | 12 | German | Deliberate synonym substitution, no cognates |

**Predictions:**
- L1–L2: No SDG effect expected (ceiling — table names transparent, descriptions redundant)
- L3–L4: Moderate SDG effect (descriptions help bridge German↔English)
- L5–L6: Largest SDG effect (descriptions provide the semantic context that vague/opaque queries need)

**Ground truth:** `northwind_extended_difficulty_v1.contracts.json` + `.reference_sql.json`
Required tables extracted from reference SQL via regex (FROM/JOIN clauses).

### H2b: Sage ERP (Production Transfer)

**File:** `eval/datasets/cockpit_partner_queries_v1.jsonl`
**N = 9 queries** (CP1–CP9), real business questions from the practical partner.

**Ground truth:** `cockpit_partner_table_labels_v1.json` + `cockpit_partner_table_label_overrides_v1.json` (5 corrected labels verified against live Sage catalog on 2026-03-25).

**Baseline:** 0% table recall under `scout_structural` (March 2026 runs). Both conditions
selected plausible but incorrect tables on all 9 queries. Root cause: vocabulary gap
between business language ("Material bestellen") and opaque ERP names ("KHKArtikel").

**The critical test:** Can descriptions like "Artikelstamm (Master Article/Product Table):
Contains all products/articles with stock levels..." enable the LLM to bridge this gap?

**Success criterion:** ≥2/9 queries show non-zero table recall under `scout_enriched` that
was zero under `scout_structural`.

---

## 4. Dependent Variables

| Metric | Type | Definition |
|---|---|---|
| **Table Recall** | Primary | Fraction of ground-truth required tables present in generated SQL (extracted from FROM/JOIN clauses via regex) |
| **SQL Generation Rate** | Secondary | Binary: did the agent produce executable SQL? |
| **Description Utilization** | Diagnostic | Did the LLM reference description content in its reasoning trace? (parsed from agent tool-call logs) |

---

## 5. Execution Plan

### 5.1 Pre-Run: Description Generation

Before evaluation runs, generate and cache descriptions for both databases:

```bash
# Northwind (14 tables)
SCOUT_DESCRIPTIONS_ENABLED=true \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/northwind_descriptions.json \
SCOUT_DESCRIPTIONS_DATABASE_TYPE=northwind \
python -c "from mcp_server.scout.runner import ScoutRunner; ..."

# Sage (943 tables)
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/sage_descriptions.json \
SCOUT_DESCRIPTIONS_DATABASE_TYPE=sage \
python -c "..."
```

**Quality gate:** Manually review descriptions for:
- All 14 Northwind tables (full review)
- 20–30 Sage tables covering each KHK prefix family (KHKArtikel*, KHKVKBelege*, KHKEKBelege*, KHKPps*, Osemziz*)
- Specifically verify CP1–CP9 required tables have useful descriptions

Regenerate any low-quality descriptions before proceeding.

### 5.2 Evaluation Runs (4 Runs Total)

| # | Dataset | Condition | Tag | N | Notes |
|---|---|---|---|---|---|
| 1 | Northwind N=64 | scout_enriched | `h2a_sdg_enriched` | 64 | Descriptions ON |
| 2 | Northwind N=64 | scout_structural | `h2a_structural_baseline` | 64 | Descriptions OFF — reuse March 28 CLEAN if accessible, else re-run |
| 3 | Sage CP1–CP9 | scout_enriched | `h2b_sdg_enriched` | 9 | Descriptions ON |
| 4 | Sage CP1–CP9 | scout_structural | `h2b_structural_baseline` | 9 | Descriptions OFF |

**Run order:** Run all 4 within the same day to minimize API model version drift.

**MCP server restart** between each run (clean catalog state).

### 5.3 Reuse of March 28 CLEAN Runs

The `20260328_131450_h2a_CLEAN_scout_on` run used `scout_structural` (descriptions were not
enabled in March). If the data is accessible and the dataset matches
`northwind_extended_difficulty_v1.jsonl` (64 queries), it can serve as Run #2.

**Verification before reuse:**
- [ ] File is readable (currently locked — check again)
- [ ] Dataset was northwind_extended_difficulty_v1.jsonl (64 queries, 6 categories)
- [ ] No code changes to evaluation scripts or contracts since March 28
- [ ] Same LLM model (gpt-4o) and temperature (0.0)

If any check fails, re-run #2 fresh.

---

## 6. Analysis Plan

### 6.1 Primary: Difficulty × Condition Interaction (H2a)

The central table in the thesis. This is the main finding.

| Difficulty | Scout+SDG | Scout Structural | Δ | N |
|---|---|---|---|---|
| L1 Direct | | | | 10 |
| L2 Paraphrase | | | | 10 |
| L3 Cross-lingual | | | | 12 |
| L4 Complex | | | | 8 |
| L5 Underspecified | | | | 12 |
| L6 Schema-opaque | | | | 12 |
| **Overall** | | | | **64** |

**Expected pattern:** Flat delta at L1–L2 (ceiling), growing delta at L3→L6 (descriptions
increasingly needed as vocabulary gap widens).

### 6.2 Statistical Tests (H2a)

- **Paired Wilcoxon signed-rank test** (one-sided, SDG > structural) on per-query table recall
- **Cohen's d** effect size on paired differences
- **Per-level tests** if per-level N permits (L3: n=12, L5: n=12, L6: n=12 — borderline)
- Significance threshold: p < 0.05
- Report: W statistic, p-value, effect size, direction counts (SDG wins, structural wins, tied)

### 6.3 Production Transfer (H2b)

| Query | Required Tables | Scout+SDG Found | Scout Structural Found | SDG Improved? |
|---|---|---|---|---|
| CP1 | KHKArtikel, KHKArtikelLieferant, KHKArtikelVarianten | | ❌ (0%) | |
| CP2 | KHKVKBelege, KHKVKBelegePositionen | | ❌ (0%) | |
| ... | ... | | ❌ (0%) | |

**Success criterion:** ≥2/9 queries with improved table recall. Even partial improvement
(finding 1/3 required tables instead of 0/3) counts.

**If SDG achieves >0% on some queries:** Report which description content enabled the
correct table selection (trace analysis).

**If SDG still achieves 0%:** Report honestly. The vocabulary gap between business language
and the KHK/Osemziz naming convention exceeds what automated descriptions can bridge.
Domain-specific mappings (KHK→Kaufmännisches Handwerk) require human annotation.

### 6.4 Diagnostic: Description Utilization

For `scout_enriched` runs, parse agent reasoning traces:
- Count tool calls where the LLM referenced description text in subsequent reasoning
- Identify cases where descriptions were present but ignored
- Identify cases where descriptions led to correct vs incorrect table selection

---

## 7. Threats to Validity

| Threat | Category | Mitigation |
|---|---|---|
| Description quality varies across tables | Construct | Manual review before runs; regenerate low-quality |
| LLM stochasticity | Internal | temperature=0.0; same model for both conditions |
| Small N on Sage (9 queries) | Statistical | Report as directional, not confirmatory |
| Descriptions leak into ranking | Internal | Unit test confirms descriptions NOT used for scoring |
| API model updates between runs | Internal | Run all conditions same day |
| Baseline from different date (March 28) | Internal | Verify or re-run; prefer same-day runs |

---

## 8. Mapping to Thesis Sections

| Thesis Section | Content |
|---|---|
| **Sec 3 (Architecture)** | Scout Mode has two layers: structural indexing (catalog builder, table ranker) and semantic enrichment (SDG). Both are described as architectural components. |
| **Sec 4 (Methodology)** | Two-condition design. N=64 difficulty gradient. Sage CP1–CP9. Metrics. User study used structural baseline. |
| **Sec 5 (Results)** | H2a: difficulty × condition table. H2b: production transfer. Per-query analysis where modes diverge. |
| **Sec 6 (Discussion)** | What descriptions add. Where they're insufficient. Connection to BIRD evidence, Gao auto-descriptions, SEED. |

---

## 9. File Inventory

| File | Role |
|---|---|
| `eval/datasets/northwind_extended_difficulty_v1.jsonl` | H2a queries (N=64) |
| `eval/datasets/northwind_extended_difficulty_v1.contracts.json` | H2a ground truth |
| `eval/datasets/cockpit_partner_queries_v1.jsonl` | H2b queries (N=9) |
| `eval/datasets/cockpit_partner_table_labels_v1.json` | H2b ground truth |
| `eval/datasets/cockpit_partner_table_label_overrides_v1.json` | H2b label corrections |
| `eval/cache/northwind_descriptions.json` | Generated descriptions (Northwind) |
| `eval/cache/sage_descriptions.json` | Generated descriptions (Sage) |
| `mcp_server/scout/description_generator.py` | SDG v2 implementation |
| `mcp_server/scout/description_enricher.py` | Catalog enrichment logic |
| `eval/run_h2a_full_pipeline.py` | H2a evaluation script |
| `eval/run_h2b_process_query_grounding.py` | H2b evaluation script |
