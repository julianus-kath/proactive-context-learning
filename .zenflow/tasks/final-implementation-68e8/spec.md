# Final Implementation – SQL Orchestrator Alignment with LangGraph SQL Tutorial

## Technical Context

- **Language / Runtime**: Python 3, async-first where possible.
- **Core libraries**:
  - `langgraph` (`StateGraph`, `START`, `END`) for graph orchestration.
  - `langchain_openai.ChatOpenAI` for LLM-backed agents.
  - Internal MCP client (`langgraph_integration.mcp_client`) as the database access layer instead of `SQLDatabase`.
- **Existing architecture**:
  - Top-level orchestrator in `langgraph_integration/orchestrator.py` (`QueryOrchestrator`) with nodes:
    - `index_database` → MCP health + Scout catalog.
    - `parse_intent` → `IntentParserAgent`.
    - `concept_mapping` → `ConceptMapper`.
    - `route_operation` → conditional routing.
    - Data-query path: `discovery` → `join_sql` → `validate_sql` → `exec_recovery` → `result_validator` → `answer`.
    - Other paths: `discovery_for_schema` → `answer_schema`, `answer_health`, `answer_error`, `interpret`.
  - Specialized agents as subgraphs:
    - `DiscoveryAgent` (`langgraph_integration/agents/discovery/agent.py`).
    - `JoinPlanAndSQLAgent` (`langgraph_integration/agents/join_sql/agent.py`).
    - `SQLValidatorAgent` (`langgraph_integration/agents/sql_validator/agent.py`).
    - `ExecAndRecoveryAgent` (`langgraph_integration/agents/exec_recovery/agent.py`).
    - `AnswerAgent` (`langgraph_integration/agents/answer/agent.py`).
    - `ResultValidator` node via `build_result_validator_node`.
  - Shared state contracts in `langgraph_integration/contracts/state.py`:
    - `BaseState`, `DiscoveryAgentInput/Output`, `JoinPlanAndSQLAgentInput/Output`, `ExecAndRecoveryAgentInput/Output`, `AnswerAgentInput/Output`.
  - DB access:
    - Primary: MCP tools (`query_bounded`, catalog/column index, table describe).
    - Secondary (not used by orchestrator today): `DirectDatabaseClient` in `langgraph_integration/direct_db_client.py`.

Overall, the system already follows the broad LangGraph SQL tutorial pattern (schema discovery → SQL generation → validation → execution → answer) but still has several custom/legacy paths and inconsistencies that should be cleaned up and made more “tutorial-like” (linear, tool-centric, bounded loops).

## Difficulty Assessment

- **Difficulty**: **Hard**.
  - Multiple agents and subgraphs with non-trivial contracts and loop controls.
  - Changes affect the main production orchestrator and need to maintain behavior across existing integration and E2E tests.
  - Requires careful coordination between state contracts, routing logic, and error handling.

## Implementation Approach

High-level goal: converge the current multi-agent SQL orchestrator onto the proven LangGraph SQL agent pattern:

> 1) deterministic schema discovery → 2) explicit SQL generation → 3) pre-exec validation/repair → 4) bounded execution + error-driven retries → 5) final LLM answer.

### 1. Normalize the SQL Agent Pipeline to the Tutorial Pattern

**Goal**: Make the main query path explicitly reflect the canonical sequence `schema_inspection → table_selection → sql_generation → sql_check → sql_execution → result_to_answer`, with minimal side paths and no hidden fallbacks.

