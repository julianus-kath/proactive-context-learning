# ReAct Supervisor Integration – Technical Specification

## 1. Technical Context

- **Language / Runtime**
  - Python 3.x
  - Async-first orchestration using `asyncio`
- **Core Libraries**
  - `langgraph` – existing StateGraph-based orchestrator and agent subgraphs.
  - `langgraph-supervisor` – ReAct-style supervisor for multi-agent control.
  - `langchain-openai` / `openai` – LLM access for supervisor and LLM-based agents.
  - `fastapi` / `uvicorn` – HTTP API (`langgraph_integration/api.py`).
  - Internal modules:
    - `langgraph_integration.orchestrator.QueryOrchestrator`
    - Agents under `langgraph_integration/agents/*`
    - State and contracts under `langgraph_integration/contracts/*`
    - MCP client under `langgraph_integration/mcp_client.py`
- **Existing Architecture (Baseline for Comparison)**
  - A single `QueryOrchestrator` builds a **fixed LangGraph pipeline**:
    - `index_database → parse_intent → concept_mapping → route_operation → discovery → join_sql → validate_sql → exec_recovery → result_validator → answer`.
    - Conditional edges enable retries and re-plans, but the topology is static.
  - Each agent is a LangGraph subgraph or async callable but is **embedded as a graph node**, not exposed as a reusable tool.
  - Budgeting and safety live inside `QueryOrchestrator` and its helpers:
    - Fields on `BaseState` (e.g., `plan_attempt_count`, `retry_attempt_count`, `semantic_retry_count`, `max_llm_calls`, `max_graph_cycles`, etc.).
    - Routing helpers (e.g., `_route_validation_result_for_state`) decide whether to go back to discovery/join or proceed to answer.
  - MCP access is centralized via `get_shared_mcp_tool()` and used inside agents (discovery, validation, execution).

This spec introduces an additional orchestration layer – a **ReAct Supervisor graph** – that sits on top of the existing agents and budgets, rather than replacing them. The supervisor uses `langgraph-supervisor` to decide which capability tool (wrapped agents) to call next, while the existing orchestrator logic is refactored toward a shared **safety and execution substrate**.

## 2. Target Architecture Overview

### 2.1 High-Level Components

1. **Capability Tools (wrapped agents)**
   - Thin adapters around existing agents/subgraphs:
     1. `interpret_query` → `IntentParserAgent` / `InterpretationAgent`
     2. `discover_schema` → `DiscoveryAgent`
     3. `plan_sql` → `JoinPlanAndSQLAgent`
     4. `validate_sql` → `SQLValidatorAgent` (+ guardrails)
     5. `execute_sql` → `ExecAndRecoveryAgent`
     6. `evaluate_result` → `ResultValidator`
     7. `finalize_answer` → `AnswerAgent`
   - Each tool:
     - Accepts and returns `BaseState` (or a compatible adapter).
     - Emits a `tool_output` payload, `error_info`, `progress_signal`, and `suggested_next_actions`.
     - Updates shared budgets and instrumentation fields (e.g., `llm_usage`, `total_llm_calls`, `node_entry_counts`).

2. **ReAct Supervisor**
   - Implemented using `langgraph-supervisor.create_supervisor`.
   - Uses an LLM to run a **bounded ReAct loop**:
     - `thought → choose_tool → act → observe → decide_next`.
   - Decisions are recorded in a `supervisor_trace` structure on `BaseState`:
     - `step`, `thought_summary`, `action`, `tool_inputs_digest`, `observation_summary`, `progress_signal`, `budgets`.
   - Enforces global budgets:
     - `max_supervisor_steps`
     - `max_llm_calls_total` (mapped to `BaseState.max_llm_calls`)
     - `max_no_progress_repeats`

3. **Orchestration Mode Selector**
   - A configuration flag (e.g., `orchestration_mode`) determines how external callers invoke the system:
     - `"pipeline"` – existing `QueryOrchestrator.graph` (fixed pipeline; current default).
     - `"react_supervisor"` – new supervisor graph (ReAct loop over tools).
   - Exposed via:
     - Environment variable (`ORCHESTRATION_MODE`).
     - Optional parameter to factory helpers:
       - `create_query_orchestrator(orchestration_mode="pipeline" | "react_supervisor")`.
     - Optional field in API metadata for experiments (`ProcessQueryRequest.metadata["orchestration_mode"]`).

