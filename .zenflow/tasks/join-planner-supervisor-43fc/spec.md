# Technical Specification – Join Planner & Supervisor

## 1. Scope & Difficulty

- **Task type:** Refactor & behavior change across multiple agents.
- **Difficulty:** **Hard**
  - Touches core query-planning path (join planner, SQL generator, validator, result validator, supervisor).
  - Requires careful coordination of contracts (`BaseState`, `JoinPlan`, `validation_result`, `error_info`).
  - Must preserve existing behaviors and tests while tightening semantics.

Goal: Make `JoinPlanAndSQLAgent` either (a) produce a semantically aligned join plan + SQL for the user’s analytic intent, or (b) clearly signal that it cannot do so with the current schema, so that the **ReactSupervisor** can intelligently re-plan (rediscover schema, try alternative fact tables, or ask the user), using LLM-driven routing at runtime rather than hard‑coded Python decision trees.

---

## 2. Current Architecture & Behavior

Section 2 describes the **status quo** of the system today (how join planning, SQL generation, validation, and supervision currently work). Sections 3–6 describe the **desired end state** and implementation approach for this task.

### 2.1 Core Components

- `langgraph_integration/agents/join_sql/agent.py`
  - `JoinPlanAndSQLAgent.build_subgraph()` builds a 5‑node LangGraph:
    - `_check_view_coverage_node` – views‑first shortcut using discovery candidates and `role_coverage`.
    - `_fetch_relations_node` – calls MCP `list_relations` for FK hints.
    - `_build_join_plan_node` – builds a `JoinPlan` from:
      - `discovery_role_hints` (`DiscoveryRoleHints` with `fact_candidates` + `dimensions`).
      - FK hints (`fk_hints`) and `relevant_tables`.
      - Intent (`ParsedIntent`): `required_action`, metrics, filters, time_window, entities.
    - `_generate_sql_node` – generates SQL from `join_plan` + `intent`:
      - Uses analytic routing:
        - `intent.analytic_template` → `_generate_count_entity_sql`, `_generate_top_k_by_metric_sql`, `_generate_period_comparison_sql`, etc.
        - `intent.required_action` in template set (`topk_sum_by_customer`, `sum_with_period`, `sum_by_product`, `growth_analysis`, `comparative_analysis`, `low_stock`) → `MSSQLTemplateBuilder`.
        - Other `required_action` values (e.g. `trend_series`, `department_productivity`) → specialised helpers (`_generate_trend_series_sql`, `_generate_topk_customer_revenue_sql`, etc.).
      - Fallback “legacy logic” for unrecognised actions:
        - Heuristics for aggregation (`has_aggregation`, `wants_sum`, `top_k` parsing, time windows).
        - Column probing via MCP (`_probe_columns`) to infer date/metric columns.
        - Generates:
          - Either aggregate SQL via `_generate_aggregation_sql_with_hints` / `_generate_topk_sum_sql`, or
          - Simple `SELECT TOP {row_limit} * FROM <primary_table>` (view or join strategy) with optional joins and filters.
      - Minimal structural validation (starts with `SELECT`, has `FROM`, non‑empty).
      - On failure, sets `error_info` with `type="SQL_GEN_ERROR"`.
    - `_validate_sql_node` – **local** MSSQL validation:
      - Checks SELECT/CTE shape, `FROM`, basic completeness, balanced quotes/parentheses, forbids DML.
      - **Phase 11:** Validates table names against discovered tables (`relevant_tables` / `candidate_views`).
      - On failure, sets `error_info` with `type="SQL_VALIDATION_ERROR"` and `replan_needed=True`.
  - Helper methods:
    - `_select_fact_candidate` – chooses a fact candidate from `DiscoveryRoleHints.fact_candidates` based on metric scores, estimated_rows, required dimension roles, entities, and keywords.
      - Still biased toward “large, metric‑like” tables (e.g., `AbrechnungenDetail`).
    - `_select_dimension`, `_find_fk_condition`, `_synthesize_join_condition`, `_match_entity_columns`, `_canonical_entity`, `_ensure_columns_probed_for_join_plan`, plus many template-specific helpers.
  - `join_plan` structure follows `JoinPlan` TypedDict in `contracts/state.py`.

