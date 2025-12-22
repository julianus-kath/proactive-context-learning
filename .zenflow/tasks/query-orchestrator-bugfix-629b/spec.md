# Query Orchestrator Bugfix – Technical Specification

## Difficulty
- **Level**: Medium – localized bug fix with multiple call sites and state-shape invariants to preserve across the orchestrator graph.

## Technical Context
- **Language / runtime**: Python 3.x async application.
- **Core module**: `langgraph_integration/orchestrator.py` (`QueryOrchestrator`), plus related state contracts in `langgraph_integration/contracts/state.py`.
- **Key dependencies**:
  - `langgraph` (`StateGraph`, node/edge orchestration).
  - `langchain_openai.ChatOpenAI` for LLM calls.
  - `pydantic` models `ResponseEnvelope` and `ErrorInfo` for normalized `exec_result`/`error_info` payloads.
- **State model**:
  - `BaseState` defines `error_info: Dict[str, Any]` (logically treated as `Optional[Dict[str, Any]]` in practice).
  - Orchestrator nodes and agents pass `error_info` through the graph to control routing and user-visible error responses.
- **Execution model**:
  - The orchestrator builds a `StateGraph` with async node functions for discovery, planning, execution/recovery, validation, and answering.
  - Budget and retry “circuit breakers” (LLM budget, plan retries, exec attempts) short‑circuit the pipeline by setting `error_info` and switching the `intent` into a clarification mode.

## Current Behavior and Bug
- **Intended behavior**:
  - When budgets or retry limits are exceeded, the orchestrator should:
    - Set `state["intent"]` to a clarification‑style intent (`operation="clarify"`, `needs_clarification=True`, etc.).
    - Populate `state["error_info"]` with a structured dict (e.g., `{"type": "LLM_BUDGET_EXCEEDED", ...}`).
    - Allow the graph to continue to the `answer` node where `error_info` is rendered into a user‑friendly explanation (no internal crash).
- **Actual behavior**:
  - Several code paths assume `state["error_info"]` is always a dict and use the pattern:
    ```python
    state.setdefault("error_info", {})
    state["error_info"].update({...})
    ```
  - Elsewhere in the pipeline, `error_info` may legitimately be set to `None` to signal “no error” after a successful recovery or execution (e.g., inside `_exec_recovery_node`).
  - If a previous node sets `state["error_info"] = None`, the subsequent `setdefault("error_info", {})` does **not** overwrite the key (because the key exists), leaving `state["error_info"]` as `None`.
  - The following `.update({...})` call then raises:
    - `"'NoneType' object has no attribute 'update'"`, which surfaces as a `PIPELINE_ERROR` instead of a bounded, structured error response.
- **Known problematic sites in `orchestrator.py`**:
  1. `_check_llm_budget` (LLM budget exceeded branch).
  2. `route_validation_result`:
     - Global plan budget exceeded (`plan_attempt_count >= max_total_plans`).
     - Per‑candidate retries exceeded (`retry_attempt_count >= max_retries_per_candidate_set`).
  3. `_exec_recovery_node`:
     - Global execution budget exceeded (`exec_attempt_count >= max_exec_attempts`).
- **Related pattern outside orchestrator**:
  - `langgraph_integration/agents/discovery/agent.py` also uses `state.setdefault("error_info", {})` + `.update(...)` in the `NO_CANDIDATES_LEFT` path. This should be kept in mind as a follow‑up hardening target but is out of scope for the minimal orchestrator‑focused fix.

## Implementation Approach

### Invariant for `error_info`
- Establish a simple invariant for orchestrator‑owned state writes:
  - At any point where we write/update `state["error_info"]` in orchestrator control code, we ensure it is either:
    - A `dict` matching the `ErrorInfo` shape, or
    - `None` / absent (meaning “no error”).
  - We **never** rely on `setdefault` with a possibly non‑dict existing value.

### Normalization Pattern
- Replace each problematic `setdefault` + `update` block in `orchestrator.py` with an explicit normalization pattern:
  ```python
  error_info = state.get("error_info")
  if not isinstance(error_info, dict):
      error_info = {}
  error_info.update({
      "type": "...",
      "message": "...",
      # any additional fields
  })
  state["error_info"] = error_info
  ```
- This achieves:
  - Correct behavior when `error_info` is `None`, a previous dict, or any other non‑dict value (we coerce to a fresh dict).
  - Preservation/augmentation of existing error context when it is already a dict.
  - Alignment with `BaseState`’s expectation that `error_info` be a dict when populated.

### Targeted Code Changes
- **File**: `langgraph_integration/orchestrator.py`

1. `_check_llm_budget`
   - **Current**: uses `state.setdefault("error_info", {})` + `.update({...})` when `total_llm_calls >= max_llm_calls`.
   - **Change**:
     - Replace with the normalization pattern above, setting:
       - `type="LLM_BUDGET_EXCEEDED"`.
       - `message` explaining the global LLM call budget exhaustion.
       - `stage` (current stage string).
       - `total_llm_calls`.
   - **Rationale**:
     - Prevents crashes when the LLM budget check fires after some node has set `error_info` to `None`.
     - Keeps the “clarify” intent routing semantics intact.

2. `route_validation_result`
   - **Global plan budget exceeded branch** (`plan_attempt >= max_plans`):
     - **Current**: normalizes `intent` to a clarification style then calls `state.setdefault("error_info", {})` + `.update({...})`.
     - **Change**: replace the `setdefault`/`update` pair with the normalization pattern, using:
       - `type="MAX_RETRIES_EXCEEDED"`.
       - `message` describing exhaustion of discovery/planning cycles.
   - **Per‑candidate retries exceeded branch** (`retry_attempt >= max_retries`):
     - **Current**: same `setdefault` + `.update({...})` pattern with a similar `MAX_RETRIES_EXCEEDED` payload.
     - **Change**: same normalization pattern as above.
   - **Rationale**:
     - Ensures that complex retry/plan loops fail gracefully with a structured error instead of raising a `NoneType.update` error when previous stages have cleared `error_info`.

