# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: dbc2c927-adaf-49d6-8e1f-f3a45ce3a55f -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Save the PRD to `{@artifacts_path}/requirements.md`.

### [x] Step: Technical Specification

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
<!-- chat-id: 0bd7788c-6294-4d89-81ef-461afa356112 -->

Create a detailed implementation plan based on `{@artifacts_path}/spec.md`.

1. Break down the work into concrete tasks
2. Each task should reference relevant contracts and include verification steps
3. Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function) or too broad (entire feature).

If the feature is trivial and doesn't warrant full specification, update this workflow to remove unnecessary steps and explain the reasoning to the user.

Save to `{@artifacts_path}/plan.md`.

### [x] Step: Extend BaseState for benchmark mode and semantic counters
<!-- chat-id: 1c84b474-b530-4138-ad48-4b7a47f57d8c -->

Scope:
- Update `langgraph_integration/contracts/state.py` to add:
  - `eval_mode: Optional[str]` (e.g., `"benchmark"` vs `None` / `"interactive"`),
  - `semantic_retry_count: int`,
  - `max_semantic_retries: int`.
- Update `langgraph_integration/orchestrator.py:QueryOrchestrator.process_query()` to:
  - initialize `eval_mode` and semantic counters from `metadata` (default `eval_mode=None`, `semantic_retry_count=0`, `max_semantic_retries=2` in benchmark mode),
  - ensure `semantic_retry_count <= max_semantic_retries` and `plan_attempt_count + semantic_retry_count <= max_total_plans` (NF‑1, NF‑2).
- Ensure new fields are included in state/response models where `BaseState` is exposed, in particular:
  - any Pydantic models in `langgraph_integration/contracts/response_envelope.py`,
  - top‑level responses returned from `QueryOrchestrator.process_query()` and exposed via `langgraph_integration/api.py`,
  while keeping them backward‑compatible and optional for existing callers.

Verification:
- Run `pytest tests/test_orchestrator_integration.py::TestQueryOrchestrator::test_state_contracts_valid -q` to confirm state contracts remain consistent.
- Smoke‑run `python -m langgraph_integration.orchestrator` or existing orchestrator startup paths (e.g., FastAPI import via `tests/test_orchestrator_integration.py::TestFastAPIIntegration::test_fastapi_imports_orchestrator`) to confirm no import/runtime regressions.
- Add or extend an integration test (e.g., `tests/test_orchestrator_integration.py::TestQueryOrchestrator::test_orchestrator_intent_routing_query`) to assert that interactive (non‑benchmark) queries continue to route and respond as before aside from additional internal fields.

### [x] Step: Propagate eval headers and query contracts into LangGraph state
<!-- chat-id: a3b2e8fa-b7a6-4c85-80b6-5c71cf0abd23 -->

Scope:
- Update `langgraph_integration/api.py` (FastAPI service) to:
  - read `X-Eval-Run-Id` and `X-Eval-Query-Id` headers on benchmark requests,
  - set `metadata={"eval_run_id": ..., "eval_query_id": ..., "eval_mode": "benchmark"}` when calling `QueryOrchestrator.process_query()`,
  - accept an optional `query_contract` payload (or reuse existing request body/extensible metadata mechanism) and pass it through `metadata`.
- Update `langgraph_integration/orchestrator.py:QueryOrchestrator.process_query()` to:
  - merge `eval_run_id`, `eval_query_id`, `eval_mode`, and `query_contract` from `metadata` into the initial `BaseState`,
  - keep `eval_mode` read‑only for all downstream nodes (BM‑1).

Verification:
- Add or update a small FastAPI integration test (or extend `tests/test_orchestrator_integration.py::TestFastAPIIntegration`) to assert that:
  - passing eval headers results in `state.eval_mode == "benchmark"` and `state.eval_query_id` being set.
- Manually exercise the FastAPI service (if available) with a single benchmark query and log `BaseState` to confirm metadata is present.

### [x] Step: Implement per‑dataset contract loading and metric catalog in eval harness
<!-- chat-id: 6e2851b7-fe17-4020-baae-838bd2768e4e -->

Scope:
- Define per‑dataset contract files alongside existing JSONL datasets, e.g. `eval/datasets/<dataset>.contracts.json` (as in §4.1).
- Introduce a shared `QueryContract` schema (e.g., a `TypedDict` or Pydantic model) in `langgraph_integration/contracts/semantic_contracts.py` that:
  - matches the fields in §4.1–4.3 (`query_id`, `entity`, `entity_table`, `metric_key`, `metric_expression_sql`, `required_tables`, `allowed_join_paths`, `analytic_template`, etc.),
  - is imported both by `eval/run_benchmark.py` and by the semantic validator / orchestrator, so contract shape stays consistent.