- `langgraph_integration/templates/mssql_template_builder.py`
  - Deterministic templates for analytic actions, **currently MSSQL-biased**:
    - `sum_with_period`, `sum_by_customer`, `topk_sum_by_customer`, `sum_by_product`, `topk_sum_by_product`, `low_stock`, `growth_analysis`, `comparative_analysis`.
  - Consumes `join_plan` + `intent`, requires:
    - Fact table (`fact_table`/`primary_table`).
    - Metric candidates / date columns.
    - Dimension definitions (e.g., `dimensions["customer"]` with id/label columns and join conditions).
  - Raises `TemplateBuildError` on missing pieces (no fact, dimension, metric, date, threshold).
  - Today assumes MSSQL dialect (TOP, DATEADD, square brackets). The broader system already uses `DB_DIALECT` (e.g. in `_probe_columns`) to distinguish Postgres vs MSSQL; future changes in this task must respect `DB_DIALECT` and avoid introducing new hard-coded MSSQL-only syntax.

- `langgraph_integration/agents/sql_validator/agent.py`
  - `SQLValidatorAgent`:
    - Graph: validate → (repair loop) → final_validation.
    - `_validate_sql_comprehensive`:
      - Basic syntax (`_validate_sql_syntax`).
      - MSSQL dialect (`_validate_mssql_dialect`), which currently enforces MSSQL-specific rules (e.g. forbidding `LIMIT`, requiring `TOP`) without consulting `DB_DIALECT`.
      - Table/column existence (`_validate_table_column_existence`), populating `tables_used`, `tables_used_base`, `cte_names`.
      - Lightweight semantic checks (`_validate_sql_semantics`) but not full intent‑level correctness.
    - Repairs invalid SQL via LLM using `SQL_REPAIR_PROMPT`.

- `langgraph_integration/agents/result_validator/agent.py`
  - `ResultValidator` (deterministic, non‑LLM):
    - Validates `exec_result` vs `intent`:
      - Zero rows, too many rows/truncation, all NULLs, schema mismatch, suspicious patterns.
      - Produces `ValidationResult` with `valid`, `issue`, `retry_action` (e.g. `accept`, `replan_with_aggregation`, `try_next_candidate`).
    - Has hooks for semantic contracts (`QueryContract`) but focuses mainly on row‑count/shape, not analytic template correctness.

- `langgraph_integration/tools/capability_tools.py`
  - Wraps orchestrator agents as capability tools:
    - `plan_sql_tool` → `JoinPlanAndSQLAgent`.
    - `validate_sql_tool` → `SQLValidatorAgent`.
    - `evaluate_result_tool` → `ResultValidator`.
  - Attaches `tool_output`, `error_info`, `progress_signal`, `suggested_next_actions` via `_derive_progress_and_actions`.
    - For `plan_sql`: currently treats any non‑empty `sql_query` as **positive** progress and suggests `["replan", "stop"]` even if SQL is simplistic or semantically wrong.

- `langgraph_integration/supervisor.py`
  - `ReactSupervisor` drives the loop over capability tools.
  - Uses:
    - `_select_initial_tool` – simple deterministic routing based on presence of intent, tables, SQL, validation, exec_result.
    - `_llm_select_next_tool` – LLM‑based tool selection using a compact `summary`:
      - Includes intent summary, `have_relevant_tables`, `have_sql_query`, simple `validation_result.is_valid` / `retry_action`, `exec_result.ok` / `row_count`, `error_info.type`, last tool, `progress_signal`, `suggested_next_actions`, budgets.
    - `_select_next_tool` – heuristic fallback when LLM selection fails or must be overridden (e.g. always run `evaluate_result` after `execute_sql`).
  - Enforces budgets (`max_supervisor_steps`, LLM budgets, no‑progress repeats) and normalizes `stop_reason`.
  - Today the supervisor LLM only selects the **next tool name**; it does not send structured, tool-specific instructions (e.g. hints for `plan_sql` / `_generate_sql_node`), and Python fallback logic does some routing based on simple heuristics.

- `langgraph_integration/orchestrator.py`
  - Wires agents into `QueryOrchestrator` and exposes `invoke_agent("join_sql", state)` for `plan_sql_tool`.

