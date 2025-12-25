# Technical Specification – Semantic Correctness & Benchmark Mode

This spec makes the PRD implementable and bounded. It does **not** change goals or expand scope; it tightens behavior around:
- non‑functional limits (performance & safety),
- semantic validator integration,
- benchmark mode contracts and propagation,
- query contract schema,
- replanning semantics,
- template scope (Phase 1 only),
- production vs evaluation behavior.

All section numbers below are implementation constraints, not new goals.

---

## 1. Non‑Functional Constraints (Performance & Safety)

### 1.1 Global bounds (re‑use existing budgets)

We will re‑use the existing global orchestration budgets in `BaseState` and `QueryOrchestrator` instead of adding new unbounded counters:
- `BaseState.plan_attempt_count`, `BaseState.max_total_plans` (see `langgraph_integration/contracts/state.py:120-132`).
- `BaseState.validation_attempt_count`, `BaseState.max_validation_attempts` (validation / repair loops).
- `BaseState.exec_recovery_attempt_count`, `BaseState.max_exec_recovery_attempts`.
- `BaseState.total_llm_calls`, `BaseState.max_llm_calls`, `BaseState.llm_budget_safety_margin`.

`QueryOrchestrator.process_query()` already seeds:
- `"max_total_plans": 4`,
- `"max_exec_attempts": 4`,
- `"max_validation_attempts": self.max_validation_attempts` (default from env),
- `"max_exec_recovery_attempts": self.max_exec_recovery_attempts`,
- `"max_no_progress_repeats": self.max_no_progress_repeats`,
in `langgraph_integration/orchestrator.py:2800-2885`.

**NF‑1:** All semantic validation and replanning MUST operate *within* these budgets. No new counter may be introduced that can increase the number of cycles beyond:
- `max_total_plans` for plan/validate cycles,
- `max_validation_attempts` for validation/replan cycles,
- `max_exec_recovery_attempts` for execution/repair,
- `max_llm_calls` for LLM token usage.

### 1.2 Max semantic replan attempts

Semantic validation introduces an additional notion of “semantic retry” (replanning due to entity/metric/join mismatches). We define:

- `BaseState.semantic_retry_count: int` (new state field).
- `BaseState.max_semantic_retries: int` (new state field).

Values:
- In `QueryOrchestrator.process_query()`, initialize:
  - `"semantic_retry_count": 0`,
  - `"max_semantic_retries": 2` (hard cap for benchmark mode).

**NF‑2:** For any query, the number of semantic replans MUST satisfy:
- `semantic_retry_count <= max_semantic_retries`, and
- `plan_attempt_count + semantic_retry_count <= max_total_plans`.

Implementation:
- Each time semantic validation requests a retry (see §5), increment `semantic_retry_count` and `plan_attempt_count` together.
- If either cap is reached, no further semantic replans are allowed; the system must proceed to final failure/answer.

### 1.3 Latency overhead in benchmark mode

We target bounded overhead rather than a hard millisecond SLA, since underlying DB and LLM latency dominates.

**NF‑3:** Benchmark mode may **increase per‑query latency**, but:
- Must not introduce *unbounded* loops (enforced via NF‑1, NF‑2).
- Must respect existing per‑query orchestrator timeout in `process_query()`:
  - `timeout_s = max(self.query_timeout_seconds, 60)` (`orchestrator.py:2800-2885`).

Acceptable overhead definition:
- Semantic validation and replanning MAY add:
  - at most `max_semantic_retries` extra cycles that go through `join_sql` + `validate_sql` + `exec_recovery` + `result_validator`,
  - but MUST terminate when either the timeout is reached, `max_total_plans` is hit, or `max_semantic_retries` is hit.

No new async tasks or background loops are introduced. All work remains within the single `process_query()` call, which is already guarded by `asyncio.wait_for`.

### 1.4 No unbounded loops

**NF‑4:** Semantic validation MUST NOT introduce any new edge in the LangGraph that bypasses:
- the existing `route_validation_result()` loop controls (`result_validator` → `discovery|join_sql|answer`, `orchestrator.py:820-980`), and
- the existing LLM budget and plan counters.

