# ReAct Integration (Codex) – Product Requirements

## 1. Problem & Context

- The current LangGraph-based `QueryOrchestrator` in `langgraph_integration/orchestrator.py` follows a mostly fixed pipeline of agents (intent → discovery → join_sql → validate_sql → exec → result formatting / validation).
- This pipeline is good at structural correctness (valid SQL, safe execution) but brittle when semantics are slightly off:
  - It can “lock in” to an early discovery / join plan and then push it through to execution even when the result clearly does not answer the user’s question.
  - Guardrails, templates, and result validation have been added incrementally, but they are tightly coupled to the pipeline order and are harder to extend.
- The repo already includes:
  - Specialized agents (`IntentParserAgent`, `DiscoveryAgent`, `JoinPlanAndSQLAgent`, `SQLValidatorAgent`, `ExecAndRecoveryAgent`, result validation, answer) under `langgraph_integration/agents`.
  - A LangGraph orchestrator that composes these as nodes with retry logic and budgets (LLM call caps, validation/exec retry limits, no-progress detection).
  - MCP as the substrate for catalog, relations, and execution.
- We now want to introduce a LangGraph Supervisor running a ReAct-style loop (think → act(tool) → observe → repeat), using the existing agents as tools instead of a fixed one-way pipeline.

## 2. Goals (What Success Looks Like)

### 2.1 Functional Goals

- Replace the rigid “single-path” agent pipeline with a supervisor-driven loop that:
  - Treats the main agents (intent, discovery, join_sql, validate_sql, exec, result validation, answer) as tools that can be invoked in different orders and multiple times as needed.
  - Runs an explicit ReAct-style cycle: the supervisor “thinks” (LLM reasoning over current state and history), chooses a tool to “act” with, observes the result, then decides the next action.
  - Remains compatible with current query types (data queries, schema queries, health checks, follow-ups) and continues to use MCP for catalog/relations/execution.
- Enable the system to:
  - Detect when an answer or intermediate output does not match the user question (e.g., wrong entity, wrong metric, wrong slice) and trigger replanning instead of finalizing.
  - Proactively gather missing information (e.g., schema details, relations, metrics) via MCP-backed tools and discovery utilities when the supervisor judges that more context is needed.
  - Try different candidate paths (different discovery candidates, different join strategies, or alternative filters/aggregations) when the current path stalls or yields low-quality results.
  - Stop early (with a clear explanation) when budgets or safety limits are reached, rather than hanging or looping indefinitely.

### 2.2 Non-Functional / Quality Goals

- **Autonomy, bounded by budgets**
  - Supervisor can autonomously choose the next step without a pre-baked route, but:
    - Must honor existing and new caps (e.g., `max_llm_calls`, `max_graph_cycles`, `max_validation_attempts`, `max_exec_recovery_attempts`, `max_total_plans`, `max_no_progress_repeats`).
    - Must surface budget usage and stopping reasons in the state (so callers and logs can see why the loop stopped).
- **Correct-by-construction at critical gates**
  - SQL cannot be executed without passing through validation (existing SQL validator / AST checks remain mandatory).
  - Semantic correctness checks (result validator, additional semantic gates) can trigger replans, but cannot bypass validation or execution safety.
- **Debuggability / Observability**
  - Every supervisor step is inspectable as:
    - The thought (LLM reasoning or summary of why a tool was chosen).
    - The tool call (which agent/tool, with what inputs).
    - The observation (structured output of the tool, including error_info).
  - Logs and state should make failure modes obvious:
    - Why a specific tool was chosen.
    - Why the loop stopped (success, budget, ambiguity, persistent error, user clarification needed).
- **Extensibility**
  - Adding new specialized agents or tools (e.g., metric lookup, heuristic join path search, contract-based semantic validation) should require minimal changes to the supervisor wiring and no large restructuring of the orchestrator core.

## 3. Users & Use Cases

- **Primary user:** End-user in chat UI asking enterprise data questions (via `chatbot_ui` / FastAPI).
  - Wants: correct and trustworthy answers to natural language questions about ERP/analytics data.
  - Typical queries:
    - “Show me top 10 products by revenue this quarter.”
    - “Which customers churned after price increases?”
    - “What tables contain project profitability by month?”
- **Secondary user:** Internal developers and SREs operating and debugging the system.
  - Wants:
    - Clear logs and traces when an answer is wrong or missing.
    - Simple ways to reproduce and inspect the supervisor loop for a given conversation.
    - Confidence that budget limits and safety constraints are reliably enforced.
- **Tertiary user:** Evaluation harnesses and benchmarks.
  - Wants:
    - Deterministic-ish behavior under constrained settings (benchmark mode).
    - Explicit signals for semantic retries, contract-based execution, and final stop reasons so metrics can be computed.

## 4. Scope

### 4.1 In Scope

- Introduce a ReAct-style supervisor graph (likely using `langgraph-supervisor` and/or `create_react_agent`) that:
  - Wraps existing agents as tools/subgraphs.
  - Manages the overall loop until a final answer or stop condition is reached.
- Keep MCP as the only way to:
  - Access database/catalog.
  - Execute SQL.
- Integrate with the existing orchestrator entry points (`QueryOrchestrator` / API layer) so that:
  - The external API surface (FastAPI endpoints, orchestrator factory/getter) is preserved or minimally adjusted.
  - Callers can opt-in to the supervisor mode without a breaking change, or default to it when ready.
- Preserve the current guardrail semantics:
  - Required relations and schema checks.
  - Row limits and timeouts.
  - Result validation logic that can trigger retries/replans.

### 4.2 Out of Scope (for this task)

