# ADR-0027: Semantic Correctness Contracts & Benchmark Mode

**Status**: Accepted
**Date**: 2025-12-25
**Author**: Julianus Kath

## Problem

The system can execute SQL, return rows, and pass structural validation while still answering the **wrong question**:

- Returns the wrong **entity** (e.g., `order_id` instead of `customer`).
- Computes the wrong **metric** (e.g., `items` instead of `revenue`).
- Uses an invalid or unintended **join path** (e.g., skipping required dimension tables).

This makes the system *technically successful but semantically wrong*, invalidating hypothesis **H2a (Proof of Performance)**:

> We cannot claim performance if the agent optimizes for plausible output instead of correct intent.

Root cause: lack of **hard semantic constraints** connecting:

- What the user asked (entity + metric),
- What the system plans (tables, joins, dimensions),
- What the system accepts as “valid”.

Semantic correctness was emergent (LLM judgment + weak guardrails), not structural.

---

## Decision

Introduce a **benchmark mode with explicit semantic contracts** and a **semantic validator** wired into the existing orchestrator and evaluation harness:

1. **Lock Correctness Contracts per Benchmark Query.**
2. **Enforce post-execution semantic validation** (entity, metric, join path).
3. **Preserve required discovery tables** from being dropped by ranking.
4. **Ground join planning in actual FK paths**, not heuristics.
5. **Make metric resolution deterministic** from contracts.
6. **Reduce LLM degrees of freedom** via analytic templates.
7. **Score semantic correctness explicitly** in the eval harness.

These changes are **benchmark-only** (when `eval_mode == "benchmark"`) and respect:

- Existing budget caps (`max_total_plans`, `max_llm_calls`, validation/exec budgets).
- Existing graph topology (no new graph nodes/edges).
- Backwards compatibility for interactive callers and public APIs.

---

## Before vs After

### Before

- Orchestrator:
  - Only structural validation (`SQLValidatorAgent` + required-relations guardrail).
  - No notion of benchmark vs interactive mode.
  - No explicit semantic status; silent mismatches could pass.
- Discovery & Join planning:
  - Heuristic ranking; required dimension tables could be dropped.
  - Join paths derived from names/IDs without explicit contract.
- Metric resolution:
  - Open-ended; LLM free to interpret phrases loosely.
- Evaluation:
  - `eval/run_benchmark.py` captured final answers, SQL, tables, latency.
  - `eval/scoring/score_run.py` measured:
    - Success rate,
    - SQL execution rate,
    - Non-empty results rate,
    - Failure categorization.
  - No metric for **semantic correctness** (entity + metric + join).

### After

- Orchestrator state:
  - `BaseState` extended with:
    - `eval_mode: Optional[str]` (e.g., `"benchmark"` vs `None` / `"interactive"`),
    - `semantic_retry_count: int`,
    - `max_semantic_retries: int`.
  - `QueryOrchestrator.process_query()`:
    - Seeds `eval_mode` from metadata (`None` by default).
    - In benchmark mode: `semantic_retry_count = 0`, `max_semantic_retries = 2`.
    - Enforces `semantic_retry_count <= max_semantic_retries` and
      `plan_attempt_count + semantic_retry_count <= max_total_plans`.
    - Normalizes these counters **after** merging metadata into `initial_state`.

- API & metadata propagation:
  - `langgraph_integration/api.py`:
    - Reads `X-Eval-Run-Id` / `X-Eval-Query-Id` headers.
    - Accepts optional `query_contract` payload in `ProcessQueryRequest`.
    - Builds `metadata` with:
      - `eval_run_id`, `eval_query_id`,
      - `eval_mode = "benchmark"` when eval headers are present,
      - `query_contract` when supplied.
  - `QueryOrchestrator.process_query()`:
    - Merges `metadata` into `initial_state`, keeping `eval_mode` read-only.

