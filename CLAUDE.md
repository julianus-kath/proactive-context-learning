# CLAUDE.md — ERP Natural Language Query Assistant

## What This Is

LangGraph-based system that transforms natural language questions into SQL queries for enterprise databases. Three services: SQL Agent (port 5001), MCP Database Server (port 8000), Web UI (port 3000). The system's core contribution is **Scout Mode** — autonomous schema discovery that indexes database tables/columns and provides ranked metadata to the LLM before SQL generation.

This is a master's thesis codebase. Do not refactor for aesthetics. Changes should be purposeful: fixing bugs, completing documentation, or preparing the release.

---

## Architecture (3 Services)

```
User → chatbot_ui (3000) → simple_sql_agent (5001) → mcp_server (8000) → Database
                                    ↑                        ↑
                              LangGraph ReAct           Scout Mode
                              agent.py (16K)          scout/mode.py (29K)
                                                      scout/runner.py (21K)
                                                      tools/__init__.py (111K)
```

### Entry Points
- `simple_sql_agent/service.py` — FastAPI agent service (port 5001)
- `mcp_server/server/app.py` — MCP database server (port 8000)
- `chatbot_ui/web_app.py` — Web interface (port 3000)
- `start_scripts/start_all_services_mac.sh` — Native dev startup (macOS / Linux with venv)
- `docker-compose.yml` + `run.sh` — Docker stack (recommended)

### Critical Files (by impact)
- `mcp_server/tools/__init__.py` (111K) — All database tools, Scout routing, table ranking, query validation. This is the workhorse.
- `mcp_server/scout/mode.py` (29K) — Scout Mode semantic search
- `mcp_server/scout/runner.py` (21K) — Table ranking algorithm
- `mcp_server/tools/discovery_tools.py` (68K) — Discovery tool implementations
- `simple_sql_agent/agent.py` (16K) — LangGraph ReAct agent
- `simple_sql_agent/service.py` (19K) — Agent FastAPI wrapper

---

## Environment Setup

```bash
# Python 3.10+ required
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Config: copy .env.example → .env, fill in:
# - OPENAI_API_KEY (or ANTHROPIC_API_KEY)
# - MCP_SERVER_URL
# - Database connection strings
```

Config variants: `.env.northwind` for controlled benchmark, `.env` for production (Luisi & Diener via VPN).

---

## Evaluation Framework (`eval/`)

This is the thesis evidence base. Do not modify results or run data. The directory was consolidated on 2026-04-14 — pre-SDG scripts, datasets, runs, and docs live under `archived_*/` and `runs/archived/` and should not be referenced in the thesis.

### Key Scripts (top level only)
| Script | Purpose |
|--------|---------|
| `run_h2a_full_pipeline.py` | H2a controlled evaluation (Northwind) |
| `run_h2b_process_query_grounding.py` | H2b production transfer evaluation (Cockpit/Sage) |
| `generate_descriptions.py` | SDG — semantic description generation for Scout catalog |
| `contracts.py` | Ground truth contract definitions |
| `eval_client.py` | Instrumentation client |
| `service.py` | Eval tracking service |

### Canonical Datasets (`eval/datasets/`)
| File | Role |
|---|---|
| `northwind_extended_difficulty_v1.jsonl` (+ `.contracts.json`) | H2a queries, N=64 |
| `northwind_queries_underspecified_v1.*` | L5 source (12 queries) |
| `northwind_queries_lexical_breakpoint_v1.*` | L6 source (12 queries) — see naming note below |
| `cockpit_partner_queries_v1.jsonl` | H2b queries, N=9 |
| `cockpit_partner_table_labels_v1.json` (+ `.md`, `_overrides_v1.json`) | H2b ground truth |
| `northwind_pilot_n10_v1.jsonl` | SDG pilot smoke-test set, N=10 |

Everything else is in `datasets/archived/`.

### Naming Note: `lexical_breakpoint` vs "schema-opaque"
The thesis refers to L6 queries as **schema-opaque**. The dataset files and `category` field values are named **`lexical_breakpoint`** for historical reasons and are kept as-is to avoid breaking ground truth references. Do not rename. When writing thesis text, use "schema-opaque"; when writing code/scripts/queries, use `lexical_breakpoint`.

### Reference Runs (`eval/runs/`)
Four runs kept at top level; 302 pre-SDG runs moved to `runs/archived/`:
- `20260327_071347_h2b_full_pipeline_scout_off_aligned_REAL` — first real H2b run
- `20260328_131450_h2a_CLEAN_scout_on` — structural baseline, N=64
- `20260328_131936_h2a_CLEAN_scout_off_aligned` — confirms Scout ON ≈ OFF under identical conditions
- `20260414_093339_pilot_n10_scout_structural` — SDG pilot smoke test

### Documentation
- `eval/README.md` — Framework architecture (post-consolidation)
- `eval/SDG_ABLATION_EXPERIMENTAL_SETUP.md` — Canonical experimental design
- `eval/SDG_EVALUATION_RUNBOOK.md` — How to run the SDG-era evaluations

### Known Issue: REFERENCE_CHECK_UNAVAILABLE
Some queries are flagged as having unavailable references despite having expert-written reference SQL. This needs investigation — likely a lookup bug in the evaluation code, not a data gap.

---

## ADRs (`adrs/`)

34 Architecture Decision Records documenting the full evolution. Key recent ones:
- **ADR-0030**: Simple SQL Agent architecture
- **ADR-0031**: Complete architecture update
- **ADR-0032**: Few-shot SQL patterns + generic table search ranking fixes
- **ADR-0033**: KPI library
- **ADR-0034**: Agent quality debugging and fixes

Index: `adrs/adr-index.yaml`

---

## Hypotheses (Thesis Context)

The codebase serves four hypotheses:
- **H1**: Scout Mode autonomously builds a query-useful schema catalog
- **H2a**: Proactive schema grounding delivers semantic correctness (controlled, Northwind)
- **H2b**: System transfers to production (Luisi & Diener ERP)
- **H3**: Users derive exploratory value (UTAUT + NASA-TLX)

Scout ON/OFF ablation is central to H2a evidence.

---

## Rules

- Do not commit `.env` files, API keys, or credentials
- Do not modify files in `eval/runs/` — these are research artifacts
- Do not change agent behavior on the release branch — this is thesis evidence, not a feature branch
- When removing dead code, verify it isn't referenced by evaluation scripts first
- ADRs are append-only documentation; update with new ADRs, don't rewrite old ones
- The `data/catalog/scout_catalog.json.gz` is a generated artifact — regenerate, don't hand-edit
