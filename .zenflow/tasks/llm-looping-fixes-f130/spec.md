# Technical Specification — LLM Looping Fixes & Budget-Aware Orchestration

This spec translates the PRD in `.zenflow/tasks/llm-looping-fixes-f130/requirements.md` into concrete code changes across the LangGraph orchestrator, agents, and evaluation tooling.

---

## 1. Technical Context

- **Language / runtime**
  - Python 3.x.
- **Core libraries**
  - `langgraph` — graph orchestration (`StateGraph`, `ainvoke`).
  - `langchain_openai.ChatOpenAI` — LLM interface (used by orchestrator and agents).
  - `fastapi`, `uvicorn` — HTTP APIs (`/process_query`, evaluation service).
  - `httpx` — async HTTP client for benchmark runner.
- **Key modules involved**
  - Orchestrator and graph:
    - `langgraph_integration/orchestrator.py`
    - `langgraph_integration/graph_definition.py` (for LangGraph Studio export, minimal impact)
  - Agents:
    - `langgraph_integration/agents/intent_parser/agent.py`
    - `langgraph_integration/agents/discovery/agent.py`
    - `langgraph_integration/agents/join_sql/agent.py`
    - `langgraph_integration/agents/sql_validator/agent.py`
    - `langgraph_integration/agents/exec_recovery/agent.py`
    - `langgraph_integration/agents/result_validator/agent.py`
    - `langgraph_integration/agents/answer/agent.py`
  - Shared contracts & utilities:
    - `langgraph_integration/contracts/state.py`
    - `langgraph_integration/contracts/discovery_models.py`
    - `langgraph_integration/concept_mapper.py`
    - `langgraph_integration/debug_logger.py`
    - `langgraph_integration/mcp_client.py`
  - HTTP entrypoints / evaluation:
    - `chatbot_ui/langgraph_service.py` (`/process_query`).
    - `langgraph_integration/api.py` (direct LangGraph API).
    - `eval/run_benchmark.py`, `eval/eval_client.py`, `eval/service.py`.

---

## 2. Implementation Overview

We implement the PRD in five phases, each producing verifiable behavior:

1. **Instrumentation** — add structured LLM usage accounting and loop event logging.
2. **Loop & budget controls** — cache discovery/join outputs, detect redundant retries, and add budget-aware short-circuits.
3. **Deterministic answer fallback** — use structured renderers when SQL already succeeded, even with zero LLM budget.
4. **KPI-driven table selection guardrails** — enforce required tables from KPI expressions and product-domain sanity checks.
5. **Early identifier canonicalization** — normalize table names (e.g. `[dbo].[Order Details]` → `public.order_details`) at concept/discovery/join stages.

Each phase is scoped so it can be developed and tested independently while preserving existing contracts and tests.

---

## 3. Source Structure & Changes

### 3.1 New helpers / modules

- **`langgraph_integration/utils/canonical_names.py`** (new)
  - `canonical_table_name(raw_name: str, dialect: str = "mssql" | "postgres" | "generic", schema: str = "") -> str`
    - Normalizes raw table identifiers from concepts/MCP into canonical `schema.table` or `schema.view` names.
    - Handles:
      - Bracketed MSSQL-style names: `[dbo].[Order Details]` → `public.order_details` (when dialect = postgres, schema = "public").
      - Dot-prefixed names: `dbo.Products` → `public.products` (postgres) or `dbo.Products` (mssql).
      - Removes duplicate schema prefixes: `[dbo].[dbo].[Suppliers]` → `dbo.Suppliers` or `public.suppliers` depending on dialect.
    - Encapsulates regex parsing and normalization rules so they are shared by:
      - `ConceptMapper` for `seed_tables`.
      - `DiscoveryAgent` when assigning `relevant_tables` / `final_tables`.
      - `JoinPlanAndSQLAgent` when consuming `relevant_tables` / `role_hints`.
  - Optional extension: `canonicalize_table_list(tables: List[str], dialect: str, schema: str) -> List[str]` as a thin wrapper.

