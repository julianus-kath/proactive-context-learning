"""
Tests for JoinPlanAndSQLAgent join planning metadata and SQL generation.

These tests focus on the contract-level behaviour introduced for
plan_status / plan_issues and analytic template gating, without
calling external MCP or LLM services.
"""

import os
import sys
from typing import Any, Dict

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.contracts.state import BaseState


def _base_intent() -> Dict[str, Any]:
    """Minimal parsed intent skeleton used in tests."""
    return {
        "operation": "query",
        "primary_entities": ["customers"],
        "metrics": ["count"],
        "filters": [],
        "time_window": None,
        "keywords_for_discovery": ["customers"],
        "raw_query": "How many customers do we have?",
        "confidence": 0.9,
        "analytic_template": None,
        "required_action": None,
        "template_params": {},
    }


def _base_join_plan(plan_status: str = "ok") -> Dict[str, Any]:
    """Minimal join_plan structure with planner metadata."""
    return {
        "strategy": "template",
        "fact_table": "dbo.Customers",
        "primary_table": "dbo.Customers",
        "joins": [],
        "fk_hints": [],
        "metric_candidates": {},
        "date_columns": [],
        "entity_keys": {},
        "dimensions": {},
        "filters": [],
        "time_window": None,
        "required_action": None,
        "fact_estimated_rows": 100,
        "plan_status": plan_status,
        "plan_confidence": 0.9 if plan_status == "ok" else 0.0,
        "plan_issues": [],
    }


@pytest.mark.asyncio
async def test_generate_sql_count_entity_ok_plan_produces_sql_and_metadata():
    """
    Analytic COUNT_ENTITY intents with an OK join plan should
    produce SQL and expose template/plan metadata on join_plan.
    """
    agent = JoinPlanAndSQLAgent()

    intent = _base_intent()
    intent["analytic_template"] = "COUNT_ENTITY"
    intent["template_params"] = {"entity": "customers"}

    state: BaseState = {
        "intent": intent,
        "join_plan": _base_join_plan(plan_status="ok"),
        "relevant_tables": ["dbo.Customers"],
    }

    result = await agent._generate_sql_node(state)

    sql = (result.get("sql_query") or "").strip()
    assert sql, "SQL should be produced for COUNT_ENTITY with ok plan"
    assert sql.upper().startswith("SELECT")
    assert "COUNT" in sql.upper()

    join_plan_out = result.get("join_plan") or {}
    assert join_plan_out.get("template") == "COUNT_ENTITY"
    # Successful analytic plan should keep or normalise to an OK status.
    assert join_plan_out.get("plan_status") in {None, "ok", "exploratory"}
    assert result.get("error_info") is None


@pytest.mark.asyncio
async def test_generate_sql_declines_for_incomplete_analytic_plan():
    """
    When join_plan.plan_status is incomplete for an analytic intent,
    _generate_sql_node must decline SQL generation and surface a
    PLAN_INCOMPLETE-style error instead of guessing SQL.
    """
    agent = JoinPlanAndSQLAgent()

    intent = _base_intent()
    intent["analytic_template"] = "COUNT_ENTITY"
    intent["template_params"] = {"entity": "customers"}

    state: BaseState = {
        "intent": intent,
        # Pre-mark the plan as incomplete to simulate planning failure.
        "join_plan": _base_join_plan(plan_status="incomplete"),
        "relevant_tables": ["dbo.Customers"],
    }

    result = await agent._generate_sql_node(state)

    sql = (result.get("sql_query") or "").strip()
    assert not sql, "SQL should not be produced for incomplete analytic plan"

    error_info = result.get("error_info") or {}
    assert error_info.get("type") == "PLAN_INCOMPLETE"

    join_plan_out = result.get("join_plan") or {}
    assert join_plan_out.get("plan_status") in {"incomplete", "unsupported"}
    assert join_plan_out.get("plan_confidence") == 0.0
    issues = join_plan_out.get("plan_issues") or []
    assert any(issue.get("type") == "PLAN_INCOMPLETE" for issue in issues)


@pytest.mark.asyncio
async def test_topk_by_metric_template_missing_params_marks_plan_incomplete():
    """
    TOP_K_BY_METRIC template must fail hard (no SQL) when required
    template_params are missing, and mark the join plan as incomplete
    with structured plan_issues.
    """
    agent = JoinPlanAndSQLAgent()

    intent = _base_intent()
    intent["analytic_template"] = "TOP_K_BY_METRIC"
    # Deliberately omit mandatory metric/group_by params in interactive mode.
    intent["template_params"] = {"top_k": 5}

    join_plan = _base_join_plan(plan_status="ok")

    state: BaseState = {
        "intent": intent,
        "join_plan": join_plan,
        "relevant_tables": ["dbo.Customers"],
    }

    result = await agent._generate_sql_node(state)

    sql = (result.get("sql_query") or "").strip()
    assert not sql, "SQL should not be produced when TOP_K_BY_METRIC params are missing"

    error_info = result.get("error_info") or {}
    # Either the specific template error or the analytic-template wrapper.
    assert error_info.get("type") in {"TEMPLATE_PARAMS_MISSING", "ANALYTIC_TEMPLATE_FAILED"}

    join_plan_out = result.get("join_plan") or {}
    assert join_plan_out.get("plan_status") == "incomplete"
    assert join_plan_out.get("plan_confidence") == 0.0

    issue_types = {issue.get("type") for issue in (join_plan_out.get("plan_issues") or [])}
    # The planner should surface both the template-parameter issue and the
    # higher-level analytic template failure to the supervisor.
    assert "TEMPLATE_PARAMS_MISSING" in issue_types
    assert "ANALYTIC_TEMPLATE_FAILED" in issue_types

