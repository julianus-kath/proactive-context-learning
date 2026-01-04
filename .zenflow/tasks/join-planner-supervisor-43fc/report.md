# Join planner & supervisor – tests and UX report

## Overview

- Added focused tests around the join planner metadata, capability tool envelopes, and supervisor LLM wiring to validate the new `plan_status`/`plan_issues` contract and routing behaviour.
- Verified that analytic queries no longer fall back to weak `SELECT *`/`SUM(...)` plans when required pieces are missing, and that exploratory outputs are clearly surfaced as such to the supervisor.

## JoinPlanAndSQLAgent behaviour

- **COUNT_ENTITY success path** (`tests/test_join_plan_and_sql_agent.py::test_generate_sql_count_entity_ok_plan_produces_sql_and_metadata`):
  - Builds a minimal analytic intent with `analytic_template="COUNT_ENTITY"` and an `ok` join_plan.
  - Asserts that `_generate_sql_node` produces a `SELECT ... COUNT(*)` style query, attaches `template="COUNT_ENTITY"`, and keeps `plan_status` in `{None,"ok","exploratory"}` with no `error_info`.
- **Analytic plan hard-gate on incomplete plan** (`test_generate_sql_declines_for_incomplete_analytic_plan`):
  - Seeds `join_plan.plan_status="incomplete"` for an analytic COUNT_ENTITY intent.
  - Confirms `_generate_sql_node` returns **no SQL**, emits `error_info.type="PLAN_INCOMPLETE"`, forces `plan_confidence=0.0`, and appends a `PLAN_INCOMPLETE` issue to `plan_issues`.
- **Template-parameter failure path** (`test_topk_by_metric_template_missing_params_marks_plan_incomplete`):
  - Uses `analytic_template="TOP_K_BY_METRIC"` with missing `metric`/`group_by` parameters.
  - Verifies no SQL is generated, `error_info.type` reflects template failure, and `join_plan.plan_issues` contains both `TEMPLATE_PARAMS_MISSING` and `ANALYTIC_TEMPLATE_FAILED` with `plan_status="incomplete"` and `plan_confidence=0.0`.

Taken together, these scenarios cover:
- A “How many customers do we have?” style COUNT_ENTITY query.
- Analytic intents where planning has already concluded the plan is incomplete.
- Analytic intents whose deterministic template cannot be instantiated because of missing parameters.

## plan_sql_tool envelopes & progress signals

- **OK plan → positive progress** (`tests/test_plan_sql_tool.py::test_plan_sql_tool_ok_plan_positive_progress`):
  - Stubs the orchestrator so `plan_sql_tool` sees a join_plan with `plan_status="ok"` and non-empty `sql_query`.
  - Asserts that `tool_output` exposes `join_plan`, `plan_status`, `plan_confidence`, and `template`, and that `progress_signal="positive"` with `suggested_next_actions=["replan","stop"]`.
- **Incomplete plan → negative progress** (`test_plan_sql_tool_incomplete_plan_negative_progress`):
  - Stubs a join_plan with `plan_status="incomplete"` and a `FACT_NOT_FOUND` error.
  - Confirms `progress_signal="negative"` and `suggested_next_actions=["rediscover","replan","clarify","stop"]`, and that the error is visible on `last_tool_result.error_info`.
- **Exploratory plan for analytic intent → neutral progress** (`test_plan_sql_tool_exploratory_plan_neutral_for_analytic_intent`):
  - Provides a non-empty exploratory `SELECT TOP 10 * ...` SQL with `plan_status="exploratory"` but an analytic-style intent (metrics present).
  - Asserts `progress_signal="neutral"` and `suggested_next_actions=["replan","rediscover","clarify","stop"]`, so the supervisor does not treat exploratory output as a successful analytic answer.

These tests simulate the UX for:
- Analytic queries where a robust plan exists (planner should move the system forward).
- Analytic queries where planning failed or fact tables are missing (supervisor should re-discover/replan/clarify rather than execute).
- Cases where the planner only has a sample/detail query but the user intent is clearly analytic (supervisor should treat this as neutral, not success).

## Supervisor LLM integration

- **LLM-driven next-tool selection sees planner metadata** (`tests/test_supervisor_behavior.py::test_llm_select_next_tool_summary_includes_join_plan_metadata_and_instructions`):
  - Reuses `ReactSupervisor` with a dummy LLM stub.
  - Invokes `_llm_select_next_tool` on a state where `join_plan_status="incomplete"`, `template="sum_with_period"`, `error_info.type="FACT_NOT_FOUND"`, and `plan_sql_instructions` are populated.
  - Parses the JSON summary embedded in the user prompt and asserts it contains:
    - `join_plan_status`, `join_plan_strategy`, `join_plan_fact_table`, `join_plan_template`.
    - `error_info_type` derived from `error_info`.
    - The full `plan_sql_instructions` (including `preferred_fact_table` and `avoid_tables`).

This ensures the supervisor LLM has the world-view it needs at runtime to:
- Recognize incomplete/unsupported plans and associated error types.
- Adjust or re-emit `plan_sql_instructions` (e.g., change fact table, add avoid list, switch between analytic vs exploratory modes).
- Decide between rediscovery, replanning, or asking the user, without hard-coded Python routing.

## UX sanity snapshot

Representative UX scenarios covered by tests:

- **“How many customers do we have?”**
  - COUNT_ENTITY template with an OK plan produces a clean `COUNT(*)` query, not an arbitrary SUM, and surfaces the template key on `join_plan.template`.
- **“Top 5 entities by metric …” where template params are missing or underspecified**
  - TOP_K_BY_METRIC refuses to guess columns; it marks the plan as incomplete, annotates `plan_issues`, and returns no SQL so the supervisor must replan/clarify instead of executing misleading queries.
- **Exploratory SELECT samples**
  - When the planner returns an exploratory `SELECT TOP ... *` but the intent is analytic, the capability tool marks progress as neutral and points the supervisor toward replanning or rediscovery rather than treating the sample as a valid analytic answer.

## Verification

- Test commands executed:
  - `pytest tests/test_join_plan_and_sql_agent.py tests/test_plan_sql_tool.py tests/test_supervisor_behavior.py`
- All tests pass locally, with the new cases scoped to:
  - `JoinPlanAndSQLAgent` analytic template gating and planner metadata.
  - `plan_sql_tool` envelopes and progress signals.
  - Supervisor LLM summary wiring for join-plan metadata and `plan_sql_instructions`.