### 2.2 Current Pain Points (Per Requirements)

- Fact table & dimension choice:
  - `_select_fact_candidate` heavily favored by `metric_candidates` and `estimated_rows`, not by semantic alignment with `intent.analytic_template` and entities.
  - “Sales‑like” tables with many numeric columns and rows are frequently selected even when the user asks about entities like customers or products.
  - Role hints and heuristics are not surfaced as **confidence/quality** signals; they just drive a single best guess.

- SQL generation:
  - For analytic patterns outside the known templates or when templates fail:
    - `_generate_sql_node` falls back to heuristic builders.
    - These often produce very simple SQL:
      - `SELECT TOP {row_limit} * FROM <fact>` or
      - `SELECT SUM(<some_amount>) FROM <fact>` without grouping by the requested dimension.
  - Minimal validation only checks syntax/structure, not analytic/template alignment (e.g. COUNT_ENTITY must group by entity).

- Validation & result checking:
  - `SQLValidatorAgent` focuses on:
    - syntactic correctness,
    - MSSQL dialect consistency, and
    - table/column existence.
  - It does **not** verify whether the SQL satisfies the analytic template or matches expected required tables/joins (outside benchmark mode).
  - `ResultValidator` detects gross issues (zero rows, truncation, all NULLs) but not semantic misalignment such as:
    - Missing GROUP BY for count queries over entities.
    - Wrong fact table chosen even if rows are returned.

- Supervisor world‑view:
  - `plan_sql_tool` currently signals success as soon as `sql_query` is non‑empty, regardless of join plan quality or template fit.
  - `_llm_select_next_tool` only sees coarse signals (`have_sql_query`, `validation_result.is_valid`, `error_info_type`) and generic `suggested_next_actions`.
  - There is no explicit notion of:
    - “high‑quality analytic plan vs exploratory best‑guess”.
    - “missing required dimensions/tables for the analytic template”.
    - “the join planner declined to generate a plan with current tables”.
  - As a result, the supervisor tends to treat any syntactically valid SQL as good enough, proceeds to execution, and only re‑plans on obvious execution/result issues.

---

## 3. Desired Behavior

1. **Join planner should be honest about uncertainty instead of fabricating answers:**
   - For analytic intents (e.g. COUNT_ENTITY, TOP_K_BY_METRIC, SUM_WITH_PERIOD, GROWTH/COMPARATIVE analysis):
     - Either:
       - Produce a **structured join plan** and matching SQL:
         - Clear fact table.
         - Explicit dimensions and join edges for required entities.
         - Filters/time windows wired into WHERE/GROUP BY as per template.
       - Or:
         - Decline to produce a plan:
           - Missing fact table or required dimension(s).
           - Incomplete role hints for the requested analytic template.
           - Templates cannot be built by `MSSQLTemplateBuilder`.
         - Attach structured `error_info` and leave `sql_query` empty so the supervisor knows planning failed and can decide what to do next.
   - For vague/detail queries (“show sample rows from table X”), simple `SELECT TOP ... *` remains acceptable, but should be clearly marked as **exploratory** in the join plan metadata.

2. **World‑view signals and instructions between supervisor and planner:**
   - Join planner (and optionally validator/result validator) should emit:
     - Plan quality / status (e.g. `ok`, `exploratory`, `incomplete`, `unsupported`).
     - Reasons / issues (missing dimension, unsupported analytic pattern, ambiguous fact choice).
     - Confidence hints when multiple fact candidates exist.
   - These signals must be visible to the LLM supervisor via:
     - `tool_output` envelope (e.g. `tool_output.join_plan.plan_status`).
     - `error_info.type` and structured details.
     - Summaries fed into `_llm_select_next_tool` (without leaking raw CoT).

   - The supervisor should also be able to send **explicit planning/generation instructions** to the join agent when it chooses `plan_sql` next, for example:
     - “Use a different fact table candidate if available.”
     - “Focus discovery on customer-related tables, then re-plan.”
     - “Treat this as an exploratory sample, not an aggregate.”
   - These instructions should be passed through structured `BaseState` fields (e.g. `plan_sql_instructions` / `sql_generation_hints`), not as hidden chain-of-thought, and consumed by `_build_join_plan_node` / `_generate_sql_node` to adjust behavior for that invocation.