4. **Safety Substrate**
   - Existing safety layers are **not** bypassed:
     - SQL validation (`SQLValidatorAgent`) is a hard gate for any `execute_sql` call.
     - Execution (`ExecAndRecoveryAgent`) continues to enforce row caps, timeouts, and read-only semantics.
     - Result validation (`ResultValidator`) remains deterministic and non-LLM.

### 2.2 Comparison vs Current Architecture

- **Action Selection**
  - Current: Routing is deterministic and encoded in `orchestrator._build_graph()` and helper functions.
  - New: Supervisor uses LLM reasoning (via `langgraph-supervisor`) to choose among capability tools at each step, guided by tool metadata and `suggested_next_actions`.
  - In `react_supervisor` mode, the supervisor is the sole authority for agent sequencing; no fixed pipeline routing logic may be executed implicitly.

- **Topology**
  - Current: Topology is fixed; cycles only occur via conditional edges (e.g., `result_validator` → `discovery|join_sql|answer`).
  - New: Supervisor defines a **compact supervisor loop graph** where tools can be called in different orders and re-entered based on state and semantic signals (e.g., `evaluate_result` may suggest `rediscover` or `replan`).

- **State / Budgets**
  - Current: Budgets are enforced inside the orchestrator’s routing logic.
  - New: Budgets remain stored on `BaseState` but are additionally enforced at supervisor level (e.g., early stop when `total_llm_calls >= max_llm_calls` or `supervisor_step >= max_supervisor_steps`).

- **Debuggability**
  - Current: Node-level logs and `BaseState` instrumentation, but no explicit “thought/action/observation” trace.
  - New: `supervisor_trace` provides ReAct-style structured traces while still respecting chain-of-thought privacy (only summaries are logged).

## 3. Source Code Structure Changes

### 3.1 New Modules

1. `langgraph_integration/supervisor.py`
   - Contains:
     - Supervisor graph construction using `langgraph-supervisor`.
     - Capability tool wrappers that adapt existing agents to a unified tool contract.
     - Supervisor-specific configuration and budget handling.
   - Key functions/classes:
     - `build_react_supervisor_graph(...) -> CompiledGraph`
     - `create_react_supervisor(...) -> SupervisorEntryPoint`
     - `SupervisorConfig` dataclass:
       - `max_supervisor_steps`, `max_llm_calls_total`, `max_no_progress_repeats`, etc.

2. `langgraph_integration/tools/capability_tools.py`
   - Optional convenience layer to keep supervisor-specific glue separate from orchestrator:
     - `interpret_query_tool(state: BaseState) -> BaseState`
     - `discover_schema_tool(state: BaseState) -> BaseState`
     - `plan_sql_tool(state: BaseState) -> BaseState`
     - `validate_sql_tool(state: BaseState) -> BaseState`
     - `execute_sql_tool(state: BaseState) -> BaseState`
     - `evaluate_result_tool(state: BaseState) -> BaseState`
     - `finalize_answer_tool(state: BaseState) -> BaseState`
   - Each tool:
     - Delegates into the corresponding agent / subgraph (reusing current implementations).
     - Adds tool-level metadata and structured outputs for the supervisor’s policy model.

These modules intentionally align with the existing `langgraph_integration` namespace and reuse current agents and contracts to minimize migration risk.

### 3.2 Modifications to Existing Files

1. `langgraph_integration/orchestrator.py`
   - Add orchestration mode handling:
     - Constructor accepts `orchestration_mode: str = "pipeline"`.
     - `process_query()` routes to:
       - `self.graph.ainvoke(...)` for `"pipeline"`.
       - `self._invoke_supervisor(...)` for `"react_supervisor"`.
   - Introduce a small adapter to share `BaseState` budgets with the supervisor:

     - On entry:
       - Initialize supervisor-specific fields: `supervisor_step_count`, `max_supervisor_steps`, `supervisor_trace`.
     - On exit:
       - Normalize final `stop_reason` and `final_response` using the supervisor’s result envelope, then reuse existing normalization logic.
   - Keep existing `_build_graph()` pipeline intact to avoid breaking current tests; supervisor is additive.

2. `langgraph_integration/api.py`
   - Allow API callers to select orchestration mode:
     - From metadata: `request.metadata["orchestration_mode"]`.
     - From environment default (e.g., `ORCHESTRATION_MODE`).
   - Pass orchestration mode through to `QueryOrchestrator.process_query()`.

