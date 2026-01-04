# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: 11f4e804-1212-4025-829f-1d23a960bd4c -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Save the PRD to `{@artifacts_path}/requirements.md`.

### [x] Step: Technical Specification
<!-- chat-id: 9c9550fe-7b70-4156-826c-3921547d7768 -->

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
<!-- chat-id: aa8cbed5-474f-4e2b-82c3-8dcb08614db4 -->

Create a detailed implementation plan based on `{@artifacts_path}/spec.md`.

1. Break down the work into concrete tasks
2. Each task should reference relevant contracts and include verification steps
3. Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function) or too broad (entire feature).

If the feature is trivial and doesn't warrant full specification, update this workflow to remove unnecessary steps and explain the reasoning to the user.

Save to `{@artifacts_path}/plan.md`.

### [x] Step: Phase A – Mapping & Contracts
<!-- chat-id: 6c0f0207-2f45-426e-9d24-6cabe6a6f8c9 -->

Create a precise map of current responsibilities and state contracts for supervisor and agents.

1. For `ReactSupervisor` and capability tools (`langgraph_integration/supervisor.py`, `langgraph_integration/tools/capability_tools.py`), document:
   - Inputs/outputs on `BaseState` (`contracts/state.py`)
   - How `progress_signal`, `suggested_next_actions`, `validation_result` / `result_validation_result`, and budgets (`max_supervisor_steps`, `max_llm_calls_total`, `no_progress_repeat_count`) are produced and consumed.
2. For each core agent:
   - `agents/intent_parser/agent.py`
   - `agents/discovery/agent.py`
   - `agents/join_sql/agent.py`
   - `agents/sql_validator/agent.py`
   - `agents/exec_recovery/agent.py`
   - `agents/result_validator/agent.py`
   - `agents/answer/agent.py`
   capture the minimal intended contract:
   - Required input fields from `BaseState`
   - Output fields it is responsible for setting
   - Any internal loops or subgraphs it owns today.
3. Align these findings with ADRs (especially `adrs/0023-Agent-Orchestration-Architecture.md`, `adrs/0024-Comprehensive-ERP-Assistant-Architecture.md`, `adrs/0029-react-supervisor-orchestration-mode.md`) and update inline docstrings / comments where contracts are unclear.
4. Verification:
   - Run focused tests to confirm current behavior before refactors:
     - `python -m pytest tests/test_orchestrator_integration.py -q`
     - `python -m pytest tests/test_full_pipeline_e2e.py::test_happy_path_query -q` (if present).

### [x] Step: Phase B – Supervisor & Capability Tool Hardening
<!-- chat-id: d76bd409-2088-4599-b4c4-d148be2ccd48 -->

Ensure the supervisor owns global reasoning/loops and capability tools remain thin wrappers around agents.

1. Refine `ReactSupervisor` logic so that:
   - All cross-agent retries (rediscovery, replan, revalidate, re-execute) are driven by supervisor policy, not by agents.
   - Budgets and stop conditions (`max_supervisor_steps`, `max_llm_calls_total`, `max_no_progress_repeats`, `stop_reason`) are consistently enforced.
   - Routing decisions that used to be implicit pipeline assumptions (e.g., treating every `"query"` intent as "always go to discovery") are made explicit and semantic: the supervisor may sometimes skip discovery/SQL entirely and go straight to clarification or answering when a query is clearly out-of-scope for the ERP DB.
2. Tighten capability tools in `tools/capability_tools.py`:
   - Each tool only:
     - Validates preconditions on state (e.g., require validated SQL before execution).
     - Invokes the corresponding agent node or function.
     - Normalizes its result into a small, explicit tool result envelope on `BaseState`.
   - Remove or quarantine debugging / evaluation hooks from capability tools into `debugging/` or `eval/` as appropriate.
3. Ensure supervisor “world view”:
   - Maintains a concise `supervisor_trace` of tool calls and decisions.
   - Uses structured outputs (`progress_signal`, `retry_action`, `suggested_next_actions`) to decide next steps.
   - Plans for future enhancements where supervisor can orchestrate **multiple** complementary plan/validate/execute cycles (N queries) and aggregate their `exec_result` before answering, by extending `BaseState` to track multiple candidate plans/results instead of a single scalar `sql_query`/`exec_result`.
   - Plans to replace hardcoded `thought_summary` / `observation_summary` strings with summaries derived from LLM reasoning or structured signals (while still never exposing raw chain-of-thought outside the system).
4. Verification:
   - Add/adjust unit tests for supervisor and capability tools (e.g., new tests under `tests/test_supervisor_behavior.py` or similar) to cover:
     - Termination when budgets are hit.
     - Correct routing based on `retry_action` from result validation.
   - Re-run orchestrator tests: `python -m pytest tests/test_orchestrator_integration.py -q`.

### [ ] Step: Phase C – Agent Simplification
<!-- chat-id: 803704c6-e567-4f9c-9562-0c786053c2ad -->

Refactor individual agents to be single-pass, narrowly scoped tools aligned with the PRD/spec.