3. **Intelligent, LLM‑driven replanning (minimal hard-coded heuristics):**
   - Supervisor decisions (discover vs plan vs validate vs execute vs ask user) should be driven primarily by the LLM, based on:
     - Plan quality/status and error types from `plan_sql`.
     - Retry actions from `ResultValidator` (`try_next_candidate`, `replan_with_aggregation`, `ask_user`).
     - Validation failures that indicate discovery mismatch (`missing_table`, `SQL_VALIDATION_ERROR` with unknown tables).
   - Python heuristics (`_select_initial_tool`, `_select_next_tool`) should remain **minimal guardrails** and fallbacks:
     - Ensure required ordering (e.g. don’t execute before validation; always evaluate results after execution).
     - Avoid infinite loops and respect budgets.
     - **Not** encode complex join‑planning logic, dataset‑specific behavior, or “clever” fallbacks—those should come from the LLM given a rich, structured summary of the state.

---

## 4. Implementation Approach

### 4.1 Extend JoinPlan & Planner Metadata

**Data model extensions (non‑breaking):**

- Update `langgraph_integration/contracts/state.py` `JoinPlan` TypedDict documentation to include optional metadata fields (all remain optional; `total=False`):
  - `plan_status: Literal["ok", "exploratory", "incomplete", "unsupported"]`
    - `"ok"` – planner believes the plan can answer the intent with current schema.
    - `"exploratory"` – planner is intentionally returning a sample/detail query, not a full analytic answer.
    - `"incomplete"` – required components (fact, dimensions, time window, etc.) are missing or ambiguous.
    - `"unsupported"` – the requested analytic pattern is not supported by current templates/logic.
  - `plan_confidence: Optional[float]`
    - Value in `[0.0, 1.0]` representing a best‑effort confidence in plan correctness.
    - `None` when the planner cannot meaningfully score confidence (e.g. exploratory mode).
  - `plan_issues: List[JoinPlanIssue]`
    - Where `JoinPlanIssue` is a small TypedDict (to be added alongside `JoinPlan`) with fields like:
      - `type: str` – machine-parseable code (e.g. `"FACT_NOT_FOUND"`, `"MISSING_DIMENSION"`, `"MISSING_JOIN_CONDITION"`, `"EXPLORATORY_PLAN"`).
      - `severity: Literal["info", "warning", "error"]` – coarse severity.
      - `message: Optional[str]` – short human‑readable description (for logging / debugging).
      - `details: Optional[Dict[str, Any]]` – structured context (e.g. `{"role": "customer"}`).
  - `template: Optional[str]`
    - Template key used by deterministic builders or templates, e.g. `"sum_with_period"`, `"topk_sum_by_customer"`, `"growth_analysis"`, etc.

**Planner changes:**

- In `_build_join_plan_node`:
  - Start with a default `join_plan`:
    - `plan_status="ok"` and `plan_confidence` derived from:
      - Whether a fact candidate exists.
      - Whether all required dimension roles (from `_required_dimension_roles`) are present.
  - When `_select_fact_candidate` returns `None`:
    - Set `join_plan.plan_status="incomplete"` and add a `plan_issues` entry with `type="FACT_NOT_FOUND"`.
    - Set `error_info` with `type="FACT_NOT_FOUND"` and no `sql_query`.
  - When required dimensions are missing or join conditions cannot be synthesized for required roles:
    - Set `join_plan.plan_status="incomplete"` and add `plan_issues` entries (`"MISSING_DIMENSION"`, `"MISSING_JOIN_CONDITION"`).
    - Set `error_info` with `type="DIMENSION_MISSING"` before returning.
  - For cases where only optional dimensions are missing (e.g. labels for low‑stock), keep `plan_status="ok"` but add warnings to `plan_issues`.

- In `_select_fact_candidate`:
  - Keep existing ranking logic but:
    - Prefer fact candidates whose table names and `entity_keys` match `intent.primary_entities` and `intent.analytic_template` when available.
    - If no candidate satisfies required roles/metrics, return `None` so `_build_join_plan_node` can emit a clear error instead of silently picking an arbitrary high‑row table.

### 4.2 Supervisor Instructions & Hard Gating of Analytic Templates

