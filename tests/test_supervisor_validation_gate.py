from __future__ import annotations

from typing import Any, Dict, List

import pytest

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.supervisor import SupervisorConfig, run_supervisor
from langgraph_integration.tools import capability_tools


class StubOrchestratorInvalidValidation:
    """Orchestrator stub where SQL validation always fails."""

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
        elif agent_name == "join_sql":
            new_state["sql_query"] = "SELECT COUNT(*) AS total_orders FROM dbo.orders"
        elif agent_name == "validate_sql":
            # Always mark SQL as invalid
            new_state["validation_result"] = {"is_valid": False, "error_type": "TEST_INVALID"}
        elif agent_name == "exec_recovery":
            # Should ideally never be called in this stub since validation is invalid.
            new_state["exec_result"] = {
                "ok": False,
                "data": [],
                "row_count": 0,
                "execution_time_ms": 1,
                "truncated": False,
                "warnings": [],
            }

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


class StubOrchestratorValidValidation(StubOrchestratorInvalidValidation):
    """Orchestrator stub where SQL validation succeeds."""

    async def invoke_agent(
        self,
        agent_name: str,
        state: Dict[str, Any],
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        result = await super().invoke_agent(agent_name, state, options)
        output_state = result["output_state"]
        if agent_name == "validate_sql":
            output_state["validation_result"] = {"is_valid": True}
        return result


@pytest.mark.asyncio
async def test_supervisor_never_calls_execute_when_validation_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When validation_result.is_valid is False, the supervisor policy should
    not select the execute_sql capability tool.
    """
    stub = StubOrchestratorInvalidValidation()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: stub, raising=True
    )

    initial_state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }
    config = SupervisorConfig(max_supervisor_steps=6, max_no_progress_repeats=2)

    result = await run_supervisor(initial_state, config=config)
    trace = result.get("supervisor_trace") or []
    tools_run = [entry.get("tool") for entry in trace]

    assert "execute_sql" not in tools_run


@pytest.mark.asyncio
async def test_supervisor_calls_execute_after_successful_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When validation_result.is_valid is True, the supervisor policy should
    eventually select execute_sql in the tool sequence.
    """
    stub = StubOrchestratorValidValidation()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: stub, raising=True
    )

    initial_state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }
    config = SupervisorConfig(max_supervisor_steps=10, max_no_progress_repeats=3)

    result = await run_supervisor(initial_state, config=config)
    trace = result.get("supervisor_trace") or []
    tools_run = [entry.get("tool") for entry in trace]

    assert "execute_sql" in tools_run

