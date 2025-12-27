from __future__ import annotations

from typing import Any, Dict, List

import pytest

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.supervisor import SupervisorConfig, run_supervisor
from langgraph_integration.tools import capability_tools


class DummyOrchestrator:
    """Minimal orchestrator stub used by supervisor tests."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    async def invoke_agent(
        self,
        agent_name: str,
        state: Dict[str, Any],
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        self.calls.append(agent_name)
        new_state: Dict[str, Any] = dict(state)

        if agent_name == "parse_intent":
            new_state["intent"] = {
                "operation": "query",
                "primary_entities": ["orders"],
                "metrics": ["count"],
                "filters": [],
                "time_window": {},
                "keywords_for_discovery": ["orders"],
            }
        elif agent_name == "discovery":
            new_state["relevant_tables"] = ["dbo.orders"]
            new_state["schema_snippet"] = "dbo.orders(order_id int)"
            new_state["candidate_views"] = []
            new_state["column_index"] = {"dbo.orders": ["order_id"]}
        elif agent_name == "join_sql":
            new_state["join_plan"] = {
                "strategy": "single_table",
                "primary_table": "dbo.orders",
            }
            new_state["sql_query"] = "SELECT COUNT(*) AS total_orders FROM dbo.orders"
        elif agent_name == "validate_sql":
            vr = dict(new_state.get("validation_result") or {})
            vr.setdefault("is_valid", True)
            new_state["validation_result"] = vr
        elif agent_name == "exec_recovery":
            new_state["exec_result"] = {
                "ok": True,
                "data": [{"total_orders": 42}],
                "row_count": 1,
                "execution_time_ms": 5,
                "truncated": False,
                "warnings": [],
            }
            new_state.setdefault(
                "sql_query", "SELECT COUNT(*) AS total_orders FROM dbo.orders"
            )
        elif agent_name == "result_validator":
            vr = dict(new_state.get("validation_result") or {})
            vr.setdefault("valid", True)
            vr.setdefault("retry_action", "accept")
            if "is_valid" not in vr:
                vr["is_valid"] = bool(vr.get("valid"))
            new_state["validation_result"] = vr
        elif agent_name == "answer":
            new_state.setdefault("final_response", "There are 42 orders.")

        return {
            "agent": agent_name,
            "ok": True,
            "data": [],
            "row_count": new_state.get("exec_result", {}).get("row_count")
            if new_state.get("exec_result")
            else None,
            "execution_time_ms": 0,
            "truncated": False,
            "warnings": [],
            "error": None,
            "error_info": new_state.get("error_info"),
            "input_state": state,
            "output_state": new_state,
            "state_delta": {},
        }


@pytest.mark.asyncio
async def test_run_supervisor_populates_trace_and_runs_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyOrchestrator()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: dummy, raising=True
    )

    initial_state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }
    config = SupervisorConfig(max_supervisor_steps=10, max_no_progress_repeats=3)

    result = await run_supervisor(initial_state, config=config)

    # Supervisor should set orchestration_mode and produce a trace.
    assert result.get("orchestration_mode") == "react_supervisor"
    trace = result.get("supervisor_trace") or []
    assert isinstance(trace, list) and trace, "Expected non-empty supervisor_trace"

    first_entry = trace[0]
    assert "step" in first_entry
    assert "tool" in first_entry
    assert "thought_summary" in first_entry
    assert "observation_summary" in first_entry
    assert "budgets" in first_entry

    # Stop reason should be normalized to the stable set.
    assert result.get("stop_reason") in {
        "success",
        "clarify",
        "budget_exhausted",
        "fatal_error",
    }
    assert result.get("final_response"), "final_response should be populated"


@pytest.mark.asyncio
async def test_run_supervisor_respects_step_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyOrchestrator()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: dummy, raising=True
    )

    initial_state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }
    # Force a very small supervisor step budget.
    config = SupervisorConfig(max_supervisor_steps=1, max_no_progress_repeats=1)

    result = await run_supervisor(initial_state, config=config)

    assert int(result.get("supervisor_step_count", 0)) <= 1
    assert result.get("stop_reason") in {"budget_exhausted", "success"}
    assert result.get("final_response"), "final_response should be populated even on budget stop"