- **Supervisor → planner instructions:**
  - Introduce a structured field on `BaseState` (e.g. `plan_sql_instructions`) that the supervisor LLM can populate when it selects `plan_sql` as the next tool.
    - In `contracts/state.py` add a `PlanSQLInstructions` TypedDict (total=False) with fields:
      - `preferred_fact_table: Optional[str]`
      - `avoid_tables: Optional[List[str]]`
      - `mode: Optional[Literal["analytic", "exploratory_sample"]]`
      - `narrow_discovery_keywords: Optional[List[str]]`
      - `notes: Optional[str]` (short human-readable hint, optional).
    - Add `plan_sql_instructions: Optional[PlanSQLInstructions]` to `BaseState`.
  - Examples of instructions:
    - `{ "preferred_fact_table": "dbo.Invoices", "avoid_tables": ["dbo.FunctionHistory"], "mode": "analytic" }`
    - `{ "mode": "exploratory_sample" }`
    - `{ "narrow_discovery_keywords": ["customer", "revenue"] }`
  - `_build_join_plan_node` and `_generate_sql_node` should read these hints and adjust:
    - Fact/dimension selection preferences.
    - Whether to aim for a full analytic template vs exploratory sample.
    - Whether to decline planning if constraints cannot be met (rather than inventing a weak plan).
  - These instructions are entirely LLM-generated at runtime; Python code only defines the schema and how hints are consumed, not *when* or *why* they are set.

- In `_generate_sql_node`:
  - **Analytic templates (`intent.analytic_template` or `required_action` in template set):**
    - Attempt to generate SQL only via:
      - Template routing (`MSSQLTemplateBuilder`) or specialised generators (`_generate_topk_customer_revenue_sql`, `_generate_trend_series_sql`, etc.).
    - If templates or specialised generators fail due to missing fact/dim/metric/time window:
      - Do **not** fall back to generic `SELECT TOP ... *` or a random `SUM(...)`.
      - Update `join_plan.plan_status="incomplete"` or `"unsupported"` and append detailed `plan_issues`.
      - Set `error_info` (e.g. `type="TEMPLATE_BUILD_ERROR"` or `type="PLAN_UNSUPPORTED"`).
      - Leave `sql_query` empty so `plan_sql_tool` and the supervisor see that planning failed.
  - **Vague/detail queries (no analytic template, metrics empty, intent looks like “show rows” and/or supervisor instructions specify exploratory mode):**
    - Allow simple sample SQL (e.g. `SELECT TOP {row_limit} *` or dialect-appropriate LIMIT form).
    - Mark `join_plan.plan_status="exploratory"` and add a `plan_issues` entry like `{"type": "EXPLORATORY_PLAN"}`.
  - **Safety check over generated SQL:**
    - For analytic templates, add simple semantic checks before accepting `sql`:
      - COUNT/Top‑K entity analytics should have at least one grouping key corresponding to an entity dimension (customer/product/project).
      - If these checks fail, treat as template failure and surface structured `error_info` rather than returning degenerate SQL.

- **Dialect awareness:**
  - Where this task touches SQL generation for templates or fallback paths, use `DB_DIALECT` to select appropriate syntax:
    - MSSQL: `SELECT TOP`, `DATEADD`, square brackets.
    - Postgres: `LIMIT`, `CURRENT_DATE`, double-quoted identifiers as needed.
  - The goal for this task is not to fully rewrite existing MSSQL-specific code, but **new or modified code** must not add further hard-coded MSSQL assumptions; it should branch on `DB_DIALECT` where necessary.

### 4.3 Error & Signal Taxonomy

Normalize and reuse error types from `JoinPlanAndSQLAgent`, and make the mapping between `plan_status` and `error_info.type` explicit.

- Existing error types in `join_sql`:
  - `FACT_NOT_FOUND`
  - `DIMENSION_MISSING`
  - `NO_PLAN`
  - `SQL_GEN_ERROR`
  - `TEMPLATE_BUILD_ERROR`
  - `SQL_VALIDATION_ERROR`

- New join‑specific types:
  - `PLAN_UNSUPPORTED` – analytic template not supported with current hints/schema.
  - `PLAN_INCOMPLETE` – required fact/dim/time window missing or ambiguous, but more specific than raw `NO_PLAN`.

