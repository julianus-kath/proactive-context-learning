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

### [ ] Step: Phase 6 — Benchmark & Regression Verification

Consolidate verification across phases and confirm budget/loop improvements.

1. Re-run the 12-query benchmark via `eval/run_benchmark.py`:
   - Capture `results.json` and inspect:
     - `llm_usage` per query.
     - `node_entry_counts` and `loop_events` (with focus on discovery/join loops).
     - Frequency of `LLM_BUDGET_EXCEEDED` errors, especially at `stage="answer"`.
2. Compare with previous run:
   - Confirm typical queries use ~3–8 LLM calls.
   - Confirm a significant reduction in budget-exceeded failures and improved `final_response` quality.
3. Run full test suite (or at least orchestrator + integration tests) and document any deviations.

Verification:
- All orchestrator and system tests pass.
- Benchmark metrics demonstrate fewer loops and more successful data-backed answers.