- Implement a contract loader in `eval/run_benchmark.py` to:
  - load the contract file for the selected dataset into a `Dict[query_id, QueryContract]`,
  - validate basic schema (required fields like `query_id`, `entity`, `entity_table`, `metric_key`, `metric_expression_sql`, `required_tables`, `allowed_join_paths`, `analytic_template`),
  - select the correct `Contract` per benchmark query using `eval_query_id`,
  - pass the selected contract into `QueryOrchestrator.process_query()` via `metadata["query_contract"]`.
- Introduce a canonical metric mapping per dataset (metric key → SQL expression, metric phrase) that matches the contract schema and is used by the intent/metric resolver in benchmark mode.

Verification:
- Add or update a lightweight unit test under `tests/` (or near `eval/run_benchmark.py`) that:
  - loads a sample `.contracts.json` file,
  - asserts that each dataset entry has a matching contract keyed by `query_id`,
  - verifies `run_benchmark` passes a non‑empty `query_contract` when `eval_mode == "benchmark"`.
- Perform a dry‑run benchmark on a very small subset (e.g., a single query) to confirm contract loading and wiring without enforcing semantic validation yet.
- Add a new unit test module (e.g., `tests/test_eval_contracts.py`) that validates the `QueryContract` schema and its round‑trip from JSON → model → metadata.

### [x] Step: Implement deterministic metric resolution and analytic template selection
<!-- chat-id: 17b67bed-d3dc-4d22-99ce-9924d984f771 -->

Scope:
- Implement a dedicated metric/analytic template resolver (e.g., `_resolve_metric_and_template_from_contract`) in `langgraph_integration/orchestrator.py` (or a small helper module it owns) so that in benchmark mode:
  - `intent["metrics"]` becomes a structured list with at least `{"key": "<metric_key>", "phrase": "<metric_phrase>"}` derived from the contract (R6.1–R6.3),
  - `intent["analytic_template"]` is set to the contract’s `analytic_template` for Phase 1 templates (`TOP_K_BY_METRIC`, `COUNT_ENTITY`).
- Update `JoinPlanAndSQLAgent` (`langgraph_integration/agents/join_sql/agent.py`) to:
  - honor `intent["analytic_template"]` and `query_contract.metric_expression_sql` when generating SQL,
  - ensure TOP‑K queries follow the “SELECT entity_dim, metric_expression FROM ... GROUP BY entity_dim ORDER BY metric DESC LIMIT K” pattern,
  - ensure COUNT_ENTITY queries use the contract’s count expression (e.g., `COUNT(DISTINCT ...)`).
- Update `DiscoveryAgent` (`langgraph_integration/agents/discovery/agent.py`) and any ranking/pruning logic to:
  - treat `contract.required_tables` as hard constraints in benchmark mode (must not be dropped once present in candidates),
  - propagate required entity tables into `relevant_tables` / `candidate_views` even if their heuristic score is low,
  - log when a required table would have been dropped absent the contract (R4.2–R4.3).
- Ensure discovery and join planning are grounded in FK paths when `eval_mode == "benchmark"`, using `contract.required_tables` and `contract.allowed_join_paths` plus catalog FK info (R4.*, R5.*).
- Define behavior for out‑of‑scope cases:
  - benchmark queries whose contracts specify an analytic template outside Phase 1 should fall back to current behavior but mark a semantic status of `UNSUPPORTED_METRIC` (or equivalent) so they are counted as semantically failing,
  - multi‑metric queries in benchmark datasets should either be explicitly unsupported (and treated as `UNSUPPORTED_METRIC`) or mapped to a deterministic subset of metrics defined in the contract.

Verification:
- Add targeted unit tests around the metric/template selection logic to assert:
  - metric phrases in benchmark datasets resolve to the expected `metric_key` and SQL expression,
  - incorrect or unsupported metric phrases yield an `UNSUPPORTED_METRIC` semantic status (once validator is wired).
- Use existing debugging harnesses (e.g., `PHASE_11_VERIFICATION.py` or a new small script) to generate SQL for a couple of contract‑backed benchmark queries and visually confirm template adherence.
- Add unit tests for discovery behavior (e.g., `tests/test_discovery_required_tables.py`) that:
  - construct states with `eval_mode == "benchmark"` and a `query_contract.required_tables` including a low‑scoring table,
  - assert that required tables are retained in `relevant_tables` and passed downstream to join planning.

### [x] Step: Implement semantic validator logic in result_validator agent
<!-- chat-id: 76456252-d4de-4f32-a61f-03990270585b -->

