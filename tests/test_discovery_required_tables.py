from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph_integration.contracts.state import BaseState


@patch("langgraph_integration.agents.discovery.agent.ChatOpenAI", autospec=True)
@patch("langgraph_integration.agents.discovery.agent.get_shared_mcp_tool", autospec=True)
def test_discovery_preserves_contract_required_tables_in_benchmark_mode(mock_mcp, mock_chat):
    """
    DiscoveryAgent should treat contract.required_tables and entity_table as hard constraints
    in benchmark mode, ensuring they appear in relevant_tables when present in seed_tables.
    """
    from langgraph_integration.agents.discovery.agent import DiscoveryAgent

    mock_mcp.return_value = MagicMock()
    mock_chat.return_value = MagicMock()

    agent = DiscoveryAgent()

    state = BaseState(
        intent={"operation": "query"},
        eval_mode="benchmark",
        # Benchmark contract requires the products table (base name only).
        query_contract={
            "query_id": "Q1",
            "entity": "product",
            "entity_table": "products",
            "metric_key": "items_purchased",
            "metric_expression_sql": "SUM(order_details.quantity)",
            "required_tables": ["products"],
            "allowed_join_paths": [["products"]],
        },
        # Concept mapper provided canonical seed tables including products
        seed_tables=["public.orders", "public.products", "public.order_details"],
        # Discovery details initially missed products
        relevant_table_details=[
            {"full_name": "public.orders", "estimated_rows": 100, "has_rows": True},
            {"full_name": "public.order_details", "estimated_rows": 100, "has_rows": True},
        ],
        relevant_tables=["public.orders", "public.order_details"],
        discovery_log={},
        db_dialect="postgres",
        db_default_schema="public",
    )

    updated = agent._finalize_discovery_payload(state)

    relevant = updated.get("relevant_tables") or []
    assert "public.products" in relevant, "Contract-required products table should be injected into relevant_tables"

    details = updated.get("relevant_table_details") or []
    product_details = [d for d in details if d.get("full_name") == "public.products"]
    assert product_details, "Discovery payload should include detail metadata for contract-required products table"
