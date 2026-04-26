# ADR-0029: ReAct Supervisor Orchestration Mode
**Status**: Accepted
**Date**: 2025-12-27
**Author**: Julianus Kath


## Status
Accepted — **Superseded by [ADR-0030](0030-simple-sql-agent-architecture.md)** (the supervisor-over-agents design was collapsed into a single ReAct agent with tools; see [`README.md`](README.md)).

## Context

The current LangGraph `QueryOrchestrator` in `langgraph_integration/orchestrator.py` is a fixed,
rule-based pipeline:

- Graph topology and routing are hard-coded (intent → discovery → join_sql → validate_sql →
  exec_recovery → result_validator → answer, plus a few conditional branches).
- Agents are graph nodes, not tools. Routing depends on enums like `retry_action` and bespoke
  helpers such as `_route_validation_result_for_state()`.
- There is no explicit **think → act(tool) → observe → decide-next** loop; once a plan is chosen,
  the system can only repair within that plan.

This leads to brittle failure modes:

- Wrong entity/metric/join paths can propagate all the way to execution and answer.
- Semantic validators and guardrails can detect problems but cannot easily trigger a re-discovery
  or re-planning pass with new constraints.
- Adding more templates and routing heuristics increases complexity instead of robustness.

At the same time, the system already has:

- A shared `BaseState` (budgets, error envelopes, contracts).
- Specialized agents (`IntentParserAgent`, `DiscoveryAgent`, `JoinPlanAndSQLAgent`,
  `SQLValidatorAgent`, `ExecAndRecoveryAgent`, result validator, `AnswerAgent`,
  `InterpretationAgent`).
- A strict validation → execution safety model and MCP-only DB access.

What is missing is a thin supervisory layer that:

- Treats existing agents as **capability tools**.
- Uses LLM reasoning to choose the next tool.
- Runs a bounded ReAct loop on top of the existing safety substrate.

## Decision

Introduce a **ReAct-style supervisor orchestration mode** alongside the existing pipeline:

- Add a `react_supervisor` mode that:
  - Uses a small supervisor loop (`ReactSupervisor` in `langgraph_integration/supervisor.py`).
  - Exposes seven capability tools in `langgraph_integration/tools/capability_tools.py`:
    `interpret_query`, `discover_schema`, `plan_sql`, `validate_sql`, `execute_sql`,
    `evaluate_result`, `finalize_answer`.
  - Runs a bounded think → act(tool) → observe loop until a terminal condition or budget is hit.
- Keep the existing `pipeline` mode intact for compatibility and as a deterministic baseline.
- Control mode selection via:
  - `QueryOrchestrator(orchestration_mode="pipeline" | "react_supervisor")`.
  - `metadata["orchestration_mode"]` on `process_query(...)`.
  - `ORCHESTRATION_MODE` environment variable (default remains `pipeline`).

The supervisor:

- Delegates all schema, relation, and execution access to the existing MCP-backed agents.
- Enforces the same hard validation gate: `execute_sql` capability refuses to run unless
  `validation_result.is_valid is True`.
- Tracks supervisor-specific budgets and a structured `supervisor_trace` for debuggability.

## Alternatives Considered

1. **Keep the fixed pipeline and add more heuristics**
   - Pros: Minimal structural change; reuse existing routing and templates.
   - Cons: Continues to commit early to a single plan; becomes increasingly brittle as more
     special cases are added.
   - Outcome: Rejected – does not address the core need for adaptive control.

2. **Single monolithic “do-everything” agent**
   - Pros: Conceptually simple; one LLM entry point.
   - Cons: Loses the hard safety gates, MCP isolation, and testable agent boundaries that the
     current system depends on.
   - Outcome: Rejected – too risky for production DB access and hard to debug.

3. **Hybrid pipeline with semantic side-channel (no supervisor)**
   - Pros: Reuses existing pipeline, adds semantic feedback loops.
   - Cons: Still driven by hard-coded graph edges; hard to express richer re-discovery/re-planning
     strategies without turning the pipeline into an ad-hoc supervisor.
   - Outcome: Rejected – more complexity without a clear control model.

## Consequences

### Positive

- **Adaptive control**: The supervisor can re-discover, re-plan, or ask for clarification when
  result semantics conflict with the original intent.
- **Bounded autonomy**: Budgets are explicit and enforced:
  - `max_supervisor_steps`.
  - `max_llm_calls_total` (aligned with `BaseState.max_llm_calls`).
  - `max_no_progress_repeats` (based on tool `progress_signal` + fingerprints).
- **Safety preserved**: SQL validation and execution rules are unchanged:
  - `execute_sql` refuses to call `ExecAndRecoveryAgent` unless `validation_result.is_valid`
    is `True`.
  - MCP remains the only DB substrate.
- **Debuggability**: `supervisor_trace` records:
  - `step`, `tool`, `thought_summary`, `tool_inputs_digest`, `observation_summary`,
    `progress_signal`, and a snapshot of budgets.
  - No raw chain-of-thought is persisted or returned.
- **Dual-mode operation**: `pipeline` remains available for regression comparison, fallbacks,
  and existing tests.

### Negative

- **Additional complexity**: There are now two orchestration modes to understand and maintain.
- **New surface area**: Capability tools and supervisor policy need their own tests and
  monitoring.
- **Behavioral drift**: Supervisor mode may diverge from pipeline behavior on edge cases;
  alignment must be validated on representative workloads.

## Rollout

1. **Phase A – Tools & Contracts**
   - Define `BaseState` extensions for supervisor fields and tool envelopes.
   - Implement the seven capability tools as thin wrappers over existing agents.
   - Introduce a hard validation gate inside the `execute_sql` tool.

2. **Phase B – Supervisor Graph**
   - Implement `ReactSupervisor` and `run_supervisor()` with budgets and trace emission.
   - Wire `react_supervisor` into `QueryOrchestrator.process_query()` as an alternate mode.
   - Add tests proving:
     - Supervisor mode runs end-to-end.
     - No SQL executes without passing validation.
     - Budgets map cleanly to `stop_reason` (`success`, `clarify`, `budget_exhausted`,
       `fatal_error`).

3. **Phase C – Cleanup & Simplification**
   - Isolate pipeline-only routing helpers (e.g. `_route_validation_result_for_state`) and mark
     them as candidates for deletion once pipeline mode is retired, per the Ruthless Code Removal
     Policy (Section 9 of the ReAct supervisor SDD requirements).
   - Remove dead or unused helpers from the orchestrator that are not required for:
     - ReAct supervisor mode.
     - The seven capability tools.
     - MCP safety gates.
     - API entrypoints and tests.
   - Update `langgraph_integration/README.md` and the top-level `README.md` to describe
     `pipeline` vs `react_supervisor` and how to configure `orchestration_mode`.

4. **Migration Strategy**

- Short term:
  - Keep `pipeline` as the default (`ORCHESTRATION_MODE=pipeline` or unset).
  - Run `react_supervisor` in controlled environments (e.g., evaluation harnesses, canaries)
    by setting `metadata["orchestration_mode"] = "react_supervisor"` on `process_query`.
  - Compare results against pipeline on a curated query set (including the “top 10 products”
    acceptance query) and monitor supervisor traces.
- Medium term:
  - Gradually flip the default for selected routes or tenants once quality is confirmed.
  - Use `pipeline` as a fallback path for critical failures as needed.
- Long term:
  - Once supervisor mode is stable and superior, deprecate pipeline-only routing helpers and
    remove dead branches following the Ruthless Code Removal Policy.

