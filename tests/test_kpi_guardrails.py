from unittest.mock import patch, MagicMock

import pytest

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.guardrails.required_relations import (
    evaluate_required_relations,
)


@patch("langgraph_integration.agents.discovery.agent.ChatOpenAI", autospec=True)
@patch("langgraph_integration.agents.discovery.agent.get_shared_mcp_tool", autospec=True)
def test_discovery_injects_kpi_required_tables(mock_mcp, mock_chat):
    """DiscoveryAgent should inject KPI-required tables (e.g., products) into relevant_tables when present in seed_tables."""
    from langgraph_integration.agents.discovery.agent import DiscoveryAgent

    mock_mcp.return_value = MagicMock()
    mock_chat.return_value = MagicMock()

    agent = DiscoveryAgent()

    state = BaseState(
        intent={"operation": "query"},
        # KPI requires products table (e.g., inventory_reorder KPI)
        required_tables_from_kpi=["public.products"],
        # Concept mapper provided canonical seed tables including products
        seed_tables=["public.orders", "public.products", "public.order_details"],
        # Discovery details initially missed products
        relevant_table_details=[
            {"full_name": "public.orders", "estimated_rows": 100, "has_rows": True},
            {"full_name": "public.order_details", "estimated_rows": 100, "has_rows": True},
        ],
        relevant_tables=["public.orders", "public.order_details"],
        discovery_log={},
    )

    updated = agent._finalize_discovery_payload(state)

    relevant = updated.get("relevant_tables") or []
    assert "public.products" in relevant, "KPI-required products table should be injected into relevant_tables"

    details = updated.get("relevant_table_details") or []
    product_details = [d for d in details if d.get("full_name") == "public.products"]
    assert product_details, "Discovery payload should include detail metadata for KPI-required products table"


@pytest.mark.asyncio
async def test_required_relations_guardrail_marks_missing_tables_and_requests_replan():
    """Guardrail should detect missing required tables and request one replan, forcing those tables."""
    state = BaseState(
        required_tables_from_kpi=["public.products"],
        validator_tables_used=["public.orders", "public.order_details"],
        validator_tables_used_base=["orders", "order_details"],
        db_dialect="postgres",
        db_default_schema="public",
    )

    error = evaluate_required_relations(state)
    assert error is not None
    assert error.get("type") == "REQUIRED_TABLE_MISSING_IN_SQL"
    assert error.get("replan_needed") is True
    missing = error.get("missing_required_tables") or []
    assert "public.products" in missing
    forced = state.get("forced_tables") or []
    assert "public.products" in forced
    assert state.get("required_enforcement_attempts") == 1


@pytest.mark.asyncio
async def test_required_relations_guardrail_stops_after_repeated_missing_set():
    """Guardrail should stop requesting replans when the same missing set appears again."""
    state = BaseState(
        required_tables_from_kpi=["public.products"],
        validator_tables_used=["public.orders"],
        validator_tables_used_base=["orders"],
        db_dialect="postgres",
        db_default_schema="public",
        required_enforcement_attempts=1,
        last_required_missing_tables=["public.products"],
        forced_tables=["public.products"],
    )

    error = evaluate_required_relations(state)
    assert error is not None
    assert error.get("type") == "REQUIRED_TABLE_MISSING_IN_SQL"
    assert error.get("replan_needed") is False
    assert state.get("required_enforcement_attempts") == 2


@pytest.mark.asyncio
async def test_required_relations_guardrail_no_error_when_all_required_present():
    """Guardrail should do nothing when all required tables are present in validator tables_used."""
    state = BaseState(
        required_tables_from_kpi=["public.products"],
        validator_tables_used=["public.orders", "public.products"],
        validator_tables_used_base=["orders", "products"],
        db_dialect="postgres",
        db_default_schema="public",
    )

    error = evaluate_required_relations(state)
    assert error is None
