# SDG Evaluation Runbook — Coding Agent Handoff

> **Purpose:** Execute the H2a/H2b evaluation with SDG as the independent variable.
> **Prerequisite:** SDG v2 is fully implemented. This document covers evaluation execution only.
> **Output:** 4 timestamped run directories with results, plus statistical analysis.

---

## 0. Context

We are running a two-condition evaluation to measure whether LLM-generated semantic
table descriptions improve the SQL agent's table selection accuracy.

**Independent variable:** `SCOUT_DESCRIPTIONS_ENABLED` (true/false)

| Condition | Label | Description Field |
|---|---|---|
| C1: `scout_enriched` | Treatment | LLM-generated business descriptions per table |
| C2: `scout_structural` | Baseline | Empty string (`""`) |

Both conditions use identical ranking (same TableRanker, same scores, same table order).
The ONLY difference is whether the LLM can read a `description` field explaining what
each table is for.

**No Scout OFF condition.** Scout OFF (aligned) is functionally identical to C2.

---

## 1. Pre-Run: Generate and Cache Descriptions

Descriptions must be generated ONCE and cached to disk for reproducibility.
All evaluation runs then read from this cache — no live LLM calls during eval.

### 1.1 Create cache directory

```bash
mkdir -p eval/cache
```

### 1.2 Generate Northwind descriptions (14 tables)

```bash
cd /path/to/code

SCOUT_DESCRIPTIONS_ENABLED=true \
SCOUT_DESCRIPTIONS_MODEL=claude-sonnet-4-20250514 \
SCOUT_DESCRIPTIONS_DATABASE_TYPE=northwind \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/northwind_descriptions.json \
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
python -c "
from mcp_server.scout.description_generator import build_description_generator_from_env
from mcp_server.scout.description_enricher import enrich_tables_with_descriptions
from mcp_server.scout.runner import ScoutRunner

# Initialize ScoutRunner to get the catalog
runner = ScoutRunner(db_adapter=<northwind_adapter>)
catalog = runner._catalog_store.load()  # Raw catalog without descriptions
tables = catalog.get('tables', [])

# Build generator from env (will use cache path)
generator = build_description_generator_from_env()

# Generate descriptions — results cached to SCOUT_DESCRIPTIONS_CACHE_PATH
count = enrich_tables_with_descriptions(tables, generator)
print(f'Generated {count} descriptions for {len(tables)} Northwind tables')
"
```

**IMPORTANT:** The above is pseudocode. The actual mechanism depends on how your
database adapter is initialized. The key env vars are:

| Env Var | Value | Purpose |
|---|---|---|
| `SCOUT_DESCRIPTIONS_ENABLED` | `true` | Activates LLM description generator |
| `SCOUT_DESCRIPTIONS_MODEL` | `claude-sonnet-4-20250514` | Which model generates descriptions |
| `SCOUT_DESCRIPTIONS_DATABASE_TYPE` | `northwind` or `sage` | Adjusts prompt context |
| `SCOUT_DESCRIPTIONS_CACHE_PATH` | `eval/cache/northwind_descriptions.json` | Persists descriptions to disk |
| `ANTHROPIC_API_KEY` | (your key) | Required for LLM calls |

**Alternative approach:** Start the MCP server with descriptions enabled and let it
generate on first `get_catalog()` call:

```bash
# Start MCP server with descriptions ON + cache
SCOUT_DISABLE=false \
SCOUT_DESCRIPTIONS_ENABLED=true \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/northwind_descriptions.json \
SCOUT_DESCRIPTIONS_DATABASE_TYPE=northwind \
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
python -m mcp_server.server.app --port 8000
```

Then trigger a `search_tables` call to force catalog load + enrichment. The cache file
will be written automatically. Kill the server after cache is populated.

### 1.3 Generate Sage descriptions (943 tables)

Same approach, different config:

```bash
SCOUT_DESCRIPTIONS_DATABASE_TYPE=sage \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/sage_descriptions.json \
# ... same other env vars ...
```

**Cost:** ~943 API calls × ~500 tokens ≈ $2–5 with Claude Sonnet.
**Time:** ~5–15 minutes depending on rate limits.

### 1.4 Quality Gate

Before running evaluations, manually inspect descriptions:

```bash
# Quick check: are all tables covered?
python -c "
import json
descs = json.load(open('eval/cache/northwind_descriptions.json'))
print(f'Northwind: {len(descs)} descriptions')
for name, desc in descs.items():
    print(f'  {name}: {desc[:80]}...')
"
```