- **(Optional, Phase 1+2)** `langgraph_integration/utils/llm_usage.py`
  - Small helper for merging/initializing `llm_usage` dicts and emitting structured log payloads to `debug_logger` to keep orchestrator nodes cleaner.

### 3.2 Modified core contracts

- **`langgraph_integration/contracts/state.py`**
  - Extend `BaseState` with budget accounting and loop metrics:
    - `llm_usage: Dict[str, int]` — per-node counters:
      - Keys: `"intent"`, `"discovery"`, `"join"`, `"repair"`, `"answer"`, `"other"` (for spillover), `"total"`.
    - `node_entry_counts: Dict[str, int]` — how many times each orchestrator node has been entered (`"discovery"`, `"join_sql"`, `"exec_recovery"`, `"result_validator"`, `"answer"`, etc.).
    - `loop_events: Dict[str, int]` — counts of specific loop patterns:
      - `"discovery_reentered_same_tables"` — discovery re-invoked with unchanged `final_tables`.
      - `"join_sql_regenerated_same_sql"` — join node produced identical `sql_query` as previous.
  - Keep `total_llm_calls` and `max_llm_calls` as-is but treat `total_llm_calls` as derived from `llm_usage["total"]` inside orchestrator.
  - No breaking changes: all fields remain optional (`total=False`), and existing code can ignore the new keys.

### 3.3 Orchestrator: graph, nodes, and budget checks

- **`langgraph_integration/orchestrator.py`**
  - **LLM usage accounting**
    - Update `_check_llm_budget(state: BaseState, stage: str)`:
      - Initialize `state["llm_usage"]` if missing with zeros for known stages.
      - Increment `llm_usage[stage_key]` where:
        - `stage_key` maps orchestrator node → usage bucket, e.g.:
          - `"parse_intent"` → `"intent"`.
          - `"discovery"` → `"discovery"`.
          - `"join_sql"` / `"validate_sql"` → `"join"` and `"repair"` respectively.
          - `"exec_recovery"` → `"repair"` (LLM-based simplifications).
          - `"answer"` → `"answer"`.
      - Increment `llm_usage["total"]` and keep `state["total_llm_calls"]` synchronized from `llm_usage["total"]`.
      - Emit a structured debug log (via `debug_logger.state_updated` or new `llm_usage` helper) with:
        - `node` / `stage`
        - `llm_usage` snapshot
        - `retry_attempt_count`, `plan_attempt_count`, `total_graph_cycles`
        - Whether this is the **first** entry for this node vs a re-entry (using `node_entry_counts`).
    - Ensure all orchestrator-level LLM entry points call `_check_llm_budget` exactly once per subgraph invocation:
      - `_parse_intent_node` (already does).
      - `_discovery_node`.
      - `_join_sql_node`.
      - `_validate_sql_node`.
      - `_exec_recovery_node`.
      - `_answer_node`.
  - **Node entry / loop logging**
    - At the start of each orchestrator node (discovery, join_sql, exec_recovery, result_validator, answer):
      - Increment `state["node_entry_counts"][node_name]`.
      - If `node_entry_counts[node_name] > 1`, log an event:
        - For discovery: “discovery re-entered” with current `tried_candidate_tables`, `skip_tables`, and a marker for whether inputs changed.
        - For join_sql: similar re-entry log including `relevant_tables` and `last_sql_query`.
      - Keep these logs centralized via `debug_logger.info` / `decision_made`.
  - **Discovery caching & redundancy checks (Phase 2)**
    - In `_discovery_node`:
      - Compute an **input fingerprint**:
        - Tuple of `(user_input, intent.operation, intent.keywords_for_discovery, sorted(skip_tables), sorted(tried_candidate_tables), tuple(seed_tables))`.
      - Store in `state["discovery_cache"]`:
        - `{"fingerprint": ..., "result": { "relevant_tables": ..., "schema_snippet": ..., "candidate_views": ..., "column_index": ..., "discovery_role_hints": ..., "discovery_log": ... }}`
      - On entry:
        - If fingerprint matches previously cached fingerprint:
          - Increment `loop_events["discovery_reentered_same_tables"]`.
          - Skip building/invoking the discovery subgraph; reuse cached `result` and re-emit logs (lightweight).
        - Optionally, detect **no-op** re-entry where `relevant_tables` unchanged but `skip_tables` or `tried_candidate_tables` evolved; these still go through once but are logged as “same tables, different skip set”.
  - **Join / SQL redundancy checks (Phase 2)**
    - In `_join_sql_node`:
      - Maintain a `state["last_sql_query"]` and `state["last_join_plan"]` snapshot.
      - After generating SQL, if the new `sql_query` exactly matches `last_sql_query`, increment `loop_events["join_sql_regenerated_same_sql"]`.
      - Before invoking `JoinPlanAndSQLAgent`:
        - If current `relevant_tables` and `discovery_role_hints` match the last join inputs and `sql_query` is already present and validated:
          - Short-circuit: do **not** re-call the join subgraph; keep existing `sql_query` and skip to validation or exec, depending on where we’re re-entering from.
  - **Budget-aware routing (Phase 2)**
    - Extend `_check_llm_budget` or add a helper `remaining_llm_budget(state) -> int`.
    - In nodes that can be reached late in the pipeline (`discovery`, `join_sql`, `validate_sql`, `exec_recovery`, `answer`):
      - If `remaining_llm_budget(state) <= N` (configurable threshold, default 1–2):
        - Skip any new LLM-heavy subgraphs and prefer deterministic behavior:
          - For `discovery` re-entry: reuse cached results, do not hit LLM for additional ranking/tie-breaking.
          - For `join_sql` re-entry: keep previous `sql_query` if available, and forward to validation/exec.
          - For `answer`: avoid invoking `AnswerAgent` and instead use deterministic rendering (below).
    - Keep the existing `intent.needs_clarification` / budget-exceeded handling but augment it with exec-result-based fallbacks (Phase 3).

