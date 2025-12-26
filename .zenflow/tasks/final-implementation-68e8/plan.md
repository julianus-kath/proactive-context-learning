# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 9e6fc0c7-907b-4071-bda1-a54d4ed001cb -->

Assess the task's difficulty, as underestimating it leads to poor outcomes.
- easy: Straightforward implementation, trivial bug fix or feature
- medium: Moderate complexity, some edge cases or caveats to consider
- hard: Complex logic, many caveats, architectural considerations, or high-risk changes

Create a technical specification for the task that is appropriate for the complexity level:
- Review the existing codebase architecture and identify reusable components.
- Define the implementation approach based on established patterns in the project.
- Identify all source code files that will be created or modified.
- Define any necessary data model, API, or interface changes.
- Describe verification steps using the project's test and lint commands.

Save the output to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `{@artifacts_path}/spec.md`:
- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

---

### [ ] Step: Phase 1 – Canonical Pipeline & Golden Path

Implement a single, robust core path through the orchestrator and verify it end-to-end.

- Code changes:
  - Normalize routing in `langgraph_integration/orchestrator.py` so default `operation="query"` always follows:
    - `index_database → parse_intent → concept_mapping → route_operation → discovery → join_sql → validate_sql → exec_recovery → result_validator → answer`
  - For `execute_direct`, route via:
    - `validate_sql → exec_recovery → result_validator → answer` (no execution without validation)
  - Ensure only `answer`, `answer_schema`, `answer_error`, and `interpret` point to `END`.
  - Tighten state contracts at node boundaries:
    - Before `discovery`: `user_input`, `intent`
    - Before `join_sql`: `intent`, `relevant_tables`, `schema_snippet`, `column_index`
    - Before `validate_sql`: `sql_query`, `join_plan`, `column_index`
    - Before `exec_recovery`: validated `sql_query`, `retry_count`
- Tests / deliverable:
  - Add a “golden path” test in `tests/test_orchestrator_integration.py` that:
    - Calls `QueryOrchestrator.ainvoke` with a realistic analytic query
    - Asserts `final_response` exists, `sql_query` is non-empty, and `validation_result.is_valid` is True on success.
  - Manual check: hitting `/process_query` with a simple benchmark-style question yields a coherent SQL + answer, with logs confirming the exact node sequence.

### [ ] Step: Phase 2 – Agent-Level HTTP Endpoints for Targeted Testing

Expose lightweight HTTP endpoints to invoke individual agents (orchestration nodes) with partial state for focused debugging and use them throughout later phases.

- Code changes:
  - In `chatbot_ui/langgraph_service.py`:
    - Implement endpoints such as:
      - `POST /agent/discovery`
      - `POST /agent/join_sql`
      - `POST /agent/validate_sql`
      - `POST /agent/exec_recovery`
      - `POST /agent/result_validator`
    - Use `AgentInvokeRequest` / `AgentInvokeResponse` (already defined) to:
      - Accept partial `state` and optional `options`.
      - Route to the corresponding orchestrator node or subgraph (e.g., `DiscoveryAgent.build_subgraph().ainvoke`, `SQLValidatorAgent`, `ExecAndRecoveryAgent`, result validator node).
    - Normalize outputs so each endpoint returns:
      - Result data (e.g., `relevant_tables`, `sql_query`, `exec_result`, `validation_result`)
      - Any `error_info`.
  - Optionally add a thin helper in `langgraph_integration/api.py` to encapsulate agent invocation logic so it can be reused from tests or other services.
- Tests / deliverable:
  - Add FastAPI tests that:
    - Hit each `/agent/*` endpoint with a minimal, valid state and assert:
      - 2xx responses.
      - Expected fields are present in the JSON body (e.g., `relevant_tables` for discovery, `validation_result` for validator).
    - Confirm that bad or incomplete state yields clear, localized errors (without running the full pipeline).
  - Manual check:
    - Use curl/Postman to call, for example, `/agent/validate_sql` with a candidate `sql_query` and inspect validation behavior directly, without going through the entire pipeline.

### [ ] Step: Phase 3 – Discovery as Scout + Schema Linking

Make Discovery explicitly “Scout search + deterministic schema linking” and verify it in isolation.

- Code changes:
  - In `langgraph_integration/agents/discovery/agent.py`:
    - Keep Scout search in `search_candidates` / `rank_candidates`.
    - Treat `describe_selected` + `build_schema_snippet` + `fetch_column_index` as the canonical schema-linking phase.
    - Guarantee success outputs:
      - `relevant_tables` (canonical names, non-empty)
      - `schema_snippet` (≤ 3 entities, human-readable)
      - `column_index` (exact column names per table)
      - `discovery_result` summary.
  - In `_discovery_node` (`orchestrator.py`):
    - Use `DISCOVERY_NO_CANDIDATES` for zero-table cases.
    - In `route_discovery_result`, route:
      - To `answer_error` when `error_info` exists
      - To `answer` with a clear explanation when `DISCOVERY_NO_CANDIDATES` is set.