- Mapping guidelines:
  - If `_select_fact_candidate` returns `None`:
    - `plan_status="incomplete"`.
    - `plan_issues` include a `JoinPlanIssue` with `type="FACT_NOT_FOUND"` and `severity="error"`.
    - `error_info.type` SHOULD be `"FACT_NOT_FOUND"` (or `"PLAN_INCOMPLETE"` with `details.type="FACT_NOT_FOUND"` if we consolidate codes).
  - If required dimensions are missing or required join conditions cannot be synthesized:
    - `plan_status="incomplete"`.
    - `plan_issues` include `type="MISSING_DIMENSION"` and/or `type="MISSING_JOIN_CONDITION"` with `severity="error"`.
    - `error_info.type` SHOULD be `"DIMENSION_MISSING"` (or `"PLAN_INCOMPLETE"` with corresponding details).
  - If a requested analytic template is not supported at all (no builder/route):
    - `plan_status="unsupported"`.
    - `plan_issues` include `type="PLAN_UNSUPPORTED"` with `severity="error"`.
    - `error_info.type` SHOULD be `"PLAN_UNSUPPORTED"`.
  - If a template exists but fails to build due to inconsistent metadata:
    - `plan_status="incomplete"` OR `"unsupported"` depending on whether this is fixable via discovery/instructions.
    - `error_info.type` SHOULD be `"TEMPLATE_BUILD_ERROR"` with a `details` payload from `TemplateBuildError`.
  - Generic/unexpected failures inside `_generate_sql_node`:
    - `plan_status` remains unchanged if a more specific status was already set; otherwise set to `"incomplete"`.
    - `error_info.type` SHOULD be `"SQL_GEN_ERROR"`.

- In all cases, `error_info` payloads must follow the `ErrorInfo` contract (via `normalize_error_info_payload` where they are surfaced to tools/supervisor), and join-specific details should be mirrored in `plan_issues` for easy LLM consumption.


### 4.4 Surface Plan Quality to Capability Tools & Supervisor

- `langgraph_integration/tools/capability_tools.py`:
  - Extend `_derive_progress_and_actions` for `tool_name == "plan_sql"`:
    - Inspect:
      - `error_info.type` where present.
      - `join_plan.plan_status` if `join_plan` is in `state`.
      - `intent.analytic_template` and `intent.metrics` when available.
    - Behaviors:
      - If `error_info` indicates `FACT_NOT_FOUND`, `DIMENSION_MISSING`, `PLAN_INCOMPLETE`, `PLAN_UNSUPPORTED`, `TEMPLATE_BUILD_ERROR`, or `SQL_GEN_ERROR`:
        - Treat as **negative** progress.
        - Set `suggested_next_actions` to bias toward `["rediscover", "replan", "clarify"]` (not to “just execute anyway”).
      - If `sql_query` exists but `join_plan.plan_status == "exploratory"` while the intent is clearly analytic (template or metrics present):
        - Treat as **neutral** (not positive) with `["replan", "rediscover", "clarify"]`.
      - Only treat planning as **positive** when:
        - `sql_query` is non‑empty, and
        - `join_plan.plan_status` is absent or explicitly `"ok"`.
    - Keep logic deterministic and simple – just coarse signals, not detailed routing rules.

