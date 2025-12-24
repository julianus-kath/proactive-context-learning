# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: 36d99975-8dd3-4c91-bfe7-a90ad26e7dd2 -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Save the PRD to `{@artifacts_path}/requirements.md`.

### [x] Step: Technical Specification
<!-- chat-id: 5c786d01-280c-48bc-9fe4-42a4478acdea -->

Create a technical specification based on the PRD in `{@artifacts_path}/requirements.md`.

1. Review existing codebase architecture and identify reusable components
2. Define the implementation approach

Save to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach referencing existing code patterns
- Source code structure changes
- Data model / API / interface changes
- Delivery phases (incremental, testable milestones)
- Verification approach using project lint/test commands

### [x] Step: Planning
<!-- chat-id: 8614782f-f9fa-4422-9882-3e5ebc5fa48e -->

Create a detailed implementation plan based on `{@artifacts_path}/spec.md`.

1. Break down the work into concrete tasks
2. Each task should reference relevant contracts and include verification steps
3. Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function) or too broad (entire feature).

If the feature is trivial and doesn't warrant full specification, update this workflow to remove unnecessary steps and explain the reasoning to the user.

Save to `{@artifacts_path}/plan.md`.

### [x] Step: Step 0 — Pre-flight Configuration
<!-- chat-id: f64efa0b-686d-43bc-aaef-66d9898dda5b -->

Define configuration knobs and ensure they are wired into orchestrator/config loading.

1. Add or confirm environment/config defaults:
   - `MAX_LLM_CALLS` (existing, keep behavior).
   - `LLM_BUDGET_SAFETY_MARGIN` (default `2`, used in budget-aware routing).
   - `DB_DIALECT` and `DB_DEFAULT_SCHEMA` (used by canonicalization; default to current behavior, e.g., `mssql`/`dbo` or `postgres`/`public` depending on deployment).
2. Ensure these config values are accessible to:
   - Orchestrator (for budget checks and routing).
   - Canonicalization utilities (Phase 5).
3. (Optional) Create or document a feature branch for this work (outside this repo automation).

Verification:
- System starts cleanly with and without the new env vars set.
- Existing behavior is unchanged when env vars are not provided (backward compatible defaults).

### [x] Step: Phase 1 — Instrumentation
<!-- chat-id: fca8d27f-2cb9-4e23-9712-e8790c2ab872 -->

Implement LLM usage accounting and loop diagnostics.

1. Extend `langgraph_integration/contracts/state.py`:
   - Add optional fields: `llm_usage`, `node_entry_counts`, `loop_events`, `answer_mode`.
   - Add optional fields for loop helpers: `discovery_cache`, `last_sql_query`, `last_join_plan`, `required_tables_from_kpi`.
   - Keep all new fields Optional in the type definitions and initialize them lazily at runtime (e.g., with `or {}`) to maintain backward compatibility.
   - Preserve and continue populating `total_llm_calls` so existing tests and consumers remain valid; treat it as a derived summary from `llm_usage["total"]`.
2. Update orchestrator (`langgraph_integration/orchestrator.py`):
   - Increment `node_entry_counts` on each node entry (intent, discovery, join_sql, sql_validator, exec_recovery, result_validator, answer).
   - Define a single accounting rule for LLM usage (Phase 1): **count per orchestrator subgraph invocation**:
     - Each time the orchestrator invokes an agent subgraph that may use an LLM internally (intent, discovery, join_sql, sql_validator, exec_recovery, result_validator, answer), increment `llm_usage[node_name]` by 1 and `llm_usage["total"]` by 1.
     - Implement this in a centralized helper or wrapper (e.g., around `_check_llm_budget` / node dispatch) so the rule is consistent and low-overhead.
   - Keep `total_llm_calls` in sync with `llm_usage["total"]` to avoid conflicting counters.
   - Emit structured debug logs via `debug_logger` when:
     - A node spends a call (include node, reason, retry_action, loop-related flags).
     - Budget is near / exceeds `max_llm_calls`.
3. Ensure `process_query` return payload includes `llm_usage`, `node_entry_counts`, and `loop_events`, and update `eval/run_benchmark.py` to persist them onto each query artifact.
   - Optionally add a simple `graph_cycles`/`graph_iterations` counter if available from LangGraph primitives.
   - Extend benchmark reporting to emit a per-query table with at least:
     - `query_id | total_calls | intent | discovery | join | repair | answer | discovery_entries | join_entries | same_tables_suppressed | same_sql_suppressed`.