### 3.4 Deterministic answer fallback

- **`langgraph_integration/orchestrator.py::_answer_node`**
  - Current behavior:
    - Calls `_check_llm_budget("answer")`.
    - If budget exhaustion sets `needs_clarification`, returns a generic budget message.
    - Otherwise, normalizes `exec_result` via `_coerce_exec_result`, then:
      - Enforces “grounding gate” (requires successful exec for `operation == "query"`).
      - For some COUNT cases, attempts a small deterministic summary, else delegates to `AnswerAgent` subgraph.
  - New behavior (Phase 3):
    1. **Budget-aware early exit**
       - After `_check_llm_budget`:
         - If `error_info.type == "LLM_BUDGET_EXCEEDED"` and `exec_result.ok == True` and `row_count > 0`:
           - **Do not** set `needs_clarification`.
           - Call `await self._format_execution_results(exec_result, intent, user_input)` to build a deterministic `final_response`.
           - Set a small flag in state, e.g. `state["answer_mode"] = "deterministic_from_data"`.
           - Return without invoking `AnswerAgent`.
         - If budget exceeded and there is **no data**:
           - Maintain a clear diagnostic final_response as currently, but include:
             - Stage, total calls, and recommended next action.
    2. **Normal (non-budget) path**
       - Before delegating to `AnswerAgent`, check:
         - If `exec_result.ok == True` and `row_count > 0`:
           - Prefer `_format_execution_results` for simple aggregates and tabular answers (using existing logic).
           - If `_format_execution_results` returns a non-empty string, use it as `final_response` and short-circuit `AnswerAgent`.
       - Only call `AnswerAgent` when:
         - We genuinely need richer narrative or explanation (e.g., complex KPIs, clarifications).
  - This preserves the “grounding gate” while ensuring any successful SQL execution returns a meaningful answer even with zero remaining budget.

### 3.5 KPI-driven table selection guardrails