- Semantic contracts:
  - New `QueryContract` model in `langgraph_integration/contracts/semantic_contracts.py`:
    - Fields: `query_id`, `entity`, `entity_table`, `metric_key`,
      `metric_expression_sql`, `required_tables`, `allowed_join_paths`,
      `analytic_template`, `metric_phrase`, etc.
  - Per-dataset contract files:
    - `eval/datasets/<dataset>.contracts.json`.
    - `eval/run_benchmark.py`:
      - `load_query_contracts_for_dataset()` loads and validates contracts.
      - Selects the correct contract per `query_id`.
      - Passes `query_contract` through to `/process_query`.

- Deterministic metric resolution & templates:
  - Orchestrator:
    - In benchmark mode, maps contract metrics into intent:
      - `intent["resolved_metrics"]` with `{key, phrase, expression_sql}`.
      - `intent["analytic_template"]` set from contract (`TOP_K_BY_METRIC`, `COUNT_ENTITY` in Phase 1).
  - `JoinPlanAndSQLAgent`:
    - Uses `analytic_template` and `metric_expression_sql` to generate SQL with fixed patterns:
      - TOP-K: `SELECT entity_dim, metric_expression ... ORDER BY metric DESC LIMIT K`.
      - COUNT: `COUNT(DISTINCT ...)` as specified by contract.
  - Out-of-scope:
    - Unsupported templates mark queries with semantic status `UNSUPPORTED_METRIC`.
    - Multi-metric queries can be treated as unsupported or mapped to a deterministic subset.

- Discovery & join planning:
  - `DiscoveryAgent`:
    - Treats `contract.required_tables` as **hard constraints** in benchmark mode.
    - Ensures required entity tables survive scoring/pruning.
    - Logs when a required table would have been dropped absent the contract.
  - Join planning:
    - Uses catalog FK information plus `allowed_join_paths` to ensure a connected path from fact → dimension before SQL is accepted.

- Semantic validator:
  - `langgraph_integration/agents/result_validator/agent.py`:
    - Extends existing `ResultValidator` node; no new graph nodes.
    - Reads:
      - `state["eval_mode"]`,
      - `state["query_contract"]`,
      - `state["intent"]`,
      - `state["validator_tables_used_base"]`,
      - `state["join_plan"]`,
      - `state["exec_result"]`.
    - Computes semantic fields:
      - `semantic_status` (one of):
        - `"OK"`,
        - `"ENTITY_MISMATCH"`,
        - `"METRIC_MISMATCH"`,
        - `"JOIN_PATH_INVALID"`,
        - `"NO_VALID_JOIN_PATH"`,
        - `"UNSUPPORTED_METRIC"`,
        - `"CONTRACT_MISSING"`.
      - `semantic_failure_reasons: List[str]`,
      - `semantic_retry_action: "none" | "replan" | "try_next_candidate"` (Phase 1 uses `"none"`/`"replan"`),
      - `contract_id`.
    - Benchmark mode (`eval_mode == "benchmark"`):
      - Validates entity (`intent.primary_entities` vs `contract.entity` and `entity_table` usage).
      - Validates metric key + normalized expression + analytic template.
      - Validates join path against `required_tables` and `allowed_join_paths`.
    - Interactive mode:
      - Still attaches semantic fields but does **not** trigger additional retries.

- Semantic-aware routing:
  - `langgraph_integration/orchestrator.py: route_validation_result`:
    - Reads:
      - `validation_result.semantic_status`,
      - `validation_result.semantic_retry_action`,
      - `semantic_retry_count`, `max_semantic_retries`,
      - `plan_attempt_count`, `max_total_plans`,
      - `eval_mode`.
    - In benchmark mode:
      - For semantic failures (`ENTITY_MISMATCH`, `METRIC_MISMATCH`, `JOIN_PATH_INVALID`, `NO_VALID_JOIN_PATH`):
        - If `semantic_retry_action == "replan"` and budgets allow:
          - Maps to existing retry actions:
            - Join-path issues → `"try_next_candidate"`.
            - Entity/metric mismatches → `"replan_with_aggregation"`.
          - Increments `semantic_retry_count`.
      - Enforces:
        - `semantic_retry_count <= max_semantic_retries`.
        - `plan_attempt_count + semantic_retry_count <= max_total_plans`.
      - When exhausted, sets `stop_reason = "max_semantic_retries"`.
    - In interactive mode:
      - Semantic findings are logging-only; retry behavior remains unchanged.

