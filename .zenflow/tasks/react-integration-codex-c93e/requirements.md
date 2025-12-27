# ReAct Supervisor Integration – SDD Requirements

## 1. Motivation

- The current LangGraph-based `QueryOrchestrator` in `langgraph_integration/orchestrator.py` is a deterministic controller with bounded retries, not a true ReAct-style supervisor.
- It owns a global `BaseState`, enforces budgets (`plan_attempt_count`, `retry_attempt_count`, `semantic_retry_count`, `validation_attempt_count`, `exec_recovery_attempt_count`, `total_llm_calls`), and centralizes routing / error policy via helpers like `_route_validation_result_for_state()`.
- However, it still behaves like a static, rule-based pipeline:
  - Graph topology and node order are fixed (intent → discovery → join_sql → validate_sql → exec → result_validator → answer, plus some conditional branches).
  - Agents are graph nodes, not dynamic tools; the orchestrator routes based on hard-coded edges and retry_action enums, not on LLM-driven reasoning.
  - There is no explicit “thought → act(tool) → observe” loop; agents run because the graph routes to them, not because a supervisor decided they were needed.
- This leads to the core failure mode:
  - Once a semantically wrong plan (wrong entity, metric, join path, or aggregation shape) enters the pipeline, the system can only try to repair *within that plan*.
  - It cannot step back and re-run discovery/planning with new constraints based on semantic evidence from results.
- Guardrails, templates, semantic validators, and contracts have been added to mitigate this, but they are layered on top of a rigid pipeline, making the system brittle and harder to extend.
- The repo already includes:
  - Specialized agents (`IntentParserAgent`, `DiscoveryAgent`, `JoinPlanAndSQLAgent`, `SQLValidatorAgent`, `ExecAndRecoveryAgent`, result validation, `AnswerAgent`, `InterpretationAgent`) under `langgraph_integration/agents`.
  - A LangGraph orchestrator graph with budgets and safety gates.
  - MCP as the substrate for catalog, relations, and execution.

**Motivating insight:** You already have state, budgets, safety, and observability. What is missing is a thin ReAct-style supervisory layer above this that:
- Uses LLM reasoning to decide *which tool to invoke next*.
- Treats existing agents as tools.
- Runs a bounded ReAct loop.
- Delegates SQL validation and execution safety to the existing machinery.

## 2. End Goal

- Introduce a LangGraph Supervisor that:
  - Runs a bounded ReAct loop: **reason → choose tool → act → observe → decide next**.
  - Uses existing pipeline components as **capability tools**, not a fixed workflow.
  - Keeps execution safety rigid (no change to validation/exec safety rules).
- The supervisor should:
  - Re-run discovery and planning when evidence (from results, validators, or contracts) suggests the current plan is wrong.
  - Converge toward semantically correct answers with fewer brittle assumptions and templates.
  - Stop safely and transparently when budgets are hit, explaining why.

## 3. Scope

### 3.1 In Scope

- Introduce a **Supervisor graph** (ReAct-style loop) as an alternative orchestration path.
- Wrap existing agents into **seven capability tools** with a common contract:
  1. `interpret_query` – intent parsing / interpretation (intent vs. follow-up).
  2. `discover_schema` – discovery + schema snippet (Scout / catalog).
  3. `plan_sql` – join planning and SQL generation.
  4. `validate_sql` – SQL validation & repair (mandatory gate).
  5. `execute_sql` – safe SQL execution via MCP (mandatory gate).
  6. `evaluate_result` – semantic/result validation and replanning hints.
  7. `finalize_answer` – answer formatting and clarification messages.
- Ensure the supervisor interacts with MCP **only via tools** (discovery, validation, execution paths).
- Add **structured step traces** per supervisor loop iteration, including:
  - `thought_summary` (short, no raw chain-of-thought leakage).
  - `action` (tool selected).
  - `observation` / `observation_summary`.
  - `progress_signal`.
  - `budgets` snapshot.

### 3.2 Out of Scope

- MCP server redesign.
- New UI visualizations beyond using existing logs/state traces.
- Major rewrites of all agent internals; only refactors needed to:
  - Expose them as tools/subgraphs.
  - Clean up contracts for the seven capability tools.

## 4. Hard Constraints (Non-Negotiable)

