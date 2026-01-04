# Technical Specification: Agent Cleanup & Responsibility Simplification (LangGraph Integration)

## 1. Technical Context

- **Languages / runtimes**: Python 3.x, LangGraph, LangChain/OpenAI, FastAPI.
- **Core modules in scope**:
  - Orchestration & supervisor: `langgraph_integration/orchestrator.py`, `langgraph_integration/supervisor.py`, `langgraph_integration/graph_definition.py`, `langgraph_integration/tools/capability_tools.py`.
  - Agents:
    - Intent: `agents/intent_parser/agent.py`.
    - Discovery: `agents/discovery/agent.py`.
    - Join & SQL: `agents/join_sql/agent.py`.
    - SQL validation: `agents/sql_validator/agent.py`.
    - Execution & recovery: `agents/exec_recovery/agent.py`.
    - Result validation: `agents/result_validator/agent.py`.
    - Answer formatting: `agents/answer/agent.py`.
  - Contracts & utilities: `contracts/state.py`, `contracts/semantic_contracts.py`, `contracts/response_envelope.py`, `utils/*`, `prompts/*`.
- **Execution model (current)**:
  - `QueryOrchestrator.process_query()` normalizes state, ensures MCP/catalog readiness, and then always runs the ReAct-style supervisor via `run_supervisor()`.
  - The supervisor chooses among capability tools (`interpret_query`, `discover_schema`, `plan_sql`, `validate_sql`, `execute_sql`, `evaluate_result`, `finalize_answer`), which in turn delegate to orchestrator agent nodes.
  - Legacy fixed `pipeline` mode is effectively disabled; pipeline-only helpers remain as technical debt.

## 2. Architectural Intent

- **Single “world view” owner**: `ReactSupervisor` holds the global view over the query, current state, and available tools; it decides *when* to re-run discovery, planning, validation, or execution.
- **Agents as capability tools**: Each agent is a bounded, single-pass tool with a narrow contract, invoked via capability wrappers. They should not implement cross-phase loops or orchestrate other agents directly.
- **Primary path** (data queries):
  1. Interpret/parse intent → `IntentParserAgent` via `interpret_query_tool`.
  2. Discover relevant tables/views + schema snippet → `DiscoveryAgent` via `discover_schema_tool`.
  3. Plan joins and synthesize SQL → `JoinPlanAndSQLAgent` via `plan_sql_tool`.
  4. Validate/repair SQL → `SQLValidatorAgent` via `validate_sql_tool`.
  5. Execute SQL safely via MCP → `ExecAndRecoveryAgent` via `execute_sql_tool` (gated by validation).
  6. Evaluate result semantics → `ResultValidator` via `evaluate_result_tool`.
  7. Format final answer → `AnswerAgent` via `finalize_answer_tool`.
- **Supervisor responsibilities** (target):
  - Maintain budgets (`max_supervisor_steps`, `max_llm_calls_total`, `max_no_progress_repeats`).
  - Route based on `progress_signal`, `suggested_next_actions`, and `validation_result.retry_action`.
  - Decide re-discovery vs re-planning vs re-validation vs re-execution.
  - Decide termination and set a coherent `stop_reason` and `final_response` when needed.

## 3. Current-State Issues (from code review)

- **Overgrown agents**:
  - `IntentParserAgent` and `DiscoveryAgent` contain extensive heuristics, internal subgraphs, and LLM prompts (multi-step reasoning, template detection, strategic discovery, enrichment search, fallback business discovery, etc.).
  - `JoinPlanAndSQLAgent` mixes deterministic template planning with large, inline template/heuristic code and fallback SQL generation paths.
  - `ExecAndRecoveryAgent` implements its own LangGraph subgraph for repair/simplification loops, despite the supervisor owning cross-phase control.
- **Responsibility overlap**:
  - Execution agent performs diagnosis, repair, simplification, and even result shaping (e.g., attempting aggregate synthesis when user likely wanted a TOP-K SUM).
  - Result validation and exec recovery both reason about retry behavior; the supervisor also makes retry decisions.
  - Orchestrator still holds pipeline routing helpers and semantic retry/budget logic that overlap with supervisor policy.
- **Legacy / debug code in hot paths**:
  - Numerous “SURGICAL DEBUG” blocks, verbose logging, and experimentation hooks live in core agent nodes and orchestrator nodes.
  - Some agents still reference or guard behavior needed only for earlier phases (e.g., pipeline mode, evaluation/benchmark-specific paths) that add cognitive and runtime overhead.