- **Required tables from KPI expressions (Phase 4)**
  - Concepts provide `kpi_expressions` via `ConceptMapper` → `state["concept_hints"]["kpi_expressions"]`.
  - Implement a small parser/helper:
    - In `langgraph_integration/utils/canonical_names.py` or a dedicated helper:
      - `extract_tables_from_expression(expr: str) -> Set[str]`
        - Uses regex over identifiers like `Products.`, `OrderDetails.`, etc., lowercased and normalized (singular/plural).
  - **Integration point: orchestrator and join agent**
    - In `_concept_mapping_node`:
      - Compute `state["required_tables_from_kpi"]` using all `kpi_expressions`:
        - e.g., any identifier prefix `Products.` implies `products` table; `OrderDetails.` implies `order_details`.
    - In `JoinPlanAndSQLAgent._build_join_plan_node`:
      - Accept `concept_hints` and `required_tables_from_kpi` from `state` (they are already in state, just read them).
      - When selecting `fact_candidate` and dimensions:
        - Ensure that any table implied by KPI expressions appears either:
          - As the chosen `fact_table`, or
          - As a dimension table attached via `attach_dimension`.
      - For inventory-reorder-like KPIs (e.g., concept “inventory_reorder” with `Products.*` in expression):
        - Force inclusion of a Product dimension:
          - If not present in `role_hints.dimensions`, attempt to construct a synthetic dimension candidate from:
            - `relevant_tables` that look product-like (based on existing heuristics).
          - If still impossible, surface a deterministic `DIMENSION_MISSING` error as today, but with a clearer message pointing to `products`.

- **Domain guardrails for product queries (Phase 4)**
  - Add a deterministic validation step after SQL generation (before `_validate_sql_node` or inside `_validate_sql_node`):
    - Helper: `validate_product_semantics(sql: str, state: BaseState) -> Optional[Dict[str, Any]]`
      - Parse segments like `SELECT ... AS product_name` looking for:
        - `order_id` or similar IDs being aliased as product attributes when:
          - Intent entities include `"product"` or concept list includes inventory-related concepts.
      - If suspicious mapping detected:
        - Return an error payload:
          - `{"type": "PRODUCT_MAPPING_ERROR", "message": "...", "retry_action": "replan_with_product_dimension"}`.
    - Wire into orchestrator:
      - In `_validate_sql_node` or just after join_sql, if `validate_product_semantics` returns an error:
        - Set `validation_result` accordingly.
        - Let `result_validator` route back to `join_sql` with a specific `retry_action`, and:
          - Add `state["forced_tables"]` or a similar hint to include the canonical products table in the next discovery/join cycle.
  - This guardrail is deterministic and only triggers when an obviously incorrect mapping (e.g., `order_details.order_id AS product_name`) is used in a clearly product-focused query.

### 3.6 Early identifier canonicalization

- **`langgraph_integration/concept_mapper.py`**
  - When populating `seed_tables` from concept definitions:
    - After `seed_tables.append(table)`, canonicalize via:
      - `canonical_table_name(table, dialect=state/config dialect, schema=default_schema)`.
    - Because `ConceptMapper` currently has no access to dialect/schema, make dialect configurable:
      - Option A (minimal): Environment variables: `DB_DIALECT`, `DB_DEFAULT_SCHEMA` with defaults (`"mssql"`, `"dbo"`).
      - Option B (cleaner): Let orchestrator pass dialect/schema via intent/metadata and extend `ConceptMapper.map(...)` signature to optionally accept them; changes kept backward compatible by using kwargs.
  - Ensure `mapped["seed_tables"]` is already canonical before orchestrator writes it into `state["seed_tables"]` and `discovery_log["seed_tables"]`.

- **`langgraph_integration/agents/discovery/agent.py`**
  - In `_search_candidates_node` and `_finalize_discovery_payload`:
    - Whenever table names are read from MCP or seed tables and written into:
      - `state["relevant_tables"]`
      - `DiscoveryCandidate.full_name`
      - `DiscoveryOutput.relevant_tables`
      - `discovery_log["final_tables"]`
    - Apply `canonical_table_name(..., dialect, default_schema)` so that:
      - All downstream consumers see canonical names (e.g., `public.orders` on Postgres).
  - Ensure `column_index` and `discovery_role_hints` use the same canonical names as keys.