For Sage, spot-check the tables required by CP1–CP9:
- `dbo.KHKArtikel` — should mention "Artikelstamm", "products", "material"
- `dbo.KHKVKBelege` — should mention "Verkaufsbelege", "sales documents"
- `dbo.KHKPpsFaBelege` — should mention "Fertigungsaufträge", "production orders"
- `dbo.OsemzizZEBuchungen` — should mention "Zeiterfassung", "time tracking"
- `dbo.KHKPpsBdeStempel` — should mention "Betriebsdatenerfassung", "shop floor"
- `dbo.KHKArtikelLieferant` — should mention "Lieferantenzuordnung", "supplier"
- `dbo.KHKEKBelege` — should mention "Einkaufsbelege", "purchase documents"

If any description is generic ("Table dbo.KHKArtikel") or misses the business terms,
regenerate it by deleting the entry from the cache file and re-running.

---

## 2. Evaluation Runs

### 2.1 H2a: Northwind (N=64, controlled benchmark)

**Run C1 (scout_enriched):**

```bash
# Start MCP server with descriptions ON (reads from cache)
SCOUT_DISABLE=false \
SCOUT_DESCRIPTIONS_ENABLED=true \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/northwind_descriptions.json \
python -m mcp_server.server.app --port 8000 &
MCP_PID=$!

# Wait for health
sleep 5 && curl -s http://localhost:8000/health

# Run H2a evaluation
python -m eval.run_h2a_full_pipeline \
  --dataset eval/datasets/northwind_extended_difficulty_v1.jsonl \
  --contracts eval/datasets/northwind_extended_difficulty_v1.contracts.json \
  --mcp-url http://localhost:8000 \
  --mode scout_on \
  --run-tag h2a_sdg_enriched

kill $MCP_PID
```

**Run C2 (scout_structural):**

```bash
# Start MCP server with descriptions OFF
SCOUT_DISABLE=false \
SCOUT_DESCRIPTIONS_ENABLED=false \
python -m mcp_server.server.app --port 8000 &
MCP_PID=$!

sleep 5 && curl -s http://localhost:8000/health

python -m eval.run_h2a_full_pipeline \
  --dataset eval/datasets/northwind_extended_difficulty_v1.jsonl \
  --contracts eval/datasets/northwind_extended_difficulty_v1.contracts.json \
  --mcp-url http://localhost:8000 \
  --mode scout_on \
  --run-tag h2a_structural_baseline

kill $MCP_PID
```

**NOTE:** Both runs use `--mode scout_on` because both conditions have Scout enabled.
The difference is `SCOUT_DESCRIPTIONS_ENABLED`. Do NOT use `--mode scout_off_aligned`.

