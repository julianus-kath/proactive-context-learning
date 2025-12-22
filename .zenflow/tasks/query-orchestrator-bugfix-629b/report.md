## Implementation Report – query-orchestrator-bugfix-629b

**Date:** 2025-12-22  
**Files touched:**
- `langgraph_integration/contracts/state.py`
- `langgraph_integration/orchestrator.py`
- `langgraph_integration/agents/discovery/agent.py`
- `tests/test_state_passing_fix.py`
- `.zenflow/tasks/query-orchestrator-bugfix-629b/plan.md`

### What was implemented

- **State contract fix**
  - Updated `BaseState.error_info` in `langgraph_integration/contracts/state.py` from `Dict[str, Any]` to `Optional[Dict[str, Any]]` to match real runtime usage where agents frequently omit or clear `error_info` by setting it to `None`.
  - Added a shared helper `merge_error_info(state: BaseState, payload: Dict[str, Any])` in the same module. This normalizes `state["error_info"]` to a dict (creating one if `None` or missing) and then merges the provided payload. This is the central, reusable way to mutate `error_info` going forward.

- **Orchestrator error_info normalization**
  - Imported `merge_error_info` into `langgraph_integration/orchestrator.py` and replaced all direct `setdefault("error_info", {})` + `.update(...)` patterns with the helper:
    - In `_check_llm_budget`, when the global LLM call budget is exceeded, error metadata is now merged via `merge_error_info` instead of calling `.update` on a potentially `None` value.
    - In `route_validation_result`, both the global plan budget and per-candidate retry budget exhaustion branches now use `merge_error_info` to record `MAX_RETRIES_EXCEEDED` without assuming `error_info` is a dict.
    - In `_exec_recovery_node`, the global execution budget exhaustion branch now uses `merge_error_info` to set `MAX_EXEC_ATTEMPTS_EXCEEDED` safely.
  - These changes eliminate the `'NoneType' object has no attribute 'update'` failure mode anywhere in the orchestrator while preserving existing error payload shapes and routing behavior.

- **Discovery agent guardrail alignment**
  - Updated `langgraph_integration/agents/discovery/agent.py` to import `merge_error_info` and use it in the "no candidates left" guardrail inside `_filter_to_limit_node`:
    - Previously: `state.setdefault("error_info", {})` followed by `state["error_info"].update({...})`.
    - Now: a single `merge_error_info(state, {...})`, ensuring this path also respects `error_info` being optional and preventing the same `NoneType.update` crash if a prior node cleared `error_info`.

- **Unit test coverage for the helper**
  - Extended `tests/test_state_passing_fix.py` (within `TestStateContracts`) with `test_merge_error_info_handles_none`:
    - Constructs a `BaseState` with `error_info` explicitly set to `None`.
    - Calls `merge_error_info` with a simple payload.
    - Asserts that `error_info` becomes a dict and that `type` and `message` fields are correctly populated.
  - This directly verifies the normalization behavior that protects against the regression you're seeing.

- **Task plan tracking**
  - Updated `.zenflow/tasks/query-orchestrator-bugfix-629b/plan.md` to mark the “Implementation” step as completed (`[x]`), in line with the Zenflow task requirements.

### How the solution was tested

- **Targeted compilation**
  - Ran `python -m compileall` on the key modules to catch syntax or import errors early:
    - `python -m compileall langgraph_integration/contracts/state.py langgraph_integration/orchestrator.py langgraph_integration/agents/discovery/agent.py`
  - All compiled successfully with exit code 0.

- **Pytest runs**
  - Attempted a focused test run for the state/contracts and discovery guardrail logic:
    - Initial run without PYTHONPATH:
      - `pytest tests/test_state_passing_fix.py tests/test_discovery_guardrails.py -q`
      - Failed during collection because `langgraph_integration` was not on `PYTHONPATH` (ModuleNotFoundError).
    - Reran with `PYTHONPATH=.`:
      - `PYTHONPATH=. pytest tests/test_state_passing_fix.py tests/test_discovery_guardrails.py -q`
      - All tests in `tests/test_state_passing_fix.py`, including the new `test_merge_error_info_handles_none`, executed.
      - Several tests in `TestKeywordExtraction` and `TestSQLExtraction` failed due to missing OpenAI configuration (no `OPENAI_API_KEY` in environment), not due to code changes.
        - The failures originated from `DiscoveryAgent()` and `ExecAndRecoveryAgent()` initialization, where `ChatOpenAI` attempts to construct an OpenAI client and raises `openai.OpenAIError` if `OPENAI_API_KEY` is unset.
      - The added `merge_error_info` test passed, confirming normalization logic works as intended.
  - No linter runs were executed because there is no explicit lint configuration in the task instructions or repository root for this phase; changes are small and localized, and `compileall` plus unit tests provide basic validation.

### Biggest issues or challenges encountered

- **Environment-dependent test failures**
  - Many of the existing tests instantiate LangChain/OpenAI-backed agents directly. In this environment, no `OPENAI_API_KEY` is configured, so creating `DiscoveryAgent` or `ExecAndRecoveryAgent` triggers `openai.OpenAIError` during client construction.
  - This causes several unrelated tests in `tests/test_state_passing_fix.py` to fail even though the changes to `error_info` handling are correct and compile cleanly.
  - To avoid altering the project’s global testing strategy, I did not modify those tests or inject mock clients beyond what is already present (e.g., `tests/test_discovery_guardrails.py` already uses `unittest.mock.patch` to avoid real LLM calls).

- **Ensuring a single, reusable error-info pattern**
  - The original codebase duplicated the `setdefault("error_info", {})` + `.update(...)` pattern in multiple places (orchestrator and discovery agent), which was the root cause of the `NoneType.update` crash once `error_info` was allowed to be `None`.
  - The challenge was to fix the immediate bug without introducing new state-shape regressions:
    - The solution centralizes mutation behavior in `merge_error_info` and updates all known `.update` call sites to use it.
    - This keeps error payloads and routing semantics unchanged while making the system robust to `error_info` being absent or cleared.

Overall, the changes align the `BaseState` contract with real runtime usage (`error_info` is optional), remove all direct `.update` calls on `state["error_info"]`, and introduce a single helper that prevents the `'NoneType' object has no attribute 'update'` pipeline error from reoccurring in the orchestrator and discovery agent paths you highlighted.