Verification:
- Run `pytest tests/test_orchestrator.py tests/test_orchestrator_integration.py`.
- Run a small benchmark (`eval/run_benchmark.py` with 3–5 queries) and confirm:
  - `llm_usage` totals match `total_llm_calls`.
  - `node_entry_counts` reflect expected node visits.
  - `loop_events` are present (even if mostly zeros initially).

### [x] Step: Phase 2 — Loop Control & Budget-Aware Routing
<!-- chat-id: cc74c738-e507-4116-8c84-ededc83861f1 -->

Cache discovery/join outputs, detect redundant loops, and short-circuit when near budget.

1. Implement discovery caching in orchestrator:
   - Add `discovery_cache` to state, storing a fingerprint (user_input, intent, skip_tables/tried_candidate_tables) and last discovery result (`relevant_tables`, `final_tables`, role hints).
   - Define a precise discovery fingerprint and store it alongside the cached payload:
     - Normalized `user_input` (e.g., stripped/lowercased).
     - `intent.operation` and any selected concept IDs (if present).
     - `sorted(skip_tables)` and `sorted(tried_candidate_tables)`.
     - Canonicalized `seed_tables` (once Phase 5 is in place; until then, include current `seed_tables` representation).
   - Before re-entering discovery, compare fingerprint; if unchanged, reuse cached discovery result and avoid an LLM call.
2. Add redundant loop guards:
   - Track `last_discovery_final_tables` and `last_sql_query` in state.
   - If discovery returns the same `final_tables` as previous, increment `loop_events["discovery_reentered_same_tables"]` and skip another discovery call.
   - In join node, if generated SQL matches `last_sql_query`, increment `loop_events["join_sql_regenerated_same_sql"]` and skip regeneration; proceed directly to validation/execution.
3. Implement budget-aware routing:
   - In `_check_llm_budget` (or equivalent), expose remaining budget to nodes.
   - If `llm_usage["total"]` is within 1–2 of `max_llm_calls`, short-circuit nodes that would require LLM calls (e.g., further discovery/join retries) and route toward deterministic paths (validation/exec/answer fallback).

Verification:
- Re-run a known “bad” query from the benchmark (high prior LLM usage, e.g. the “Chai reorder” query above):
  - Confirm discovery runs at most once per unchanged fingerprint (even if `discovery` node_entry_counts are >1, `llm_usage["discovery"]` should stay low and `discovery_cache_hit` / `discovery_budget_short_circuit` events should be present).
  - Confirm join does not regenerate identical SQL more than once (multiple `join_sql` node entries should mostly be covered by `join_inputs_cache_hit` / `join_budget_short_circuit` loop events, with `llm_usage["join"]` staying low).
  - Inspect `llm_usage` and `loop_events` in benchmark artifacts to validate that most residual budget usage now comes from validation/repair (`llm_usage["repair"]`) rather than from repeated discovery/join loops, and that `LLM_BUDGET_EXCEEDED` at `stage=answer` is rare.

### [x] Step: Phase 3 — Deterministic Answer Fallback
<!-- chat-id: 45b0cd06-8304-4ceb-99eb-b572bf47880b -->

Ensure users receive a meaningful answer when SQL execution succeeds, even with zero remaining LLM budget.

1. Extend answer node (`langgraph_integration/agents/answer/agent.py` or orchestrator `_answer_node`):
   - When `exec_result.ok` and `row_count > 0` (independent of current budget state), prefer deterministic rendering:
     - Use `_format_execution_results` (or a new small helper) to build `final_response` and `final_answer` without calling LLM when deterministic mode is enabled or budget is exhausted.
     - Ensure there is a clear, config-controlled path where `exec_result.ok` and `row_count > 0` results in deterministic rendering even if some budget remains, so behavior is predictable.
   - Set `answer_mode` in state (e.g., `"deterministic_from_data"` vs `"llm"`).
2. Handle `LLM_BUDGET_EXCEEDED` and planner/repair exhaustion gracefully:
   - If an LLM call is blocked at stage `answer` but `exec_result` has data:
     - Fall back to deterministic rendering and clear/adjust `error_info` to indicate a degraded but valid answer (e.g., `type="LLM_BUDGET_EXCEEDED_DEGRADED_ANSWER"`).
   - If there is no data but we have strong structural signals (e.g., required KPI tables missing from `final_tables`, or domain guardrails like `PRODUCT_MAPPING_ERROR` fired in Phase 4):
     - Prefer a **specific, domain-aware** diagnostic over the generic `UNGROUNDED_RESPONSE_PREVENTED` message, indicating which tables/concepts were missing and what the user can change.
   - If there is no data and no structural hints, return a generic but safe diagnostic message indicating:
     - Missing tables or unresolved concepts.
     - Suggested user actions (“narrow scope to X”, etc.).