3. `langgraph_integration/contracts/state.py`
   - Extend `BaseState` with supervisor-related fields:
     - `supervisor_trace: List[Dict[str, Any]]`
     - `supervisor_step_count: int`
     - `max_supervisor_steps: int`
     - `last_tool_name: Optional[str]`
     - `last_tool_progress_signal: Optional[str]`
     - `no_progress_repeat_count: int`
     - `orchestration_mode: Optional[str]`  # “pipeline” | “react_supervisor”
   - Add reusable types for tool output envelopes if helpful (e.g., `ToolCallResult` TypedDict).

4. `langgraph_integration/contracts/response_envelope.py`
   - Optionally extend or add a small wrapper model for supervisor outputs, e.g.:
     - `SupervisorStopReason = Literal["success", "clarify", "budget_exhausted", "fatal_error"]`.
     - Ensure `final_response` and `stop_reason` fields remain consistent for both modes; the acceptance criteria expect `stop_reason` to be returned.

5. Tests (`tests/` directory)
   - New tests:
     - Unit tests for capability tools (state transformations and tool contracts).
     - Integration tests for supervisor mode:
       - Basic end-to-end queries (e.g., “top 10 products by total sales last 12 months”).
       - Budget enforcement (LLM calls and supervisor steps).
       - Validation-gate enforcement (no `execute_sql` without passing `validate_sql`).
   - Existing orchestrator tests:
     - For `"pipeline"` mode, tests remain unchanged and must still pass.
     - For `"react_supervisor"` mode, either:
       - Reuse existing tests with added options, or
       - Add parallel test cases with supervisor mode enabled.

## 4. Capability Tool Contracts

Each capability tool shares a **common contract**, aligning with FR‑2 while staying compatible with current agent APIs.

### 4.1 Shared Tool Envelope

- **Input**
  - `state: BaseState` – shared orchestrator state.
- **Output (mutations on state)**
  - `tool_output`: `Dict[str, Any]` – structured result for the specific capability.
  - `error_info`: `Optional[Dict[str, Any]]` – normalized error information (using `ErrorInfo` semantics).
  - `progress_signal`: `Literal["positive", "neutral", "negative"]`.
  - `suggested_next_actions`: `List[Literal["rediscover", "replan", "clarify", "stop"]]`.
  - Tool-specific fields (e.g., `intent`, `relevant_tables`, `sql_query`, `validation_result`, `exec_result`, etc.).

Implementation detail: in Python, each capability tool will be a callable registered with the supervisor as a resource/tool and will internally call the existing agent’s graph or async method.

### 4.2 Mapping to Existing Agents

1. `interpret_query`
   - Backed by:
     - `IntentParserAgent.build_subgraph()` for initial queries.
     - `InterpretationAgent` for follow-up interpretation (when `required_action == "interpret_previous"`).
   - Tool output:
     - `tool_output.intent: ParsedIntent`
     - `progress_signal`: `positive` if confidence ≥ threshold; `negative` if clarification is needed.
     - `suggested_next_actions`: e.g., `["discover_schema"]` or `["clarify"]`.

2. `discover_schema`
   - Backed by `DiscoveryAgent.build_subgraph()`.
   - Tool output:
     - `tool_output.relevant_tables`, `schema_snippet`, `candidate_views`, `column_index`, etc.
     - `progress_signal`: `positive` when new tables/views are found; `negative` if repeated zero-results or discovery errors.
     - `suggested_next_actions`: typically `["plan_sql"]`, or `["rediscover"]` when signals indicate misalignment.

3. `plan_sql`
   - Backed by `JoinPlanAndSQLAgent` (similar subgraph pattern as discovery/intent).
   - Tool output:
     - `tool_output.join_plan`, `tool_output.sql_query`.
     - `progress_signal`: `positive` when a non-empty, consistent plan is produced; `negative` if planning fails or recycles previous fingerprints without progress.
     - `suggested_next_actions`: `["validate_sql"]` on success; `["rediscover", "stop"]` on repeated failures.

4. `validate_sql`
   - Backed by `SQLValidatorAgent.__call__`.
   - Tool output:
     - `tool_output.validation_result` with `is_valid`, `error_type`, `error_message`, `tables_used`, `tables_used_base`, etc.
     - If `is_valid` is `False`, `progress_signal` is typically `negative`.
     - `suggested_next_actions`:
       - For repairable issues: `["replan"]` (e.g., wrong aggregation) or `["rediscover"]` (wrong tables).
       - For fatal issues: `["stop"]` or `["clarify"]`.