- Tests / deliverable:
  - Add targeted tests in `tests/test_orchestrator_integration.py` (or a dedicated discovery test file) that:
    - Invoke the `DiscoveryAgent` subgraph directly and assert `relevant_tables`, `schema_snippet`, `column_index` are all populated for a simple query.
    - Verify that a nonsense query results in a graceful “no tables found” style answer via the orchestrator, not a hang.
  - Manual check: inspect `/debug/logs` to see Discovery’s candidate tables and schema_snippet for a known query.

### [ ] Step: Phase 4 – SQL Validation as Hard, Bounded Gate

Ensure every SQL goes through a bounded validation/repair loop before any execution.

- Code changes:
  - In `orchestrator.py`:
    - Confirm edges are always `join_sql → validate_sql → exec_recovery`.
    - For `execute_direct`, ensure flow also passes through `validate_sql`.
    - In `_exec_recovery_node`, if `validation_result` is missing or `is_valid=False` without an explicit override, log critical and return a safe `error_info` instead of executing.
  - In `agents/sql_validator/agent.py` and `contracts/state.py`:
    - Ensure `validation_result` always contains:
      - `is_valid`, `error_type`, optional `error_message`
      - `tables_used` and canonical variants (`tables_used_canonical`, `tables_used_base`).
    - Track `repair_attempts` consistently.
  - In `orchestrator.py` (`route_validation_result`):
    - Restrict `retry_action` to: `accept`, `try_next_candidate`, `replan_with_aggregation`, `replan_with_filter`, `ask_user`.
    - Enforce caps for:
      - `plan_attempt_count` vs `max_total_plans`
      - `validation_attempt_count` vs `max_validation_attempts`
      - `exec_recovery_attempt_count` vs `max_exec_recovery_attempts`
      - `retry_attempt_count` vs `max_retries_per_candidate_set`
    - On cap hit, convert to a clarify-style answer with `stop_reason` and actionable `error_info`.
- Tests / deliverable:
  - Add unit-style tests for `SQLValidatorAgent` that cover:
    - Valid SQL, syntax errors, unknown tables/columns, and repair scenarios.
  - Add tests for `route_validation_result` to verify each `retry_action` and cap behavior.
  - Manual check: send intentionally broken SQL via `execute_direct` and confirm:
    - Validation catches it.
    - Repair attempts are bounded.
    - Final answer clearly explains the problem instead of silently failing.

### [ ] Step: Phase 5 – Deterministic Join Graph & Rich SQL Generation

Ground SQL generation in a deterministic join graph and ensure it can produce Q1/Q2-level queries.

- Code changes:
  - In `contracts/state.py` and `agents/join_sql/agent.py`:
    - Define and enforce a `join_plan` schema:
      - `primary_table`, `joins[]` (table, join_type, join_keys, direction).
    - Build `join_plan` only from:
      - `relevant_tables`, `column_index`, FK metadata, `discovery_role_hints`.
    - Remove or isolate logic that builds joins purely from unconstrained LLM guesses.
  - In `JoinPlanAndSQLAgent`:
    - Generate SQL using only tables from `join_plan` / `relevant_tables` and columns from `column_index`.
    - Add debug-mode assertions to fail fast when the generated SQL references unknown tables/columns.
  - In `SQLValidatorAgent`:
    - Treat unknown tables/columns as explicit, well-typed validation errors.
  - Enhance templates/prompts in `agents/join_sql/agent.py` so they can produce:
    - CTE-based queries with window functions and time-window logic, similar to your Q1/Q2 examples.
    - Clear aggregations and aliases suitable for benchmark-style analytics.
- Tests / deliverable:
  - Add benchmark-focused tests where the input question matches Q1/Q2 patterns and assert:
    - SQL includes appropriate CTEs, filters, groupings, and window functions (doesn’t devolve to trivial SELECTs).
  - Manual check: run the benchmark harness and compare:
    - Fewer “I don’t know” answers.
    - Richer SQL structure closer to your hand-written examples.

### [ ] Step: Phase 6 – Answer Shaping & Core API Stability

Ensure every terminal path yields a useful answer and the main API remains simple and predictable.

- Code changes:
  - In `agents/answer/agent.py` and `orchestrator.py`:
    - Guarantee that any path that reaches `END` has `final_response` set.
    - For success cases: concise summary, optionally referencing key tables.
    - For schema queries: structured explanation of relevant tables/views and key columns (not raw dumps).
    - For errors: use `error_info.type/message/suggestion` to produce actionable, non-generic answers.
  - In `langgraph_integration/api.py` and `chatbot_ui/langgraph_service.py`:
    - Keep public interface minimal:
      - Input: `message`/`user_input`, optional `conversation_history`.
      - Output: `answer` (`final_response`), plus optional `sql_query` and `error_info` in debug.
    - Avoid exposing internal loop counters; rely on logs and `/debug/*` endpoints instead.
- Tests / deliverable:
  - Extend API/HTTP tests (e.g., `chatbot_ui/test_web_ui.py`) to:
    - Assert `final_response` is always non-empty for valid inputs.
    - Verify error cases return meaningful messages.
  - Manual check: query different modes (data, schema, health, clarify) via `/process_query` and confirm all responses are usable and informative.
