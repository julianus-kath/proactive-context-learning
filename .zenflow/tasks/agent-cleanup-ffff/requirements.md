# PRD: Agent Cleanup & Responsibility Simplification (LangGraph Integration)

## 1. Problem Statement

The current LangGraph multi-agent stack for answering ERP database questions has grown organically. Individual agents (intent parsing, discovery, join/SQL generation, validation, execution/recovery, result validation, answer formatting) and the ReAct-style `ReactSupervisor` now contain large, complex code paths with overlapping responsibilities and legacy behavior.

This complexity creates several problems:
- Many thousands of lines of agent code with overlapping or redundant logic increase the chance of bugs and regressions.
- Responsibilities between the `ReactSupervisor` and individual agents (especially discovery, join/SQL, exec/recovery, and result validation) are blurred, making failures hard to reason about.
- The primary user-facing goal – accurately answering natural-language questions about the ERP database – is diluted by debugging paths, legacy fallbacks, and evaluation hooks inside production agents.
- The codebase is harder to maintain, extend, and evaluate as a production system.

We need to ruthlessly simplify the agents and clarify the role of the supervisor so that the core query-answering path is lean, predictable, and production-focused.

## 2. Goals & Non‑Goals

### 2.1 Goals

- **G1 – Lean, production-focused agents**  
  Each agent should implement only the minimum logic required for its phase in the query pipeline:
  - Intent parsing
  - Discovery (table/view selection + compact schema context)
  - Join planning & SQL generation
  - SQL validation (syntax + dialect + column/table existence)
  - Safe execution & minimal recovery
  - Result validation (semantic sanity checks)
  - Answer formatting

- **G2 – Clear responsibility split with supervisor**  
  `ReactSupervisor` owns global reasoning and loop control:
  - Maintains a “world view” over user query, state, and available tools.
  - Decides which capability tool (agent) to invoke next, based on progress signals and contracts.
  - Enforces budgets (steps, LLM calls, no-progress repeat limit) and terminal conditions.  
  Individual agents become capability tools with narrow, deterministic contracts and minimal internal orchestration.

- **G3 – Robust core path for database question answering**  
  Optimize for the main path:
  - User asks a data question → intent parsed → discovery identifies minimal relevant tables/views → join/SQL plan generated → SQL validated → query executed safely via MCP → result validated → answer formatted.  
  The system should reliably produce correct or clearly‑flagged answers for typical ERP analytics questions.

- **G4 – Remove legacy / redundant behavior inside agents**  
  Identify and remove or quarantine within `debugging/`, `tests/redundant/`, or dedicated `redundant` folders:
  - Deprecated probing loops (e.g., aggressive fallback probing in older `exec_recovery`).
  - Duplicate or superseded heuristics that conflict with MCP‑side catalog logic.
  - Ad‑hoc evaluation/tracking logic that does not belong in production agent code.

- **G5 – Preserve safety guarantees**  
  While simplifying, maintain:
  - MCP‑only DB access (no direct DB drivers in LangGraph layer).
  - Validation gate before execution (no SQL runs unless `validation_result.is_valid` is true).
  - Row caps, timeouts, and read‑only guarantees in Exec/Recovery.

- **G6 – Make agent behavior observable and testable**  
  Use structured state contracts and logging (via `debug_logger` and `supervisor_trace`) to:
  - Understand the sequence of tools and decisions for a given query.
  - Write focused tests per agent and for supervisor+tools end‑to‑end.

### 2.2 Non‑Goals

- NG1: Redesigning MCP server or database schema; the focus is on LangGraph integration and agents.  
- NG2: Replacing LangGraph with another orchestration framework.  
- NG3: Building new user‑facing features in the UI; scope is internal behavior and quality.  
- NG4: Changing the fundamental DB safety model (bounded queries, read‑only MCP tools).  
- NG5: Removing the legacy `pipeline` mode immediately; it may remain as a baseline until supervisor mode is fully validated. It should have already been removed, however legeacy remnants may remain and should be noted.

