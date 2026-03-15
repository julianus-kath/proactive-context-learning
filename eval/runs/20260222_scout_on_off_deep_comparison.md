# Deep Comparison: Scout ON vs Scout OFF (Northwind)

## Runs compared
- Scout ON: `20260222_195813_northwind_ab_scout_on_clean_v2` (MCP backend: `ScoutRunner`)
- Scout OFF: `20260222_195526_northwind_ab_scout_off_clean` (MCP backend: `SchemaCatalog`)
- Dataset: `eval/datasets/northwind_queries.jsonl` (10 queries)

## 1) Execution-level outcomes
- Success rate: ON `10/10`, OFF `10/10`
- SQL executed rate: ON `10/10`, OFF `10/10`
- Non-empty result rate: ON `10/10`, OFF `10/10`
- Avg end-to-end latency: ON `3553.4 ms`, OFF `3730.9 ms` (OFF-ON `+177.5 ms`)

## 2) Semantic correctness vs reference SQL
Reference file: `eval/datasets/northwind_queries.reference_sql.json`

### Strict metrics (fully automatic)
- Strict result equality (same columns and ordered rows): ON `2/10`, OFF `2/10`
- Same-column multiset equality (ignoring row order): ON `2/10`, OFF `2/10`
- Positional multiset equality (ignoring aliases): ON `4/10`, OFF `4/10`
- Common-column multiset equality: ON `7/10`, OFF `6/10`

(Computed in `eval/runs/20260222_scout_on_off_semantic_vs_reference.json`)

### Contract/intent-aware equivalence (manual-normalized)
When allowing benign formatting/projection differences (e.g., tie-order in top-k, month representation), both runs pass:
- ON `8/10`
- OFF `8/10`

Pass: NW1, NW2, NW4, NW5, NW6, NW8, NW9, NW10
Fail: NW3, NW7

### Main semantic failures
- `NW3` (both ON/OFF): metric differs from reference intent.
  - Reference uses non-discounted order value; generated SQL used discounted value.
  - Mean absolute customer-level deviation: `2511.0`; max deviation: `11311.44`.
- `NW7` (both ON/OFF): co-occurrence logic differs from reference CTE definition.
  - Reference top-pair count starts at `25`; ON produces `32`, OFF `31` for top pair.
  - ON and OFF are both semantically off here; OFF also produced a larger pair set.

## 3) Where ON/OFF actually differ
Generated SQL differs on 4 queries: `NW7`, `NW8`, `NW9`, `NW10`.
- `NW8`, `NW9`: syntactic/alias differences, equivalent outputs.
- `NW10`: different time representation (`year+month` vs `YYYY-MM`) but equivalent revenue-by-month after normalization.
- `NW7`: genuinely different logic between ON and OFF (`<>` plus supplier filter vs `<`), and both diverge from reference.

## 4) How queries are sent in benchmark mode
Each benchmark call sends:
- `user_input`: natural-language query text
- `query_contract`: full per-query semantic contract object from `*.contracts.json`

Source: `eval/run_benchmark.py` posts to `/process_query` with `query_contract` in payload.

## 5) How contracts currently play into runtime
Important implementation reality:
- `query_contract` is accepted by `simple_sql_agent/service.py` request model,
- but **not used** when calling agent execution (`agent.arun(request.user_input)`).
- No `validation_result` is returned by this endpoint, so artifact fields remain unset:
  - `semantic_status = None` for all 10/10 queries in both runs,
  - `contract_id = None` for all 10/10 queries.

So currently, contracts are effectively metadata loaded/sent by the harness, but not yet enforced/scored online by the running service path.

## 6) Contract-structure checks still useful offline
Despite missing runtime validation, contract-required table coverage is:
- ON `10/10`
- OFF `10/10`

This shows generated SQL includes the contract-required tables in all benchmark cases, but does not guarantee metric correctness (see NW3/NW7).