1. `IntentParserAgent`:
   - Remove legacy/duplicate intent heuristics and internal orchestration that are not required for:
     - Operation classification (query/schema_query/health_check/clarify/freeform).
     - Entity/metric/time window extraction relevant to ERP queries.
   - Ensure it sets a well-typed `intent` object on state and avoids downstream routing decisions (no implicit "query → discovery" coupling; all routing goes back through the supervisor).
   - Reduce or remove hardcoded keyword lists where possible and rely more on LLM-derived semantic cues for discovery hints, so that `keywords_for_discovery` are hints rather than hard gates that can block valid but unusual queries.
2. `DiscoveryAgent`:
   - Focus on selecting minimal relevant tables/views and producing compact `schema_snippet` / `column_index` using MCP-side catalog; remove exploratory probing not required for core queries.
   - Rely on supervisor-provided hints (`seed_tables`, `skip_tables`, `forced_tables`) instead of implementing its own multi-attempt loops, and treat `keywords_for_discovery` as soft hints from intent rather than strict filters that can cause false negatives.
3. `JoinPlanAndSQLAgent`:
   - Separate deterministic join-plan building from prompt-heavy SQL generation where possible.
   - Remove pipeline-era fallbacks and dead paths; ensure it always emits `join_plan` + `sql_query` in a consistent struct that the supervisor can call multiple times if needed (e.g., for multi-query strategies in later phases).
4. `SQLValidatorAgent`:
   - Keep syntax/dialect validation and minimal repair; remove attempts to re-discover or re-plan.
   - Normalize its output to a `sql_validation_result` contract used by supervisor/capability tools.
5. `ExecAndRecoveryAgent`:
   - Trim internal LangGraph subgraphs and aggressive recovery loops; retain only bounded, policy-aligned recovery (e.g., at most one simplified retry).
   - Ensure it never runs on unvalidated SQL and always returns a normalized `exec_result`/`error_info`.
6. `ResultValidator`:
   - Keep deterministic checks for row counts, truncation, schema mismatches, and suspicious patterns.
   - Map findings to a small enum-style `retry_action` (`accept`, `ask_user`, `try_next_candidate`, `replan_with_aggregation`, `replan_with_filter`), without duplicating intent/discovery logic.
7. `AnswerAgent`:
   - Constrain to pure presentation: format final responses based on `intent`, `exec_result`, `schema_snippet`, `error_info`, `clarification_question`, and `stop_reason`.
   - Remove retry/decision logic or embedded evaluation behavior.
8. Move or remove large debugging and experimental blocks from agents into:
   - `debugging/` (for debug-only utilities) or
   - `docs/redundant/` / `agents/*/README*.md` for historical reference.
9. Verification:
   - Add/update unit tests per agent (e.g., `tests/test_intent_parser.py`, `tests/test_discovery_agent.py`, etc.) focusing on simplified contracts.
   - Run targeted tests for modified agents plus orchestrator integration tests.

### [ ] Step: Phase D – Orchestrator & Pipeline Cleanup
<!-- chat-id: 45b3dd73-89c2-4e02-884e-8dd148820381 -->

Align `orchestrator.py` with supervisor-first architecture and remove dead pipeline paths.

1. Audit `orchestrator.py` for:
   - Pipeline-only helpers and routing functions no longer used in `react_supervisor` mode, including any legacy LangGraph pipeline graphs.
   - Legacy imports or cross-boundary references (e.g., removed Windows-only rankers).
2. Remove or quarantine unused pipeline-only code:
   - Prefer deleting the legacy pipeline graph and routing helpers entirely once tests confirm supervisor-mode behavior covers required scenarios; keep only minimal compatibility shims (e.g., `invoke_agent`) that are still used by capability tools and external callers.
3. Ensure `QueryOrchestrator.process_query()`:
   - Uses supervisor mode as the primary path (as per spec).
   - Maintains MCP-only DB access via `mcp_client.py` and respects validation/exec gates.
4. Update `langgraph_integration/README.md` to reflect:
   - Supervisor-first orchestration model.
   - Simplified agent responsibilities and contracts.
5. Verification:
   - Re-run full orchestrator and pipeline tests:
     - `python -m pytest tests/test_orchestrator_integration.py -q`
     - `python -m pytest tests/test_full_pipeline_e2e.py -q` (where environment permits).

### [ ] Step: Phase E – Documentation, Observability & Final Verification
<!-- chat-id: feccc78a-daac-44c3-823e-c4c3fa8e7823 -->

Polish documentation, logging, and tests to support long-term maintainability.

1. Update or add documentation:
   - `langgraph_integration/README.md` sections on agents, supervisor, and orchestration modes.
   - High-level docs under `docs/langgraph/` to describe the cleaned-up multi-agent architecture and core query-answering path.
2. Ensure structured logging via `debug_logger`:
   - Keep high-value logs for agent entry/exit, tool calls, and supervisor decisions.
   - Remove or gate verbose debug logs behind configuration flags.
3. Add or refine tests for:
   - Core user journeys (ERP data queries, schema queries, health checks).
   - Failure modes (invalid SQL, timeouts, zero-row results, ambiguous intents) exercising supervisor-driven retries and result validation.
4. Final verification:
   - Run the agreed test suite (at minimum):
     - `python -m pytest tests/test_orchestrator_integration.py -q`
     - `python -m pytest tests/test_full_pipeline_e2e.py -q`
   - Optionally run a small benchmark of representative queries to compare latency and LLM-call counts before vs. after refactor (using existing eval tooling if enabled).
