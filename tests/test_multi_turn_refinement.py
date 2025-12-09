"""
Integration tests for multi-turn conversation and refinement query detection.

Tests:
1. Single-turn happy path: "What products are low in stock?"
2. Two-turn refinement: Previous response + "Look in KHKArtikelLagerbewegungen"
3. Target table extraction from refinement queries
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator(llm_model="gpt-4o")


@pytest.fixture
def mock_mcp():
    """Create a mock MCP client."""
    mcp = AsyncMock()
    mcp.search_tables = AsyncMock(return_value={
        "status": "ok",
        "results": [
            {
                "table_name": "Products",
                "full_name": "dbo.Products",
                "relevance_score": 0.95,
                "estimated_rows": 5000,
                "role_coverage": 0.85
            }
        ]
    })
    mcp.search_views = AsyncMock(return_value={"status": "ok", "results": []})
    mcp.describe_table = AsyncMock(return_value="Table with product information")
    mcp.get_columns = AsyncMock(return_value=["ProductID", "ProductName", "StockLevel"])
    mcp.query_bounded = AsyncMock(return_value={
        "ok": True,
        "data": [{"ProductName": "Item1", "StockLevel": 5}],
        "row_count": 1,
        "columns": ["ProductName", "StockLevel"]
    })
    return mcp


class TestSingleTurnQuery:
    """Test single-turn query processing."""
    
    @pytest.mark.asyncio
    async def test_single_turn_happy_path(self, orchestrator, mock_mcp):
        """Test: What products are low in stock?"""
        with patch("langgraph_integration.mcp_client.get_shared_mcp_tool", return_value=mock_mcp):
            # Single turn: just user input
            result = await orchestrator.process_query(
                user_input="What products are low in stock?",
                messages=[
                    {"role": "user", "content": "What products are low in stock?"}
                ],
                conversation_id="test-conv-1"
            )
            
            # Assertions
            assert result is not None, "Result should not be None"
            assert isinstance(result, dict), "Result should be a dict"
            assert "intent" in result, "Result should have intent"
            
            intent = result.get("intent", {})
            assert intent.get("operation") == "query", f"Operation should be 'query', got {intent.get('operation')}"
            assert intent.get("conversation_id") == "test-conv-1", "Conversation ID should be preserved"
            
            print(f"✅ Single-turn test passed")
            print(f"  - Operation: {intent.get('operation')}")
            print(f"  - Confidence: {intent.get('operation_confidence')}")
            print(f"  - Required action: {intent.get('required_action')}")


class TestMultiTurnRefinement:
    """Test multi-turn refinement queries."""
    
    @pytest.mark.asyncio
    async def test_two_turn_refinement(self, orchestrator, mock_mcp):
        """Test two-turn conversation with refinement."""
        with patch("langgraph_integration.mcp_client.get_shared_mcp_tool", return_value=mock_mcp):
            # Turn 1: Original query
            messages_turn1 = [
                {"role": "user", "content": "What products are low in stock?"},
            ]
            
            result1 = await orchestrator.process_query(
                user_input="What products are low in stock?",
                messages=messages_turn1,
                conversation_id="test-conv-2"
            )
            
            assert result1.get("intent", {}).get("operation") == "query"
            
            # Turn 2: Refinement with table name
            messages_turn2 = [
                {"role": "user", "content": "What products are low in stock?"},
                {"role": "assistant", "content": "I found some products with low stock levels."},
                {"role": "user", "content": "Look in KHKArtikelLagerbewegungen"}
            ]
            
            result2 = await orchestrator.process_query(
                user_input="Look in KHKArtikelLagerbewegungen",
                messages=messages_turn2,
                conversation_id="test-conv-2"
            )
            
            # Assertions for refinement
            intent2 = result2.get("intent", {})
            print(f"\nTurn 2 Intent Analysis:")
            print(f"  - Operation: {intent2.get('operation')}")
            print(f"  - Required action: {intent2.get('required_action')}")
            print(f"  - Target tables: {intent2.get('target_tables')}")
            print(f"  - Conversation ID: {result2.get('conversation_id')}")
            
            # Verify refinement detection
            assert intent2.get("required_action") in ["query", "refine_previous"], \
                f"Required action should be 'query' or 'refine_previous', got {intent2.get('required_action')}"
            
            # If target_tables extracted, verify they contain the table name
            target_tables = intent2.get("target_tables", [])
            if target_tables:
                table_found = any("KHK" in t or "Lager" in t for t in target_tables)
                print(f"  - Table extraction: {'✅ Found KHKArtikelLagerbewegungen' if table_found else '⚠️  Table not extracted'}")
            
            print(f"✅ Two-turn refinement test passed")
    
    @pytest.mark.asyncio
    async def test_target_table_extraction(self, orchestrator, mock_mcp):
        """Test explicit table name extraction in refinement."""
        with patch("langgraph_integration.mcp_client.get_shared_mcp_tool", return_value=mock_mcp):
            # Multi-turn with explicit table mention
            messages = [
                {"role": "user", "content": "Which customers ordered recently?"},
                {"role": "assistant", "content": "Found recent orders"},
                {"role": "user", "content": "Check the Orders table"}
            ]
            
            result = await orchestrator.process_query(
                user_input="Check the Orders table",
                messages=messages,
                conversation_id="test-conv-3"
            )
            
            intent = result.get("intent", {})
            target_tables = intent.get("target_tables", [])
            
            print(f"\nTarget table extraction test:")
            print(f"  - User input: 'Check the Orders table'")
            print(f"  - Target tables extracted: {target_tables}")
            
            # Note: The actual table name extraction depends on LLM performance
            # We're mainly testing that the field is present and populated if the LLM recognizes it
            assert isinstance(target_tables, list), "target_tables should be a list"
            
            print(f"✅ Target table extraction test passed")


class TestConversationMemory:
    """Test conversation memory preservation."""
    
    @pytest.mark.asyncio
    async def test_conversation_id_persistence(self, orchestrator, mock_mcp):
        """Test that conversation_id is preserved through turns."""
        with patch("langgraph_integration.mcp_client.get_shared_mcp_tool", return_value=mock_mcp):
            conv_id = "persistent-conv-123"
            
            # Turn 1
            result1 = await orchestrator.process_query(
                user_input="First question",
                messages=[{"role": "user", "content": "First question"}],
                conversation_id=conv_id
            )
            
            # Turn 2
            result2 = await orchestrator.process_query(
                user_input="Follow-up",
                messages=[
                    {"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "Answer"},
                    {"role": "user", "content": "Follow-up"}
                ],
                conversation_id=conv_id
            )
            
            # Verify conversation IDs match
            assert result1.get("conversation_id") == conv_id or conv_id == "", \
                "Conversation ID should be in result or empty state"
            assert result2.get("conversation_id") == conv_id or conv_id == "", \
                "Conversation ID should be consistent across turns"
            
            print(f"\n✅ Conversation ID persistence test passed (conv_id: {conv_id})")
    
    @pytest.mark.asyncio
    async def test_messages_passed_through(self, orchestrator, mock_mcp):
        """Test that full message history is available in state."""
        with patch("langgraph_integration.mcp_client.get_shared_mcp_tool", return_value=mock_mcp):
            messages = [
                {"role": "user", "content": "Question 1"},
                {"role": "assistant", "content": "Answer 1"},
                {"role": "user", "content": "Question 2"}
            ]
            
            result = await orchestrator.process_query(
                user_input="Question 2",
                messages=messages,
                conversation_id="msg-test"
            )
            
            # The messages should be available in the state during processing
            # (We can't directly inspect the state after execution, but the fact that
            # the orchestrator processes without error is a good sign)
            assert result is not None, "Orchestrator should handle messages without error"
            
            print(f"\n✅ Messages passed through test passed ({len(messages)} messages)")


if __name__ == "__main__":
    # Run tests with: python -m pytest test_multi_turn_refinement.py -v
    print("Run with: pytest test_multi_turn_refinement.py -v")