- `langgraph_integration/supervisor.py`:
  - In `_llm_select_next_tool`:
    - Enrich the `summary` fed to the LLM with:
      - `join_plan_status`: `state.get("join_plan", {}).get("plan_status")`.
      - `join_plan_strategy`: `state.get("join_plan", {}).get("strategy")`.
      - `join_plan_fact_table`: `state.get("join_plan", {}).get("fact_table") or ...`.
      - `join_plan_template`: `state.get("join_plan", {}).get("template")`.
      - `error_info_type`: already present; keep.
      - `result_retry_action`: `validation_result.get("retry_action")` after `evaluate_result`.
    - Update the system prompt text to explain these signals and instruct the LLM:
      - When `join_plan_status` is `"incomplete"`/`"unsupported"` or error types indicate planning failure (e.g. `FACT_NOT_FOUND`, `PLAN_UNSUPPORTED`), the LLM should decide whether to:
        - Re‑run `discover_schema` (possibly with narrower/wider keywords based on `intent` and past failures).
        - Re‑run `plan_sql` but with explicit `plan_sql_instructions` telling the planner what to change.
        - Call `finalize_answer` to ask the user for constraints/schema hints and then resume planning.
      - When `result_retry_action` is `try_next_candidate` or `replan_with_*`, the LLM should prioritise `discover_schema` or `plan_sql` as appropriate, again optionally setting `plan_sql_instructions`.
  - `_select_initial_tool` / `_select_next_tool` remain as guardrail fallbacks when `_llm_select_next_tool` returns `None`; they must **not** become the primary source of routing logic.
  - **LLM output protocol for `_llm_select_next_tool`:**
    - Change the user prompt so the LLM always responds with a **single JSON object** of the form:
      ```json
      {
        "next_tool": "plan_sql",
        "plan_sql_instructions": {
          "preferred_fact_table": "dbo.Invoices",
          "avoid_tables": ["dbo.FunctionHistory"],
          "mode": "analytic"
        }
      }
      ```
    - Keys:
      - `next_tool: ToolName` – one of the allowed tools (`interpret_query`, `discover_schema`, `plan_sql`, `validate_sql`, `execute_sql`, `evaluate_result`, `finalize_answer`, `__STOP__`).
      - `plan_sql_instructions: Optional[PlanSQLInstructions]` – only present when `next_tool == "plan_sql"`.
    - `_llm_select_next_tool` will:
      - Parse the LLM response as JSON; on success:
        - Write `plan_sql_instructions` (if present) into `state["plan_sql_instructions"]`.
        - Return `next_tool` as the tool name.
      - On parsing failure or missing `next_tool`:
        - Fall back to the current behavior of treating the whole response as a plain tool name (for backward compatibility).

### 4.5 Optional Semantic Checks in Validator/ResultValidator

(Can be implemented incrementally; not strictly required to satisfy the initial request, but useful in benchmark mode.)

- `SQLValidatorAgent`:
  - Optionally use semantic info from `intent.analytic_template` and `join_plan` (if present) to enrich `_validate_sql_semantics`, e.g.:
    - Ensure at least one required table from `join_plan.dimensions` appears in `tables_used_base`.
    - Emit warnings (not hard errors) when GROUP BY is missing for COUNT_ENTITY templates.

- `ResultValidator`:
  - When `QueryContract` is present on state (benchmark mode):
    - Compare `validation_result.tables_used_base` from SQL validation with `contract.required_tables`.
    - Surface `semantic_status` and `semantic_retry_action` when tables/join paths violate the contract.
  - Use these semantic hints to prefer `retry_action="try_next_candidate"` or `"replan"` when results look numerically plausible but violate contract expectations.

### 4.6 Backwards Compatibility, Risk Mitigation & Legacy Cleanup

- All new fields on `join_plan` are optional; existing agents/tests that ignore them will continue to work.
- Planning failures are surfaced as `error_info` with no `sql_query`:
  - Downstream tools already handle absence of `sql_query` (e.g. `validate_sql_tool` treats missing SQL as negative progress).
  - For this task we will rely more on the **LLM supervisor** to interpret these failures (via enriched summaries) and choose the next action, with heuristic fallbacks only as a safety net.
- Legacy heuristic clean‑up:
  - As part of changes to `_generate_sql_node`, we will remove or significantly reduce legacy fallback heuristics that “make up” a simple aggregate or `SELECT *` for analytic queries.
  - The preferred fallback is for the planner to say “I cannot build a correct plan for this intent with the current tables” via structured `error_info`, and let the supervisor reason over replanning steps instead of emitting low‑quality SQL.

---

## 5. Source Files to Modify

Planned code changes will primarily touch:

- `langgraph_integration/agents/join_sql/agent.py`
  - Extend `JoinPlan` metadata usage (`plan_status`, `plan_confidence`, `plan_issues`, `template`).
  - Tighten `_build_join_plan_node` and `_generate_sql_node` to:
    - Gate analytic templates vs exploratory fallbacks.
    - Emit structured `error_info` instead of low‑quality SQL where appropriate.
  - Add lightweight semantic validation of generated SQL for analytic templates (grouping/entity presence), and consume optional `plan_sql_instructions` / supervisor hints when building plans and SQL.