- **`langgraph_integration/agents/join_sql/agent.py`**
  - Treat all incoming table names (`relevant_tables`, `fact_candidate.table`, `dimension.table`) as canonical.
  - When generating SQL:
    - Avoid reintroducing `[dbo].` prefixes on Postgres; respect `DB_DIALECT` and `DB_DEFAULT_SCHEMA` in template builder calls.
  - If necessary, normalize any residual raw names before building `join_plan`.

- **`SQLValidatorAgent`**
  - Continue to normalize dialect at validation/execution time, but **do not** change logical table names that have already been canonicalized.
  - Ensure that any representation of `tables_used` in `exec_result.metadata` uses canonical names, not MSSQL-only forms.

### 3.7 Evaluation pipeline / results artifacts

- **`langgraph_integration/orchestrator.py`**
  - Ensure `process_query(...)` includes `llm_usage`, `node_entry_counts`, and `loop_events` in the returned top-level dict so they are visible to callers.

- **`chatbot_ui/langgraph_service.py`**
  - The `/process_query` handler already passes through orchestrator results; no contract changes needed beyond accepting these extra fields.

- **`eval/run_benchmark.py`**
  - When building `artifact` per query:
    - Capture:
      - `artifact["llm_usage"] = result.get("llm_usage")`
      - `artifact["node_entry_counts"] = result.get("node_entry_counts")`
      - `artifact["loop_events"] = result.get("loop_events")`
    - These fields are not required for scoring, but they support the Phase 1 analysis (“calls per node per query”, “discovery re-entered events”, “same tables selected again”).

---

## 4. Data Model & API Changes

### 4.1 State-level changes

- **New fields in `BaseState` (non-breaking, optional)**
  - `llm_usage: Dict[str, int]`
  - `node_entry_counts: Dict[str, int]`
  - `loop_events: Dict[str, int]`
  - `discovery_cache: Dict[str, Any]` (fingerprint + last discovery result).
  - `last_sql_query: str`, `last_join_plan: Dict[str, Any]`.
  - `required_tables_from_kpi: List[str]` (derived from KPI expressions).
  - `answer_mode: str` (e.g., `"llm"`, `"deterministic_from_data"`, `"clarification"`) — optional diagnostic flag.

These keys are used internally by orchestrator/agents and surfaced only in top-level results for analysis; they are not required by existing tests, but we will avoid removing or renaming any previous fields.

### 4.2 Orchestrator return envelope

- **`QueryOrchestrator.process_query`**
  - Continue returning:
    - `user_input`, `intent`, `relevant_tables`, `sql_query`, `exec_result`, `error_info`, `final_response`, `final_answer`.
  - Add optional diagnostics:
    - `llm_usage`, `node_entry_counts`, `loop_events`.
  - For backward compatibility, no existing keys are renamed or removed.

### 4.3 Evaluation service

- **`eval/service.py`**
  - The `QueryArtifact` pydantic model is currently focused on UI-facing metrics and does not need to be extended for this task, since we store `llm_usage` directly in the run’s `results.json`.
  - Optionally, we can extend `QueryArtifact` later to include these fields if we want them in the eval service UI; not required for this task.

---

## 5. Delivery Phases & Milestones

### Phase 1 — Instrumentation

Scope:
- Add `llm_usage`, `node_entry_counts`, `loop_events` to `BaseState`.
- Implement per-node LLM accounting in `_check_llm_budget` with structured logs.
- Track node re-entries (discovery/join/exec/answer) and log why.
- Ensure `process_query` results include these diagnostics.