3. Ensure grounding and safety gates remain intact:
   - Preserve existing guards for hallucination / no-data scenarios.

Verification:
- Run `pytest tests/test_orchestrator_result_validator_integration.py tests/test_complete_system.py`.
- Add or adapt a test where `max_llm_calls` is artificially low but SQL execution succeeds:
  - Assert `final_response` contains tabular data and summary text without answer-node LLM usage.
- Add a test mirroring the “Chai reorder” shape where joins or required tables are intentionally mis-specified:
  - Assert the system returns a **specific** diagnostic (e.g., about missing `products` table or bad product mapping) rather than a generic ungrounded-response message.
- In a benchmark rerun, confirm that queries with successful SQL execution always yield a data-based `final_response` even when `error_info.type == "LLM_BUDGET_EXCEEDED"`, and that purely structural failures produce clear, targeted diagnostics.

### [x] Step: Phase 4 — KPI-Driven Table Selection Guardrails
<!-- chat-id: 06430c1c-dd31-4d25-ab9a-e33c5816fabf -->

Use KPI expressions to enforce required tables and add product-domain sanity checks.

1. Derive `required_tables_from_kpi`:
   - In `langgraph_integration/concept_mapper.py` (or related module), parse KPI expression strings for table-qualified identifiers (e.g., `Products.`, `OrderDetails.`).
   - Map these to canonical table names (e.g., `public.products`, `public.order_details`) and store in state as `required_tables_from_kpi`.
2. Enforce required tables during discovery/join:
   - In discovery agent (`langgraph_integration/agents/discovery/agent.py`), ensure `required_tables_from_kpi` are present in `final_tables` when applicable (or flagged if missing from catalog). For the `inventory_reorder` KPI specifically, require inclusion of the `products` table (and any other tables referenced in its expression).
   - In join planning (`langgraph_integration/agents/join_sql/agent.py`), ensure required tables are included as fact or dimension tables; if not, bias selection or surface a deterministic error (`DIMENSION_MISSING` with clearer guidance) **before** spending more cycles on execution/repair.
3. Add domain guardrails for product semantics:
   - Implement `validate_product_semantics(sql: str, state: BaseState)` (e.g., in join agent or a small helper) to detect obviously wrong mappings like `order_details.order_id AS product_name` when intent/entities mention “product” or KPIs reference `Products.`.
   - If triggered, set a structured validation error (`PRODUCT_MAPPING_ERROR`) and either:
     - Route back to join with hints forcing inclusion of the `products` table/product_id column, or
     - Short-circuit with a clear diagnostic if the catalog cannot satisfy the required mapping (e.g., no `products` table exists).

Verification:
- Add/extend tests for KPI/concept-driven queries (including the “Chai reorder” scenario):
  - Assert `relevant_tables` / `final_tables` include the products table whenever `inventory_reorder` (or other `Products.` KPIs) are active.
  - Assert final SQL joins orders, order_details, and products, and filters by product (e.g., `products.product_name = 'Chai'`), **never** projecting `order_id` as `product_name`.
- Manually run the “Chai reorder” query via eval or service and confirm:
  - No `order_id AS product_name` pattern appears in the generated SQL.
  - The user receives either a correct data-backed reorder answer or a targeted diagnostic explaining which product/inventory tables are missing or inconsistent.

### [x] Step: Phase 5 — Early Identifier Canonicalization
<!-- chat-id: 041199fe-fdc4-4662-9cf4-036fb098b2ae -->

Normalize table identifiers early so the entire pipeline uses a consistent naming scheme.

1. Add `langgraph_integration/utils/canonical_names.py`:
   - Implement `canonical_table_name(raw_name: str, dialect: str, schema: str) -> str` to:
     - Normalize bracketed MSSQL forms (`[dbo].[Order Details]`) and dotted forms (`dbo.Products`) into canonical `schema.table`.
     - Prevent duplicates such as `[dbo].[dbo].[Suppliers]`.
   - Optionally add `canonicalize_table_list`.
2. Wire canonicalization into concept mapping:
   - In `concept_mapper.py`, when building `seed_tables`, call `canonical_table_name` using configured `DB_DIALECT` and `DB_DEFAULT_SCHEMA` (env or config).
   - Ensure `state["seed_tables"]` and logged seed tables are canonical (e.g., `public.orders` on Postgres).
