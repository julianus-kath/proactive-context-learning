# H2b Sage SDG Experiment — Execution Runbook (corrected for real CLI)

> Run on the **Windows box** where the MCP server has VPN access to Sage. Both
> MCP (port 8000) and the SQL agent service (port 5001) need to be reachable
> from whatever box runs the eval script — running everything on Windows is
> simplest.

---

## Two Conditions

| Condition | Label | `SCOUT_DESCRIPTIONS_ENABLED` | `SCOUT_DESCRIPTIONS_RANKING` | `--run-tag` |
|---|---|---|---|---|
| C2 | `scout_structural`      | `false` | `false` | `h2b_sage_structural` |
| C3 | `scout_enriched_ranked` | `true`  | `true`  | `h2b_sage_enriched_ranked` |

No C1 (descriptions in agent payload only, without ranker). On Sage, a plain
payload injection is expected to be useless because the right tables never
reach top-k under structural ranking — the agent never sees their
descriptions. C3 is the only condition that tests the full mechanism.

---

## Pre-flight checks

### 1. Confirm the Sage description cache is warm

Run from the project root on the Windows box:

```cmd
python -c "import json, os; p=os.environ.get('SCOUT_DESCRIPTIONS_CACHE_PATH','data\\cache\\sage_descriptions.json'); d=json.load(open(p,encoding='utf-8')); print('entries:', len(d)); import itertools; [print('---', k); print(v[:180]) for k,v in itertools.islice(d.items(),0,3)]"
```

Expected: `entries: 943` (or close) and sensible German business prose in the
samples. If the count is <900, the cache is incomplete — don't run the eval.

### 2. Spot-check that key Sage tables contain the right German business terms

If their descriptions don't contain the German terms from the partner queries,
the ranker can't match on them and C3 will collapse to C2. Run:

```cmd
python -c "import json, os; p=os.environ.get('SCOUT_DESCRIPTIONS_CACHE_PATH','data\\cache\\sage_descriptions.json'); d=json.load(open(p,encoding='utf-8')); probes={'KHKArtikel':['artikel','material','produkt'],'KHKVKBelege':['verkauf','bestellung','umsatz','lieferung'],'KHKPpsBdeStempel':['anwesenheit','stempel','zeiterfassung'],'OsemzizZEBuchungen':['zeiterfassung','buchung','anwesenheit'],'KHKArtikelLieferant':['lieferant','artikel']}; [print(f\"{t}: hits={[w for w in ws if w.lower() in d.get(f'dbo.{t}','').lower()]}\") for t,ws in probes.items()]"
```

Every probe should report at least one hit. Zero hits on `KHKVKBelege` or
`KHKArtikel` means the descriptions are too generic and the experiment will
likely produce 0/9 on both conditions — consider regenerating with a more
specific SDG prompt before proceeding.

### 3. Ground truth + overrides sanity

```cmd
python -c "import json; queries=[json.loads(l) for l in open('eval/datasets/cockpit_partner_queries_v1.jsonl',encoding='utf-8') if l.strip()]; labels=json.load(open('eval/datasets/cockpit_partner_table_labels_v1.json',encoding='utf-8')); overrides=json.load(open('eval/datasets/cockpit_partner_table_label_overrides_v1.json',encoding='utf-8')); print('queries:', len(queries)); print('labels:', len(labels) if isinstance(labels,dict) else sum(1 for _ in labels)); print('overrides:', len(overrides) if isinstance(overrides,dict) else sum(1 for _ in overrides))"
```

Expected: 9 queries, 9 labels, 5 overrides applied (script applies
overrides automatically via `--manual-overrides`).

### 4. Agent + MCP env and reachability

Both the MCP server **and** the SQL agent service read `SCOUT_DESCRIPTIONS_*`
from their own process env. The eval script sets mode-specific env when it
spawns them (see step §Execution below).

Also set once, for both processes:

```cmd
set OPENAI_API_KEY=sk-...
set MCP_API_KEY=supersecretapikey
set API_KEY=supersecretapikey
set DB_DIALECT=mssql
set SCOUT_DESCRIPTIONS_MODEL=gpt-4o-mini
set SCOUT_DESCRIPTIONS_DATABASE_TYPE=sage
set SCOUT_DESCRIPTIONS_CACHE_PATH=data\cache\sage_descriptions.json
:: plus whatever DB_HOST / DB_NAME / DB_USER / DB_PASSWORD pointing at Sage
```