1. **Validation gate for execution**
   - No SQL execution without passing validation.
   - Supervisor MUST enforce that `execute_sql` can only be invoked on SQL that `validate_sql` has marked as valid (e.g., `validation_result.is_valid == True`).
2. **Supervisor–MCP isolation**
   - Supervisor MUST NOT call MCP directly.
   - All catalog, schema, relation, and execution access goes through tools built on top of existing MCP clients.
3. **Bounded autonomy**
   - Supervisor MUST enforce and respect budgets including:
     - `max_llm_calls_total` (existing, e.g., 20).
     - `max_supervisor_steps` (loop iterations).
     - `max_no_progress_steps` (consecutive negative/neutral progress).
     - `max_replans_per_tool` (per-tool retries).
   - On budget exhaustion, supervisor MUST stop and return a safe explanation.
4. **No raw chain-of-thought leakage**
   - External surfaces (API responses, logs likely to reach end users) MUST only include short `thought_summary` fields, not full internal reasoning traces.
   - Richer traces may be stored internally for debugging, but must not be surfaced directly to end users.
5. **Supervisor authority**
   - For data queries, the ReAct Supervisor MUST be the sole component responsible for sequencing agent/tool execution.
   - The legacy pipeline (intent → discovery → join → validate → exec → answer) MUST NOT be executed automatically as a fixed path; it may only be entered via supervisor-initiated tool calls (or via an explicit “pipeline mode” feature flag when supervisor is disabled).

## 5. Functional Requirements

### FR‑1: Supervisor Loop

- The system MUST run a ReAct-style loop:
  - **reason**: generate a short `thought_summary` based on current state and history.
  - **choose tool**: pick one tool from the fixed toolset `{interpret_query, discover_schema, plan_sql, validate_sql, execute_sql, evaluate_result, finalize_answer}`.
  - **act**: call the tool with the current state / relevant inputs.
  - **observe**: record tool output and integrate it into state.
  - **update**: update budgets and progress metrics.
  - **stop** when any of the following is true:
    - Supervisor deems the answer ready (success).
    - Supervisor needs user clarification (clarify).
    - Budgets are reached (budget).
    - A non-recoverable error occurs (fatal).

### FR‑2: Tool Contract (All Capability Tools)

- Each tool MUST:
  - Accept a shared state object (directly compatible with `BaseState` or via a thin adapter).
  - Return a structured payload including:
    - `tool_output`: structured result (e.g., intent object, candidate tables, SQL text, execution result, validation verdict).
    - `error_info`: structured, typed error (compatible with `ErrorInfo` model), or `None`.
    - `progress_signal`: one of `{positive, neutral, negative}`.
    - `suggested_next_actions`: a small, enumerated list of recommended next actions (e.g., `["rediscover", "replan", "clarify", "stop"]`).
- Supervisor MAY use `suggested_next_actions` as hints but retains final authority on which tool to call next.

### FR‑3: Re‑entrant Discover/Plan

- Supervisor MUST be able to:
  - Re-run discovery with updated constraints (e.g., “must include products table”, alternative seed tables, or stricter entity/metric hints).
  - Re-run planning with different fact/dimension assumptions or templates.
  - Attempt alternative candidate sets when current ones lead to poor results or no-progress cycles.
- Discovery and planning tools MUST be designed to be safely re-entrant and respect cumulative state (e.g., `tried_candidate_tables`, `skip_tables`, or similar fields).

### FR‑4: Result Semantics Drive Replanning

- `evaluate_result` MUST, at minimum, detect:
  - **Wrong entity** (e.g., user requested products, but grouping is by orders or unrelated IDs).
  - **Wrong metric type** (e.g., summing non-numeric or address-like fields).
  - **Wrong aggregation shape** (e.g., scalar aggregate when top‑k list requested).
  - **Missing dimension labeling** when requested (e.g., no product name/identifier in result).
- When `evaluate_result` produces a negative `progress_signal`, it MUST recommend one or more of:
  - `rediscover` – re-run discovery with refined constraints.
  - `replan` – re-run SQL planning/aggregation with adjusted assumptions.
  - `clarify` – ask user for clarification.
  - `stop` – terminate with a safe failure message.

### FR‑5: Finalization

- `finalize_answer` MUST produce a response envelope that always includes:
  - `final_response`: human-readable answer or clarification question.
  - `stop_reason`: one of `{success, clarify, budget_exhausted, fatal_error}`.