- **Mixed contracts**:
  - Agents read and write loosely-typed keys on `BaseState`; some keys (e.g., `skip_tables`, `seed_tables`, `discovery_log`, `repair_signatures_seen`) are used across multiple phases without a crisp contract.
  - Capability tools pass through most of the state instead of projecting to a minimal, documented subset.

These issues drive the need for a systematic cleanup that keeps the *behavioral contract* but simplifies implementation and clarifies supervisor/agent separation.

## 4. Target Responsibilities Per Agent / Component

### 4.1 ReactSupervisor & capability tools

- **Supervisor (`ReactSupervisor` in `supervisor.py`)**
  - Owns tool selection and termination.
  - Uses `progress_signal`, `suggested_next_actions`, and `validation_result.retry_action` to:
    - Decide whether to re-run discovery or planning (`rediscover`, `replan`).
    - Decide whether to ask the user for clarification (`clarify`, `ask_user`).
    - Decide when to stop (`stop_reason` set to `success`, `clarify`, `budget_exhausted`, or `fatal_error`).
  - Tracks:
    - `supervisor_step_count` vs `max_supervisor_steps`.
    - `total_llm_calls` vs `max_llm_calls_total`.
    - `no_progress_repeat_count` vs `max_no_progress_repeats`.
  - Delegates **all** domain-specific work to capability tools; never inspects raw data or SQL beyond simple booleans and counts.

- **Capability tools (`tools/capability_tools.py`)**
  - Wrap orchestrator nodes and provide a stable envelope:
    - `tool_output` (agent-specific outputs).
    - `error_info` (normalized via `normalize_error_info_payload`).
    - `progress_signal` in {`positive`, `neutral`, `negative`}.
    - `suggested_next_actions` in a small, enumerated set.
  - Enforce gates that belong near execution:
    - `execute_sql_tool` must refuse to call ExecAndRecovery when SQL has not passed validation (`VALIDATION_GATE_VIOLATION`).
  - Future cleanup target: keep these wrappers thin and side-effect free; any heavy logic belongs in agents or supervisor, not in the wrappers.

### 4.2 IntentParserAgent

- **Current role**: multi-step LangGraph subgraph with LLM analysis, classification, entity extraction, ambiguity handling, template detection, and confidence scoring.
- **Target responsibilities**:
  - Take `{user_input, messages}` and produce a `ParsedIntent` on `state["intent"]` with:
    - `operation` ∈ {`query`, `schema_query`, `health_check`, `clarify`, `interpret_previous`}.
    - `primary_entities`, `metrics`, `filters`, `time_window`.
    - `keywords_for_discovery`, `required_action`, and confidence scores.
  - Avoid cross-agent decisions (no direct discovery, planning, or execution).
  - Keep internal subgraph, but:
    - Limit prompt branching and heuristics to those needed for reliable ERP query classification.
    - Remove or quarantine experimental template detection / derived-metric logic if not critical for current workloads.

### 4.3 DiscoveryAgent

- **Current role**: heavy multi-step discovery agent, with strategic discovery, enrichment searches, seed table handling, view ranking, FK- and role-hint-aware scoring, and extensive logging.
- **Target responsibilities**:
  - Input: `{user_input, intent, seed_tables?, skip_tables?, session_described_tables?}`.
  - Output:
    - `relevant_tables`: up to N (e.g., ≤3) canonical table/view identifiers.
    - `candidate_views`: optional list of view candidates.
    - `schema_snippet`: compact schema text for the selected entities.
    - `column_index`: per-table column names, used downstream by validation and SQL generation.
  - Reasoning scope:
    - Use MCP discovery tools (`search_tables`, `search_views`, `describe_table`, column index tools) and lightweight local heuristics for ranking and role hints.
    - Respect supervisor-provided `skip_tables` and `seed_tables` (e.g., when result validator asks to “try next candidate”).
  - Cleanup focus:
    - Remove aggressive fallbacks and domain-specific hacks that are not clearly supporting typical ERP questions.
    - Quarantine or simplify verbose diagnostic logging and experimental enrichment modes.

### 4.4 JoinPlanAndSQLAgent

- **Current role**: complex join planner and SQL generator with views-first strategy, FK-hints reasoning, role-hints normalization, heuristic fallbacks, and inline SQL template-building fallback code.
- **Target responsibilities**:
  - Input: `{intent, relevant_tables, schema_snippet, discovery_role_hints, column_index}`.
  - Output:
    - `join_plan`: fact table, dimensions, join edges, and any template metadata.
    - `sql_query`: *one* MSSQL (or dialect-normalized) SELECT query aligned with intent.
  - Reasoning scope:
    - Deterministically choose a fact table and dimension tables consistent with `intent` and `DiscoveryRoleHints`.
    - Apply a views-first strategy when high-coverage views exist; otherwise plan joins with bounded depth.
  - Cleanup focus:
    - Consolidate template-building behavior into `MSSQLTemplateBuilder` (or dialect-specific builders) and remove large inline fallback SQL generators where possible.
    - Prune legacy or rarely-used paths that auto-modify user intent (e.g., opportunistic aggregate synthesis beyond what intent/validator specify).

