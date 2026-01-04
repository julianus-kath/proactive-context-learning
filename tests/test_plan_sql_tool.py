"""
Tests for plan_sql_tool envelopes and progress signals.

These tests stub the orchestrator so that plan_sql_tool can be
exercised without invoking real agents or external services.
"""

import os
import sys
from typing import Any, Dict, List

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.tools import capability_tools


class _DummyOrchestrator:
    """Minimal orchestrator stub for plan_sql_tool tests."""

    def __init__(self, output_state: BaseState, error_info: Dict[str, Any] | None = None):
        self._output_state = output_state
        self._error_info = error_info or {}
        self.calls: List[str] = []

    async def invoke_agent(self, name: str, state: BaseState) -> Dict[str, Any]:  # type: ignore[override]
        self.calls.append(name)
        assert name == "join_sql"
        return {"output_state": self._output_state, "error_info": self._error_info}


@pytest.mark.asyncio
async def test_plan_sql_tool_ok_plan_positive_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    """OK join plans with non-empty SQL should produce positive progress."""
    join_plan = {
        "strategy": "template",
        "fact_table": "dbo.FactOrders",
        "primary_table": "dbo.FactOrders",
        "joins": [],
        "fk_hints": [],
        "metric_candidates": {"amount": 0.9},
        "date_columns": [],
        "entity_keys": {},
        "dimensions": {},
        "filters": [],
        "time_window": None,
        "required_action": "sum_with_period",
        "fact_estimated_rows": 1000,
        "plan_status": "ok",
        "plan_confidence": 0.8,
        "plan_issues": [],
        "template": "sum_with_period",
    }
    updated_state: BaseState = {
        "intent": {
            "operation": "query",
            "metrics": ["sum"],
            "analytic_template": "COUNT_ENTITY",
        },
        "join_plan": join_plan,
        "sql_query": "SELECT 1 AS value",
    }

    dummy = _DummyOrchestrator(updated_state, error_info=None)
    monkeypatch.setattr(capability_tools, "get_orchestrator", lambda: dummy)

    result = await capability_tools.plan_sql_tool(BaseState())

    # Tool envelope should include join plan metadata.
    tool_output = result.get("tool_output") or {}
    assert tool_output.get("join_plan", {}).get("plan_status") == "ok"
    assert tool_output.get("plan_status") == "ok"
    assert tool_output.get("plan_confidence") == 0.8
    assert tool_output.get("template") == "sum_with_period"
    assert tool_output.get("sql_query") == "SELECT 1 AS value"

    assert result.get("progress_signal") == "positive"
    assert result.get("suggested_next_actions") == ["replan", "stop"]

    envelope = result.get("last_tool_result") or {}
    assert envelope.get("tool_output") == tool_output
    assert envelope.get("progress_signal") == "positive"


@pytest.mark.asyncio
async def test_plan_sql_tool_incomplete_plan_negative_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Incomplete or unsupported join plans should be treated as negative
    progress so the supervisor can rediscover/replan instead of executing.
    """
    join_plan = {
        "strategy": "template",
        "fact_table": None,
        "primary_table": None,
        "joins": [],
        "fk_hints": [],
        "metric_candidates": {},
        "date_columns": [],
        "entity_keys": {},
        "dimensions": {},
        "filters": [],
        "time_window": None,
        "required_action": "sum_with_period",
        "fact_estimated_rows": None,
        "plan_status": "incomplete",
        "plan_confidence": 0.0,
        "plan_issues": [
            {"type": "FACT_NOT_FOUND", "severity": "error", "message": "No fact table", "details": {}}
        ],
        "template": None,
    }
    updated_state: BaseState = {
        "intent": {
            "operation": "query",
            "metrics": ["sum"],
            "analytic_template": "COUNT_ENTITY",
        },
        "join_plan": join_plan,
        "sql_query": "",
    }
    error_info = {"type": "FACT_NOT_FOUND", "message": "No fact table"}

    dummy = _DummyOrchestrator(updated_state, error_info=error_info)
    monkeypatch.setattr(capability_tools, "get_orchestrator", lambda: dummy)

    result = await capability_tools.plan_sql_tool(BaseState())

    tool_output = result.get("tool_output") or {}
    assert tool_output.get("plan_status") == "incomplete"
    assert tool_output.get("plan_confidence") == 0.0

    assert result.get("progress_signal") == "negative"
    assert result.get("suggested_next_actions") == ["rediscover", "replan", "clarify", "stop"]

    envelope = result.get("last_tool_result") or {}
    assert envelope.get("error_info", {}).get("type") == "FACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_plan_sql_tool_exploratory_plan_neutral_for_analytic_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exploratory/sample plans should be neutral progress when the intent
    is clearly analytic, even if they produce SQL.
    """
    join_plan = {
        "strategy": "joins",
        "fact_table": "dbo.FactOrders",
        "primary_table": "dbo.FactOrders",
        "joins": [],
        "fk_hints": [],
        "metric_candidates": {},
        "date_columns": [],
        "entity_keys": {},
        "dimensions": {},
        "filters": [],
        "time_window": None,
        "required_action": None,
        "fact_estimated_rows": 1000,
        "plan_status": "exploratory",
        "plan_confidence": None,
        "plan_issues": [],
        "template": None,
    }
    updated_state: BaseState = {
        "intent": {
            "operation": "query",
            "metrics": ["revenue"],
            "analytic_template": None,
        },
        "join_plan": join_plan,
        "sql_query": "SELECT TOP 10 * FROM dbo.FactOrders",
    }

    dummy = _DummyOrchestrator(updated_state, error_info=None)
    monkeypatch.setattr(capability_tools, "get_orchestrator", lambda: dummy)

    result = await capability_tools.plan_sql_tool(BaseState())

    tool_output = result.get("tool_output") or {}
    assert tool_output.get("plan_status") == "exploratory"
    assert result.get("progress_signal") == "neutral"
    assert result.get("suggested_next_actions") == ["replan", "rediscover", "clarify", "stop"]