**Reuse of March 28 CLEAN run:**
The run at `eval/runs/20260328_131450_h2a_CLEAN_scout_on/` used scout_on with
descriptions disabled (SDG wasn't enabled in March). If this run:
- Used `northwind_extended_difficulty_v1.jsonl` (64 queries)
- Used the same contracts file
- Same LLM model (gpt-4o, temperature=0.0)

Then it CAN serve as C2 instead of re-running. Verify by checking its `summary.json`
for query count and dataset path. If in doubt, re-run C2 fresh.

### 2.2 H2b: Sage ERP (N=9, production transfer)

**Run C1 (scout_enriched):**

```bash
# Start MCP server against Sage database with descriptions ON
SCOUT_DISABLE=false \
SCOUT_DESCRIPTIONS_ENABLED=true \
SCOUT_DESCRIPTIONS_CACHE_PATH=eval/cache/sage_descriptions.json \
SCOUT_DESCRIPTIONS_DATABASE_TYPE=sage \
python -m mcp_server.server.app --port 8000 &
MCP_PID=$!

sleep 10 && curl -s http://localhost:8000/health

python -m eval.run_h2a_full_pipeline \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --contracts eval/datasets/cockpit_partner_table_labels_v1.json \
  --label-overrides eval/datasets/cockpit_partner_table_label_overrides_v1.json \
  --mcp-url http://localhost:8000 \
  --mode scout_on \
  --run-tag h2b_sdg_enriched

kill $MCP_PID
```

**Run C2 (scout_structural):**

```bash
SCOUT_DISABLE=false \
SCOUT_DESCRIPTIONS_ENABLED=false \
python -m mcp_server.server.app --port 8000 &
MCP_PID=$!

sleep 10 && curl -s http://localhost:8000/health

python -m eval.run_h2a_full_pipeline \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --contracts eval/datasets/cockpit_partner_table_labels_v1.json \
  --label-overrides eval/datasets/cockpit_partner_table_label_overrides_v1.json \
  --mcp-url http://localhost:8000 \
  --mode scout_on \
  --run-tag h2b_structural_baseline

kill $MCP_PID
```

**NOTE on H2b runner:** The `run_h2b_process_query_grounding.py` script is a more
complex orchestrator that can start/stop services per mode. You may use it instead,
but `run_h2a_full_pipeline.py` works for both Northwind and Sage if pointed at the
right dataset and MCP server. The key is that the MCP server connects to the correct
database (Northwind PostgreSQL vs Sage MS SQL).

---

## 3. Expected Outputs

Each run produces a timestamped directory under `eval/runs/`:

```
eval/runs/{timestamp}_{run_tag}_{mode}/
├── results_raw.jsonl     # One JSON line per query
├── summary.json          # Aggregate metrics
```

**results_raw.jsonl format (per line):**
```json
{
  "query_id": "CL2",
  "question": "Welche Kundenländer bringen den größten Gesamtumsatz...",
  "sql_generated": true,
  "generated_sql": "SELECT c.country, SUM(...) ...",
  "tables_found": ["customers", "orders", "order_details"],
  "required_tables": ["customers", "orders", "order_details"],
  "table_recall": 1.0,
  "category": "crosslingual",
  "language": "de"
}
```

**summary.json format:**
```json
{
  "run_tag": "h2a_sdg_enriched",
  "mode": "scout_on",
  "n_queries": 64,
  "mean_recall": 0.xxx,
  "sql_generation_rate": 0.xxx,
  "perfect_recall_count": N,
  "zero_recall_count": N,
  "per_category": {
    "direct": {"n": 10, "mean_recall": x.xx},
    "paraphrase": {"n": 10, "mean_recall": x.xx},
    "crosslingual": {"n": 12, "mean_recall": x.xx},
    "complex": {"n": 8, "mean_recall": x.xx},
    "underspecified": {"n": 12, "mean_recall": x.xx},
    "lexical_breakpoint": {"n": 12, "mean_recall": x.xx}
  }
}
```

---

## 4. Post-Run: Statistical Analysis

After all 4 runs complete, compute:

### 4.1 Per-Difficulty Comparison Table (H2a)

Load both H2a results_raw.jsonl files, join on query_id, compute:

```python
import json
from scipy.stats import wilcoxon
from statistics import mean

# Load paired results
enriched = {r["query_id"]: r for r in load_jsonl("h2a_sdg_enriched/results_raw.jsonl")}
structural = {r["query_id"]: r for r in load_jsonl("h2a_structural_baseline/results_raw.jsonl")}

# Per-difficulty breakdown
for category in ["direct", "paraphrase", "crosslingual", "complex", "underspecified", "lexical_breakpoint"]:
    e_recalls = [enriched[qid]["table_recall"] for qid in enriched if enriched[qid]["category"] == category]
    s_recalls = [structural[qid]["table_recall"] for qid in structural if structural[qid]["category"] == category]
    delta = mean(e_recalls) - mean(s_recalls)
    print(f"{category}: enriched={mean(e_recalls):.1%}, structural={mean(s_recalls):.1%}, delta={delta:+.1%}")

# Overall Wilcoxon signed-rank test
e_all = [enriched[qid]["table_recall"] for qid in sorted(enriched)]
s_all = [structural[qid]["table_recall"] for qid in sorted(structural)]
diffs = [e - s for e, s in zip(e_all, s_all)]
non_zero_diffs = [d for d in diffs if d != 0]

if non_zero_diffs:
    stat, p = wilcoxon(non_zero_diffs, alternative="greater")
    cohens_d = mean(diffs) / (sum((d - mean(diffs))**2 for d in diffs) / len(diffs)) ** 0.5
    print(f"Wilcoxon W={stat}, p={p:.4f}, Cohen's d={cohens_d:.3f}")

# Direction counts
wins = sum(1 for d in diffs if d > 0)
losses = sum(1 for d in diffs if d < 0)
ties = sum(1 for d in diffs if d == 0)
print(f"SDG wins: {wins}, structural wins: {losses}, ties: {ties}")
```

### 4.2 H2b Analysis

```python
# Simple comparison: any non-zero recall under enriched?
for qid in sorted(enriched_h2b):
    e = enriched_h2b[qid]["table_recall"]
    s = structural_h2b[qid]["table_recall"]
    improved = "✅ IMPROVED" if e > s else ("➡️ same" if e == s else "❌ worse")
    print(f"{qid}: enriched={e:.0%}, structural={s:.0%} {improved}")
```

### 4.3 Output: Statistical Summary File

Save to `eval/runs/sdg_ablation_statistical_analysis.json`:

```json
{
  "h2a": {
    "n": 64,
    "enriched_mean_recall": 0.xxx,
    "structural_mean_recall": 0.xxx,
    "delta": 0.xxx,
    "wilcoxon_W": N,
    "wilcoxon_p": 0.xxx,
    "cohens_d": 0.xxx,
    "sdg_wins": N,
    "structural_wins": N,
    "ties": N,
    "per_difficulty": { ... }
  },
  "h2b": {
    "n": 9,
    "enriched_mean_recall": 0.xxx,
    "structural_mean_recall": 0.0,
    "queries_improved": N,
    "per_query": { ... }
  }
}
```

---

## 5. Run Checklist

- [ ] `eval/cache/` directory created
- [ ] Northwind descriptions generated and cached (`eval/cache/northwind_descriptions.json`)
- [ ] Sage descriptions generated and cached (`eval/cache/sage_descriptions.json`)
- [ ] Quality gate: manually reviewed descriptions for key tables
- [ ] H2a C1 run complete (`h2a_sdg_enriched`)
- [ ] H2a C2 run complete (`h2a_structural_baseline`) — or March 28 CLEAN reused
- [ ] H2b C1 run complete (`h2b_sdg_enriched`)
- [ ] H2b C2 run complete (`h2b_structural_baseline`)
- [ ] Statistical analysis computed and saved
- [ ] Per-difficulty comparison table produced

---

## 6. Key Files

| File | Path |
|---|---|
| H2a dataset | `eval/datasets/northwind_extended_difficulty_v1.jsonl` |
| H2a contracts | `eval/datasets/northwind_extended_difficulty_v1.contracts.json` |
| H2b dataset | `eval/datasets/cockpit_partner_queries_v1.jsonl` |
| H2b labels | `eval/datasets/cockpit_partner_table_labels_v1.json` |
| H2b overrides | `eval/datasets/cockpit_partner_table_label_overrides_v1.json` |
| H2a runner | `eval/run_h2a_full_pipeline.py` |
| H2b runner | `eval/run_h2b_process_query_grounding.py` |
| Contracts | `eval/contracts.py` |
| SDG generator | `mcp_server/scout/description_generator.py` |
| SDG enricher | `mcp_server/scout/description_enricher.py` |
| ScoutRunner | `mcp_server/scout/runner.py` |
| Description cache (NW) | `eval/cache/northwind_descriptions.json` (generated) |
| Description cache (Sage) | `eval/cache/sage_descriptions.json` (generated) |

---

## 7. Environment Variable Reference

| Variable | C1 (enriched) | C2 (structural) |
|---|---|---|
| `SCOUT_DISABLE` | `false` | `false` |
| `SCOUT_DESCRIPTIONS_ENABLED` | `true` | `false` |
| `SCOUT_DESCRIPTIONS_CACHE_PATH` | `eval/cache/{db}_descriptions.json` | (not needed) |
| `SCOUT_DESCRIPTIONS_MODEL` | `claude-sonnet-4-20250514` | (not needed) |
| `SCOUT_DESCRIPTIONS_DATABASE_TYPE` | `northwind` or `sage` | (not needed) |
| `ANTHROPIC_API_KEY` | (required for generation) | (not needed) |

---

## 8. Troubleshooting

**"No descriptions generated"** — Check `SCOUT_DESCRIPTIONS_ENABLED=true` is set.
The factory function at `description_generator.py:266` falls back to
`NullDescriptionGenerator` if the env var is missing, empty, or `false`.

**"Cache file empty"** — The `DiskCachedDescriptionGenerator` persists after EACH
table. If the process was killed mid-generation, the cache will have partial entries.
Re-run; existing entries will be cache hits.

**"Same results for C1 and C2"** — Verify descriptions actually appear in MCP responses.
Call `search_tables` manually and check the `description` field. If empty under C1,
the cache path may be wrong or the server didn't load the cached descriptions.

**"run_h2a_full_pipeline.py errors on Sage contracts format"** — H2b uses a different
contract format (table labels JSON, not QueryContract list). Use `--label-overrides`
for the 5 corrected labels. If the script doesn't support the label format natively,
you may need to use `run_h2b_process_query_grounding.py` instead.
