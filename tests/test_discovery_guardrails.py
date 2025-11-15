from unittest.mock import MagicMock, patch

from langgraph_integration.contracts.state import BaseState


@patch("langgraph_integration.agents.discovery.agent.ChatOpenAI", autospec=True)
@patch("langgraph_integration.agents.discovery.agent.get_shared_mcp_tool", autospec=True)
def test_finalize_discovery_payload_triggers_clarification_when_only_empty_tables(mock_mcp, mock_chat):
    from langgraph_integration.agents.discovery.agent import DiscoveryAgent

    mock_mcp.return_value = MagicMock()
    mock_chat.return_value = MagicMock()

    agent = DiscoveryAgent()

    state = BaseState(
        intent={"operation": "query"},
        relevant_table_details=[
            {"full_name": "dbo.empty_sales", "estimated_rows": 0, "has_rows": False},
            {"full_name": "dbo.empty_customers", "estimated_rows": None, "has_rows": False},
        ],
        relevant_tables=["dbo.empty_sales", "dbo.empty_customers"],
    )

    updated = agent._finalize_discovery_payload(state)

    intent = updated.get("intent", {})
    assert intent.get("needs_clarification") is True
    assert "clarify" in (intent.get("clarification_question") or "").lower()

    error_info = updated.get("error_info")
    assert error_info is not None
    assert error_info.get("type") == "DISCOVERY_EMPTY_TABLES"
    assert error_info.get("suggestion")

    assert updated.get("relevant_tables") == []
    assert updated.get("relevant_table_details") == []