3. Apply canonicalization in discovery and join:
   - In discovery agent:
     - Canonicalize all table names when populating `relevant_tables`, `final_tables`, `DiscoveryOutput.relevant_tables`, and `discovery_log`.
     - Ensure column index and role hints use canonical table keys.
   - In join agent:
     - Treat incoming tables as canonical; avoid reintroducing `[dbo].` prefixes when `DB_DIALECT=postgres`.
4. Guard SQL validator behavior:
   - Ensure SQL validator preserves canonical logical names and only performs dialect-specific syntactic rewrites (quoting, casing), not schema renaming back to `[dbo]`.

Verification:
- Add or update tests to cover canonicalization behavior:
  - `[dbo].[Order Details]` → `public.order_details` when `DB_DIALECT=postgres`.
  - No double-schema artifacts like `[dbo].[dbo].[Suppliers]`.
- Run a discovery-heavy benchmark subset and confirm logs show only canonical names (`public.*`) and no `[dbo].*` on Postgres.

### [x] Step: Additional Syntax Cleansiung
<!-- chat-id: 9e32a1da-dd53-453f-ab10-4a9f89773a30 -->

Summary of what the logs show (with concrete examples)

1) The API returns “execution failed / no rows”, but the MCP server clearly executes and returns rows

Symptom in API response:
	•	exec_result.ok = false
	•	row_count = 0
	•	data = []

But MCP server log for the same request:
	•	Executes successfully and returns rows:

Example (MCP):
	•	Input SQL (still MSSQL-ish):
	•	SELECT TOP 1000 [public].[order_details]...
	•	MCP normalizes and runs:
	•	SELECT public.order_details.order_id AS product_name, SUM(public.order_details.quantity) AS total_metric FROM public.order_details ... LIMIT 1000
	•	Result:
	•	✅ QUERY EXECUTION COMPLETED
	•	📊 Results: 100 rows ... Truncated: True

Conclusion: there is a mismatch between the MCP execution result and what the web API returns (results are being dropped/overwritten or a different executor path is being used later).

⸻

2) You still have a “dialect leakage” path that sends MSSQL syntax to Postgres (TOP, dbo, brackets)

Your Postgres container log contains many failures where Postgres is receiving MSSQL syntax directly.

Examples (Postgres container):
	•	MSSQL TOP sent to Postgres:
	•	ERROR: syntax error at or near "1000" at character 12
	•	STATEMENT: SELECT TOP 1000 ...
	•	MSSQL schema dbo.* sent to Postgres:
	•	ERROR: relation "dbo.customers" does not exist
	•	STATEMENT: ... FROM dbo.customers
	•	Bracket identifiers also appear in these failing statements:
	•	FROM [dbo].[order_details]

Conclusion: you have at least one execution/probing path that bypasses MCP normalization and hits Postgres directly.

⸻

3) There is an invalid query being generated: COUNT(DISTINCT *)

Postgres container log:
	•	ERROR: syntax error at or near "*" at character 23
	•	STATEMENT: SELECT COUNT(DISTINCT *) AS customers_count FROM customers

Conclusion: some part of the pipeline (profiling/validator/recovery) is issuing an invalid “distinct star” query. This can poison “exec ok” signals even if the main query succeeds.

⸻

4) Wrong query semantics: the system generates a query unrelated to “reorder Chai”

From the API response:

Generated SQL:

SELECT TOP 1000 [public].[order_details].[order_id] AS product_name,
       SUM([public].[order_details].[quantity]) AS total_metric
FROM [public].[order_details]
GROUP BY [public].[order_details].[order_id]
ORDER BY total_metric DESC

Problems:
	•	order_id AS product_name is wrong mapping.
	•	Query computes “top orders by quantity”, not “when to reorder product Chai”.

Discovery output also shows table/schema inconsistencies:
	•	sources: public.order_details, public.orders, public.customers, dbo.products
	•	final_schema snippet only lists order_details, orders, customers (no products columns), so join planner can’t build reorder logic.

Conclusion: join/SQL planning is missing the products table/columns needed for stock/reorder computations.

⸻

5) “dbo” resolution mismatch in Postgres mode is still present

In the API discovery log:
	•	seed injection includes [dbo].[...] tables
	•	final tables include dbo.products

But MCP catalog warmup reports “14 tables” in Postgres Northwind (typically under public, not dbo).