- It SHOULD also include when available:
  - `sql_query`: final SQL used (if any).
  - `tables_used`: list of tables/views involved.
  - `budget_usage`: summary of consumed vs. configured budgets.
  - `trace_id`: an identifier to correlate with logs/traces.

## 6. Non‑Functional Requirements

### NFR‑1: Safety

- Validation and execution safety rules from the existing orchestrator MUST remain unchanged:
  - SQL validation and AST checks remain mandatory.
  - Execution continues to respect row caps, timeouts, and error handling already implemented in `ExecAndRecoveryAgent`.
- Supervisor MUST not introduce any bypasses around validation or safety guards.

### NFR‑2: Debuggability

- Each supervisor iteration MUST append a trace item to a `supervisor_trace` structure, for example:

```json
{
  "step": 3,
  "thought_summary": "Metric looks wrong; likely using orders instead of order_details",
  "action": "plan_sql",
  "tool_inputs_digest": "...",
  "observation_summary": "...",
  "progress_signal": "negative",
  "budgets": {"llm_remaining": 12, "steps_remaining": 9}
}
```

- The trace MUST be easily accessible for:
  - Unit/integration tests (e.g., assertions on step count and stop reason).
  - Developers using existing debug tools / logs.

**Supervisor Reasoning Representation**

- The supervisor MAY internally reason using hidden LLM chain-of-thought.
- Persisted state and logs MUST store only:
  - A short, human-readable decision summary (e.g., “Result mismatched intent → replanning discovery”).
  - The chosen action/tool.
  - The observed outcome (or summarized observation).
- Raw chain-of-thought MUST NOT be logged or returned in API responses.

### NFR‑3: Performance

- For “easy” queries, supervisor SHOULD typically converge within:
  - ~1 discovery + 1 plan + 1 validate + 1 exec + 1 answer (no unnecessary loops).
- Tool implementations MUST:
  - Prefer MCP metadata and deterministic heuristics over extra LLM calls where possible.
  - Avoid redundant heavy operations (e.g., repeated catalog fetches without need).

### NFR‑4: Compatibility

- Existing orchestrator tests and APIs MUST:
  - Continue to pass when running in “pipeline” mode.
  - Either pass or be updated in a controlled way for “react_supervisor” mode, with minimal breaking changes to external callers.

## 7. Compatibility & Rollout

- Introduce a configuration flag to control orchestration mode, e.g.:
  - `orchestration_mode = "pipeline" | "react_supervisor"`.
- Rollout phases:
  - **Phase A:** Supervisor behind feature flag, dev-only. Pipeline remains default.
  - **Phase B:** Optional “shadow mode” where supervisor runs in parallel for tracing only (no user-visible changes), if feasible.
  - **Phase C:** Supervisor becomes default for selected routes or user segments once stability/quality is validated.

## 8. Acceptance Criteria (Pass/Fail)

1. **Top‑k analytic query quality**
   - For “top 10 products by total sales last 12 months”, the final plan and SQL MUST:
     - Include a product dimension (name/identifier).
     - Use a correct metric expression (e.g., `unit_price * quantity` or equivalent).
     - Produce a top‑k shape (`ORDER BY metric DESC LIMIT 10` or SQL Server equivalent).
     - Apply an appropriate time filter via orders date joins.
2. **Supervisor trace clarity**
   - The supervisor MUST emit a readable, structured step trace and stop with an explicit `stop_reason`.
3. **Validation gate enforced**
   - No SQL executes without passing validation; any attempt to bypass MUST be impossible by construction.
4. **Budgets respected**
   - LLM calls and supervisor steps MUST not exceed configured budgets; on attempted excess, the system MUST stop with a clear explanation.

## 9. Ruthless Code Removal Policy (for this branch)

### Principle

- If code is not required for:
  - ReAct Supervisor.
  - The seven capability tools.
  - MCP safety gates.
  - API entrypoints.
  - Tests that exercise these paths.
- …then it SHOULD be removed or archived.

**Codebase Simplification Requirement**

- As part of this integration, redundant orchestration logic, unused routing branches, deprecated agents, and pipeline-specific glue code MUST be removed where they are no longer reachable or necessary under the supervisor-driven architecture.
- Backward compatibility inside this branch is not required unless explicitly stated; deprecation stubs are only needed for public entrypoints that external callers still rely on.

