import json
import os
import sys
from typing import Any, Dict

import pytest

# Add langgraph_integration to path (mirror existing tests)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph_integration import supervisor as sup
from langgraph_integration.contracts.state import BaseState
from langgraph_integration.supervisor import SupervisorConfig, run_supervisor
from langgraph_integration.tools.capability_tools import execute_sql_tool


@pytest.mark.asyncio
async def test_execute_sql_tool_blocks_when_sql_not_validated() -> None:
    """
    execute_sql_tool must enforce the validation gate and refuse to
    touch ExecAndRecoveryAgent when validation_result.is_valid is not True.
    """
    state: BaseState = {
        "sql_query": "SELECT 1",
        "validation_result": {"is_valid": False},
    }

    result = await execute_sql_tool(state)

    # The tool should attach a structured validation-gate error.
    error_info = result.get("error_info") or {}
    assert error_info.get("type") == "VALIDATION_GATE_VIOLATION"

    # Progress and suggested actions should steer the supervisor away from execution.
    assert result.get("progress_signal") == "negative"
    assert result.get("suggested_next_actions") == ["replan", "clarify", "stop"]

    # It should not fabricate a new exec_result in the failure path.
    assert "exec_result" in result.get("tool_output", {})


@pytest.mark.asyncio
async def test_supervisor_respects_step_budget_without_invoking_tools() -> None:
    """
    When max_supervisor_steps is zero, the supervisor must stop immediately
    with a budget_exhausted stop_reason and emit a budget trace entry,
    without calling any capability tools.
    """
    initial: BaseState = {
        "user_input": "dummy",
        "messages": [],
        # Pre-populate a final_response so _ensure_final_answer is a no-op.
        "final_response": "pre-computed answer",
        "total_llm_calls": 0,
        "max_llm_calls": 5,
    }

    config = SupervisorConfig(
        max_supervisor_steps=0,
        max_llm_calls_total=None,
        max_no_progress_repeats=3,
    )

    result = await run_supervisor(initial, config=config)

    assert result.get("stop_reason") == "budget_exhausted"
    assert int(result.get("supervisor_step_count", 0)) == 0

    trace = result.get("supervisor_trace") or []
    assert trace, "supervisor_trace should contain at least one entry"
    last_entry: Dict[str, Any] = trace[-1]
    assert last_entry.get("tool") == "__budget_stop__"
    budgets = last_entry.get("budgets") or {}
    assert budgets.get("max_supervisor_steps") == 0


@pytest.mark.asyncio
async def test_supervisor_respects_llm_budget_without_invoking_tools() -> None:
    """
    When the global LLM budget is already exhausted, the supervisor must
    stop before invoking any tools and normalize stop_reason to budget_exhausted.
    """
    initial: BaseState = {
        "user_input": "dummy",
        "messages": [],
        "final_response": "pre-computed answer",
        # Exceed the LLM budget before the supervisor loop starts.
        "total_llm_calls": 10,
        "max_llm_calls": 5,
    }

    config = SupervisorConfig(
        max_supervisor_steps=5,
        max_llm_calls_total=None,
        max_no_progress_repeats=3,
    )

    result = await run_supervisor(initial, config=config)

    assert result.get("stop_reason") == "budget_exhausted"
    assert int(result.get("supervisor_step_count", 0)) == 0

    trace = result.get("supervisor_trace") or []
    assert trace, "supervisor_trace should contain at least one entry"
    last_entry: Dict[str, Any] = trace[-1]
    assert last_entry.get("tool") == "__budget_stop__"
    budgets = last_entry.get("budgets") or {}
    assert budgets.get("max_llm_calls") == 5


def test_select_next_tool_routes_based_on_retry_action() -> None:
    """
    _select_next_tool must honor ResultValidator retry_action hints
    when deciding what to do after evaluate_result.
    """
    state: BaseState = {"validation_result": {"retry_action": "accept"}}
    assert sup._select_next_tool(state, "evaluate_result") == "finalize_answer"

    state["validation_result"]["retry_action"] = "ask_user"
    assert sup._select_next_tool(state, "evaluate_result") == "finalize_answer"

    state["validation_result"]["retry_action"] = "try_next_candidate"
    assert sup._select_next_tool(state, "evaluate_result") == "discover_schema"

    state["validation_result"]["retry_action"] = "replan_with_aggregation"
    assert sup._select_next_tool(state, "evaluate_result") == "plan_sql"

    state["validation_result"]["retry_action"] = "replan_with_filter"
    assert sup._select_next_tool(state, "evaluate_result") == "plan_sql"


@pytest.mark.asyncio
async def test_llm_select_next_tool_summary_includes_join_plan_metadata_and_instructions() -> None:
    """
    _llm_select_next_tool must surface join plan metadata and any
    existing plan_sql_instructions in the LLM summary payload.
    """

    class _DummyLLM:
        def __init__(self) -> None:
            self.last_messages = None

        async def ainvoke(self, messages):  # type: ignore[override]
            self.last_messages = messages

            class _Result:
                def __init__(self) -> None:
                    self.content = '{"next_tool": "__STOP__", "plan_sql_instructions": null}'

            return _Result()

    config = SupervisorConfig(
        max_supervisor_steps=5,
        max_llm_calls_total=None,
        max_no_progress_repeats=3,
    )
    supervisor = sup.ReactSupervisor(config=config)
    dummy_llm = _DummyLLM()
    supervisor.llm = dummy_llm  # type: ignore[assignment]

    join_plan = {
        "strategy": "template",
        "fact_table": "dbo.FactOrders",
        "primary_table": "dbo.FactOrders",
        "plan_status": "incomplete",
        "plan_confidence": 0.0,
        "plan_issues": [],
        "template": "sum_with_period",
    }
    plan_sql_instructions = {
        "preferred_fact_table": "dbo.FactOrdersAlt",
        "avoid_tables": ["dbo.BadFact"],
        "mode": "analytic",
        "narrow_discovery_keywords": ["orders"],
        "notes": "unit-test",
    }

    state: BaseState = {
        "intent": {
            "operation": "query",
            "primary_entities": ["orders"],
            "metrics": ["sum"],
        },
        "join_plan": join_plan,
        "plan_sql_instructions": plan_sql_instructions,
        "validation_result": {},
        "exec_result": {},
        "error_info": {"type": "FACT_NOT_FOUND", "message": "No fact table"},
        "supervisor_step_count": 0,
        "max_supervisor_steps": 5,
        "total_llm_calls": 0,
        "max_llm_calls": 10,
        "no_progress_repeat_count": 0,
        "progress_signal": "negative",
        "suggested_next_actions": ["rediscover", "replan"],
    }

    await supervisor._llm_select_next_tool(state, last_tool_name="plan_sql")

    messages = getattr(dummy_llm, "last_messages", None)
    assert isinstance(messages, list) and len(messages) == 2

    user_content = messages[1]["content"]
    prefix = "Current state summary (JSON):\n"
    start = user_content.find(prefix)
    assert start != -1
    start += len(prefix)
    end = user_content.find("\n\n", start)
    summary_json = user_content[start:end]
    summary = json.loads(summary_json)

    assert summary["join_plan_status"] == "incomplete"
    assert summary["join_plan_strategy"] == "template"
    assert summary["join_plan_fact_table"] == "dbo.FactOrders"
    assert summary["join_plan_template"] == "sum_with_period"
    assert summary["error_info_type"] == "FACT_NOT_FOUND"
    assert summary["plan_sql_instructions"]["preferred_fact_table"] == "dbo.FactOrdersAlt"
