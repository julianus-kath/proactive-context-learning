# PRD – LLM Looping Fixes & Budget-Aware Orchestration

## 1. Problem Statement

The current multi‑agent LangGraph orchestrator for ERP-style analytical queries frequently exhausts its global LLM call budget and/or hits the LangGraph recursion limit before producing a high‑quality business answer.

Observed issues from recent benchmark runs and logs:
- Most queries consume the full LLM budget (`total_llm_calls` ≈ 20) and/or recursion limit before the `answer` stage can run successfully.
- Even “successful” queries often fall back to generic budget‑exhaustion or “data does not answer your question” messages instead of providing business-relevant insights.
- The orchestrator repeatedly loops through discovery and planning cycles (keyword extraction → seed injection → search → rank → selection → join/repair) without strong loop guards, burning multiple LLM calls per loop.
- Table selection for KPI‑driven queries is brittle; in some cases the selected tables and generated SQL are structurally wrong (e.g., using `order_details.order_id AS product_name` instead of joining to `products`).
- Identifier naming is inconsistent across the pipeline (e.g., `[dbo].[Orders]` vs. `public.orders`), which introduces confusion in discovery prompts, ranking, and join planning, and risks double‑schema patterns like `[dbo].[dbo].[Suppliers]`.
- Answer generation currently depends heavily on the LLM, even when a valid `exec_result` is available, so budget exhaustion at late stages can erase value from already‑executed SQL.

The net effect is that the system is unreliable for complex KPI-style questions, wastes LLM budget on repeated loops, and produces weak or generic final answers even when it has the right data.

## 2. Goals & Non‑Goals

### 2.1 Goals

- Reduce global LLM budget consumption per query by eliminating redundant discovery and replanning loops.
- Make LLM usage transparent per stage (intent, discovery, join, repair/validation, answer) to support debugging and tuning.
- Ensure that, whenever SQL execution succeeds and returns data, the user receives a meaningful, structured answer even if no LLM budget remains.
- Improve table selection and SQL quality for KPI‑driven queries (e.g., inventory reorder, supplier risk, revenue/fulfillment KPIs).
- Normalize table and identifier naming early in the pipeline so all agents see a consistent, dialect‑appropriate schema view.
- Maintain or improve current success rate on the benchmark dataset without regressing simpler queries.

### 2.2 Non‑Goals

- Redesigning the entire multi‑agent architecture or replacing LangGraph is out of scope.
- Overhauling the MCP/server‑side discovery implementation is out of scope; changes should be limited to client orchestration and prompt/state wiring unless absolutely necessary.
- Adding brand‑new user‑facing features (e.g., visual dashboards) is out of scope; the work focuses on reliability, budget efficiency, and answer quality for existing query flows.
- Changing database schemas or business KPIs is out of scope; we assume the current schema and KPI expressions remain the source of truth.

## 3. Users & Use Cases

Primary users:
- Data/BI consumers using natural language to ask ERP questions (e.g., inventory managers, operations analysts).
- The thesis evaluation harness and internal developers running `eval/run_benchmark.py` to measure query success.

Key use cases:
- Complex KPI questions (e.g., “When will Chai need to be reordered?”, “What percentage of orders are fulfilled by each shipper and their average delivery time?”) should:
  - Select structurally appropriate tables/views (including `products` for inventory questions).
  - Generate valid SQL that encodes the KPI correctly.
  - Return a useful answer even under tight LLM budgets.
- Simpler questions (counts, simple selections) should complete within a handful of LLM calls and avoid unnecessary discovery/repair loops.
- Developers should be able to inspect, for each benchmark query:
  - How many LLM calls each node consumed.
  - How often discovery/join were re‑entered and whether candidate sets actually changed.

## 4. Functional Requirements

### 4.1 Instrumentation & LLM Usage Accounting (Phase 1)

- The orchestrator state MUST track LLM usage per node/stage:
  - `state["llm_usage"] = {"intent": int, "discovery": int, "join": int, "repair": int, "answer": int, "total": int}`.
  - The existing `total_llm_calls` counter MUST remain supported for backward compatibility, but should become a derived or synchronized value from `llm_usage["total"]`.
- Every place where an LLM subgraph or LLM call is invoked (intent, discovery, join/SQL generation, validation/repair, answer) MUST:
  - Increment the relevant per‑node counter and `llm_usage["total"]`.
  - Log a structured debug event with: node name, reason/context, and current retry counters.