- Keep the top-level nodes but clarify and enforce their responsibilities:
  - `index_database`:
    - Only MCP health + catalog readiness; no partial fallback behavior.
    - Fail loud on missing/empty catalog (already mostly done) and surface a consistent `error_info` shape for downstream `answer_error`.
  - `discovery`:
    - Treat as the canonical “schema discovery + table selection + schema snippet + column_index” phase.
    - Ensure it always produces (or explicitly fails with) **all tutorial-style schema context**:
      - `relevant_tables` (canonical names).
      - `schema_snippet` (≤ 3 entities, human-readable).
      - `column_index` (per-table exact columns).
      - `discovery_result` summary for logging/answer provenance.
  - `join_sql`:
    - Responsible only for **join planning + SQL text generation**, not execution or repair.
    - Ensure it consumes only the declared `JoinPlanAndSQLAgentInput` fields: `intent`, `relevant_tables`, `schema_snippet`, `column_index`, `session_described_tables`.
    - Confirm that any template-based SQL generation is fed with the same schema context (`schema_snippet`, `column_index`) that `SQLValidatorAgent` will later use.
  - `validate_sql`:
    - Single source of truth for pre-execution SQL verification and LLM-based repair, using `SQLValidatorAgent`’s internal subgraph.
    - Always set `validation_result` (even on unexpected errors) so that `route_validation_result` has a consistent contract.
    - Normalize `tables_used` metadata to canonical names (already partially done) and ensure `evaluate_required_relations` relies only on this normalized information.
  - `exec_recovery`:
    - Strictly handle **execution + execution-level repair** only (no discovery or SQL generation).
    - Respect `max_retries` and keep retry semantics bounded, mirroring tutorial-style “few attempts with explicit error feedback”.
  - `result_validator`:
    - Align with the tutorial’s “SQL checker” concept by interpreting `exec_result`, `validation_result`, and simple dataset heuristics into `retry_action` values that drive bounded loops (back to discovery or join_sql) without introducing new hidden branches.
  - `answer`/`answer_schema`/`answer_error`:
    - Final mapping from raw results/schema/errors into user-facing answers.
    - Ensure `final_response` is always set by one of these nodes, and `orchestrator.ainvoke` consistently returns it.

**Key changes**:
- Audit and remove any residual “shortcut” logic in `orchestrator.py` that:
  - Executes SQL without going through `validate_sql` (except explicitly documented advanced paths).
  - Re-enters `ExecAndRecoveryAgent` with newly generated SQL but without updating `validation_result`.
- Tighten `route_operation` to keep normal “query” traffic on the canonical pipeline and make non-standard operations (`execute_direct`, interpretation/refinement) explicit and well-documented.

### 2. Align Schema Discovery with Tutorial’s Schema Inspection

**Goal**: Ensure the schema discovery phase provides the same kind of rich context the tutorial passes to the LLM, while staying deterministic/tool-based.

- In `DiscoveryAgent` (`agents/discovery/agent.py`):
  - Verify that `build_subgraph()` already constitutes the tutorial’s “schema inspection + table discovery” stage:
    - `search_candidates` (keyword + intent-based search via MCP).
    - `rank_candidates` (views-first + role coverage).
    - `filter_to_limit` (≤ 3 entities).
    - `describe_selected` / `build_schema_snippet`.
    - `fetch_column_index` (column index from catalog).
  - Make sure all required outputs are populated or a coherent `error_info` is set:
    - Avoid returning empty `relevant_tables` without `error_info` (orchestrator already has a “fail loud” branch; keep this contract tight).
  - Document the exact shape of `discovery_result` in `contracts/state.py` and ensure orchestrator uses it only for logging and answer provenance.
- For direct schema questions (`schema_query` operation):
  - Confirm that `discovery_for_schema` reuses the same `DiscoveryAgent` subgraph but possibly with different constraints (e.g., more tables allowed) and that `answer_schema` uses `schema_snippet` plus `discovery_result` to produce human-readable schema answers.

### 3. Unify SQL Verification Loops with Bounded, Error-Driven Feedback

**Goal**: Match the tutorial’s explicit, bounded retry loop: on SQL failure, feed the concrete error back to the LLM-based components with a hard cap on attempts.

- In `SQLValidatorAgent`:
  - Keep its internal graph (`validate_sql` → `repair_sql` → retry loops → `final_validation`) as the single pre-execution verification and repair mechanism.
  - Guarantee:
    - `validation_result["is_valid"]` and `validation_result["error_type"]` are always present.
    - `repair_attempts` is tracked and capped by `max_repair_attempts`.
  - Ensure all validation error types used in `orchestrator.route_validation_result` (e.g., missing GROUP BY / WHERE) are consistent and documented.
- In `ExecAndRecoveryAgent`:
  - Keep execution-level retries limited (`max_retries` property) with clear semantics:
    - First attempt: normalized SQL from validator.
    - On execution error: prepare a structured error payload (`exec_result.error`, `error_info`) containing the exact DB error message.
    - Retry paths (`repair_sql` / simplification) should be driven by this error message, in line with tutorial’s “LLM gets error feedback and tries again”.
  - Avoid any open-ended probing loops (Phase 10 README already claims this; ensure the current subgraph reflects that).