All semantic retry routing MUST:
- use the existing `result_validator` → `route_validation_result` logic (see §2, §5),
- or be a *terminal* action (mark query as semantically failed and proceed to `answer`).

---

## 2. Semantic Validator Integration

### 2.1 Placement decision

We already have:
- `validate_sql` node → `SQLValidatorAgent` (syntax, tables, required_relations guardrail) in `orchestrator._validate_sql_node` (`orchestrator.py:1880-1960`).
- `exec_recovery` node → runs query, handles execution errors.
- `result_validator` node → `build_result_validator_node` (post‑exec, catches “silent” failures) with routing in `route_validation_result` (`orchestrator.py:820-980`).

To avoid new agents or graph nodes, we will:

**SV‑1:** Implement semantic validation as an **extension of the existing `result_validator` node**, not as a new graph node.

- The `result_validator` node will compute and set additional fields in `BaseState.validation_result`, specifically:
  - `validation_result.semantic_status: str` (see §5.1 for values),
  - `validation_result.semantic_failure_reasons: List[str]`,
  - `validation_result.contract_id: str` (the `query_id` from the contract),
  - `validation_result.semantic_retry_action: str` (see §5.2).

### 2.2 Execution phase (pre vs post)

We distinguish:
- **SQL validation (pre‑exec):** `validate_sql` remains responsible for syntax/dialect checks and required‑relations guardrail based on `tables_used`.
- **Semantic validation (post‑exec):** needs result rows, grouping, and join path, so it must run *after* at least one successful `exec_recovery` execution.

**SV‑2:** Semantic validation runs **post‑exec only** inside the `result_validator` node:
- It must NOT attempt to introspect or reject SQL solely on the prompt or plan before execution.
- It MAY use:
  - `state["exec_result"]` (rows, metadata),
  - `state["sql_query"]`,
  - `state["join_plan"]`,
  - `state["validator_tables_used"]`, `state["validator_tables_used_base"]`,
  - `state["intent"]`,
  - per‑query contract (see §4).

Pre‑exec logic (syntax, table existence, required_relations) remains in `_validate_sql_node` and `SQLValidatorAgent`.

### 2.3 Orchestration integration points

Concrete integration locations:
- **Node implementation:**
  - Extend `langgraph_integration/agents/result_validator/agent.py` (not shown here) to:
    - load the relevant query contract (see §4.3),
    - compute semantic status fields,
    - write them into `state["validation_result"]`.
- **Routing:**
  - `route_validation_result(state: BaseState) -> str` in `orchestrator._build_graph()` (`orchestrator.py:820-980`) already handles:
    - `validation_result["retry_action"]` with values like `"accept"`, `"try_next_candidate"`, `"replan_with_aggregation"`, `"replan_with_filter"`, `"ask_user"`.
  - We will:
    - keep `retry_action` as the *primary* routing field,
    - map semantic statuses to these existing actions (see §5),
    - ensure semantic retries increment existing counters as per §5.3.

There will be **no new LangGraph nodes or edges**; only the internal logic of `result_validator` and `route_validation_result` is extended.

---

## 3. Benchmark Mode Contract

### 3.1 Where the flag lives

We need a clear switch between:
- **benchmark mode** (strict semantics, deterministic metrics, template enforcement), and
- **interactive/production mode** (more relaxed behavior).

We will introduce:
- `BaseState.eval_mode: Optional[str]` with expected values:
  - `"benchmark"` – strict mode for evaluation runs,
  - `"interactive"` or `None` – normal behavior.

Source of truth:
- In `eval/run_benchmark.py`, when calling the LangGraph service:
  - We already pass headers `X-Eval-Run-Id`, `X-Eval-Query-Id` (`run_benchmark.py:120-170`).
  - The LangGraph HTTP layer (`langgraph_integration/api.py`) must:
    - read these headers,
    - set `metadata={"eval_run_id": ..., "eval_query_id": ..., "eval_mode": "benchmark"}` when calling `QueryOrchestrator.process_query()`.
- In `QueryOrchestrator.process_query()` (`orchestrator.py:2800-2885`), metadata is merged into `initial_state`, so:
  - `state["eval_mode"] = "benchmark"` will be present for benchmark runs,
  - `eval_run_id`, `eval_query_id` are already part of `BaseState` (`state.py`).