- The orchestrator MUST log when a node is re‑entered, including:
  - Node name.
  - Retry counters (e.g., `retry_attempt_count`, `plan_attempt_count`, `exec_attempt_count`).
  - Key state inputs that justify the re‑entry (e.g., new `skip_tables`, changed `final_tables`).
- Benchmark tooling MUST be able to export per‑query aggregates:
  - Total calls per node per query.
  - Count of “discovery re‑entered” events per query.
  - Count of “same tables selected again” events per query (see Phase 2).

Open question:
- Exact output format for the per‑query LLM usage summary (CSV vs JSON vs log‑only). Default assumption: JSON appended to existing `results.json` or a sibling diagnostics file.

### 4.2 Loop Control & Caching for Discovery and Planning (Phase 2)

- Discovery results MUST be cached per query as long as inputs have not materially changed:
  - Cache key MUST include at least: `user_input`, `intent.keywords_for_discovery`, `skip_tables`, `tried_candidate_tables`, and any concept/KPI hints that affect selection.
  - If the cache key is unchanged, the system MUST reuse `relevant_tables`, `final_tables`, `schema_snippet`, and related discovery outputs instead of calling the DiscoveryAgent again.
- The orchestrator MUST detect redundant discovery loops:
  - If the last discovery call’s `final_tables` is identical to the current candidate set (after canonicalization, see 4.5), it MUST NOT re‑invoke discovery and SHOULD log a “redundant_discovery_suppressed” event.
- Similarly, the orchestrator MUST avoid regenerating identical SQL:
  - If join planning or SQL generation proposes the same `sql_query` as the last attempt for the same candidate tables/intents, it MUST reuse the previous SQL and proceed to execution/validation.
  - A per‑query `sql_history` (or equivalent) MUST be retained to support this comparison.
- Budget‑aware routing:
  - The orchestrator MUST consider remaining budget (`llm_usage["total"]` vs configured limit) before entering nodes that require LLM calls.
  - If remaining budget is below a configured safety threshold (e.g., ≤ 1–2 calls left), the system SHOULD:
    - Prefer deterministic actions (reuse discovery results, reuse previous SQL, skip non‑critical LLM answer formatting).
    - Route directly to deterministic answer fallback (see 4.3) when possible.

Open questions:
- Exact thresholds for “near limit” (e.g., 1 vs 2 vs 3 remaining calls).
- Whether to expose these thresholds as environment variables/config settings vs hard‑coded defaults.

### 4.3 Deterministic Answer Fallback (Phase 3)

- If `exec_result.ok == True` and `row_count > 0`:
  - The orchestrator MUST be able to produce a usable final response without calling the AnswerAgent LLM.
  - This deterministic renderer SHOULD reuse `_format_execution_results` or a thin wrapper around it.
  - The answer MUST:
    - Show key rows and aggregates (where applicable).
    - Provide a concise, human‑readable summary even if generic (e.g., “Found N rows with columns A, B, C…”).
- If `LLM_BUDGET_EXCEEDED` occurs in any stage:
  - And valid `exec_result` data exists: the system MUST still construct a data‑based final response using the deterministic renderer.
  - If no data is available: the system MUST return a clear diagnostic, including:
    - That the LLM budget was exceeded.
    - Any obvious structural blockers (e.g., missing required tables) if known.
    - A simple suggestion for the user (e.g., “Try narrowing the time window” or “Ask a simpler question about X only”).
- The benchmark harness MUST treat queries with successful SQL execution and deterministic responses as “success” (assuming content passes existing validation rules), even if no LLM‑styled narrative is present.

Open questions:
- Whether deterministic summaries need to be tuned per operation type (e.g., counts vs aggregations vs row previews) beyond the current `_format_execution_results` behaviour.

### 4.4 Table Selection & KPI‑Driven Guardrails (Phase 4)

- The orchestrator MUST enforce “required tables” implied by KPI expressions:
  - KPI expressions (e.g., `inventory_reorder`, `supplier_risk`, `fulfillment_time`, `revenue`) MUST be parsed for table identifiers (e.g., `Products.` → `products`, `Orders.` → `orders`).
  - When a concept is selected (e.g., `inventory_reorder`), its required tables MUST be included in the final set of discovered/selected tables, assuming those tables exist in the catalog.
- For KPI‑style queries mentioning “product”, “item”, or specific product names:
  - The final table selection MUST include `products` (or an equivalent product dimension) whenever the KPI or discovery hints reference product-level metrics.