3. `_exec_recovery_node`
   - **Global execution budget exceeded branch** (`exec_attempt >= max_exec`):
     - **Current**: logs a warning and uses `state.setdefault("error_info", {})` + `.update({...})` with:
       - `type="MAX_EXEC_ATTEMPTS_EXCEEDED"`.
       - `message` summarizing exec/repair attempts exhaustion.
     - **Change**: replace with the normalization pattern.
   - **Interaction with success path**:
     - On successful execution, this node already sets `state["error_info"] = None` to clear previous errors and normalize the `intent.operation` back to `"query"`.
     - With the new pattern, a subsequent budget check (or another node) that wants to set an error will safely overwrite that `None` with a dict instead of crashing.

4. (Optional Hardening – later step, not required to fix the observed error)
   - **File**: `langgraph_integration/agents/discovery/agent.py`
   - **Site**: `NO_CANDIDATES_LEFT` branch near the bottom of the discovery pipeline, which also uses `state.setdefault("error_info", {})` + `.update({...})`.
   - **Potential change**: apply the same normalization pattern to avoid similar issues if `error_info` is ever `None` when discovery exhausts candidates.

### Use of Existing Helpers
- The module already defines `_normalize_error_info(self, error: Any) -> Optional[Dict[str, Any]]` to coerce arbitrary error payloads into the `ErrorInfoModel` schema.
- For these specific budget/retry branches, we are constructing well‑formed dicts directly, so the explicit normalization helper is not strictly required.
- However, the broader invariant is:
  - When consuming `error_info` from agents or external components, continue using `_normalize_error_info`.
  - When *writing* new orchestrator‑owned error payloads, ensure they are dicts and robust against previous `None` assignments using the pattern above.

## Source Code Structure Changes
- **Modified files**:
  - `langgraph_integration/orchestrator.py`:
    - `_check_llm_budget`: replace `setdefault`/`update` usage with `error_info` normalization.
    - `route_validation_result`: update both `MAX_RETRIES_EXCEEDED` branches to use `error_info` normalization.
    - `_exec_recovery_node`: update `MAX_EXEC_ATTEMPTS_EXCEEDED` branch to use `error_info` normalization.
- **No new modules or classes**:
  - All changes are in‑place within the existing orchestrator implementation.
  - No changes to the public constructor or interface of `QueryOrchestrator`.

## Data Model / API / Interface Changes
- **Internal state semantics**:
  - `BaseState.error_info` continues to be treated as an optional dict.
  - The orchestrator guarantees:
    - If `error_info` is present and non‑`None`, it is a dict compatible with `ErrorInfoModel`.
    - `error_info` may be explicitly set to `None` to clear an error, but any later “set error” operation will replace or normalize it to a dict.
- **External API / ResponseEnvelope**:
  - The top‑level response envelope continues to expose `error_info` as defined by `ErrorInfoModel`.
  - Behavior change is only in failure mode:
    - Previously: some budget/limit paths could crash with a `PIPELINE_ERROR` due to `NoneType.update`.
    - After fix: clients receive structured error types:
      - `LLM_BUDGET_EXCEEDED`
      - `MAX_RETRIES_EXCEEDED`
      - `MAX_EXEC_ATTEMPTS_EXCEEDED`
    - along with clarification‑style `intent` and a user‑friendly explanation from the `answer` node.
- **No contract changes for downstream agents**:
  - Discovery, Join/SQL, Exec/Recovery, and Answer agents continue to see `error_info` as before; the only difference is the absence of unexpected `PIPELINE_ERROR` crashes.

## Verification Approach

### Static / Build Verification
- Run Python compilation on orchestrator to catch syntax issues:
  - `python -m compileall langgraph_integration/orchestrator.py`

### Targeted Unit / Integration Tests
- **Existing orchestrator tests**:
  - Re‑run relevant suites to ensure no regressions:
    - `pytest tests/test_orchestrator.py`
    - `pytest tests/test_orchestrator_integration.py`
    - `pytest tests/test_orchestrator_result_validator_integration.py`
    - `pytest tests/test_full_pipeline_e2e.py`
- **New or extended tests (if needed)**:
  - Add small, focused tests that:
    1. Initialize a state with `error_info = None`, then trigger:
       - `_check_llm_budget` with an exceeded budget.
       - `route_validation_result` with `plan_attempt_count >= max_total_plans`.
       - `route_validation_result` with `retry_attempt_count >= max_retries_per_candidate_set`.
       - `_exec_recovery_node` with `exec_attempt_count >= max_exec_attempts`.
    2. Assert that:
       - No exceptions are raised.
       - `state["error_info"]` is a dict with the expected `type` and `message`.
       - The graph routes to the expected node (`answer` or the next step).

### End‑to‑End Manual Verification
- Restart the system and exercise a real query that previously triggered the pipeline error:
  - From the project root:
    - `./start_all_services_mac.sh`
  - Then issue a test query, for example:
    ```bash
    curl -s -X POST http://localhost:5001/process_query \
      -H 'Content-Type: application/json' \
      -d '{"user_input":"When will the product Chai need to be reordered based on current stock levels and sales velocity?","api_key":"supersecretapikey"}' \
      | jq
    ```
- Expected results after the fix:
  - The request completes without internal `PIPELINE_ERROR`.
  - When a budget or retry limit is exceeded, the response contains:
    - A structured `error_info` with one of the specific types above.
    - A clarification‑style message guiding the user, instead of an internal server error.