### 3.2 Propagation through LangGraph state

**BM‑1:** `eval_mode` is a **read‑only configuration flag** for nodes:
- Must NOT be mutated once set in `process_query()`.
- Nodes may branch behavior based on:
  - `state.get("eval_mode") == "benchmark"`.

Propagation:
- Because the state is a single shared `BaseState`, `eval_mode` automatically propagates through:
  - `discovery`, `join_sql`, `validate_sql`, `exec_recovery`, `result_validator`, `answer`.
- No additional propagation code is needed; nodes simply read `state["eval_mode"]`.

### 3.3 Benchmark‑only vs interactive behavior

Requirements scoped to modes:

**Benchmark‑only (STRICT when `eval_mode == "benchmark"`):**
- Semantic correctness enforcement:
  - entity/metric/join‑path contract must be checked (see §4, §5),
  - failures must set `semantic_status` and may trigger semantic replans within NF‑1/NF‑2.
- Deterministic metric mapping:
  - metric resolution must use a closed set of metrics defined per dataset/contract.
  - LLM must not invent metrics not present in the contract.
- Template enforcement:
  - only Phase 1 templates in §6 are allowed for analytic queries.
- Evaluation artifacts:
  - semantic status and failure reasons must be persisted for scoring.

**Interactive/production (RELAXED when `eval_mode` is absent or `"interactive"`):**
- Semantic validation MAY run but:
  - MUST NOT trigger replanning loops beyond existing SQL validation / exec recovery loops,
  - MUST NOT block an otherwise valid answer solely on contract mismatch (since there is no external contract).
- Metric resolution MAY be more flexible:
  - open‑ended mapping is allowed;
  - templates are recommended but not strictly enforced.
- Evaluation fields:
  - semantic statuses remain internal; no new error types are exposed directly in the user‑facing message unless explicitly opted‑in.

---

## 4. Query Contract Schema

### 4.1 JSON schema example

Contracts live alongside datasets under `eval/datasets/`. For each JSONL dataset (e.g., `cockpit_queries_top5.jsonl`), we introduce a parallel contract file, e.g.:
- `eval/datasets/cockpit_queries_top5.contracts.json`.

Each contract entry is keyed by `query_id` (matching the dataset `id`):

```json
{
  "query_id": "Q2",
  "entity": "customer",
  "entity_table": "customers",
  "metric_key": "total_revenue",
  "metric_expression_sql": "SUM(order_details.unit_price * order_details.quantity)",
  "required_tables": ["customers", "orders", "order_details"],
  "allowed_join_paths": [
    ["customers", "orders", "order_details"]
  ],
  "analytic_template": "TOP_K_BY_METRIC",
  "metric_phrase": "total revenue",
  "top_k": 3,
  "time_window": {
    "type": "calendar_year",
    "year": 2024,
    "column": "orders.OrderDate"
  }
}
```

Field meanings:
- `query_id` – must match the dataset entry `id`.
- `entity` – human‑level entity name (e.g., `"customer"`, `"order"`).
- `entity_table` – canonical dimension/fact table for that entity (unqualified; matching dataset’s `expected_tables` entries).
- `metric_key` – stable identifier for metric (e.g., `"total_revenue"`, `"orders_placed"`, `"items_purchased"`).
- `metric_expression_sql` – canonical SQL expression (without `GROUP BY` / `ORDER BY`) using table aliases as they appear in the fact/dimension tables.
- `required_tables` – list of table *base names* that must appear in `validator_tables_used_base`.
- `allowed_join_paths` – list of allowed FK paths, each a list of table base names in order from entity ↔ fact; used for semantic join validation.
- `analytic_template` – one of the Phase 1 templates (see §6).
- `metric_phrase` – natural language phrase from the question, used for debugging and metric resolution.
- `top_k` – optional; expected K for top‑K queries.
- `time_window` – optional; normalized time constraint for correctness checks.

### 4.2 Mapping contract fields → LangGraph state

We define the mapping for semantic validation:

- `contract.query_id` → `state["eval_query_id"]` (from HTTP header).
  - Semantic validator MUST use `eval_query_id` to select the contract; if not present, semantic validation is skipped.