- Join/SQL planning MUST incorporate lightweight domain guardrails:
  - If the query is about “products” and the selected columns for key fields clearly map to IDs unrelated to products (e.g., `order_details.order_id AS product_name`), the system MUST:
    - Flag this as an invalid mapping.
    - Trigger a replan that enforces inclusion of `products` and uses `products.product_name` for product names.
  - Similarly, join plans SHOULD require presence of `product_id` or `products.product_name` when answering product-focused KPIs.
- These guardrails MUST be expressed as deterministic checks around the LLM outputs (SQL strings / column mappings), not just additional prompt text, to prevent silent structural errors.

Open questions:
- How strict these guardrails should be for more ambiguous questions where “product” may be implied but not explicit.
- Whether required tables should be enforced as hard constraints vs soft preferences when they conflict with discovery scores.

### 4.5 Early Identifier Canonicalization (Phase 5)

- A canonicalization helper MUST exist, e.g.:
  - `canonical_table_name(raw_name: str, dialect: str, schema: str) -> str`
  - Behaviour examples (Postgres target):
    - `[dbo].[Order Details]` → `public.order_details`
    - `dbo.Products` → `public.products`
    - Prevents invalid forms such as `[dbo].[dbo].[Suppliers]`.
- Canonicalization MUST be applied at the earliest possible stages where table names are constructed/used:
  - Seed injection construction (e.g., the discovery seed tables).
  - Discovery results (`seed_tables`, ranked tables, selected tables, `final_tables`).
  - Join planning inputs and any derived state used for SQL generation.
- All prompts, logs, and serialized discovery logs for Postgres runs SHOULD use canonical names (e.g., `public.orders`, `public.order_details`) instead of mixed MSSQL/legacy forms.
- The SQL validator and executor MUST continue to work with canonical names and MUST NOT reintroduce `[dbo].` prefixes for Postgres deployments.

Open questions:
- How to handle cross‑dialect configurations where MSSQL is still a valid backend; likely require a `dialect`/`schema` parameter propagated from configuration.

## 5. Constraints & Assumptions

- The orchestrator remains the single entry point for query processing (`QueryOrchestrator.process_query` and `eval/run_benchmark.py` flows).
- The global LLM call budget is configured via `state["max_llm_calls"]` (default ~20), but may be increased later once loops are under control.
- LangGraph recursion limits (e.g., 1500) remain a separate safety guard; however, changes here are not a primary lever for solving the looping problem.
- The MCP catalog and discovery behaviour are treated as external systems; we assume they provide:
  - Table metadata (names, schemas, simple stats).
  - KPI expression hints and concept mappings as currently logged in `discovery_log`.
- Existing tests around orchestrator behaviour, result validation, and SQL validation MUST continue to pass; any changes to contracts must be coordinated with those tests.

## 6. Success Metrics

Target benchmarks after implementation:

- LLM usage:
  - Median LLM calls per query: 3–8 (vs ~20 today).
  - Zero queries in the benchmark should fail solely due to `LLM_BUDGET_EXCEEDED` at the `answer` stage when SQL execution has already succeeded.
- Looping and retries:
  - For typical KPI queries, discovery should run at most once per “meaningfully changed” candidate set.
  - Count of “discovery re‑entered with same final_tables” events should be zero in normal runs.
  - No queries should hit the LangGraph recursion limit for the standard benchmark dataset.
- Answer quality:
  - Any query with `exec_result.ok == True` and `row_count > 0` should:
    - Produce a non‑empty, structured final response.
    - Avoid generic budget/recursion fallback text as the primary answer.
  - KPI‑driven queries like “Chai reorder” should:
    - Include `products` in selected tables.
    - Generate SQL that joins `orders`, `order_details`, and `products` appropriately (or an equivalent view).
- Diagnostics:
  - Benchmark outputs MUST include, per query, a lightweight summary of LLM call distribution and key loop counters so regressions can be detected quickly.

## 7. Open Questions for Stakeholders

- What is the acceptable upper bound for LLM calls per query for production (vs. research) usage?
- Should deterministic answers be clearly labeled as such in the UI (e.g., “auto‑formatted from data, no LLM narrative”)?
- Do we want configuration flags to:
  - Disable deterministic answer fallback (force LLM answer) for certain environments?
  - Toggle strictness of KPI guardrails (e.g., “strict” vs “lenient”)?
- Is there a need to surface per‑stage LLM usage to end users (e.g., for cost transparency), or is it sufficient to keep this internal to logs and benchmark reports?