- In `orchestrator.route_validation_result`:
  - Treat `validation_result.retry_action` as the canonical “what to do next” flag (accept, try_next_candidate, replan_with_aggregation/filter, ask_user).
  - Maintain:
    - Global plan budget (`plan_attempt_count` vs `max_total_plans`).
    - Per-candidate retry limits (`retry_attempt_count` vs `max_retries_per_candidate_set`).
    - Validation/execution attempt caps (`validation_attempt_count`, `exec_recovery_attempt_count`, `max_validation_attempts`, `max_exec_recovery_attempts`).
  - On cap exhaustion, convert the situation into a clarified `intent` (`operation="clarify"`, `needs_clarification=True`) plus a human-readable error in `error_info`, then route to `answer` – no silent loops.

### 4. Route Direct SQL through the Same Safety and Validation Path

**Goal**: Ensure “execute_direct” (or similar advanced modes) still leverage the same validator and executor as LLM-generated SQL, mirroring tutorial patterns where the same SQL tool is reused regardless of who authored the SQL.

- In `orchestrator.route_operation`:
  - Revisit the `execute_direct` branch:
    - Preferred flow for direct SQL: `validate_sql` → `exec_recovery` → `result_validator` → `answer`.
    - Avoid bypassing `validate_sql` unless there is a strong reason; if bypass is kept, clearly document that it’s “unsafe / expert-only”.
  - Accept direct SQL from state (e.g. `state["sql_query"]`) and skip discovery/join_sql, but still use:
    - `SQLValidatorAgent` for pre-execution checks.
    - `ExecAndRecoveryAgent` for bounded execution.
    - `ResultValidator` and `AnswerAgent` for downstream behavior.

### 5. Tighten Result Transformation and Provenance

**Goal**: Match the tutorial’s “result → final natural language answer” node with clear provenance and error reporting.

- In `AnswerAgent`:
  - Confirm that it:
    - Uses `exec_result`, `schema_snippet`, `intent`, and `sql_query` to craft `final_response`.
    - Handles both success (data available) and error (`error_info` present) paths gracefully.
  - Ensure that for:
    - Data queries: the answer includes a high-level summary plus, where appropriate, mention of key tables/views used (from `discovery_result`/`validator_tables_used`).
    - Schema queries: the answer summarizes relevant tables/views and key columns rather than dumping raw schema.
    - Error cases: the answer explains what went wrong and offers actionable next steps (aligned with `error_info["suggestion"]` where present).
- In `orchestrator.ainvoke` and any public-facing API (`langgraph_integration/api.py`, FastAPI handlers in `chatbot_ui`):
  - Standardize on returning `final_response` plus optional debug/metadata fields (answer mode, SQL preview, error_info) instead of raw internal state.

### 6. Keep Contracts and Telemetry in Sync with the Graph

**Goal**: Make state contracts and instrumentation reflect the final pipeline, so debugging and evaluation are straightforward.

- In `contracts/state.py`:
  - Confirm field names used in orchestrator and agents (`schema_snippet`, `column_index`, `join_plan`, `sql_query`, `exec_result`, `validation_result`, `error_info`, `final_response`, `llm_usage`, budget/loop counters).
  - Add or refine docstrings where behavior changed (e.g., semantics of `validation_result.retry_action`, meaning of `stop_reason` and `repair_signatures_seen`).
- In `orchestrator`:
  - Ensure node-entry counting (`node_entry_counts`) and loop-event metrics (`loop_events`) are updated for any new/re-routed paths, so telemetry in logs matches the logical graph.
  - Maintain the default `recursion_limit` behavior (`ainvoke` wrapper) to accommodate nesting (main graph + subgraphs), consistent with the tutorial’s recommendation to set limits explicitly.

## Source Code Structure Changes

Planned files to modify:

- `langgraph_integration/orchestrator.py`
  - Tighten `route_operation`, `route_discovery_result`, and `route_validation_result`.
  - Normalize handling for `execute_direct` to flow through `validate_sql` where feasible.
  - Ensure node responsibilities are documented and match the normalized pipeline.
- `langgraph_integration/agents/discovery/agent.py`
  - Confirm and, if needed, refine guarantees around `relevant_tables`, `schema_snippet`, `column_index`, and `discovery_result` population, including error paths.
