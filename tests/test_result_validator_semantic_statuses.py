"""
Semantic validator tests for ResultValidator / result_validator node.

These tests focus on benchmark-mode semantic fields:
- validation_result.semantic_status
- validation_result.semantic_failure_reasons
- validation_result.contract_id
- validation_result.semantic_retry_action
"""

from pathlib import Path

import pytest

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.contracts.semantic_contracts import QueryContract
from langgraph_integration.agents.result_validator.agent import build_result_validator_node


def _make_contract(**overrides) -> dict:
    base = QueryContract(
        query_id="Q1",
        entity="customer",
        entity_table="customers",
        metric_key="total_revenue",
        metric_expression_sql="SUM(order_details.unit_price * order_details.quantity)",
        required_tables=["customers", "orders", "order_details"],
        allowed_join_paths=[["customers", "orders", "order_details"]],
        analytic_template="TOP_K_BY_METRIC",
        metric_phrase="total revenue",
        top_k=3,
    )
    data = base.model_dump(exclude_none=True)
    data.update(overrides)
    return data


def _base_exec_result() -> dict:
    return {"ok": True, "data": [{"total_revenue": 100.0}], "row_count": 1, "truncated": False}


def test_semantic_fields_present_in_interactive_mode():
    """Interactive mode should still populate semantic fields, with CONTRACT_MISSING and no retries."""
    state: BaseState = {
        "user_input": "How many customers?",
        "intent": {"operation": "query", "metrics": ["count"], "primary_entities": ["customer"]},
        "relevant_tables": ["dbo.Customers"],
        "sql_query": "SELECT COUNT(*) AS cnt FROM dbo.Customers",
        "exec_result": _base_exec_result(),
        # No eval_mode / query_contract → interactive
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert "semantic_status" in vr
    assert vr.get("semantic_status") == "CONTRACT_MISSING"
    assert vr.get("semantic_retry_action") == "none"


def test_semantic_ok_when_entity_metric_and_join_match_contract():
    """Benchmark mode: matching entity, metric and join path should yield semantic_status == OK."""
    contract = _make_contract()

    state: BaseState = {
        "user_input": "Which customers have the highest total revenue?",
        "intent": {
            "operation": "query",
            "primary_entities": ["customer"],
            "metrics": ["total_revenue"],
            "resolved_metrics": [
                {
                    "key": contract["metric_key"],
                    "phrase": contract["metric_phrase"],
                    "expression_sql": contract["metric_expression_sql"],
                }
            ],
            "analytic_template": contract["analytic_template"],
            "template_params": {
                "metric_expression_sql": contract["metric_expression_sql"],
                "entity": contract["entity"],
                "entity_table": contract["entity_table"],
            },
        },
        "relevant_tables": ["dbo.customers", "dbo.orders", "dbo.order_details"],
        "sql_query": (
            "SELECT TOP 3 customers.CustomerName AS entity, "
            "SUM(order_details.unit_price * order_details.quantity) AS metric "
            "FROM orders "
            "JOIN customers ON customers.CustomerID = orders.CustomerID "
            "JOIN order_details ON orders.OrderID = order_details.OrderID "
            "GROUP BY customers.CustomerName ORDER BY metric DESC"
        ),
        "exec_result": _base_exec_result(),
        "eval_mode": "benchmark",
        "query_contract": contract,
        "validator_tables_used_base": ["customers", "orders", "order_details"],
        "join_plan": {
            "fact_table": "orders",
            "joins": [{"table": "customers"}, {"table": "order_details"}],
        },
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert vr.get("semantic_status") == "OK"
    assert vr.get("contract_id") == contract["query_id"]
    assert vr.get("semantic_retry_action") == "none"
    reasons = vr.get("semantic_failure_reasons") or []
    assert reasons == []


def test_semantic_entity_mismatch_when_entity_or_table_differs():
    """Benchmark mode: wrong entity/table should be reported as ENTITY_MISMATCH."""
    contract = _make_contract()

    state: BaseState = {
        "user_input": "Which products have the highest total revenue?",
        "intent": {
            "operation": "query",
            "primary_entities": ["product"],
            "metrics": ["total_revenue"],
            "resolved_metrics": [
                {
                    "key": contract["metric_key"],
                    "phrase": contract["metric_phrase"],
                    "expression_sql": contract["metric_expression_sql"],
                }
            ],
            "analytic_template": contract["analytic_template"],
        },
        "relevant_tables": ["dbo.products", "dbo.orders", "dbo.order_details"],
        "sql_query": "SELECT TOP 3 * FROM products",
        "exec_result": _base_exec_result(),
        "eval_mode": "benchmark",
        "query_contract": contract,
        "validator_tables_used_base": ["products", "orders", "order_details"],
        "join_plan": {
            "fact_table": "orders",
            "joins": [{"table": "products"}, {"table": "order_details"}],
        },
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert vr.get("semantic_status") == "ENTITY_MISMATCH"
    reasons = " ".join(vr.get("semantic_failure_reasons") or [])
    assert "Expected entity 'customer'" in reasons
    assert "entity_table 'customers'" in reasons
    assert vr.get("semantic_retry_action") == "replan"


def test_semantic_metric_mismatch_for_template_mismatch():
    """Template mismatch between contract and intent should map to METRIC_MISMATCH."""
    contract = _make_contract(analytic_template="TOP_K_BY_METRIC")

    state: BaseState = {
        "user_input": "How many customers placed orders?",
        "intent": {
            "operation": "query",
            "primary_entities": ["customer"],
            "metrics": ["orders_placed"],
            "resolved_metrics": [
                {
                    "key": contract["metric_key"],
                    "phrase": contract["metric_phrase"],
                    "expression_sql": contract["metric_expression_sql"],
                }
            ],
            # Intent ended up with a different template than the contract.
            "analytic_template": "COUNT_ENTITY",
        },
        "relevant_tables": ["dbo.customers", "dbo.orders"],
        "sql_query": "SELECT COUNT(DISTINCT orders.OrderID) FROM orders",
        "exec_result": _base_exec_result(),
        "eval_mode": "benchmark",
        "query_contract": contract,
        "validator_tables_used_base": ["customers", "orders"],
        "join_plan": {"fact_table": "orders", "joins": [{"table": "customers"}]},
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert vr.get("semantic_status") == "METRIC_MISMATCH"
    reasons = " ".join(vr.get("semantic_failure_reasons") or [])
    assert "Analytic template mismatch" in reasons
    assert vr.get("semantic_retry_action") == "replan"


def test_semantic_join_path_invalid_when_path_not_allowed():
    """Join path that does not match allowed_join_paths should be marked JOIN_PATH_INVALID."""
    contract = _make_contract()

    state: BaseState = {
        "user_input": "Which customers have the highest total revenue?",
        "intent": {
            "operation": "query",
            "primary_entities": ["customer"],
            "metrics": ["total_revenue"],
            "resolved_metrics": [
                {
                    "key": contract["metric_key"],
                    "phrase": contract["metric_phrase"],
                    "expression_sql": contract["metric_expression_sql"],
                }
            ],
            "analytic_template": contract["analytic_template"],
        },
        "relevant_tables": ["dbo.customers", "dbo.orders", "dbo.order_details"],
        "sql_query": "SELECT * FROM customers c JOIN order_details od ON c.id = od.customer_id",
        "exec_result": _base_exec_result(),
        "eval_mode": "benchmark",
        "query_contract": contract,
        # All required tables are used, but the join path introduces an extra table
        # that is not part of any allowed path.
        "validator_tables_used_base": ["customers", "orders", "order_details", "products"],
        "join_plan": {
            "fact_table": "order_details",
            "joins": [{"table": "customers"}, {"table": "orders"}, {"table": "products"}],
        },
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert vr.get("semantic_status") == "JOIN_PATH_INVALID"
    reasons = " ".join(vr.get("semantic_failure_reasons") or [])
    assert "does not match any allowed paths" in reasons
    assert vr.get("semantic_retry_action") == "replan"


def test_semantic_unsupported_metric_for_out_of_scope_template():
    """Contracts with out-of-scope analytic templates are reported as UNSUPPORTED_METRIC."""
    contract = _make_contract(analytic_template="AGG_OVER_PERIOD")

    state: BaseState = {
        "user_input": "Show revenue over time.",
        "intent": {
            "operation": "query",
            "primary_entities": ["order"],
            "metrics": ["total_revenue"],
        },
        "relevant_tables": ["dbo.orders"],
        "sql_query": "SELECT * FROM orders",
        "exec_result": _base_exec_result(),
        "eval_mode": "benchmark",
        "query_contract": contract,
        "validator_tables_used_base": ["orders"],
        "join_plan": {"fact_table": "orders", "joins": []},
    }

    updated = build_result_validator_node(state)
    vr = updated.get("validation_result") or {}

    assert vr.get("semantic_status") == "UNSUPPORTED_METRIC"
    reasons = " ".join(vr.get("semantic_failure_reasons") or [])
    assert "not supported in Phase 1" in reasons
    # Unsupported metrics do not trigger replanning; they are counted as semantic failures.
    assert vr.get("semantic_retry_action") == "none"