- `langgraph_integration/contracts/state.py`
  - Update `JoinPlan` TypedDict documentation and optional keys.

- `langgraph_integration/tools/capability_tools.py`
  - Enhance `_derive_progress_and_actions` for `plan_sql` to incorporate `join_plan.plan_status` and join‑specific error types.

- `langgraph_integration/supervisor.py`
  - Enrich `_llm_select_next_tool` summary and system instructions with join plan quality, template, and result retry signals, and extend its output contract to optionally include structured `plan_sql_instructions` that are written into state before invoking `plan_sql_tool`.

- (Optional / phased)
  - `langgraph_integration/agents/sql_validator/agent.py` – augment `_validate_sql_semantics`.
  - `langgraph_integration/agents/result_validator/agent.py` – leverage `QueryContract` and SQL tables metadata for semantic correctness in benchmark mode.

---

## 6. Verification Plan

### 6.1 Unit & Integration Tests

- Existing tests to keep passing:
  - `tests/test_supervisor_behavior.py`
    - Budget behavior and `_select_next_tool` retry routing.
  - `tests/test_sql_validator_agent.py`
    - SQLValidator basic behavior and repair loop.
  - `tests/test_simple_integration.py`, `tests/test_orchestrator.py`
    - Ensure end‑to‑end orchestration remains functional.

- New or extended tests (to be added in implementation step):
  - **Join planner behavior tests** (new file, e.g. `tests/test_join_sql_agent.py`):
    - When fact/dimension hints are insufficient for an analytic template:
      - `JoinPlanAndSQLAgent` returns `join_plan.plan_status="incomplete"` or `"unsupported"`.
      - `sql_query` is empty.
      - `error_info.type` is one of the new/normalized join errors.
    - For clearly analytic queries with good hints:
      - `join_plan.plan_status="ok"`; `sql_query` uses fact + required dimensions and appropriate GROUP BY.
    - For detail/exploratory queries:
      - `plan_status="exploratory"` and SQL may be `SELECT TOP ... *`.
  - **Capability tool envelope tests** (extend or add tests under `tests/`):
    - `plan_sql_tool`:
      - When state has `join_plan.plan_status="ok"` and non‑empty `sql_query`, `progress_signal == "positive"`.
      - When `plan_status` is `"incomplete"`/`"unsupported"` or join error types are present:
        - `progress_signal == "negative"` and `suggested_next_actions` include `rediscover` or `clarify`.
      - When `plan_status="exploratory"` for analytic intents:
        - `progress_signal == "neutral"` and `suggested_next_actions` favor replanning/rediscovery.
  - **Supervisor summarization/selection tests** (may stub LLM):
    - Extend `tests/test_supervisor_behavior.py` to verify that `_llm_select_next_tool`’s input summary includes new join plan fields (by mocking `ChatOpenAI` to record prompts) or, alternatively, test that `_select_next_tool` still provides sensible fallback when `plan_sql` fails (missing SQL → replan/rediscover).

### 6.2 Manual / Scenario Testing

- Using the orchestrator in debug mode (or `chatbot_ui/langgraph_service.py`):
  - Scenario: “Top 5 customers by revenue” where discovery exposes both a sales fact and unrelated numeric heavy tables:
    - Verify that join planner chooses the correct fact table and generates a GROUP BY by customer.
    - If hints are insufficient, it should fail with a clear `PLAN_INCOMPLETE` and no SQL, prompting the supervisor to rediscover or ask the user.
  - Scenario: “How many customers do we have?” with weak/ambiguous discovery:
    - Ensure planner does **not** blindly pick a huge transactional table as fact; better to signal uncertainty.
  - Scenario: simple detail query (“Show me 10 rows from table X”):
    - Verify planner marks plan as `exploratory` and supervisor is still allowed to proceed.

### 6.3 Commands

- After implementation:
  - Run targeted tests first:
    - `pytest tests/test_supervisor_behavior.py`
    - `pytest tests/test_sql_validator_agent.py`
    - `pytest tests/test_join_sql_agent.py` (new).
  - Then a broader regression suite:
    - `pytest`
