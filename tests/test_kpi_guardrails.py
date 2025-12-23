from unittest.mock import patch, MagicMock

import pytest

from langgraph_integration.contracts.state import BaseState


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
async def test_join_sql_kpi_guardrail_missing_products_triggers_product_mapping_error():
    """JoinPlanAndSQLAgent validation should surface a PRODUCT_MAPPING_ERROR when products is required but missing from SQL."""
    from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent

    agent = JoinPlanAndSQLAgent(llm_model="gpt-4o")
    agent.mcp = MagicMock()

    state = BaseState(
        sql_query="SELECT od.order_id AS product_name FROM public.order_details od",
        relevant_tables=["public.orders", "public.order_details", "public.products"],
        candidate_views=[],
        intent={"operation": "query", "primary_entities": ["product"], "metrics": []},
        user_input="Which products need to be reordered?",
        concept_hints={
            "kpi_expressions": {
                "inventory_reorder": "CASE WHEN Products.UnitsInStock + Products.UnitsOnOrder < Products.ReorderLevel THEN 1 ELSE 0 END"
            }
        },
        required_tables_from_kpi=["public.products"],
    )

    result = await agent._validate_sql_node(state)

    error = result.get("error_info") or {}
    assert error.get("type") in {"PRODUCT_MAPPING_ERROR", "KPI_REQUIRED_TABLE_MISSING"}
    assert error.get("replan_needed") is True