5. `execute_sql`
   - Backed by `ExecAndRecoveryAgent.__call__`.
   - **Hard constraint**: must only be invoked when `validation_result.is_valid == True`.
   - Tool output:
     - `tool_output.exec_result` (normalized via `ResponseEnvelope`).
     - `tool_output.sql_query` (possibly updated by repair).
     - `progress_signal`: `positive` on successful execution; `negative` if repeated failures occur.
     - `suggested_next_actions`: `["evaluate_result"]` on success; `["rediscover", "replan", "stop"]` on persistent failures.

6. `evaluate_result`
   - Backed by `ResultValidator.validate(...)`.
   - Tool output:
     - `tool_output.validation_result` (result validator’s TypedDict).
     - `progress_signal`:
       - `positive` when `valid` and shape/entity/metric checks pass.
       - `negative` when semantic issues are detected.
     - `suggested_next_actions` based on retry actions:
       - `"try_next_candidate"` → `["rediscover"]`
       - `"replan_with_aggregation" | "replan_with_filter"` → `["replan"]`
       - `"ask_user"` → `["clarify"]`
       - `"accept"` → `["finalize_answer"]`

7. `finalize_answer`
   - Backed by `AnswerAgent.build_subgraph()`.
   - Tool output:
     - `tool_output.final_response`
     - `tool_output.stop_reason` in `{success, clarify, budget_exhausted, fatal_error}`.
     - Optionally: `sql_query`, `tables_used`, `budget_usage`, `trace_id`.
   - Supervisor treats this as a terminal action in most flows.

Wherever possible, these tools should reuse existing orchestrator methods (e.g., `_format_execution_results`) to keep behavior consistent across modes.

## 5. Supervisor Loop and Budgets

### 5.1 Supervisor Policy

- Implemented via `langgraph-supervisor.create_supervisor` using:
  - A dedicated LLM model (e.g., `ChatOpenAI(model="gpt-4o-mini")`).
  - A prompt describing:
    - Available capability tools, their responsibilities, and constraints.
    - The current state summary (intent, discovery status, validation status, budgets).
    - Requirements to:
      - Avoid bypassing validation/exec gates.
      - Stop when budgets or no-progress conditions are met.
      - Prefer deterministic signals (validation, result checks) over extra LLM calls.
  - Supervisor entry conditions:
    - On entry, the supervisor MUST begin with either:
      - `interpret_query`, or
      - a no-op state check when a valid intent already exists (e.g., structured follow-ups).
    - The supervisor MUST NOT assume discovery or planning has already happened.

- Supervisor reasoning representation:
  - Supervisor “thoughts” stored in `supervisor_trace` are decision summaries, not raw chain-of-thought.
  - These summaries MUST NOT include hidden reasoning tokens or verbatim internal prompts.

### 5.2 Budget Enforcement

- Supervisor-level counters (mirrored onto `BaseState`):
  - `supervisor_step_count` – incremented per loop iteration.
  - `max_supervisor_steps` – derived from configuration (e.g., 12–20 steps).
  - `no_progress_repeat_count` – increments when `progress_signal == "negative"` or when tools do not change key state fingerprints (e.g., join inputs fingerprint, SQL fingerprint).
  - `max_no_progress_repeats` – cap after which the supervisor stops with `stop_reason="budget_exhausted"` or `fatal_error`.
- Integration with existing budgets:
  - `total_llm_calls` and `max_llm_calls` already tracked in `BaseState`:
    - Capability tools increment `llm_usage` and `total_llm_calls` (existing patterns).
    - Supervisor LLM invocations count toward the same `total_llm_calls` and `llm_usage` counters; there is a single shared LLM budget across supervisor and agents.
    - Supervisor reads remaining budget to decide whether to call more LLM-heavy tools.
  - `total_graph_cycles` and `max_graph_cycles` remain as safety nets for the existing pipeline; for supervisor mode, we can reuse `total_graph_cycles` as the count of major re-plan cycles.

### 5.3 Stop Conditions

- Supervisor stops (and calls `finalize_answer`) when:
  - The answer is ready (`evaluate_result` + internal heuristics suggest `accept`).
  - User clarification is needed.
  - Budgets are hit:
    - `supervisor_step_count >= max_supervisor_steps`
    - `total_llm_calls >= max_llm_calls`
    - `no_progress_repeat_count >= max_no_progress_repeats`
  - A non-recoverable error occurs in tools (e.g., fatal validation failure or MCP unavailability).

Supervisory stop reasons are mapped to the response envelope’s `stop_reason` and synthesized into a user-facing explanation where appropriate (e.g., “I stopped because the allowed number of reasoning steps was reached.”).