Conclusion: your discovery seeds/templates still push dbo.* in Postgres mode, and your new canonicalization/resolver policy won’t “bridge” dbo→public unless you enable explicit schema aliasing or make seeds dialect-aware.

⸻

One-paragraph diagnosis you can paste to a coding agent

The logs show two main issues: (1) MCP successfully normalizes and executes the generated SQL on Postgres (returns ~100 rows), but the web API response still reports exec_result.ok=false and row_count=0, implying results are being dropped/overwritten or another executor/probing path is deciding failure. (2) There is dialect leakage: Postgres container receives MSSQL SQL (SELECT TOP ..., [dbo].*, brackets) and even invalid COUNT(DISTINCT *), causing repeated DB errors. Separately, the generated query itself is semantically wrong for “reorder Chai” (it aggregates order_details.order_id as product_name) and discovery/join planning appears to omit products from the schema snippet, so reorder logic can’t be formed.

⸻

Quick “evidence snippets” (copy/paste)

MCP proves execution works:
	•	📝 Final SQL ... SELECT public.order_details.order_id ... LIMIT 1000
	•	✅ QUERY EXECUTION COMPLETED
	•	📊 Results: 100 rows ... Truncated: True

Postgres container proves MSSQL syntax leakage:
	•	ERROR: syntax error at or near "1000" ... STATEMENT: SELECT TOP 1000 ...
	•	ERROR: relation "dbo.customers" does not exist ... FROM dbo.customers
	•	ERROR: syntax error at or near "*" ... STATEMENT: SELECT COUNT(DISTINCT *) ...

API proves mismatch / overwrite:
	•	"exec_result": {"ok": false, "data": [], "row_count": 0}
	•	"error_info": {"type": "UNGROUNDED_RESPONSE_PREVENTED", ...}

  Two separate problems are happening, and your recent canonicalizer/resolver changes only touch one of them.

What’s happening under the hood (based on your logs)

A) The system is still planning the wrong query

Your user question is “When will product Chai need to be reordered based on stock + sales velocity”.

But the SQL you generated is:

SELECT ... order_details.order_id AS product_name, SUM(order_details.quantity) ...
FROM order_details
GROUP BY order_details.order_id

That’s “top orders by summed quantity”, not “reorder time for product Chai”.

So even when execution works, the query is semantically unrelated. That’s why the answer layer refuses (“UNGROUNDED_RESPONSE_PREVENTED”)—it can’t justify answering the reorder question from that result.

Why did it happen?
	•	Your discovery_log.final_tables contains dbo.products but the final_schema snippet does not include products, only order_details, orders, customers.
	•	Then join/planning builds a query only from the schema snippet tables and misses the product stock columns entirely.
	•	Also, the system is confusing order_id with product_name (clearly a join-plan / column-selection bug).

B) You have dialect/schema leakage: dbo.* keeps appearing in Postgres mode

Your Postgres container log shows errors like:
	•	relation "dbo.customers" does not exist
	•	relation "dbo.order_details" does not exist
	•	SELECT TOP 1000 ... syntax errors

Those errors are from an earlier stage where SQL was being sent to Postgres without your MCP normalization. (Your current MCP log shows the validator fixes TOP/brackets and executes successfully.)

So you have two execution paths:
	1.	MCP path (works): normalizes TOP/brackets and runs public.*
	2.	Non-MCP / direct DB path or “SQL probe path” (broken): still emits dbo.* and TOP

You can see this mismatch clearly:
	•	MCP log: executed SELECT public.order_details... LIMIT 1000 → 100 rows
	•	API response: exec_result.ok=false, row_count=0, data=[]

That means the web app is not using the MCP result (or is dropping it during parse), and some other executor/validator path is deciding “failed/no rows”.

This is the core reason “not much changed”.

⸻

Why it still doesn’t work

1) Wrong table selection / snippet gating

Even though discovery “knows” products is required (required_tables_from_kpi: ["public.products"]), it doesn’t make it into the schema snippet, so join agent can’t build stock + velocity logic.

Fix: ensure “required tables” are forcibly included in:
	•	final_tables
	•	schema_snippet / final_schema
	•	and any “relevant_table_details” passed to join

If products is required for reorder KPI, the join agent must see products.units_in_stock, products.reorder_level, etc.

2) Schema mismatch you intentionally introduced (dbo preserved in Postgres)

You changed canonicalization to preserve explicit schema in Postgres:
	•	[dbo].[Order Details] → dbo.order_details

In a Postgres Northwind DB, those tables are almost certainly under public, not dbo.