Milestone verification:
- Run `pytest tests/test_orchestrator.py tests/test_orchestrator_integration.py` and ensure no regressions.
- Run a small benchmark (`eval/run_benchmark.py` with 3–5 queries) and inspect:
  - `llm_usage` distribution per query.
  - `loop_events["discovery_reentered_same_tables"]`, `loop_events["join_sql_regenerated_same_sql"]`.

### Phase 2 — Loop control & budget-aware routing

Scope:
- Add discovery caching keyed by query/intent/skip-tables fingerprint.
- Avoid re-running discovery/join when outputs are unchanged.
- Add budget-aware short-circuits when nearing `max_llm_calls`.

Milestone verification:
- Identify one previously “bad” benchmark query.
- Confirm via logs and `llm_usage` that:
  - Discovery runs at most once per true change in inputs.
  - JoinSQL does not regenerate identical SQL multiple times.
- Ensure budget-exceeded failures at stage `answer` drop significantly for the benchmark.

### Phase 3 — Deterministic answer fallback

Scope:
- Extend `_answer_node` to:
  - Use `_format_execution_results` when `exec_result.ok` and `row_count > 0`.
  - Prefer deterministic formatting when LLM budget is exhausted.
  - Keep grounding gate semantics intact.

Milestone verification:
- For benchmark queries where SQL execution succeeds:
  - `final_response` should contain a structured data-based answer even when `error_info.type == "LLM_BUDGET_EXCEEDED"`.
- Existing answer-related tests (`tests/test_orchestrator_result_validator_integration.py`, `tests/test_complete_system.py`) should still pass.

### Phase 4 — KPI-driven table selection guardrails

Scope:
- Derive `required_tables_from_kpi` from concept KPI expressions.
- Enforce inclusion of these tables in join planning (especially `products` for reorder/inventory KPIs).
- Add deterministic checks for obvious product mapping mistakes and route replanning accordingly.

Milestone verification:
- Re-run the “Chai reorder” query end-to-end (via tests or manual script):
  - `relevant_tables` and final SQL should include the `products` table.
  - SQL should join orders/order_details/products and filter by `products.product_name = 'Chai'` (or equivalent).

### Phase 5 — Identifier canonicalization

Scope:
- Implement `canonical_table_name` and apply it at:
  - `ConceptMapper` (seed tables).
  - `DiscoveryAgent` (final_tables, column_index keys, discovery_log).
  - Join planning (ensure consumption of canonical names).
- Ensure SQL validation/execution does not reintroduce `[dbo]` prefixes for Postgres runs.

Milestone verification:
- Run discovery-heavy benchmark queries on a Postgres-backed setup:
  - Discovery logs (`discovery_log.seed_tables`, `final_tables`) show `public.*` names, no `[dbo]` or duplicated schema prefixes.
  - SQL validator still successfully executes queries using canonical names.

---

## 6. Verification Strategy

- **Unit / integration tests**
  - Re-run key orchestrator tests:
    - `tests/test_orchestrator.py`
    - `tests/test_orchestrator_integration.py`
    - `tests/test_orchestrator_result_validator_integration.py`
    - `tests/test_complete_system.py`
  - Add targeted tests where feasible:
    - LLM budget accounting and `llm_usage` shape for a simple query.
    - Deterministic answer fallback when `exec_result.ok` but `max_llm_calls` is low.
    - Canonicalization of `[dbo].[Order Details]` → `public.order_details` when `DB_DIALECT=postgres`.

- **Benchmark validation**
  - Use `eval/run_benchmark.py` on the 12-query dataset:
    - Compare:
      - Distribution of `total_llm_calls` vs previous run.
      - Reduction in errors of type `LLM_BUDGET_EXCEEDED` at stage `answer`.
      - Presence of meaningful `final_response` whenever `exec_result.ok == True` and `row_count > 0`.

- **Manual spot checks**
  - Run representative queries (inventory reorder, product KPIs, schema queries) via `chatbot_ui/langgraph_service.py`:
    - Confirm that:
      - No `[dbo].*` names leak into prompts/logs for Postgres.
      - Answer text reflects actual data tables used and remains grounded.