### Removal Rules

- **Delete code** when **all** of the following hold:
  1. No imports in active runtime paths.
  2. Not referenced by tests.
  3. Not referenced by CLIs/scripts used in normal run workflows.
  4. Not required for the seven tool interfaces or MCP substrate.
- **Convert to deprecated stub** when:
  - It is part of a public API path that will be removed later.
  - It MUST be clearly marked, e.g.:
    - `DEPRECATED: ReAct supervisor migration`.

### Preferred cleanup targets

1. **Duplicate orchestrators / legacy routing**
   - Any alternate “old pipeline” variants that will not be used once the supervisor is the default.
2. **Benchmark-mode-only scaffolding**
   - Keep only what is required for evaluation; remove scaffolding that mutates runtime behavior without improving core answers.
3. **Template explosion**
   - Keep a minimal set of templates needed for MVP; prefer supervisor-driven replanning over large numbers of brittle templates.
4. **Unused direct DB paths**
   - If MCP is the enforced substrate, remove alternative DB clients unless explicitly needed for migration.
5. **Duplicate canonicalization utilities**
   - Converge on a single canonical utility module / source of truth.

### Cleanup Deliverables

- For each deletion cluster, maintain:
  - “Find usages” proof (e.g., documented evidence that code is unused).
- A running test set including:
  - Unit tests for tool wrappers and validation/exec gates.
  - 1–2 E2E queries via existing FastAPI endpoints.
- A short architecture note or ADR update explaining:
  - What was removed.
  - Why it was safe to remove (to avoid future archaeology).

## 10. Implementation Potential vs Current Architecture

### 10.1 Existing Strengths (Proto-Supervisor Behavior)

- The current `QueryOrchestrator` already provides:
  - Global state ownership (`BaseState`) across agents.
  - Budget tracking and enforcement (`plan_attempt_count`, `retry_attempt_count`, `validation_attempts`, `exec_recovery_attempts`, `total_llm_calls`, `max_total_plans`, etc.).
  - Centralized routing and policy via `_route_validation_result_for_state()` and related helpers.
  - Error interpretation that maps validation/execution issues into retry/clarify/answer decisions.
- These are **supervisor-like capabilities** that can be reused rather than discarded.

### 10.2 Gaps vs ReAct / LangGraph Supervisor Patterns

- Missing pieces relative to ReAct-style supervisors and resources like:
  - LangChain/LangGraph `create_agent` / `create_react_agent`.
  - `langgraph-supervisor` prebuilt supervisors.
  - ReAct papers and example implementations.
- Key gaps:
  - No autonomous action selection; routing is driven purely by rule-based `retry_action` enums and static edges.
  - Fixed graph topology; no dynamic tool choice or re-ordering beyond predeclared conditional edges.
  - No explicit **thought → act → observe** loop exposed in state.
  - Agents are not exposed as tools; orchestrator cannot call the same agent with different reasoning contexts as a first-class decision.

### 10.3 Mapping to a Supervisor-Based Design

- The project already depends on `langgraph` and `langgraph-supervisor`, and includes a tutorial notebook (`scripts/agent_supervisor.ipynb`) that demonstrates:
  - Creating worker agents.
  - Wrapping them with `create_react_agent`.
  - Building a supervisor that hands off control via tools and routes control back.
- Implementation potential is high because:
  - Existing agents can be wrapped as tools or subgraphs with thin adapters (to satisfy the tool contract defined in FR‑2).
  - A supervisor node can be created using ReAct-style helpers (e.g., `create_react_agent`) wired with the seven capability tools.
  - The supervisor graph can be added on top of the existing orchestrator substrate:
    - Reusing `BaseState`, error models, and budget helpers.
    - Reusing SQL validation and execution gates unchanged.
  - The feature-flagged `orchestration_mode` enables incremental rollout without breaking existing callers.

- This SDD assumes that:
  - The existing orchestrator becomes more of a **safety and execution substrate**, while the ReAct supervisor provides the **cognitive control loop**.
  - Subsequent Technical Specification and Planning steps will define the exact division of responsibility (what stays in `QueryOrchestrator` vs. what moves into the supervisor graph) and the concrete tool APIs.