So whenever LLM emits dbo.* (and it will, because your seed injection and KPI templates still use dbo), your resolver will now correctly say “not found” (by design), and you’ll end up with missing products / missing matches unless you add explicit schema aliasing.

Fix options:
	•	Best: make seed injection / KPI templates dialect-aware: in Postgres mode seed public.orders, public.order_details, public.products (not dbo.*).
	•	Pragmatic: enable a config knob schema_aliases={"dbo":"public"} in Postgres deployments. (You already outlined this.)

3) You have a broken “COUNT(DISTINCT *)” probe in some path

Your Postgres logs include SELECT COUNT(DISTINCT *) ... which is invalid SQL in Postgres. That’s not coming from your MCP validator log; it’s coming from somewhere else (profiling/stats/validator/recovery loop).

Fix: find the code that generates COUNT(DISTINCT *) and change to either:
	•	COUNT(*) (if you just want row count), or
	•	COUNT(DISTINCT <pk_or_column>) if you intended distinct entities.

This bug alone can cause “exec failed” signals even if the main query succeeds.

⸻

The minimum set of changes that will actually move the needle

1) Make execution single-source-of-truth

Right now you’re sometimes running queries outside the MCP normalization pipeline.

Action:
	•	Ensure process_query → exec_sql always goes through the MCP run_query tool for Postgres mode.
	•	Delete/disable any fallback “direct psycopg” executor, or gate it behind dialect=="mssql" only.

How to confirm:
	•	Add a log line in the orchestrator right before execution: EXECUTOR=MCP vs EXECUTOR=DIRECT.
	•	Your API response exec_result must match MCP rows (row_count=100, truncated=true) if it’s wired correctly.

2) Force-include required KPI tables into the schema snippet

When discovery emits required_tables_from_kpi=["public.products"], enforce:
	•	final_tables = union(final_tables, required_tables_from_kpi)
	•	schema snippet includes those tables/columns (at least columns needed for reorder logic)

This prevents join agent from producing garbage queries that never touch inventory columns.

3) Dialect-aware seed injection (stop injecting dbo in Postgres)

In Postgres mode:
	•	seed tables should be public.orders, public.order_details, public.products, etc.
	•	KPI expressions should use Postgres-safe identifiers (or at least schema-less names that resolver maps to public).

This is the cleanest fix and aligns with your “no semantic guessing” policy.

4) Fix the “TOP” and bracket identifiers at the source (not only in MCP)

Even though MCP normalizes, your other path still hits Postgres with TOP.

Action:
	•	In SQL generation templates, emit dialect-correct limit:
	•	Postgres: LIMIT n
	•	MSSQL: TOP n
	•	Use consistent quoting rules or no quoting, but don’t mix [] with Postgres.

⸻

Why the final response says it failed even though MCP executed

Because your API response shows:

"exec_result": {"ok": false, "data": [], "row_count": 0}

But MCP shows it executed and returned 100 rows.

That is not an LLM problem. That’s a plumbing / parse / executor selection problem:
	•	Either you’re not reading the MCP response payload correctly, or
	•	you executed in MCP but then overwrote exec_result with a later failing probe, or
	•	the validator/recovery loop is marking it failed due to unrelated probes (COUNT DISTINCT , dbo.).

⸻

Fast debugging checklist (no refactors, just pinpoint)

Do these in order:
	1.	Log the executor path in orchestrator (MCP vs direct) and include it in the API JSON temporarily.
	2.	Print the raw MCP response (first 200 chars) in the orchestrator right after run_query and before you map to exec_result.
	3.	Search your codebase for COUNT(DISTINCT *) and remove it.
	4.	Search for TOP  generation in join/repair templates; ensure Postgres path never emits it.

### [ ] Step: Pass 2 — Central SQL Execution Gateway
<!-- chat-id: dialect-pass-2 -->

Centralize dialect handling and safety checks in a single execution gateway used by all probes and “real” queries.

1. Implement a shared execution helper in LangGraph integration:
   - Signature sketch:
     - `async def execute_sql(sql_raw: str, *, state: BaseState, purpose: str = "final") -> Dict[str, Any]`.
   - Inside the helper:
     - Canonicalize identifiers (strip quotes/brackets, normalize spacing).
     - Qualify schema using `db_default_schema` and dialect-aware rules.
     - Call the dialect-aware normalizer (TOP↔LIMIT, dbo→schema, etc.).
     - Apply safety sanitizers (`COUNT(DISTINCT *)` → `COUNT(*)`, etc.).
     - Enforce read-only + row caps (reusing MCP `QueryValidator` semantics).
     - Dispatch to MCP via `query_bounded` / `run_query`.
