from __future__ import annotations

from typing import Any, Dict, List

import pytest

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.tools import capability_tools


class StubOrchestrator:
    """
    Small orchestrator stub that mimics the canonical pipeline for a single
    golden-path query. Used to compare pipeline vs. scripted capability tools
    without depending on external services.
    """

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
            vr.setdefault("valid", True)
            vr.setdefault("retry_action", "accept")
            if "is_valid" not in vr:
                vr["is_valid"] = bool(vr.get("valid"))
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

    async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate the canonical pipeline: intent → discovery → join_sql → validate → exec → result_validator → answer."""
        ordered_agents = [
            "parse_intent",
            "discovery",
            "join_sql",
            "validate_sql",
            "exec_recovery",
            "result_validator",
            "answer",
        ]
        current: Dict[str, Any] = dict(state)
        for name in ordered_agents:
            result = await self.invoke_agent(name, current)
            current = result.get("output_state") or current
        return current


@pytest.mark.asyncio
async def test_capability_tools_match_pipeline_on_golden_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    For a simple golden-path query, a scripted capability-tool sequence should
    reproduce the key intermediates that the canonical pipeline produces.
    """
    orchestrator = StubOrchestrator()
    monkeypatch.setattr(
        capability_tools, "get_orchestrator", lambda: orchestrator, raising=True
    )

    initial_state: BaseState = {
        "user_input": "How many orders did we have last month?",
    }

    # Canonical pipeline (stubbed) via orchestrator.ainvoke
    pipeline_result = await orchestrator.ainvoke(initial_state)

    # Scripted capability-tool sequence
    tool_state: BaseState = dict(initial_state)
    tool_state = await capability_tools.interpret_query_tool(tool_state)
    tool_state = await capability_tools.discover_schema_tool(tool_state)
    tool_state = await capability_tools.plan_sql_tool(tool_state)
    tool_state = await capability_tools.validate_sql_tool(tool_state)
    tool_state = await capability_tools.execute_sql_tool(tool_state)
    tool_state = await capability_tools.evaluate_result_tool(tool_state)
    tool_state = await capability_tools.finalize_answer_tool(tool_state)

    # Key invariants between pipeline and tools
    assert pipeline_result.get("intent") == tool_state.get("intent")
    assert pipeline_result.get("relevant_tables") == tool_state.get("relevant_tables")
    assert pipeline_result.get("sql_query") == tool_state.get("sql_query")

    pipeline_validation = pipeline_result.get("validation_result") or {}
    tools_validation = tool_state.get("validation_result") or {}
    assert bool(pipeline_validation.get("is_valid")) == bool(
        tools_validation.get("is_valid")
    )

    pipeline_exec = pipeline_result.get("exec_result") or {}
    tools_exec = tool_state.get("exec_result") or {}
    assert bool(pipeline_exec.get("ok")) == bool(tools_exec.get("ok"))