- Evaluation harness & scoring:
  - `eval/run_benchmark.py`:
    - For each query, now captures semantic fields from the orchestrator response:
      - Reads `result["validation_result"]` (if present) and copies:
        - `semantic_status`,
        - `semantic_failure_reasons`,
        - `semantic_retry_action`,
        - `contract_id`.
      - Copies `semantic_retry_count` from the top-level result when present.
    - Emits per-query artifacts with a stable shape:
      - Success path: all semantic fields populated when available.
      - Exception path: semantic keys present with `None` / empty defaults.
  - `eval/scoring/score_run.py`:
    - Extends scoring metrics with:
      - `entity_metric_join_correct_count`:
        - Number of queries where `status == "success"` and `semantic_status == "OK"`.
      - `entity_metric_join_correct_rate`:
        - That count divided by total queries (as `"%.1f%%"`).
    - Keeps existing metrics unchanged:
      - Success rate,
      - SQL execution rate,
      - Non-empty results rate,
      - Failure categorization.
    - CLI (`python -m eval.scoring.score_run ...`) now prints:
      - `Semantic Correctness (entity+metric+join): <count> (<rate>)`.

---

## Consequences

### Benefits

- **Semantic correctness becomes structural**:
  - Entity, metric, and join path are checked against explicit contracts.
  - Benchmark-mode answers that pass are strongly constrained to the intended semantics.

- **Reduced “confident nonsense”**:
  - SQL that executes but violates contracts is marked as semantically failing.
  - Semantic failures can trigger replanning within strict budgets.

- **Explainable, localizable failures**:
  - `semantic_status` and `semantic_failure_reasons` give precise reasons:
    - Wrong entity,
    - Wrong metric or template,
    - Invalid or missing join path,
    - Unsupported metric/template.

- **Thesis-ready metrics for H2a**:
  - `entity_metric_join_correct_rate` explicitly measures semantic correctness.
  - Structural success alone is no longer treated as proof of performance.

- **Backwards-compatible**:
  - Interactive / production callers:
    - See the same high-level behavior and API surface.
    - Semantic fields remain internal and optional.
  - Eval harness:
    - Older runs without semantic fields still score successfully; semantic metrics fall back to zero.

### Trade-offs & Risks

- **Latency**:
  - Benchmark mode adds semantic validation and possible replans.
  - Mitigated by:
    - `max_semantic_retries` = 2,
    - Shared `max_total_plans`,
    - Existing LLM and validation/exec budgets,
    - `process_query()` timeout.

- **Complexity**:
  - More fields in `BaseState` and validation results.
  - Additional logic in `route_validation_result`.
  - Mitigated by:
    - Reusing existing nodes and budgets (no new graph edges).
    - Encapsulating semantic logic in `result_validator`.

- **Contract maintenance**:
  - Benchmark datasets now require curated `*.contracts.json`.
  - Any schema changes must be reflected in contracts and metric mappings.

---

## Implementation Notes

Key implementation touchpoints:

- `langgraph_integration/contracts/state.py`
- `langgraph_integration/orchestrator.py`
- `langgraph_integration/agents/result_validator/agent.py`
- `langgraph_integration/agents/discovery/agent.py`
- `langgraph_integration/agents/join_sql/agent.py`
- `langgraph_integration/api.py`
- `langgraph_integration/contracts/semantic_contracts.py`
- `eval/run_benchmark.py`
- `eval/scoring/score_run.py`
- `eval/datasets/*.contracts.json`

This ADR supersedes the *structural-only* evaluation described in ADR 0026 by adding semantic contracts and correctness scoring, while remaining compatible with that architecture.