2. Route all probes through the gateway:
   - `_probe_candidate_counts` in orchestrator:
     - Replace direct `self.mcp.query_bounded(sql, ...)` with `execute_sql(sql_raw, purpose="probe")`.
   - `_probe_columns` in `JoinPlanAndSQLAgent`:
     - Replace inline `SELECT TOP 1` / `LIMIT 1` and direct MCP calls with gateway usage.
   - Any other “probe-like” calls (profiling, stats, auto-aggregate helpers) should also call the gateway with `purpose="probe"`.
3. Route ExecAndRecovery through the same gateway:
   - In `ExecAndRecoveryAgent._execute_query_node` and `_query_with_recording`, avoid constructing dialect-specific SQL or calling MCP directly.
   - Instead, build logical SQL and hand off to the gateway, tagging `purpose="final"` for the main answer query and `purpose="probe"` for any auxiliary checks.
4. Make probe failures explicitly non-fatal:
   - When `purpose="probe"` and the gateway returns an error:
     - Log it and add to `warnings` / `loop_events`.
     - Do **not** set `exec_result.ok = False` for the whole request.
     - Do **not** trigger repair loops or grounding gate failures solely due to probe errors.

Verification:
- Single code path between LangGraph and MCP execution for all SQL.
- No direct `self.mcp.query_bounded(...)` remaining in orchestrator/join agents except inside the shared gateway.
- Probe-related failures never cause `UNGROUNDED_RESPONSE_PREVENTED` if the main “final” query succeeds.

### [ ] Step: Pass 3 — Remove Hardcoded Qualifiers & Name-Based Heuristics
<!-- chat-id: naming-pass-3 -->

Eliminate all hardcoded database/server/schema/table assumptions so the system is plug-and-play across databases.

1. Strip hardcoded database and schema prefixes:
   - Ensure `_qualify_table_name` and related helpers use only:
     - `db_dialect`, `db_default_schema`, and dialect-specific env/config (e.g. `DB_MSSQL_DATABASE`).
   - Never emit `OLLuisiDiener.dbo.*` or similar literals; in Postgres mode, never emit a database prefix at all (only `schema.table`).
2. Remove name-based heuristics in agents:
   - Replace any logic that looks for specific table names (`orders`, `products`, `KHKAdressen`, etc.) with:
     - role-based scoring (from Pass 1),
     - or catalog-driven metadata (primary keys, foreign keys, column names).
   - Clarify in comments/docs that agent behavior must not depend on particular ERP schemas.
3. Ensure discovery and join planning are completely decoupled from vendor-specific names:
   - Use only:
     - intent entities/metrics,
     - catalog metadata (column names, types, FK graph),
     - role hints inferred from that metadata.
4. Guard with simple regression checks:
   - Add or update lightweight tests that:
     - spin up a minimal synthetic catalog with different schema/table names,
     - confirm discovery/join/exec still produce a coherent plan without any assumptions about “orders/products/customers”.

Verification:
- Grep for vendor-specific names (`dbo.`, `KHKAdressen`, `OLLuisiDiener`, etc.) yields only:
  - docs,
  - tests explicitly documenting old behavior,
  - or commented migration helpers.
- Changing only connection/dialect config and restarting MCP is sufficient to point the system at a new database without code changes.

### [ ] Step: Agent Response Optimization

“From the latest benchmark run (results.json), main systemic failures are: (1) schema_snippet/table selection drops required dimension tables (e.g., Q6 drops shippers), (2) early abort returns generic ‘system working’ answer with missing_sql even when required tables exist (Q7), (3) non-canonical dbo.* leaks into final_tables under Postgres (Q8), (4) result validator accepts answers that ignore core entities (Q9 employees/products missing), (5) probe-style SQL (SELECT * ... LIMIT) is being treated as final answering SQL. Implement invariants: intent/KPI required tables must be present in schema_snippet; enforce canonical table naming before join; block probe SQL as final unless sampling intent; remove health-fallback path for non-health intents; strengthen result validator to require table/entity coverage and metric computation.”

Benchmark run summary (from 20251224_111756_northwind_v2/results.json)

High-level
	•	Total queries: 12
	•	Status: 9 success, 3 failed (Q2, Q5, Q7)
	•	Avg latency: ~5.5s/query
	•	Avg LLM calls: ~5.25/query
	•	Failure reasons frequency:
	•	missing_sql: 3
	•	invalid_final_answer: 2
	•	grounding_gate_activated: 2
	•	missing_tables: 1

