# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: c76313dd-7d87-4299-8802-ed04c19b59d7 -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Save the PRD to `{@artifacts_path}/requirements.md`.

### [ ] Step: Technical Specification
<!-- chat-id: c2a801ac-0803-462b-abe3-312483244c46 -->

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

### [x] Step: Technical Specification
<!-- auto-complete: spec.md created and aligned with current architecture -->

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

Create a detailed implementation plan based on `{@artifacts_path}/spec.md`.

1. Break down the work into concrete tasks
2. Each task should reference relevant contracts and include verification steps
3. Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function) or too broad (entire feature).

If the feature is trivial and doesn't warrant full specification, update this workflow to remove unnecessary steps and explain the reasoning to the user.

Save to `{@artifacts_path}/plan.md`.

### [ ] Step: Phase A – Capability Tools & State Contracts

Implementation is broken into three phases aligned with `spec.md`: **Phase A – Tools & Contracts**, **Phase B – Supervisor Graph**, and **Phase C – Cleanup & Rollout**.

Each task below should be executed in order. For every task:
- Update the checkbox when complete
- Run the listed verification commands (or closest equivalent) where feasible
- Capture notable outcomes or deviations directly under the task as bullet points
---

### Phase A – Capability Tools & State Contracts

**Definition of Done (Phase A)**
- All 7 capability tools exist and use a consistent shared tool envelope.
- `execute_sql` is hard-gated in the wrapper and cannot execute without a valid `validation_result`.
- A scripted capability-tool sequence reproduces current pipeline behavior on a shared reference query set (intent present, relevant_tables non-empty when expected, sql_query generated, validation_result populated).

#### [ ] Task A1: Extend BaseState for Supervisor Fields

Update `langgraph_integration/contracts/state.py`:
- Add optional supervisor-related fields to `BaseState`:
  - `supervisor_trace: List[Dict[str, Any]]`
  - `supervisor_step_count: int`
  - `max_supervisor_steps: int`
  - `last_tool_name: Optional[str]`
  - `last_tool_progress_signal: Optional[str]`
  - `no_progress_repeat_count: int`
  - `orchestration_mode: Optional[str]`  # "pipeline" | "react_supervisor"
- Ensure all new fields are optional and safe for existing callers.

Verification:
- `python -m pytest tests/test_orchestrator_integration.py::TestQueryOrchestrator::test_orchestrator_initialization -q`
- (If fast) `python -m pytest tests/test_orchestrator_integration.py -q`

#### [ ] Task A2: Define Shared Tool Envelope Types

Update `langgraph_integration/contracts/state.py` (or a small adjacent module) to define:
- A `TypedDict` (e.g., `ToolCallResult`) capturing:
  - `tool_output: Dict[str, Any]`
  - `error_info: Optional[Dict[str, Any]]`
  - `progress_signal: Literal["positive", "neutral", "negative"]`
  - `suggested_next_actions: List[Literal["rediscover", "replan", "clarify", "stop"]]`
- Optional helper functions for normalizing `error_info` using `ErrorInfo` semantics.

Verification:
- Type check informally by importing and using types in a small unit test or REPL snippet.

#### [ ] Task A3: Implement Capability Tool Wrappers Module

Add `langgraph_integration/tools/capability_tools.py`:
- Implement thin wrappers:
  - `interpret_query_tool(state: BaseState) -> BaseState`
  - `discover_schema_tool(state: BaseState) -> BaseState`
  - `plan_sql_tool(state: BaseState) -> BaseState`
  - `validate_sql_tool(state: BaseState) -> BaseState`
  - `execute_sql_tool(state: BaseState) -> BaseState`
  - `evaluate_result_tool(state: BaseState) -> BaseState`
  - `finalize_answer_tool(state: BaseState) -> BaseState`
- Each wrapper:
  - Invokes the corresponding agent/subgraph (reusing existing classes and `build_subgraph()` / `__call__` methods).
  - Populates the shared tool envelope fields on `state`:
    - `tool_output`, `error_info`, `progress_signal`, `suggested_next_actions`.
  - Updates `last_tool_name` and `last_tool_progress_signal`.
  - Increments `node_entry_counts` and `llm_usage` consistently with existing patterns.