Scope:
- Extend `langgraph_integration/agents/result_validator/agent.py` to:
  - load `state["query_contract"]` and skip semantic validation when it is absent or `eval_mode` is not `"benchmark"`,
  - compare:
    - resolved entity vs `contract.entity` and `contract.entity_table` using `state["intent"]["primary_entities"]`, `state["validator_tables_used_base"]`, and `state["join_plan"]`,
    - resolved metric key and normalized SQL expression vs `contract.metric_key` and `contract.metric_expression_sql`,
    - actual join path (from `join_plan` and catalog FK info) vs `contract.allowed_join_paths`,
  - set `validation_result.semantic_status` using the codes in §5.1 (`"OK"`, `"ENTITY_MISMATCH"`, `"METRIC_MISMATCH"`, `"JOIN_PATH_INVALID"`, `"NO_VALID_JOIN_PATH"`, `"UNSUPPORTED_METRIC"`, `"CONTRACT_MISSING"`), treating §5.1 as the authoritative set:
    - encode template‑selection mismatches under `"METRIC_MISMATCH"` with a specific failure reason (rather than introducing a separate `METRIC_OR_TEMPLATE_MISMATCH` code mentioned earlier in the spec),
  - populate `validation_result.semantic_failure_reasons`, `validation_result.contract_id`, and `validation_result.semantic_retry_action` (`"none"`, `"replan"`, `"try_next_candidate"`).
- Ensure semantic validation runs post‑exec only, using `state["exec_result"]`, `state["sql_query"]`, and `state["join_plan"]` (SV‑2).

Verification:
- Add focused unit tests for the result validator that:
  - construct synthetic `BaseState` + `query_contract` combinations and assert the correct `semantic_status`/failure reasons,
  - cover each major failure mode (entity mismatch, metric mismatch, join path invalid, unsupported metric).
- Run an end‑to‑end benchmark on 1–2 queries with intentionally wrong SQL (via mocks) to confirm semantic failures are detected even when SQL executes successfully.
- Add a small test (e.g., `tests/test_result_validator_semantic_statuses.py`) that verifies template mismatches are reported as `METRIC_MISMATCH` with a clear `semantic_failure_reasons` entry.

### [x] Step: Enforce semantic replanning budgets and routing in route_validation_result
<!-- chat-id: d131d67d-8f28-4071-8488-bcf78bc355a3 -->

Scope:
- Update `langgraph_integration/orchestrator.py:route_validation_result` to:
  - interpret `validation_result.semantic_status` and `semantic_retry_action`,
  - in benchmark mode, map semantic failures to existing `retry_action` values (`"replan_with_aggregation"`, `"replan_with_filter"`, `"try_next_candidate"`) without introducing new graph nodes or edges (SV‑1, NF‑4),
  - increment `state["semantic_retry_count"]` whenever a semantic replan is triggered,
  - enforce `max_semantic_retries` and `max_total_plans` caps (NF‑2, RP‑1) and set `state["stop_reason"] = "max_semantic_retries"` when exhausted,
  - in interactive mode, treat semantic findings as logging‑only (no additional retries), preserving current UX.
- Ensure semantic retries share the existing budgets for validation attempts and plan attempts (NF‑1).

Verification:
- Add unit tests for `route_validation_result` that:
  - simulate states with various `semantic_status`/`semantic_retry_action` combinations and assert routing decisions,
  - verify counters (`plan_attempt_count`, `semantic_retry_count`) increment correctly and stop at configured caps.
- Run `pytest tests/test_orchestrator_integration.py::TestQueryOrchestrator::test_orchestrator_with_mock_mcp -q` (and nearby tests) to ensure orchestration flow remains healthy.
- Add an explicit regression test (e.g., `tests/test_orchestrator_semantic_routing.py`) that:
  - runs a representative interactive query with `eval_mode` unset,
  - asserts no additional semantic replanning cycles are introduced and the existing UX (clarification vs answer) remains unchanged.

### [x] Step: Extend evaluation artifacts and scoring for semantic correctness
<!-- chat-id: 9e73d011-91d2-4178-961c-b8ef66756f74 -->

Scope:
- Update `eval/run_benchmark.py` to:
  - capture semantic fields from the orchestrator response (`semantic_status`, `semantic_failure_reasons`, `semantic_retry_count`, `semantic_retry_action`, `contract_id`),
  - persist them alongside existing per‑query artifacts under `eval/runs/<run_id>/` (PRD‑1, §5.4).
- Update `eval/scoring/score_run.py` to:
  - consume the new semantic fields from `results.json`,
  - compute and report `entity_metric_join_correct_count` and `entity_metric_join_correct_rate` (PRD‑3),
  - ensure a query only counts as “semantically passed” when `status == "success"` **and** `semantic_status == "OK"`.
- Keep public API responses backward compatible, ensuring semantic fields remain internal/eval‑focused and optional for existing clients (PRD‑2).

Verification:
- Add or extend scoring tests to assert:
  - runs with mixed semantic statuses compute the expected semantic correctness rates,
  - legacy scoring behavior remains unchanged when semantic fields are absent.
- Execute a small benchmark run and inspect `eval/runs/<run_id>/results.json` to confirm semantic fields and new summary metrics are present and correctly derived.