---

## Execution

The H2b script manages MCP + agent service lifecycle itself under
`--start-services-per-mode`, spawning each with the correct per-mode env. That
is the recommended path — it guarantees the mode's env vars land in the right
process, and restarts are cheap because the SDG disk cache is already warm
(re-enrichment is a file load, ~1 s).

**Important:** stop any currently-running MCP (the `start_mcp_server_windows.bat`
session) before starting, so the script can take over the port.

### Run both conditions in one invocation

From the project root, Windows cmd or PowerShell:

```cmd
.venv\Scripts\python -m eval.run_h2b_process_query_grounding ^
  --modes scout_structural scout_enriched_ranked ^
  --run-tag h2b_sage_sdg ^
  --start-services-per-mode ^
  --dataset eval\datasets\cockpit_partner_queries_v1.jsonl ^
  --table-labels eval\datasets\cockpit_partner_table_labels_v1.json ^
  --manual-overrides eval\datasets\cockpit_partner_table_label_overrides_v1.json ^
  --replicates 1
```

Flag rename map (actual CLI vs the earlier draft):

| Earlier draft       | Actual flag          |
|---------------------|----------------------|
| `--labels`          | `--table-labels`     |
| `--label-overrides` | `--manual-overrides` |
| `--tag`             | `--run-tag`          |
| `--mode X`          | `--modes X [X ...]`  |

### If you want to run them separately

```cmd
:: C2 structural first
.venv\Scripts\python -m eval.run_h2b_process_query_grounding ^
  --modes scout_structural --run-tag h2b_sage_structural ^
  --start-services-per-mode

:: then C3 enriched-ranked
.venv\Scripts\python -m eval.run_h2b_process_query_grounding ^
  --modes scout_enriched_ranked --run-tag h2b_sage_enriched_ranked ^
  --start-services-per-mode
```

Flag defaults for `--dataset`, `--table-labels`, and `--manual-overrides`
already point at the right cockpit files, so they can be omitted.

### Health check during the run

For each mode the script prints a health-check block. The one that matters
for C3:

```
expected_backend=ScoutRunner
expected_off_control_mode=None
SCOUT_DISABLE=false
SCOUT_DESCRIPTIONS_ENABLED=true
SCOUT_DESCRIPTIONS_RANKING=true
```

And in the MCP log you should see (once per mode, on first search):

```
🔤 SDG search_tables: query=... returned=N with_description=N/N sample[dbo.KHKVKBelege]='Verkaufsbelege (Sales Documents) ...'
```

If `with_description=0/N` in the C3 log, the description cache did not land on
the MCP process — kill everything, verify `SCOUT_DESCRIPTIONS_CACHE_PATH` in
the environment the script inherits, and try again.

---

## Read and compare results

Each mode writes a summary under `eval/runs/<timestamp>_<run-tag>_<mode>_r1/`.
Find them:

```cmd
dir /b /od eval\runs | findstr h2b_sage
```

Print both summaries:

```cmd
for %f in (eval\runs\*h2b_sage_structural*\summary.json eval\runs\*h2b_sage_enriched_ranked*\summary.json) do @(echo === %f === && type %f)
```

Report side-by-side:

| qid  | Question (≤60 chars) | C2 recall | C3 recall | Δ | Required tables | C3 tables_used |

And aggregate:

- mean recall C2 → C3
- count of queries that moved from `0 → >0`
- any queries where C3 retrieved tables not in the label set (description
  match finding plausible but unlabeled tables — flag for discussion, not
  necessarily wrong)

---

## Constraints

- Do NOT edit the eval scripts, the cockpit dataset, labels, or the
  description cache during the run.
- If MCP fails to start, fails to reach Sage, or SDG enrichment logs
  `non_empty=0/N` for C3, STOP and report — do not keep partial results.
- All artifacts land in `eval/runs/<timestamp>_*` directories; they're kept as
  thesis evidence.