Verification:
- Add or extend unit tests (e.g., `tests/test_capability_tools.py`) to:
  - Call each tool with a minimal `BaseState`.
  - Assert that expected keys are present (`tool_output`, `progress_signal`, etc.).
- Run: `python -m pytest tests/test_capability_tools.py -q` (when added).

#### [ ] Task A4: Enforce Execute_SQL Validation Gate in Wrapper

In `execute_sql_tool`:
- Before calling `ExecAndRecoveryAgent`, enforce:
  - `state.get("validation_result", {}).get("is_valid") is True`.
- If the condition fails:
  - Do NOT call MCP or `ExecAndRecoveryAgent`.
  - Set `error_info` to a structured error:
    - `type="VALIDATION_GATE_VIOLATION"`, `message` explaining missing validation.
  - Set `progress_signal="negative"` and `suggested_next_actions=["replan", "clarify", "stop"]`.

Verification:
- Add tests exercising the negative path (no validation or validation_result.is_valid is False).
- Run: `python -m pytest tests/test_capability_tools.py::TestExecuteSqlTool -q`

#### [ ] Task A5: Add Reference Query Fixtures and Golden Expectations

- Introduce (or wire in) a shared reference query set for both pipeline and supervisor-mode tests using:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_queries.jsonl` (source of 10–20 representative queries).
- Add a small fixture/helper in `tests/` that:
  - Loads a subset of these queries (or a mirrored copy in the repo, if needed).
  - Provides expected shapes for comparison (e.g., `intent.operation`, `tables_used_base` non-empty, presence of `sql_query`, `stop_reason`).

Verification:
- `python -m pytest tests/test_query_fixtures.py -q` (or similar fixture-focused test file).

#### [ ] Task A6: Validate Tool Behavior Against Current Pipeline

Create a small test or harness (e.g., `tests/test_capability_tools_vs_pipeline.py`) that:
- For a subset of the reference queries (including the “top 10 products by total sales last 12 months” case):
  - Runs the current pipeline via `QueryOrchestrator.process_query(..., orchestration_mode="pipeline")` (or default).
  - Runs the same sequence of agents via capability tools in a scripted order:
    - `interpret_query` → `discover_schema` → `plan_sql` → `validate_sql` → `execute_sql` → `evaluate_result`.
- Compares key intermediates and invariants:
  - `intent` present and reasonable.
  - `relevant_tables` and/or `tables_used_base` non-empty where expected.
  - `sql_query` non-empty.
  - `validation_result` present with required fields even on failures.

Verification:
- `python -m pytest tests/test_capability_tools_vs_pipeline.py -q`

---

### [ ] Step: Phase B – ReAct Supervisor Graph Integration

Implementation is broken into three phases aligned with `spec.md`: **Phase A – Tools & Contracts**, **Phase B – Supervisor Graph**, and **Phase C – Cleanup & Rollout**.

**Definition of Done (Phase B)**
- `react_supervisor` mode runs end-to-end via `QueryOrchestrator.process_query`.
- `supervisor_trace` is populated with summary-only decisions (no raw chain-of-thought).
- Budgets (steps, total LLM calls, no-progress) stop cleanly and map to `stop_reason`.
- There is an explicit test proving no execution occurs without prior validation (validation gate enforced in supervisor mode).

#### [ ] Task B1: Implement Supervisor Module

Add `langgraph_integration/supervisor.py`:
- Define a `SupervisorConfig` (dataclass or simple config class) containing:
  - `max_supervisor_steps`, `max_llm_calls_total`, `max_no_progress_repeats`, etc.
- Use `langgraph_supervisor.create_supervisor` to:
  - Register capability tools as agents/tools.
  - Configure the supervisor prompt to:
    - Describe tools, constraints, and budgets.
    - Emphasize that in `react_supervisor` mode, the supervisor is the sole authority for sequencing.
  - Ensure supervisor entry conditions:
    - Start with `interpret_query` or a no-op check when `intent` is already present.
- Implement functions:
  - `build_react_supervisor_graph(config: SupervisorConfig) -> Any` (compiled supervisor).
  - `run_supervisor(state: BaseState, config: SupervisorConfig) -> BaseState`.

Verification:
- Add `tests/test_supervisor_basic.py` to:
  - Construct a minimal state and run `run_supervisor`.
  - Assert that `supervisor_trace` is populated and that at least one tool ran.
- Run: `python -m pytest tests/test_supervisor_basic.py -q`

#### [ ] Task B2: Wire Supervisor into QueryOrchestrator

Update `langgraph_integration/orchestrator.py`:
- Constructor:
  - Accept `orchestration_mode: str = "pipeline"` and store it.
  - Optionally derive default mode from env (`ORCHESTRATION_MODE`).
- Add a private method `_invoke_supervisor(initial_state: BaseState) -> Dict[str, Any]` that:
  - Initializes supervisor-specific fields on `initial_state`:
    - `supervisor_trace`, `supervisor_step_count`, `max_supervisor_steps`, `no_progress_repeat_count`, etc.
  - Calls `run_supervisor` (from `supervisor.py`).
  - Normalizes final outputs to align with existing expectations:
    - Populate `final_response`, `final_answer`, `stop_reason`.
- Update `process_query()` to:
  - Read `orchestration_mode` from:
    - The instance default.
    - `metadata.get("orchestration_mode")` if set.
  - Branch:
    - `"pipeline"` → existing `self.ainvoke(initial_state)`.
    - `"react_supervisor"` → `_invoke_supervisor(initial_state)`.

Verification:
- Extend `tests/test_orchestrator_integration.py` to:
  - Add a supervisor-mode test, e.g. `test_process_query_react_supervisor_basic`.
  - Ensure existing pipeline tests still pass.
- Run:
  - `python -m pytest tests/test_orchestrator_integration.py -q`

#### [ ] Task B3: Implement Supervisor Trace and Stop Reason Mapping

Ensure `run_supervisor` and `_invoke_supervisor`:
- Append a trace entry to `supervisor_trace` on each loop iteration:
  - `step`, `thought_summary`, `action`, `tool_inputs_digest`, `observation_summary`, `progress_signal`, `budgets`.
- Enforce reasoning constraints:
  - `thought_summary` is a short decision summary, no raw chain-of-thought.
  - No prompts or hidden reasoning tokens are stored.
- Map supervisor stop conditions to:
  - `stop_reason` in `{success, clarify, budget_exhausted, fatal_error}`.
  - A user-facing `final_response` (using existing fallback logic where needed).

Verification:
- Extend supervisor tests to:
  - Assert that `supervisor_trace` has at least one entry.
  - Assert that `stop_reason` aligns with the scenario (e.g., budget exhaustion → `budget_exhausted`).

#### [ ] Task B4: Add Budget and No-Progress Enforcement in Supervisor

Within `run_supervisor`:
- Track:
  - `supervisor_step_count`, `no_progress_repeat_count`.
  - Use existing `total_llm_calls` / `max_llm_calls` on `BaseState`.
- Implement stop conditions:
  - Stop and route to `finalize_answer` when:
    - `supervisor_step_count >= max_supervisor_steps`
    - `total_llm_calls >= max_llm_calls`
    - `no_progress_repeat_count >= max_no_progress_repeats`
- Use `progress_signal` and stable fingerprints (e.g., join inputs fingerprint, SQL fingerprint) to detect no-progress cycles.

Verification:
- Add targeted tests for budget exhaustion and no-progress:
  - Artificially small budgets to force early stop.
  - Assert `stop_reason="budget_exhausted"` and a clear final message.
- Add tests confirming supervisor LLM calls increment the same `total_llm_calls` / `llm_usage` counters used by agents (no separate budget namespace).

#### [ ] Task B5: Ensure Validation Gate Enforcement End-to-End

Add integration-level checks to confirm:
- No supervisor path can call `execute_sql` before:
  - `validate_sql` has been called.
  - `validation_result.is_valid is True`.
- Use supervisor prompt and tests to ensure:
  - The model is instructed to follow the validate-then-execute pattern.
  - Violations are caught by the `execute_sql` wrapper and surfaced as hard errors.

Verification:
- Add tests (e.g., `tests/test_supervisor_validation_gate.py`) that:
  - Simulate states where validation is missing or invalid, and confirm `execute_sql` does not bypass the guard.
- Run: `python -m pytest tests/test_supervisor_validation_gate.py -q`

---

### [ ] Step: Phase C – Cleanup, Simplification, and Rollout

Implementation is broken into three phases aligned with `spec.md`: **Phase A – Tools & Contracts**, **Phase B – Supervisor Graph**, and **Phase C – Cleanup & Rollout**.

**Definition of Done (Phase C)**
- Deprecated routing helpers and pipeline-only glue are either removed or clearly isolated behind pipeline mode.
- No dead or unreachable code executes in `react_supervisor` mode.
- An ADR documenting the ReAct supervisor decision is written and accepted.

#### [ ] Task C1: Identify Redundant Orchestrator Logic

Audit `langgraph_integration/orchestrator.py` for:
- Routing helpers and retry logic that duplicate supervisor responsibilities:
  - E.g., complex `_route_validation_result_for_state` retry branches.
- Legacy or rarely used branches that are not exercised in supervisor mode.

Produce a short internal note or comment block listing candidates for removal, referencing:
- `requirements.md` Section 9 (Ruthless Code Removal Policy).

Verification:
- `rg` / `git grep` usage checks to ensure candidates are not required for:
  - MCP safety gates.
  - API entrypoints.
  - Tests and evaluation harnesses.

#### [ ] Task C2: Apply Targeted Deletions / Deprecations

For each confirmed redundant cluster:
- Either:
  - Remove the code (when fully unused by pipeline mode, runtime paths, and tests) – preferred.
  - Replace with a stub clearly marked:
    - `DEPRECATED: ReAct supervisor migration`.
- Keep public API compatibility where needed (e.g., `graph_definition.py`-style stubs).

Verification:
- Run the core test suites:
  - `python -m pytest tests/test_orchestrator_integration.py -q`
  - `python -m pytest tests/test_full_pipeline_e2e.py -q` (if MCP connectivity is available in the environment).

#### [ ] Task C3: Documentation Updates

Update docs to reflect the new architecture:
- `langgraph_integration/README.md`:
  - Describe `pipeline` vs `react_supervisor` modes.
  - Document `orchestration_mode` configuration and recommended defaults.
- Any higher-level READMEs or architecture notes that reference the orchestrator.

Verification:
- Manual sanity check:
  - Ensure examples compile conceptually with the new API (constructor signatures, modes).

#### [ ] Task C4: Final Supervisor vs Pipeline Comparison

As a final check:
- For a small set of representative queries (including the primary acceptance criteria case):
  - Run both modes:
    - `orchestration_mode="pipeline"`
    - `orchestration_mode="react_supervisor"`
  - Compare:
    - Whether both produce semantically correct results.
    - Whether supervisor mode shows meaningful `supervisor_trace` and respects budgets.
- Capture any remaining behavioral gaps as follow-up tasks (outside this SDD if needed).

Verification:
- Prefer automated tests where possible; otherwise, document manual runs and outcomes in a short note linked from this plan.

#### [ ] Task C5: Author ADR 00XX – ReAct Supervisor Orchestration Mode

Create a new ADR in `adrs/` (e.g., `00XX-react-supervisor-orchestration-mode.md`) capturing:
- Context / problem:
  - Fixed pipeline brittleness, lack of adaptive control, and semantic failure modes.
- Decision:
  - Supervisor-driven ReAct loop using capability tools, with existing SQL validation and execution gates preserved.
- Alternatives considered:
  - Keep the fixed pipeline with heuristics.
  - Full rewrite around a single monolithic agent.
  - Hybrid approaches without a supervisor.
- Consequences:
  - New `supervisor_trace`, budgets, and dual-mode orchestration.
  - Removal / deprecation of legacy routing logic.
  - Tool contracts and MCP isolation guarantees.
- Rollout:
  - `orchestration_mode` as the feature flag.
  - Migration path and deprecation timeline for pipeline-only code.

Verification:
- Manual review of the ADR for consistency with `requirements.md`, `spec.md`, and this plan.
