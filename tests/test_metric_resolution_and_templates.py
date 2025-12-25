from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.contracts.semantic_contracts import QueryContract
from langgraph_integration.orchestrator import QueryOrchestrator


def _make_contract(
    analytic_template: str = "TOP_K_BY_METRIC",
) -> QueryContract:
    return QueryContract(
        query_id="Q1",
        entity="customer",
        entity_table="customers",
        metric_key="total_revenue",
        metric_expression_sql="SUM(order_details.unit_price * order_details.quantity)",
        required_tables=["customers", "orders", "order_details"],
        allowed_join_paths=[["customers", "orders", "order_details"]],
        analytic_template=analytic_template,
        metric_phrase="total revenue",
        top_k=3,
    )


def test_metric_resolution_anchors_intent_on_contract():
    """In benchmark mode, metric resolution should be deterministic from the QueryContract."""
    orchestrator = QueryOrchestrator()

    contract = _make_contract().model_dump(exclude_none=True)
    state = BaseState(
        user_input="Which customers have the highest total revenue?",
        intent={
            "operation": "query",
            "primary_entities": ["customer"],
            "metrics": ["revenue"],
        },
        eval_mode="benchmark",
        query_contract=contract,
    )

    updated = orchestrator._resolve_metric_and_template_from_contract(state)
    intent = updated.get("intent") or {}

    # Metrics are anchored to the contract key for downstream heuristics.
    assert intent.get("metrics") == ["total_revenue"]

    # Structured resolved_metrics contain the canonical SQL expression.
    resolved = intent.get("resolved_metrics") or []
    assert len(resolved) == 1
    metric = resolved[0]
    assert metric.get("key") == "total_revenue"
    assert metric.get("expression_sql") == _make_contract().metric_expression_sql

    # Analytic template and params are taken from the contract for Phase 1 templates.
    assert intent.get("analytic_template") == "TOP_K_BY_METRIC"
    params = intent.get("template_params") or {}
    assert params.get("metric_expression_sql") == _make_contract().metric_expression_sql
    assert params.get("top_k") == 3
    assert params.get("entity") == "customer"
    assert params.get("entity_table") == "customers"


def test_metric_resolution_marks_unsupported_templates_without_overriding():
    """
    For contracts whose analytic_template is outside Phase 1,
    the resolver should expose the contract template but not override the current one.
    """
    orchestrator = QueryOrchestrator()

    contract = _make_contract(analytic_template="AGG_OVER_PERIOD").model_dump(exclude_none=True)
    state = BaseState(
        user_input="Show total revenue by month.",
        intent={"operation": "query", "metrics": ["sum"], "primary_entities": ["order"]},
        eval_mode="benchmark",
        query_contract=contract,
    )

    updated = orchestrator._resolve_metric_and_template_from_contract(state)
    intent = updated.get("intent") or {}

    # Metrics are still anchored to the contract key.
    assert intent.get("metrics") == ["total_revenue"]

    # Analytic template is not forced to AGG_OVER_PERIOD (Phase 1 defers this).
    assert intent.get("analytic_template") is None
    assert intent.get("analytic_template_from_contract") == "AGG_OVER_PERIOD"


@patch("langgraph_integration.agents.join_sql.agent.get_shared_mcp_tool", autospec=True)
@pytest.mark.asyncio
async def test_count_entity_uses_contract_metric_expression(mock_mcp):
    """COUNT_ENTITY template should use the contract's metric_expression_sql in benchmark mode."""
    from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent

    mock_mcp.return_value = MagicMock()

    agent = JoinPlanAndSQLAgent()

    contract = QueryContract(
        query_id="Q_count",
        entity="order",
        entity_table="orders",
        metric_key="orders_placed",
        metric_expression_sql="COUNT(DISTINCT orders.order_id)",
        required_tables=["orders"],
        allowed_join_paths=[["orders"]],
        analytic_template="COUNT_ENTITY",
    ).model_dump(exclude_none=True)

    state = BaseState(
        intent={"analytic_template": "COUNT_ENTITY", "template_params": {"entity": "order"}},
        join_plan={"fact_table": "orders"},
        eval_mode="benchmark",
        query_contract=contract,
    )

    updated = await agent._generate_count_entity_sql(state)
    sql = (updated.get("sql_query") or "").upper()
    assert "COUNT(DISTINCT ORDERS.ORDER_ID)" in sql


@patch("langgraph_integration.agents.join_sql.agent.get_shared_mcp_tool", autospec=True)
@pytest.mark.asyncio
async def test_top_k_by_metric_uses_contract_metric_and_top_k(mock_mcp):
    """TOP_K_BY_METRIC template should use the contract's metric_expression_sql and top_k."""
    from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent

    mock_mcp.return_value = MagicMock()

    agent = JoinPlanAndSQLAgent()

    contract = _make_contract().model_dump(exclude_none=True)

    state = BaseState(
        intent={
            "analytic_template": "TOP_K_BY_METRIC",
            "template_params": {
                # Provide a simple group_by hint so the SQL skeleton is stable in tests.
                "group_by": "customers.CustomerID",
            },
        },
        join_plan={"fact_table": "orders"},
        eval_mode="benchmark",
        query_contract=contract,
    )

    updated = await agent._generate_top_k_by_metric_sql(state)
    sql = (updated.get("sql_query") or "")

    assert "SELECT TOP 3" in sql
    assert _make_contract().metric_expression_sql in sql
    assert "GROUP BY customers.CustomerID" in sql
    assert "ORDER BY metric DESC" in sql