## 6. MCP Isolation and Safety

- MCP interactions remain strictly within:
  - `DiscoveryAgent` (catalog/scout/describe_table).
  - `SQLValidatorAgent` (schema/column checks via MCP tools).
  - `ExecAndRecoveryAgent` (bounded query execution).
- Supervisor and capability tool wrappers:
  - **Do not** call MCP directly.
  - Only operate on `BaseState` and call agents that already encapsulate MCP usage.
- Validation gate invariants:
  - The `execute_sql` tool must enforce that:
    - `state.get("validation_result", {}).get("is_valid") is True` before execution.
    - If not, it logs and returns a hard error, and **does not** call MCP.
  - Result validator continues to run after execution to gate semantic correctness and inform replanning.

The design is consistent with the current safety model: validation and execution rules in `ExecAndRecoveryAgent` and `SQLValidatorAgent` remain unchanged.

## 7. Delivery Phases & Milestones

### Phase A – Tool Wrappers and Contracts

- Implement capability tool wrappers around existing agents and subgraphs.
- Extend `BaseState` with supervisor fields.
- Add unit tests for each tool’s contract (inputs/outputs, `progress_signal`, `suggested_next_actions`).
- Validate against current pipeline behavior:
  - For a set of reference queries, compare intermediate artifacts (intent, tables, SQL) between:
    - Direct orchestrator pipeline (`pipeline` mode).
    - Running the same agents via capability tools in a scripted sequence (no supervisor yet).

### Phase B – Supervisor Graph (React Supervisor Mode)

- Implement `langgraph_integration/supervisor.py` with:
  - Supervisor construction using `langgraph-supervisor.create_supervisor`.
  - Policies for tool selection and budget enforcement.
  - `supervisor_trace` recording.
- Integrate with `QueryOrchestrator.process_query()`:
  - Add `orchestration_mode` handling and state initialization.
- Add supervisor integration tests:
  - Happy-path analytic queries (including “top 10 products by total sales last 12 months”).
  - Cases where result evaluation triggers rediscovery or replanning.
  - Budget exhaustion scenarios.

### Phase C – Cleanup and Optional De-Pipelining

- Audit `QueryOrchestrator` for logic now redundant under supervisor mode:
  - Complex retry-routing helpers that duplicate supervisor responsibilities.
  - Template explosion and legacy path handling.
- Apply the repo’s “ruthless code removal” policy:
  - Remove unused orchestrator branches / legacy helpers once supervisor mode is stable and covered by tests.
  - Convert public APIs to clear stubs where necessary, marked as:
    - `DEPRECATED: ReAct supervisor migration`.
- Align documentation:
  - Update `langgraph_integration/README.md` and higher-level docs to describe both modes, then eventually promote supervisor as default once validated.

## 8. Verification Approach

- **Unit Tests**
  - For capability tools:
    - Verify that tool wrappers:
      - Invoke underlying agents correctly.
      - Populate `tool_output`, `progress_signal`, `suggested_next_actions`, and errors as expected.
    - Handle error conditions (MCP errors, invalid state) without breaking invariants.
  - For `BaseState` extensions:
    - Ensure supervisor fields are optional and do not break existing users of `BaseState`.

- **Integration Tests**
  - Reuse existing orchestrator tests for `"pipeline"` mode (must remain green).
  - Add tests for `"react_supervisor"`:
    - End-to-end query processing via `QueryOrchestrator.process_query()` with metadata specifying supervisor mode.
    - Validate that:
      - `stop_reason` is set appropriately.
      - `supervisor_trace` has at least one step and uses only safe summaries.
      - `execute_sql` is never called without a valid `validation_result`.

- **Performance / Budget Tests**
  - Use benchmark queries to:
    - Measure number of LLM calls (`total_llm_calls`) and supervisor steps.
    - Confirm typical “easy” queries follow approximately:
      - 1× `interpret_query` → 1× `discover_schema` → 1× `plan_sql` → 1× `validate_sql` → 1× `execute_sql` → 1× `evaluate_result` → 1× `finalize_answer`.
    - Validate that budgets cap total steps and calls as configured.

- **Manual / Debugging Checks**
  - Use existing debug/logging infrastructure and the new `supervisor_trace` to inspect:
    - Tool choice sequences for complex queries.
    - Replanning decisions triggered by `evaluate_result`.
  - Compare:
    - Current system behavior (`pipeline`).
    - Supervisor behavior (`react_supervisor`).
  - For representative queries to ensure the spec and implementation stay aligned over time.