## 3. Users & Use Cases

### 3.1 Primary Users

- **Business users / analysts** using the ERP chatbot UI to ask questions such as:
  - “How many customers did we have in 2023 vs 2022?”
  - “Show top 10 products by revenue last quarter.”
  - “Which customers are overdue on payments?”

- **Developers / operators** running the LangGraph service and MCP server in production, who need:
  - Predictable agent behavior.
  - Clear logs and traces to debug incorrect answers.
  - Confidence that the system won’t hang or spam the DB with unsafe queries.

### 3.2 Core Use Cases

- **UC1 – Data query answering (happy path)**  
  1. User asks a natural‑language data question.  
  2. Supervisor invokes intent parser to classify operation as data query, extract entities/metrics/filters.  
  3. Supervisor invokes discovery to find best tables/views and compact schema snippet.  
  4. Supervisor invokes join/SQL agent to build a join plan and SQL query.  
  5. Supervisor invokes SQL validator to ensure syntax/dialect correctness and column/table validity; repairs if safe.  
  6. Supervisor invokes Exec/Recovery to run the query via MCP and capture result or error in a standard envelope.  
  7. Supervisor invokes result validator to check row counts, truncation, schema, and suspicious patterns.  
  8. Supervisor invokes answer agent to format a clear answer, including clarification messages if needed.

- **UC2 – Schema / catalog queries**  
  - User asks “What tables contain invoices?” or “Explain the customer schema.”  
  - Intent classified as `schema_query`; supervisor may call discovery and then answer agent directly (no SQL execution), reusing schema snippets.

- **UC3 – Health checks**  
  - User asks “Is the system healthy?”  
  - Intent classified as `health_check`; supervisor routes directly to answer agent with MCP/health information, without touching heavy agents.

