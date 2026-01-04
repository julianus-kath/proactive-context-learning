# LangGraph ERP Assistant – Multi-Agent Architecture (Supervisor-First)

This document summarizes the production architecture of the ERP
assistant implemented in `langgraph_integration/`. It focuses on the
core query-answering path (user → SQL → answer) and the
responsibilities of the React-style supervisor vs. the individual
agents.

## High-Level Overview

- **Goal**: Turn natural-language ERP questions into safe, validated
  SQL queries and human-friendly answers using a small set of
  focused agents.
- **Orchestrator**: `QueryOrchestrator` prepares `BaseState` and
  delegates control to `ReactSupervisor` (`langgraph_integration/supervisor.py`).
- **World State**: All agents read and write a shared `BaseState`
  (intent, catalog context, candidate tables, SQL, validation/exec
  results, final answer, error_info, budgets).
- **Execution Strategy**: A supervisor-first ReAct loop that
  alternates between reasoning (LLM + result validation) and acting
  (capability tools/agents) under explicit budget limits.

## Supervisor Responsibilities

`ReactSupervisor` is the project manager for the whole flow:

- Maintains a **global view** of the user query, current intent,
  discovered schema, candidate SQL, validation results, execution
  results, and retry budgets.
- Invokes agents via **capability tools**:
  - `interpret_query` (intent + semantics)
  - `discover_schema` (table/view selection)
  - `plan_sql` (join plan + SQL)
  - `validate_sql` (syntax/dialect checks + repair)
  - `execute_sql` (bounded execution via MCP)
  - `evaluate_result` (result validation + retry_action)
  - `finalize_answer` (user-facing answer)
- Owns all **cross-agent loops**:
  - rediscovery or re-planning when validation fails,
  - re-execution on transient errors,
  - escalation to clarification or stop when budgets are exhausted.
- Enforces **budgets and stop conditions** on each run:
  - `max_supervisor_steps`
  - `max_llm_calls_total`
  - `max_no_progress_repeats`
  - normalizes `stop_reason` and maintains a `supervisor_trace`.

Agents are deliberately **single-pass**: they should not contain their
own multi-step orchestration or internal LangGraph subgraphs beyond
bounded, local retries.

## Agent Responsibilities (Per Phase)

Each agent is responsible for one phase, with minimal surface area:

- **IntentParserAgent (`agents/intent_parser/agent.py`)**
  - Input: `user_input`, `messages`, optional prior context.
  - Output: well-typed `intent` object with:
    - `operation`: `query`, `schema_query`, `health_check`,
      `clarify`, or `freeform`.
    - domain entities/metrics, filters, time windows, and
      keywords for discovery.
  - Does **not** route or loop; it simply describes what the user
    wants in structured form.

- **DiscoveryAgent (`agents/discovery/agent.py`)**
  - Input: `intent` and MCP-backed catalog.
  - Output: `candidate_views`, `relevant_tables`, and a compact
    `schema_snippet` / `column_index`.
  - Focuses on selecting a small, relevant subset of tables/views
    using Scout mode; avoids long exploratory probing loops.

- **JoinPlanAndSQLAgent (`agents/join_sql/agent.py`)**
  - Input: `intent`, `relevant_tables`, `schema_snippet`.
  - Output: `join_plan` and `sql_query` in a consistent structure.
  - Separates deterministic join-planning from LLM-driven SQL
    text generation where possible and adheres to the target DB
    dialect.

- **SQLValidatorAgent (`agents/sql_validator/agent.py`)**
  - Input: `sql_query`, `column_index`, `relevant_tables`.
  - Output: `validation_result` (normalized contract) and updated
    `sql_query` if repairs are applied.
  - Handles syntax/dialect checks and small repairs; does **not**
    re-discover tables or re-plan joins.

- **ExecAndRecoveryAgent (`agents/exec_recovery/agent.py`)**
  - Input: **validated** `sql_query`, runtime limits (row caps,
    timeouts).
  - Output: `exec_result` (columns + rows + execution metadata) or
    structured `error_info`.
  - Executes queries via the MCP DB tools and performs only
    bounded, policy-aligned recovery (e.g., a single simplified
    retry), never infinite probing loops.

- **ResultValidatorAgent (`agents/result_validator/agent.py`)**
  - Input: `intent`, `sql_query`, `exec_result`, `schema_snippet`.
  - Output: `validation_result` / `result_validation_result` with a
    concise `retry_action` enum:
    - `accept`
    - `ask_user`
    - `try_next_candidate`
    - `replan_with_aggregation`
    - `replan_with_filter`
  - Performs deterministic checks (row counts, truncation, schema
    mismatches, suspicious patterns) and leaves orchestration
    decisions to the supervisor.

- **AnswerAgent (`agents/answer/agent.py`)**
  - Input: `intent`, `exec_result`, `schema_snippet`, `error_info`,
    `clarification_question`, `stop_reason`.
  - Output: `final_response` suitable for display in the UI.
  - Pure presentation; does **not** initiate retries or call other
    agents.

## Core Query-Answering Path

For a typical data query, the high-level path is:

1. **Request Entry**
   - Fast-path classification via `_simple_intent_parser` for obvious
     health/schema queries.
   - Full semantic parsing via `IntentParserAgent` when needed.
2. **Schema Discovery**
   - `DiscoveryAgent` uses Scout-mode tools on the MCP server to
     select a small set of relevant views/tables, preferring curated
     business views.
3. **Join Planning & SQL Generation**
   - `JoinPlanAndSQLAgent` constructs a join plan and MSSQL/Postgres
     SQL that respects configured join and row limits.
4. **Validation**
   - `SQLValidatorAgent` checks syntax, dialect, and basic schema
     consistency, optionally repairing the query.
5. **Execution**
   - `ExecAndRecoveryAgent` runs the validated SQL via MCP with
     strict row caps and timeouts.
6. **Result Validation**
   - `ResultValidatorAgent` inspects row counts and schema to decide
     whether to accept, retry with different candidates, or re-plan.
7. **Answer Formatting**
   - `AnswerAgent` formats the final response, including data
     provenance and caveats where appropriate.

Throughout this flow, the supervisor:

- tracks budgets and stop reasons,
- records a `supervisor_trace` for observability,
- and uses `progress_signal` / `retry_action` / `suggested_next_actions`
  to choose the next tool.

## Non-Query Operations

The same supervisor + agents infrastructure also supports:

- **Schema queries** – discovery and answer agents are used to list
  tables, columns, or schemas rather than executing arbitrary SQL.
- **Health checks** – routed to lightweight checks over MCP and
  internal readiness, returning a concise status answer.
- **Clarifications / freeform chat** – modeled as intents where
  the answer agent can respond directly without touching the DB.

These paths share the same `BaseState` and supervisor infrastructure
but use a subset of the agents described above.