- `contract.entity` → `state["intent"]["primary_entities"]` and resolved entity grouping:
  - In benchmark mode:
    - `intent.primary_entities` MUST include `contract.entity` (either exact string or a simple lemma match).
    - The grouping dimension in SQL (`GROUP BY` column / dimension table) MUST map to `contract.entity_table`.

- `contract.entity_table` → `state["validator_tables_used_base"]` and `join_plan`:
  - Semantic validator checks that:
    - `contract.entity_table` is in `validator_tables_used_base`.
    - `join_plan` contains a path including `contract.entity_table`.

- `contract.metric_key` → `state["intent"]["metrics"]` and metric resolver:
  - `intent.metrics` becomes a list of objects in benchmark mode (backwards‑compatible with existing string list), at minimum:
    - `{"key": "<metric_key>", "phrase": "<metric_phrase>"}`.
  - Semantic validator checks that the resolved metric key equals `contract.metric_key`.

- `contract.metric_expression_sql` → derived metric expression:
  - A metric resolver will produce a normalized metric expression string (e.g., `SUM(order_details.quantity * order_details.unit_price)`).
  - Semantic validator compares canonicalized expressions (case‑insensitive, whitespace‑normalized) against `contract.metric_expression_sql`.
  - For Phase 1, **exact string match after normalization** is required; expression equivalence (e.g., commutativity) is deferred.

- `contract.required_tables` → `state["validator_tables_used_base"]` and `required_relations` guardrail:
  - Extend the derivation of `required_tables_from_kpi` to include `contract.required_tables`.
  - Required‑relations guardrail already enforces presence; semantic validator additionally records missing tables as semantic failures.

- `contract.allowed_join_paths` → `state["join_plan"]` and catalog FK info:
  - `join_plan` must contain enough metadata (e.g., path tables) to reconstruct the chosen path.
  - Semantic validator checks that the chosen path matches one of the allowed sequences of base table names.

- `contract.analytic_template` → `state["intent"]["analytic_template"]` and template selection:
  - In benchmark mode, `intent.analytic_template` MUST equal `contract.analytic_template` for Phase 1 templates.
  - If mismatched, semantic validator sets `semantic_status="METRIC_OR_TEMPLATE_MISMATCH"`.

### 4.3 Contract loading

Responsibility:
- **Eval layer** (outside LangGraph) will:
  - load contract files as a dictionary `contracts[query_id]`,
  - pass the specific contract into the orchestrator via metadata:
    - `metadata={"eval_run_id": ..., "eval_query_id": ..., "eval_mode": "benchmark", "query_contract": <dict>}`.

LangGraph side:
- `QueryOrchestrator.process_query()` will:
  - accept an optional `metadata["query_contract"]` dict,
  - attach it to state as `state["query_contract"]` for nodes to consume.
- `result_validator` node will:
  - read `state["query_contract"]` and skip semantic validation if missing.

---

## 5. Replanning Semantics

### 5.1 Semantic status and failure codes

Semantic validator will set:
- `validation_result.semantic_status: str` where values are:
  - `"OK"` – entity, metric, join path all satisfy contract.
  - `"ENTITY_MISMATCH"` – output grouped by wrong entity / table.
  - `"METRIC_MISMATCH"` – wrong metric key or expression.
  - `"JOIN_PATH_INVALID"` – join path does not match any `allowed_join_paths`.
  - `"NO_VALID_JOIN_PATH"` – required tables present but no allowed path found via FK info.
  - `"UNSUPPORTED_METRIC"` – metric phrase not recognized in mapping.
  - `"CONTRACT_MISSING"` – no contract found (semantic validation skipped).
- `validation_result.semantic_failure_reasons: List[str]` – human‑readable reasons (e.g., `"expected entity=customer, got product"`).
- `validation_result.semantic_retry_action: str` – one of:
  - `"none"` – no retry needed (status OK or non‑recoverable failure),
  - `"replan"` – replan with same contract but updated constraints (e.g., forced tables),
  - `"try_next_candidate"` – let existing logic pick next discovery candidate.

### 5.2 How semantic failures map to routing

We re‑use `route_validation_result(state)` in `orchestrator.py:820-980`:

Mapping:
- If `semantic_status == "OK"`:
  - `validation_result.retry_action` remains as currently computed by `result_validator` (often `"accept"`).
- If `semantic_status in {"ENTITY_MISMATCH", "METRIC_MISMATCH", "JOIN_PATH_INVALID", "NO_VALID_JOIN_PATH"}`:
  - In benchmark mode and within retry budgets:
    - Set `validation_result.retry_action = "replan_with_aggregation"` or `"replan_with_filter"` depending on mismatch type:
      - entity mismatch → `"replan_with_aggregation"` (adjust GROUP BY / join plan).
      - metric mismatch → `"replan_with_aggregation"` (change SELECT / aggregation expression).
      - join path invalid → `"replan_with_filter"` (reselect tables / joins).
    - Set `semantic_retry_action = "replan"`.
  - In interactive mode or when budgets exceeded:
    - Set `semantic_retry_action = "none"`,
    - Leave `retry_action = "accept"` to avoid additional loops; semantic failure is logged only.

`route_validation_result` already:
- increments `plan_attempt_count` when `retry_action in ("try_next_candidate", "replan_with_aggregation", "replan_with_filter")`,
- routes `"replan_with_aggregation"` and `"replan_with_filter"` to `"join_sql"`,
- respects `max_validation_attempts`, `max_total_plans`, `max_retries_per_candidate_set`.

We only add:
- increment of `semantic_retry_count` whenever `semantic_retry_action == "replan"` and `retry_action` triggers a replan.

### 5.3 Max semantic retries and counters

**RP‑1:** In benchmark mode (`eval_mode == "benchmark"`):
- When `semantic_retry_action == "replan"`:
  - If `semantic_retry_count >= max_semantic_retries` **or** `plan_attempt_count >= max_total_plans`:
    - Do NOT change `retry_action`; instead:
      - set `validation_result.retry_action = "accept"`,
      - leave `semantic_status` and failure reasons as‑is,
      - annotate `state["stop_reason"] = "max_semantic_retries"`.
  - Else:
    - increment both:
      - `state["semantic_retry_count"] += 1`,
      - `state["plan_attempt_count"] += 1`.

**RP‑2:** In interactive mode:
- `semantic_retry_count` is not incremented and does not impact routing.

### 5.4 Logging and eval artifacts

Per semantic retry or final semantic failure, we MUST:
- Log a structured message:
  - logger name: `result_validator`/`VALIDATION_ROUTE`,
  - include: `query_id`, `semantic_status`, `semantic_failure_reasons`, `semantic_retry_count`.
- Persist in evaluation artifacts:
  - `eval/run_benchmark.py` already writes `error_info`, `discovery_log`, `llm_usage`, etc. (`run_benchmark.py:120-220`).
  - We will additionally persist:
    - `semantic_status`,
    - `semantic_failure_reasons`,
    - `semantic_retry_count`,
    - `semantic_retry_action`,
  in each per‑query artifact.

This ensures failures are localizable when scoring (see §7).

---

## 6. Template Scope (Phase 1 Only)

We explicitly scope Phase 1 template support to the minimal set needed for current benchmarks.

### 6.1 Templates in scope (Phase 1)

Two analytic templates are in scope:

1. `TOP_K_BY_METRIC`
   - Query form: “Top N entities by metric over a period”.
   - Contract fields used:
     - `entity`, `entity_table`, `metric_key`, `metric_expression_sql`, `top_k`, `time_window`.
   - SQL skeleton (conceptual, not hard‑coded here):
     - `SELECT <entity_dim>, <metric_expression> AS metric FROM ... GROUP BY <entity_dim> ORDER BY metric DESC LIMIT K`.

2. `COUNT_ENTITY`
   - Query form: “How many entities did X?” (e.g., orders placed).
   - Contract fields used:
     - `entity`, `entity_table`, `metric_key`, `metric_expression_sql` (e.g. `COUNT(DISTINCT orders.order_id)`), `time_window`.

**TPL‑1:** In benchmark mode, for queries whose contract specifies `analytic_template`:
- `intent.analytic_template` MUST exactly match one of the above.
- `JoinPlanAndSQLAgent` must generate SQL consistent with the chosen template:
  - single metric column matching `metric_expression_sql`,
  - grouping column consistent with `entity_table` for `TOP_K_BY_METRIC`,
  - count/aggregation consistent with `metric_expression_sql` for `COUNT_ENTITY`.