### 4.5 SQLValidatorAgent

- **Current role**: LangGraph validation subgraph using regex-based syntax checks, dialect rules, column/table existence against `column_index`, and LLM-based repair attempts.
- **Target responsibilities**:
  - Input: `{sql_query, join_plan, column_index, relevant_tables, schema_snippet}`.
  - Output:
    - Updated `sql_query` (possibly repaired).
    - `validation_result` with `is_valid`, `error_type`, `error_message`, `tables_used`, `warnings`, and `retry_action` (where applicable).
  - Reasoning scope:
    - Structural and dialect correctness; *not* cross-phase decisions.
  - Cleanup focus:
    - Ensure repair loops are clearly bounded (`max_repair_attempts`) and expose outcomes via `validation_result` rather than implicit control flow.
    - Remove any exploratory MCP calls or non-validation responsibilities.

### 4.6 ExecAndRecoveryAgent

- **Current role**: LangGraph subgraph orchestrating execution, repair-based retry, simplification, and final error preparation; also contains heuristic logic to reshape exploratory TOP queries into aggregates.
- **Target responsibilities**:
  - Input: `{sql_query, validation_result, retry_count?, join_plan?, intent?}`.
  - Output:
    - `exec_result`: normalized `ResponseEnvelope` data (or `None` on failure).
    - Updated `error_info` on failure.
  - Reasoning scope:
    - Execute *one* validated query via MCP, with at most minimal internal retry (e.g., one repair and/or simplification attempt) and clear, bounded behavior.
    - No cross-phase loops or candidate-switching; supervisor + result validator decide whether to “try next candidate” or replan.
  - Cleanup focus:
    - Remove or quarantine behavior that infers new SQL shapes (e.g., opportunistic aggregate or TOP-K synthesis) beyond what `join_plan` and `intent` specify.
    - Simplify internal LangGraph subgraph if possible (could be restructured as a straightforward async function with explicit steps).

### 4.7 ResultValidator

- **Current role**: deterministic checker returning `ValidationResult` with retry suggestions based on row counts, truncation, schema shape, nulls, and suspicious patterns.
- **Target responsibilities**:
  - Input: `{user_input, intent, relevant_tables, sql_query, exec_result}`.
  - Output:
    - `result_validation_result` enriched with:
      - `valid`: overall verdict (`True`/`False` for accepting the result as-is).
      - `issue`, `issue_severity`: classified problem type and severity.
      - `retry_action` in {`accept`, `ask_user`, `try_next_candidate`, `replan_with_aggregation`, `replan_with_filter`}.
      - Optional `clarification_question` and semantic/benchmark metadata.
  - Reasoning scope:
    - Interpreting execution pathologies in a **deterministic**, single-pass way.
    - No direct MCP or LLM usage (pure Python rules over structured inputs).
  - Execution model:
    - Exposed as a capability tool (`evaluate_result_tool`) that the supervisor can call dynamically once an `exec_result` is available.
    - Does not perform any retries, discovery, planning, or execution itself; it only classifies and suggests actions for the supervisor.
  - Cleanup focus:
    - Keep it as a lightweight, pure-Python analyzer.
    - Ensure its contract is narrow and stable so the supervisor can reliably reason over `result_validation_result` and budgets.

### 4.8 AnswerAgent

- **Target responsibilities** (aligned with current behavior):
  - Input: `{user_input, intent, exec_result, schema_snippet, error_info, clarification_question}`.
  - Output: `{final_response}`.
  - All user-facing messaging: success answers, error messages, health-check summaries, clarification questions.
  - No retries or supervisor-like behavior.

## 5. Planned Source-Structure Changes

High-level structural changes (implementation will be phased):

1. **Clarify and document capability-tool contracts**
   - Add or update documentation (docstrings / comments) in `capability_tools.py` and `supervisor.py` to describe expected state fields in and out of each tool.
   - Ensure capability tools limit themselves to:
     - Invoking the corresponding orchestrator node.
     - Producing the shared tool envelope.
     - Enforcing gate(s) very close to that tool’s domain (e.g., validation gate on execute).

2. **Prune pipeline-only routing helpers from orchestrator**
   - Identify methods in `orchestrator.py` explicitly marked as pipeline-only or no longer reachable in supervisor mode (e.g., `_route_validation_result_for_state`, pipeline `build_graph()` export).
   - Either:
     - Move them into a dedicated legacy section and flag for removal, or
     - Remove them outright once tests are updated to use supervisor+tools flows.

