from __future__ import annotations

from typing import Any, Dict, List

import pytest

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.tools import capability_tools


class DummyOrchestrator:
    """Minimal orchestrator stub for capability tool tests."""

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
@pytest.mark.parametrize(
    ("tool_attr", "expected_agent_name"),
    [
        ("interpret_query_tool", "parse_intent"),
        ("discover_schema_tool", "discovery"),
        ("plan_sql_tool", "join_sql"),
        ("validate_sql_tool", "validate_sql"),
        ("execute_sql_tool", "exec_recovery"),
        ("evaluate_result_tool", "result_validator"),
        ("finalize_answer_tool", "answer"),
    ],
)
async def test_capability_tools_populate_envelope_fields(
    monkeypatch: pytest.MonkeyPatch,
    tool_attr: str,
    expected_agent_name: str,
) -> None:
    dummy = DummyOrchestrator()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: dummy, raising=True
    )

    tool = getattr(capability_tools, tool_attr)

    state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }
    if tool_attr in {
        "plan_sql_tool",
        "validate_sql_tool",
        "execute_sql_tool",
        "evaluate_result_tool",
        "finalize_answer_tool",
    }:
        state["sql_query"] = "SELECT COUNT(*) AS total_orders FROM dbo.orders"
        state["validation_result"] = {"is_valid": True}
        state["exec_result"] = {
            "ok": True,
            "data": [{"total_orders": 42}],
            "row_count": 1,
            "execution_time_ms": 5,
            "truncated": False,
            "warnings": [],
        }

    result = await tool(state)

    assert dummy.calls, "expected orchestrator.invoke_agent to be called"
    assert dummy.calls[0] == expected_agent_name

    # Shared envelope fields
    assert "tool_output" in result
    assert "progress_signal" in result
    assert "suggested_next_actions" in result
    assert "last_tool_result" in result
    assert "last_tool_name" in result
    assert "last_tool_progress_signal" in result


@pytest.mark.asyncio
async def test_execute_sql_tool_enforces_validation_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyOrchestrator()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: dummy, raising=True
    )

    # Missing or invalid validation_result should trigger the hard gate.
    state: BaseState = {
        "user_input": "How many orders did we have last month?",
        "sql_query": "SELECT COUNT(*) AS total_orders FROM dbo.orders",
        # validation_result intentionally omitted / invalid
        "validation_result": {"is_valid": False},
    }

    result = await capability_tools.execute_sql_tool(state)

    # Hard gate: ExecAndRecoveryAgent must not be invoked.
    assert "exec_recovery" not in dummy.calls

    error_info = result.get("error_info") or {}
    assert error_info.get("type") == "VALIDATION_GATE_VIOLATION"
    assert result.get("progress_signal") == "negative"
    assert "replan" in (result.get("suggested_next_actions") or [])