### 6.2 Templates explicitly deferred

Out of scope for Phase 1 (MUST NOT be relied on in this iteration):
- `AGG_OVER_PERIOD` with complex time‑series (month‑over‑month deltas).
- Multi‑metric comparisons (e.g., “highest revenue and volume”).
- Window functions and ranking beyond simple `TOP_K_BY_METRIC`.

These can be added in later phases with their own contract extensions and semantic checks but are **explicitly deferred** here.

---

## 7. Production vs Evaluation Behavior

### 7.1 Semantic statuses: internal vs external

Semantic statuses are primarily for evaluation and debugging.

**PRD‑1:** The following fields are **internal/eval‑only**:
- `validation_result.semantic_status`,
- `validation_result.semantic_failure_reasons`,
- `validation_result.contract_id`,
- `validation_result.semantic_retry_action`,
- `semantic_retry_count`, `max_semantic_retries`.

They MUST:
- be included in:
  - the LangGraph internal state,
  - the JSON returned by `process_query()` (so `eval/run_benchmark.py` can capture them),
  - evaluation artifacts under `eval/runs/<run_id>/`.
- NOT be surfaced in end‑user UI messages directly (Streamlit, etc.).

### 7.2 Public API response compatibility

`QueryOrchestrator.process_query()` already returns a dict that includes:
- `final_response`,
- `exec_result`,
- `error_info`,
- `sources` / `relevant_tables`,
- diagnostic usage fields in some modes.

**PRD‑2:** To avoid breaking production UX:
- Existing top‑level fields in the API response MUST remain stable (names and meanings unchanged).
- New semantic fields MUST be:
  - either nested under `state` or `validation_result`,
  - or added as optional fields that do not affect existing clients that ignore unknown keys.
- Error codes / types shown to users:
  - We MUST NOT introduce new user‑visible error messages solely due to semantic mismatch in interactive mode.
  - In benchmark mode, semantic failures are visible via artifacts and logs; the end user still sees an explanation that the system could not produce a confident answer, phrased generically.

### 7.3 Benchmark scoring integration

`eval/scoring/score_run.py` currently computes:
- success rate,
- SQL execution rate,
- non‑empty results rate.

**PRD‑3:** For semantic scoring (Phase 1), we will:
- Extend `results.json` entries to include:
  - `semantic_status`,
  - `semantic_failure_reasons`,
  - `semantic_retry_count`.
- Update `score_run()` to compute:
  - `entity_metric_join_correct_count = number of queries with semantic_status == "OK"`,
  - `entity_metric_join_correct_rate` = that count / total queries.
- A query is counted as “semantically passed” **only if**:
  - `status == "success"` (structural checks),
  - AND `semantic_status == "OK"`.

The existing “success” definition remains, but thesis H2a analyses will rely on `entity_metric_join_correct_rate` as the primary metric.

---

## 8. Implementation Notes (for Planning)

This section is not new requirements; it is a pointer for the upcoming `plan.md`:
- Add `eval_mode`, `semantic_retry_count`, `max_semantic_retries` to `BaseState` and `process_query()` initialization.
- Extend HTTP API (`langgraph_integration/api.py`) to pass eval headers and query contract in `metadata`.
- Implement contract loading in the eval harness and pass `query_contract` into `process_query()`.
- Extend `result_validator` logic to:
  - interpret contracts,
  - compute semantic statuses,
  - set `validation_result` fields accordingly.
- Update `route_validation_result` to:
  - increment `semantic_retry_count` when appropriate,
  - honor `max_semantic_retries` while respecting existing caps.
- Extend `eval/run_benchmark.py` and `eval/scoring/score_run.py` to log and score semantic correctness.

All of the above changes are incremental and confined to:
- `langgraph_integration/contracts/state.py`,
- `langgraph_integration/orchestrator.py`,
- `langgraph_integration/agents/result_validator/agent.py`,
- `langgraph_integration/api.py`,
- `eval/run_benchmark.py`,
- `eval/scoring/score_run.py`,
- `eval/datasets/*.contracts.json`.