3. **Tighten agent contracts**
   - For each agent, formalize its subset of `BaseState` and refactor implementations to honor that subset rather than using ad-hoc keys.
   - Where agents maintain internal subgraphs, ensure inputs/outputs are clearly documented and mapped back to `BaseState` in a minimal way.

4. **Reduce internal looping inside agents**
   - For `ExecAndRecoveryAgent` and `SQLValidatorAgent`, cap internal loops strictly and expose “retry intent” via state rather than re-running upstream phases.
   - For agents like `DiscoveryAgent`, rely on `skip_tables`/`seed_tables` provided by supervisor rather than implementing their own multi-attempt loops.

5. **Quarantine or remove legacy / debug paths**
   - Identify large debug/experimental blocks (e.g., SURGICAL DEBUG logs, experimental enrichment probes) and either:
     - Remove them from hot paths, or
     - Move them under explicit debug flags or into `debugging/` / `docs/redundant/` as reference.

## 6. Data Model / API / Interface Changes

- **BaseState additions/clarifications** (logical, many already exist in practice):
  - Supervisor-related:
    - `supervisor_step_count`, `max_supervisor_steps`.
    - `total_llm_calls`, `max_llm_calls`, `max_llm_calls_total`, `llm_budget_safety_margin`.
    - `no_progress_repeat_count`, `stop_reason`, `supervisor_trace`.
  - Tool/supervisor contract fields:
    - `progress_signal`: `"positive" | "neutral" | "negative"`.
    - `suggested_next_actions`: list of enumerated strings.
    - `last_tool_name`, `last_tool_result` (of type `ToolCallResult`).
  - Agent outputs clarified:
    - `intent` (`ParsedIntent`).
    - `relevant_tables`, `candidate_views`, `schema_snippet`, `column_index`.
    - `join_plan`, `sql_query`.
    - `sql_validation_result`: output of `SQLValidatorAgent` (structural/dialect validation).
    - `result_validation_result`: output of `ResultValidator` (semantic/result QA).
    - (Optional) `validation_result`: flattened view used only where necessary for backwards compatibility, derived from the two specific fields above.
    - `exec_result` (always normalized via `ResponseEnvelope`).
    - `final_response`, `final_answer`, `answer_mode`.
- **External APIs** (FastAPI in `chatbot_ui/langgraph_service.py`) remain stable:
  - The HTTP surface should continue to accept user messages and return `answer`/`final_response` + optional `exec_result`/`error_info` as today.
  - Internal refactoring must preserve these response envelopes.

## 7. Delivery Phases / Milestones

1. **Phase A – Mapping & contracts**
   - Inventory and document current state contracts per agent and capability tool.
   - Add or update docstrings and type hints where missing.

2. **Phase B – Supervisor & capability tool hardening**
   - Ensure supervisor logic and capability tools fully govern cross-agent retries and budgets.
   - Remove any cross-phase loops within agents that conflict with supervisor policy.

3. **Phase C – Agent simplification**
   - Refactor individual agents to the narrower responsibilities described above.
   - Remove or quarantine legacy debug/probing behavior.

4. **Phase D – Orchestrator cleanup**
   - Remove pipeline-only routing code and dead paths from `orchestrator.py` once tests are updated.
   - Align orchestrator helper methods with supervisor-first architecture.

5. **Phase E – Documentation & examples**
   - Update `langgraph_integration/README.md` and relevant ADRs (if necessary) to reflect the simplified supervisor+tools model and clarified agent roles.

## 8. Verification Approach

- **Unit / integration tests**:
  - Reuse and extend:
    - Orchestrator tests (`tests/test_orchestrator_integration.py`, semantic routing tests, etc.).
    - End-to-end pipeline tests (`tests/test_full_pipeline_e2e.py`) to ensure query answering still works against MCP.
  - Add targeted tests per agent where necessary to capture simplified contracts (especially for discovery, join, validation, exec, and result validation).

- **Behavioral checks**:
  - Validate that for representative ERP queries, the supervisor+tools sequence follows the expected path and terminates with a clear `stop_reason` and a sensible `final_response`.
  - Verify that no direct database access occurs from LangGraph agents; all queries must go through MCP tools.

- **Performance / safety checks**:
  - Compare median latency and LLM-call counts before and after cleanup for a small benchmark set of queries.
  - Confirm that validation gating (`execute_sql_tool` and SQLValidator) remains in place and that no unvalidated SQL can reach Exec/Recovery.
