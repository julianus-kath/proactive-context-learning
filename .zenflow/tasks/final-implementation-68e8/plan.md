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

### [ ] Step: Implementation

Implement the task according to the technical specification with a strict focus on:
- Robust, deterministic core pipeline
- High‑quality, complex SQL generation
- Bounded, predictable validation and execution loops

#### Phase 1 – Lock Down Canonical Pipeline (Happy Path)

1. Normalize routing for core query path in `langgraph_integration/orchestrator.py`
   - Ensure default `operation="query"` always follows:
     - `index_database → parse_intent → concept_mapping → route_operation → discovery → join_sql → validate_sql → exec_recovery → result_validator → answer`
   - For `execute_direct`, route via:
     - `validate_sql → exec_recovery → result_validator → answer` (no direct exec without validation)
   - Ensure only `answer`, `answer_schema`, `answer_error`, `interpret` reach `END`.

2. Tighten state contracts at node boundaries
   - Update docstrings in `langgraph_integration/contracts/state.py` and light runtime checks in `orchestrator.py` so each node has clear required inputs:
     - Before `discovery`: `user_input`, `intent`
     - Before `join_sql`: `intent`, `relevant_tables`, `schema_snippet`, `column_index`
     - Before `validate_sql`: `sql_query`, `join_plan`, `column_index`
     - Before `exec_recovery`: validated `sql_query`, `retry_count`

3. Add a “golden path” integration test
   - In `tests/test_orchestrator_integration.py`, add a test that:
     - Calls `QueryOrchestrator.ainvoke` with a realistic analytic query
     - Asserts `final_response` exists, `sql_query` is non‑empty, and `validation_result.is_valid` is True on success.

#### Phase 2 – Discovery as Scout + Schema Linking

4. Make schema linking explicit in `DiscoveryAgent`
   - In `langgraph_integration/agents/discovery/agent.py`:
     - Keep Scout search in `search_candidates` / `rank_candidates`
     - Treat `describe_selected` + `build_schema_snippet` + `fetch_column_index` as the canonical schema‑linking phase
     - Guarantee success outputs:
       - `relevant_tables` (canonical names, non‑empty)
       - `schema_snippet` (≤ 3 entities, readable)
       - `column_index` (exact columns per table)
       - `discovery_result` summary

5. Fail loud on empty/failed discovery
   - In `_discovery_node` (`orchestrator.py`):
     - Keep/use `DISCOVERY_NO_CANDIDATES` for zero‑table cases
     - Ensure `route_discovery_result`:
       - Sends `answer_error` when `error_info` exists
       - Sends `answer` with a clear explanation when `DISCOVERY_NO_CANDIDATES` is set.

6. Add targeted discovery tests
   - In `tests/test_orchestrator_integration.py`:
     - Test `DiscoveryAgent` subgraph:
       - For a simple query, all of `relevant_tables`, `schema_snippet`, `column_index` are populated
       - For nonsense queries, orchestrator produces a graceful “no tables found” answer, not a hang.

#### Phase 3 – SQL Validation as Hard, Bounded Gate

7. Enforce validation before execution
   - In `orchestrator.py`:
     - Confirm edges are always `join_sql → validate_sql → exec_recovery`
     - For `execute_direct`, ensure flow also passes through `validate_sql`
     - In `_exec_recovery_node`, if `validation_result` is missing or `is_valid=False` without an explicit override, log critical and surface a safe `error_info` instead of hitting DB.

8. Tighten `SQLValidatorAgent` contract
   - In `agents/sql_validator/agent.py` and `contracts/state.py`:
     - Ensure `validation_result` always has:
       - `is_valid`, `error_type`, optional `error_message`
       - `tables_used` and canonical variants (`tables_used_canonical`, `tables_used_base`)
     - Track `repair_attempts` consistently
     - Align `error_type` values with what `route_validation_result` expects for retry decisions.

9. Cap planning and repair loops explicitly
   - In `orchestrator.py` (`route_validation_result`):
     - Restrict `retry_action` to: `accept`, `try_next_candidate`, `replan_with_aggregation`, `replan_with_filter`, `ask_user`
     - Enforce and document caps:
       - `plan_attempt_count` vs `max_total_plans`
       - `validation_attempt_count` vs `max_validation_attempts`
       - `exec_recovery_attempt_count` vs `max_exec_recovery_attempts`
       - `retry_attempt_count` vs `max_retries_per_candidate_set`
     - On cap hit, convert to a clarify answer with `stop_reason` and actionable `error_info`.

#### Phase 4 – Deterministic Join Graph & Rich SQL Generation

10. Make `join_plan` a first‑class structure
    - In `contracts/state.py` and `agents/join_sql/agent.py`:
      - Define and enforce `join_plan` schema:
        - `primary_table`, `joins[]` (table, join_type, join_keys, direction)
      - Ensure `join_plan` is built only from:
        - `relevant_tables`, `column_index`, FK metadata, `discovery_role_hints`
      - Remove or quarantine logic that builds joins purely from unconstrained LLM guesses.

11. Tie SQL text strictly to `join_plan` and `column_index`
    - In `JoinPlanAndSQLAgent`:
      - Generate SQL that:
        - Uses only tables present in `join_plan` / `relevant_tables`
        - Uses only columns present in `column_index`
      - Add debug‑mode assertions to catch violations early.
    - In `SQLValidatorAgent`:
      - Treat unknown tables/columns as explicit validation errors with clear messages.

12. Optimize for complex, benchmark‑style SQL
    - Add or refine templates / prompt strategies in `agents/join_sql/agent.py` so that:
      - Time‑window metrics (daily velocity, reorder dates, yearly ranges) and window functions (RANK, SUM OVER) are supported, similar to your Q1/Q2 examples.
      - The agent prefers:
        - CTE‑based, well‑structured queries
        - Explicit aliases and clear aggregation semantics
      - Validate through benchmarks that:
        - Queries no longer default to trivial “I don’t know / simple SELECT count(*)” patterns when schema context is sufficient.

#### Phase 5 – Answer Shaping and API Stability

13. Guarantee `final_response` for all terminal paths
    - In `agents/answer/agent.py` and `orchestrator.py`:
      - Ensure:
        - Success: summarize results and mention key tables when helpful
        - Schema queries: explain tables/views and key fields rather than dumping raw schema
        - Errors: use `error_info.type/message/suggestion` to produce actionable answers instead of generic “I don’t know”.

14. Keep a minimal, stable public interface
    - In `langgraph_integration/api.py` and any FastAPI entrypoints:
      - Standardize:
        - Input: `message`/`user_input`, optional `conversation_history`
        - Output: `answer` (`final_response`), optionally `sql_query` and `error_info` in debug
      - Do not expose internal counters; use logs and tests to monitor loop and budget behavior.

15. Report and benchmark
    - After implementation, run the existing benchmark suite and:
      - Compare SQL quality and success rate against prior runs (especially for queries like your Q1/Q2)
      - Summarize in `{@artifacts_path}/report.md`:
        - What was implemented
        - How SQL quality and “I don’t know” frequency changed
        - Remaining gaps or edge cases to address next.