- Major redesign of MCP server internals or Windows-side ranking logic.
- New UI surfaces or visualization of the supervisor loop (beyond using existing logs and potential minimal event structures).
- Large changes to data contracts or schema of persisted data; any changes should be additive / backward compatible.
- Rewriting all existing agents; they should be reused as much as possible and only lightly refactored for tool compatibility.

## 5. Functional Requirements

### 5.1 Supervisor Loop Behavior

- The system MUST implement a supervisor that:
  - Receives user input and conversation history as its initial context.
  - Maintains a message/state history that includes:
    - User messages.
    - Supervisor thoughts (LLM responses with tool decisions).
    - Tool calls and tool outputs.
  - Repeats the cycle:
    1. Reason over current state (“thought”).
    2. Choose a tool (or decide to finalize).
    3. Call the tool.
    4. Observe and integrate tool output into state.
  - Stops when:
    - A final answer is ready and validated.
    - A budget or safety cap is reached.
    - The supervisor determines that it needs user clarification.

### 5.2 Agent-as-Tool Design

- The following existing agents MUST be available as tools to the supervisor:
  - Intent / interpretation:
    - `IntentParserAgent` (intent parsing and operation routing).
    - `InterpretationAgent` (follow-ups over prior results) where appropriate.
  - Planning & data access:
    - `DiscoveryAgent` (tables/views discovery, schema snippet).
    - `JoinPlanAndSQLAgent` (join planning + SQL generation).
    - `SQLValidatorAgent` (SQL validation & repair).
    - `ExecAndRecoveryAgent` (safe execution).
    - Result validation node/tool built from `build_result_validator_node`.
  - Answering:
    - `AnswerAgent` (final answer formatting, clarification questions).
- Tools MUST:
  - Accept and return data compatible with existing `BaseState` and contracts, or a thin adapter layer must be provided.
  - Emit structured `error_info` when failing, so the supervisor can reason about recovery vs. final failure.

### 5.3 Semantic Correctness & Replanning

- When result validator (or other semantic tools) indicates that:
  - The answer is inconsistent with intent (wrong entity/metric/slice).
  - Candidate coverage is poor (e.g., missing required relations, low row counts when high coverage expected).
  - The plan is flapping (no-progress cycles).
  - …the supervisor MUST be able to:
    - Trigger a fresh discovery or join planning pass with updated constraints (e.g., different seed tables, modified filters, or explicit “must include entity X” constraints).
    - Try alternative candidate paths (e.g., next-ranked tables/views).
    - Choose to ask the user for clarification instead of blindly continuing.
- All replans and retries MUST respect global and per-stage budgets; the supervisor cannot bypass caps by re-wrapping calls.

### 5.4 Budgeting & Safety

- Supervisor MUST track:
  - LLM call count (across supervisor and tools where feasible).
  - Supervisor loop iterations / graph cycles.
  - Validation/exec retries and result-validation-induced retries.
- When a configured budget is reached, supervisor MUST:
  - Stop additional tool calls.
  - Produce a safe, user-facing message explaining that the system could not find a stable plan within a safe number of attempts and suggest ways to simplify or refine the query.
  - Record the specific stop reason in state (`stop_reason`, `error_info.type`, etc.).
- SQL execution MUST always go through:
  - SQL validation gate (no direct execution of unvalidated SQL).
  - Execution safety guardrails already present in `ExecAndRecoveryAgent` (timeouts, row caps, error handling).

### 5.5 Debuggability & Logging

- For each supervisor step, the system MUST make it possible (via logs and/or structured state) to reconstruct:
  - Thought text or a summary of why a tool was chosen.
  - Tool name and arguments (sanitized of PII/credentials).
  - Tool output (or at least key fields and error_info).
- The system SHOULD:
  - Integrate with the existing `debug_logger` in `langgraph_integration/debug_logger.py` where appropriate.
  - Make it easy for tests or playground scripts to capture the full supervisor trace for a single query.

## 6. Non-Functional Requirements

- **Performance**
  - ReAct loop should not significantly degrade latency for “easy” queries (e.g., queries where the first discovery/join path is correct).
  - Supervisor should have a reasonable default budget (e.g., similar to current `max_llm_calls` and plan budgets) to bound worst-case latency and cost.
- **Reliability**
  - On MCP or database failures, supervisor should surface clear error messages and not hang.
  - Fallback behavior should prefer “safe failure with explanation” over infinite loops or silent partial answers.
- **Compatibility**
  - Existing orchestrator tests and APIs should either:
    - Continue to pass using the new supervisor-based orchestration; or
    - Be updated in a controlled way with clear migration notes (outside this Requirements step).

## 7. Assumptions

- `langgraph-supervisor` and LangGraph ReAct-style patterns are available and compatible with the project’s existing LangGraph version.
- Existing agents are mostly correct and will be reused; only minimal refactoring will be needed to expose them as tools and/or subgraphs.
- MCP server interface (catalog, relations, execution) remains stable; changes needed for better semantics will be handled in separate tasks.
- Evaluation harnesses and configuration helpers (e.g., `get_max_llm_calls`, `get_max_graph_cycles`) can be reused to supply budget values to the supervisor.

## 8. Open Questions / Clarifications Needed

- Should the supervisor run:
  - For all query types (including simple schema/health checks), or only for complex data queries?
  - As the default mode in production, or only in a separate “experimental” path behind a feature flag?
- How much of the supervisor trace should be surfaced to:
  - End users (e.g., as “reasoning traces” in the UI)?
  - Internal users (e.g., dedicated debug endpoint vs. logs only)?
- Are there additional semantic validators (e.g., contract-based metric/entity verification, benchmark-oriented gates) that should be first-class tools in the supervisor loop, or should they remain internal to result validation?
- What are the acceptable upper bounds for:
  - LLM calls per query in production.
  - Maximum supervisor iterations.
  - Time-to-first-answer for typical vs. worst-case queries?