- `langgraph_integration/agents/join_sql/agent.py`
  - Ensure subgraph boundaries cleanly implement “join planning + SQL generation” without overlapping validation or execution concerns.
  - Align state usage with `JoinPlanAndSQLAgentInput/Output`.
- `langgraph_integration/agents/sql_validator/agent.py`
  - Confirm return-shape of `validation_result` and repair loop semantics.
  - Make error types / fields used by orchestrator explicit and stable.
- `langgraph_integration/agents/exec_recovery/agent.py`
  - Confirm bounded retry logic, no hidden cross-node probing loops, and consistent use of `exec_result` and `error_info`.
- `langgraph_integration/agents/answer/agent.py`
  - Refine answer shaping to always produce `final_response` for all terminal paths (success, schema, error, clarify).
- `langgraph_integration/contracts/state.py`
  - Update/clarify docstrings to reflect normalized pipeline and any new fields or semantics required for loop control and provenance.
- Optionally (depending on how far we mirror the tutorial’s tool interface):
  - `langgraph_integration/api.py` and/or `langgraph_integration/direct_db_client.py`:
    - Provide a thin, documented entrypoint analogous to a “SQL tool” (e.g., `run_sql_query(user_input, mode="query"|"schema"|"execute_direct")`) that wraps the orchestrator.

No new top-level packages are anticipated; changes will be limited to the existing LangGraph integration layer.

## Data Model / API / Interface Changes

- **State-level changes**:
  - Keep existing state fields but tighten semantics:
    - `intent.operation`: ensure it includes any additional modes (`clarify`, `error`, `execute_direct`) in a well-defined way where needed.
    - `validation_result.retry_action`: central knob for deciding further graph transitions; document possible values and meaning.
    - `error_info`: converge on a small set of `type` constants for main failure modes (discovery, SQL generation, validation, execution, budget/loop caps).
    - `stop_reason`: used for reporting why the graph stopped early (budget caps, no progress, max retries exceeded).
  - Ensure `final_response` is always populated when the graph hits `END`.
- **Public interfaces**:
  - `QueryOrchestrator.ainvoke(state, config)` remains the core entrypoint.
  - Contract for callers:
    - Inputs: minimally `user_input` and `conversation_history`/`messages`.
    - Outputs: `final_response` (always), plus optional `sql_query`, `exec_result`, `error_info`, and `debug` fields depending on environment (dev vs prod).
  - For FastAPI or other HTTP endpoints, keep payloads stable but adjust internal routing to the normalized pipeline where needed.

## Verification Approach

### Automated Tests

- Reuse and extend existing tests:
  - `tests/test_orchestrator_integration.py`
    - Verify:
      - Orchestrator initialization still works with all agents.
      - Graph contains expected nodes and edges matching the normalized pipeline.
      - `route_operation` and `route_validation_result` behave as designed for:
        - `query`, `schema_query`, `health_check`, `execute_direct`, clarify/error cases.
  - `tests/test_full_pipeline_e2e.py`
    - Verify end-to-end behavior for:
      - Successful data queries (full pipeline).
      - Schema queries.
      - Execution failures that trigger validation/execution retries, then error answers.
  - `tests/test_mcp_connectivity.py`
    - Ensure MCP integration still works after any change to index/discovery behavior.
- Add or refine targeted tests if needed:
  - Unit-style tests for `route_validation_result` to cover all `retry_action` values and budget/loop caps.
  - Tests for `execute_direct` mode to confirm it flows through `validate_sql` (if we normalize it that way) and uses the same safety mechanisms as LLM-generated SQL.

### Manual / Exploratory Verification

- Run orchestrator smoke tests using the documented snippet in `langgraph_integration/README.md`:
  - Ask:
    - Standard analytic query (“top 5 products by sales”).
    - Schema query (“what tables contain customers?”).
    - Intentionally invalid queries to exercise validation and repair loops.
- Inspect logs to ensure:
  - Node entry/exit and routing messages match the intended normalized pipeline.
  - Error and budget caps result in early, user-facing clarify/error answers rather than silent hangs or infinite loops.

This specification will drive the final implementation step: refactoring and tightening the orchestrator and agent graphs to line up with the LangGraph SQL tutorial patterns while preserving existing functionality and tests.