- **UC4 – Clarification flows**  
  - For ambiguous or underspecified queries, intent parser and/or result validator request clarification.  
  - Supervisor updates state (`stop_reason = "clarify"`, sets appropriate intent, and routes to answer agent to generate a user-facing clarification question.

- **UC5 – Error handling & recovery**  
  - For SQL or execution errors, supervisor uses validator and exec/recovery outputs (`validation_result`, `exec_result`, `error_info`, `retry_action`) to decide whether to replan, rediscover, or ask the user for help; agent internals do minimal retries and never loop unboundedly.

## 4. Current vs Target Responsibilities

### 4.1 Supervisor (`ReactSupervisor` and capability tools)

**Current state (from `supervisor.py` & ADR-0029):**
- Maintains `supervisor_trace`, step counters, and LLM budget checks.
- Selects next tool based on `intent.operation`, `progress_signal`, `suggested_next_actions`, and `validation_result.retry_action`.
- Treats agents as capability tools: `interpret_query`, `discover_schema`, `plan_sql`, `validate_sql`, `execute_sql`, `evaluate_result`, `finalize_answer`.
- Has some implicit assumptions about agent behavior (e.g., discovery populates `relevant_tables`, validation populates `validation_result`, exec sets `exec_result`).

**Target responsibilities:**
- Be the **project manager / world model** for the query:
  - Own high-level understanding of user intent, discovered tables, SQL, execution outcomes, and retry history.
  - Decide when to loop back (rediscover, replan, revalidate, re-execute) vs. when to stop.
- Encapsulate **all cross-agent control logic**:
  - Agents should not invoke each other or implicitly loop; they act once per supervisor call.
  - Result evaluation / semantic retry decisions should happen via supervisor policy using structured outputs (`retry_action`, `progress_signal`, `suggested_next_actions`).
- Maintain bounded, deterministic loops:
  - Respect budgets; stop with clear `stop_reason` (`success`, `clarify`, `budget_exhausted`, `fatal_error`).
- Provide concise, privacy-safe traces for debugging and evaluation.

### 4.2 Intent Parser Agent

**Current state:**
- Large LangGraph subgraph with multiple nodes (`analyze_query`, `classify_operation`, `extract_entities`, `validate_intent`, `handle_ambiguity`, `refine_intent`).
- Heavy use of LLM prompts for classification, entity extraction, templates, derived metrics, etc.
- Contains its own ambiguity handling and clarification logic.

**Target responsibilities:**
- Provide a **single, well-typed `intent` object**:
  - `operation` in {`query`, `schema_query`, `health_check`, `clarify`}.  
  - Core fields: `primary_entities`, `metrics`, `filters`, `time_window`, `keywords_for_discovery`, `required_action`, `confidence`, `needs_clarification`.
- Avoid owning clarification loops:
  - Move clarification decision & messaging to supervisor + answer agent, based on `needs_clarification` and confidence thresholds.
- Minimize internal subgraph complexity where possible (e.g., collapse overly fine-grained steps that do not expose distinct outputs).

### 4.3 Discovery Agent

**Current state:**
- Large subgraph with search, ranking, limiting, describing tables, optional date exploration, column index fetching, refinement handling (`forced_tables`, `seed_tables`), and detailed role hints.
- Contains some debugging logs and critical markers.

**Target responsibilities:**
- Given `user_input` + `intent`, produce:
  - `relevant_tables` (small list of table/view identifiers with basic metadata).
  - `schema_snippet` for planning/answering.
  - Optional `discovery_role_hints` / `column_index` in a compact, documented form.
- Avoid cross-cutting recovery logic:
  - No infinite refinement loops; run once per supervisor call.
  - Surface structured reasons when no good tables are found (e.g., `error_info.type = NO_MATCHING_TABLES"`).
- Defer decisions like “try next candidate vs. clarify vs. relax filters” to the supervisor / result validator using explicit fields (`candidate_views`, role hints, counts).

### 4.4 JoinPlanAndSQL Agent

**Current state:**
- Builds join plans from discovery role hints and FK relations, with views-first strategy and multiple configuration knobs.
- Includes some validation and MSSQL-specific checks, plus templating via `MSSQLTemplateBuilder`.

**Target responsibilities:**
- Accept only the discovery output and intent as inputs, and produce:
  - `join_plan` (fact + dimensions + joins + filters + time window).
  - `sql_query` string (single candidate at a time).
- Keep only minimal validation needed to construct a coherent plan; rely on `SQLValidatorAgent` for full correctness checks and repairs.
- Avoid any internal retry loops; if no valid plan can be constructed, populate `error_info` clearly and let the supervisor decide next actions.

### 4.5 SQL Validator Agent

**Current state:**
- Manages its own internal validation graph with repair loops, AST/dialect checks, and schema validation against `column_index`.

**Target responsibilities:**
- Be the **single gatekeeper** for SQL correctness:
  - Validate syntax, dialect, and table/column existence.
  - Perform a bounded number of repair attempts using `SQL_REPAIR_PROMPT` and MCP schema inspection.
- Provide structured `validation_result`:
  - `is_valid` flag.
  - `error_type`, `error_message`.
  - `warnings`, `suggestions`.
  - Optional `retry_action` hints (e.g., `replan`, `rediscover`).
- Expose a simple call surface as a capability tool; avoid leaking internal graph complexity to the supervisor.

### 4.6 ExecAndRecovery Agent

**Current state:**
- Executes via MCP `query_bounded`, with its own LangGraph subgraph for execution, repair, retry, simplification, and error preparation.
- Contains retry logic and SQL repair simplification hooks.

**Target responsibilities:**
- Execute a **single, validated SQL query** via MCP with:
  - Dialect-aware normalization.
  - Row caps, timeouts, and sensitive-column handling.
- Provide a clear `exec_result` envelope (plus `error_info` when applicable).  
- Implement at most minimal, bounded recovery (e.g., one retry with a repaired or simplified query) in alignment with supervisor policy.
- Never attempt exploratory probing or catalog scanning; defer such strategies to discovery/validator + supervisor combination.

### 4.7 Result Validator Agent

**Current state:**
- Deterministic checker (no LLM) performing row-count, truncation, schema, nulls, and suspicious-pattern checks, returning a `ValidationResult` with `retry_action`.

**Target responsibilities:**
- Remain a lightweight, deterministic semantic checker for execution results.  
- Focus on mapping observed result pathologies to actionable `retry_action` values:
  - `accept`, `ask_user`, `try_next_candidate`, `replan_with_aggregation`, `replan_with_filter`.
- Avoid duplicating intent parsing or discovery logic; operate solely on contracts (`intent`, `discovery_results`, `sql_query`, `exec_result`).
- Optionally evolve into a pure library function called by the supervisor/tool wrapper rather than a heavyweight agent.

### 4.8 Answer Agent

**Current state:**
- Formats answers using LLM prompts for result, schema, error, clarification, health responses, and may embed small result previews.

**Target responsibilities:**
- Take the final state (`intent`, `exec_result`, `schema_snippet`, `error_info`, `clarification_question`) and produce a user-facing string `final_response`.
- Own **all user-facing messaging** (success answers, error messages, clarification prompts, health responses), based on supervisor-selected operation/stop_reason.
- Avoid business logic or retry decisions; remain a pure presentation layer.

## 5. Functional Requirements

- **FR1 – Single-pass agents**: Each capability tool (agent) must run in a single, bounded pass; any looping across phases (e.g., rediscover → replan → revalidate) is driven by `ReactSupervisor`.
- **FR2 – Explicit contracts per agent**: For each agent, define input and output fields on `BaseState`, and refactor code to conform to those contracts (no hidden dependencies on misc keys).
- **FR3 – Supervisor-driven retries**: Retries across agents must be governed by supervisor policy using structured outputs (e.g., `retry_action`, `progress_signal`, suggestion lists).
- **FR4 – Reduced prompt & template surface**: Where prompts are overly rich or redundant, collapse to the minimal set necessary to support high-quality answers for ERP queries.
- **FR5 – No legacy probing loops**: Remove or quarantine obsolete probing / exploration loops that are not necessary for the core answering path.
- **FR6 – Preservation of safe execution**: Ensure that validation always gates execution and that `ExecAndRecoveryAgent` does not run on unvalidated SQL.
- **FR7 – Observability**: Maintain or improve structured logs (`debug_logger`, `supervisor_trace`) without verbose, low-value logging in production paths.

## 6. Non‑Functional Requirements

- **NFR1 – Performance**: End-to-end latency for typical queries should not regress, and should ideally improve due to reduced agent complexity and fewer unnecessary retries.
- **NFR2 – Reliability**: No hanging LangGraph runs; all queries should terminate with a clear `stop_reason` and response.
- **NFR3 – Maintainability**: Agents should be small enough and modular enough that new contributors can understand and modify them without reading thousands of lines.
- **NFR4 – Testability**: Each agent and the supervisor+tools flow should have clear unit/integration tests based on the simplified contracts.

## 7. Open Questions & Clarifications Needed

- **Q1 – ResultValidator vs. supervisor**: Should `ResultValidator` remain a separate agent/tool, or should its logic be further simplified and partly absorbed into supervisor policy (while keeping deterministic checks)?
- **Q2 – Extent of internal subgraphs**: For agents like `IntentParserAgent` and `ExecAndRecoveryAgent`, how much internal LangGraph structure do we want to keep versus flatten into simpler functions?
- **Q3 – Evaluation hooks**: Which evaluation/tracing behaviors, if any, must remain in production agent code vs. being moved entirely into the `eval/` service and clients?
- **Q4 – Dialect scope**: Is MSSQL still the primary execution dialect, or should agents be cleaned up to be fully dialect-agnostic with a pluggable adapter (beyond the existing normalizer)?
- **Q5 – Pipeline mode deprecation timeline**: When is it acceptable to remove `pipeline`-only routing helpers and tests, so we can aggressively prune orchestrator complexity?