The real problem (even among “success”)

A chunk of the “success” items are functionally incorrect: the system often executes a probe-style query (e.g., SELECT * FROM public.order_details LIMIT ...) and then produces an answer that doesn’t match the question.

This is exactly the kind of systemic brittleness you’re pointing out: it’s not “fix Chai,” it’s “stop the pipeline from accepting degenerate plans.”

⸻

Concrete log examples you can pass to a coding agent

1) Selection drops required tables → join/sql can’t answer the question

Q6 question: “% of orders fulfilled by each shipper, avg delivery time”
Discovery seeds: dbo.orders, dbo.shippers, dbo.order_details, dbo.customers
But selection + schema_snippet: only order_details, orders, customers (shipppers is omitted)
Executed SQL: SELECT * FROM public.order_details ... LIMIT 10
Final answer: “No records found … in order_details” despite row_count=10 and preview rows existing.

This is a double failure:
	•	table selection/snippet misses required dimension (shippers)
	•	answer formatter asserts “no records” even though results exist

Coding-agent task framing: enforce that if intent mentions shipper/delivery-time KPI, schema_snippet must include orders + shippers (and any join path tables), not just “top 3”.

⸻

2) KPI-required tables exist but pipeline can still terminate with missing_sql

Q7 question: “inventory below reorder level”
Discovery log shows:
	•	concepts: ["inventory_reorder"]
	•	required_tables_from_kpi: ["public.products"]
	•	seed_tables: dbo.products, dbo.suppliers, dbo.order_details
But events are empty and the graph never reaches join/exec.
Node entry counts: only parse_intent:1, answer:1
Failure reasons: missing_sql, missing_tables
Final answer: “System is working. Database has 14 tables…”

This indicates an early abort / gating path that returns a “health/system” style response instead of forcing the pipeline to produce SQL when intent is clearly queryable.

Coding-agent task framing: remove/raise the threshold for any “health fallback” answer path when intent is non-health and catalog contains the required tables (here: public.products).

⸻

3) Schema and table naming leakage (dbo.*) persists into final_tables

Q8 (YoY order volume growth) discovery: required_tables_from_kpi includes public.orders, public.products
But final_tables includes: public.order_details, public.orders, public.customers, dbo.products
Executed SQL: SELECT COUNT(*) FROM public.order_details
Final answer: basically “I counted order_details; maybe you need order tables.”

So even after normalization work, the pipeline still allows:
	•	mixed canonical (public.*) and non-canonical (dbo.*) table names in the same state
	•	a “growth rate” question to collapse to a meaningless count

Coding-agent task framing: enforce a single canonical table namespace before join/sql planning and before state is finalized (no dbo.* allowed when dialect=postgres).

⸻

4) “Success” can still be totally mis-grounded (result validator not strict enough)

Q9 question: “employees revenue + top-selling products”
Executed SQL: aggregates order revenue by order_id from public.order_details only
No join to employees, no join to products, no “top-selling products”, no employee attribution.

Yet status is “success”.

Coding-agent task framing: tighten “result validator” rules:
	•	If intent mentions entity employees, require employees table (or equivalent) in tables_used OR explicit join path.
	•	If question asks for “top-selling products”, require products table usage or product identifier + name mapping.
	•	If missing, force repair (don’t accept the answer).

⸻

Systemic fixes to prioritize (generic, plug-and-play aligned)
	1.	Hard invariants between intent → required tables → schema_snippet
	•	If required_tables_from_kpi contains public.products, then final_schema must include products columns.
	•	If intent references a dimension explicitly (“shipper”, “employee”), require that dimension table (or a catalog-mapped equivalent) is included.
	2.	Block “probe SQL” from being accepted as final SQL
	•	Any final query that is just SELECT * FROM <single table> LIMIT n should be treated as non-answering unless the user asked “show sample rows”.
	3.	Canonicalization must be enforced at state boundaries
	•	No mixed dbo.* + public.* in final_tables when dialect is postgres.
	•	Canonicalize once, early, then treat non-canonical names as invalid state.
	4.	Kill the “system is working” escape hatch for non-health questions
	•	If intent != health-check and catalog has candidate tables, the graph must proceed to discovery → join_sql → validate → exec (or return a concrete error with why it could not).
	5.	Result validator needs question/intent coverage checks
	•	Validate that the executed SQL actually computes the asked metrics (YoY growth, share by shipper, avg delivery time).
	•	If not, do a repair cycle (or fail explicitly), but don’t mark success.



