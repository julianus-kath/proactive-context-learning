"""
Tests for the multi-source agent.
"""
import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crawling_agent.agent.multi_source_agent import MultiSourceAgent
from crawling_agent.llm.base_llm_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""
    
    def __init__(self):
        self.generate_response_mock = AsyncMock()
        self.generate_tool_calls_mock = AsyncMock()
    
    async def generate_response(self, messages, tools=None, temperature=0.7, max_tokens=None):
        return self.generate_response_mock(messages, tools, temperature, max_tokens)
    
    async def generate_tool_calls(self, messages, tools, temperature=0.7, max_tokens=None):
        return self.generate_tool_calls_mock(messages, tools, temperature, max_tokens)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def mock_erp_connector():
    """Create a mock ERP connector."""
    connector = AsyncMock()
    connector.__aenter__.return_value = connector
    connector.list_tables.return_value = ["customers", "orders", "products"]
    connector.get_table_schema.return_value = {
        "table": "customers",
        "columns": [
            {"name": "id", "type": "INTEGER", "primary_key": True},
            {"name": "name", "type": "TEXT"},
            {"name": "email", "type": "TEXT"},
        ]
    }
    connector.execute_sql_query.return_value = [
        {"id": 1, "name": "John Doe", "email": "john@example.com"},
        {"id": 2, "name": "Jane Smith", "email": "jane@example.com"},
    ]
    return connector


@pytest.fixture
def mock_document_connector():
    """Create a mock document storage connector."""
    connector = AsyncMock()
    connector.__aenter__.return_value = connector
    connector.list_collections.return_value = ["reports", "emails"]
    connector.get_collection_info.return_value = {
        "collection": "reports",
        "count": 10,
        "fields": ["title", "content", "date"]
    }
    connector.find_documents.return_value = [
        {"title": "Q1 Report", "content": "Sales increased by 15%", "date": "2023-03-31"},
        {"title": "Q2 Report", "content": "Sales increased by 10%", "date": "2023-06-30"},
    ]
    return connector


@pytest.fixture
def mock_knowledge_connector():
    """Create a mock knowledge graph connector."""
    connector = AsyncMock()
    connector.__aenter__.return_value = connector
    connector.get_node_types.return_value = ["Person", "Company", "Product"]
    connector.get_relationship_types.return_value = ["WORKS_FOR", "BUYS", "SELLS"]
    connector.query_nodes.return_value = [
        {"id": 1, "type": "Person", "properties": {"name": "John Doe"}},
        {"id": 2, "type": "Person", "properties": {"name": "Jane Smith"}},
    ]
    connector.query_relationships.return_value = [
        {
            "id": 1,
            "type": "WORKS_FOR",
            "start_node": {"id": 1, "type": "Person"},
            "end_node": {"id": 3, "type": "Company"},
            "properties": {"since": "2020-01-01"}
        }
    ]
    return connector


@pytest.fixture
def agent(mock_llm_client, mock_erp_connector, mock_document_connector, mock_knowledge_connector):
    """Create a multi-source agent with mock components."""
    return MultiSourceAgent(
        llm_client=mock_llm_client,
        erp_connector=mock_erp_connector,
        document_connector=mock_document_connector,
        knowledge_connector=mock_knowledge_connector,
        debug=True,
    )


@pytest.mark.asyncio
async def test_process_query_with_final_response(agent, mock_llm_client):
    """Test processing a query that results in a final response without tool calls."""
    # Set up the mock to return a final response
    mock_llm_client.generate_tool_calls_mock.return_value = {
        "role": "assistant",
        "content": "This is the final response."
    }
    
    # Process a query
    response = await agent.process_query("What is the meaning of life?")
    
    # Check that the response is correct
    assert response == "This is the final response."
    
    # Check that the LLM client was called with the correct arguments
    mock_llm_client.generate_tool_calls_mock.assert_called_once()
    args, kwargs = mock_llm_client.generate_tool_calls_mock.call_args
    assert len(args[0]) == 2  # system message and user message
    assert args[0][0]["role"] == "system"
    assert args[0][1]["role"] == "user"
    assert args[0][1]["content"] == "What is the meaning of life?"


@pytest.mark.asyncio
async def test_process_query_with_tool_calls(agent, mock_llm_client):
    """Test processing a query that results in tool calls."""
    # Set up the mock to return tool calls and then a final response
    mock_llm_client.generate_tool_calls_mock.side_effect = [
        {
            "role": "assistant",
            "content": "I'll check the ERP database.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "list_tables",
                        "arguments": "{}"
                    }
                }
            ]
        },
        {
            "role": "assistant",
            "content": "Here's what I found in the ERP database."
        }
    ]
    
    # Process a query
    response = await agent.process_query("What tables are in the ERP database?")
    
    # Check that the response is correct
    assert response == "Here's what I found in the ERP database."
    
    # Check that the LLM client was called with the correct arguments
    assert mock_llm_client.generate_tool_calls_mock.call_count == 2
    
    # Check that the tool call was executed
    agent.erp_connector.list_tables.assert_called_once()


@pytest.mark.asyncio
async def test_reasoning_loop_max_steps(agent, mock_llm_client):
    """Test that the reasoning loop stops after the maximum number of steps."""
    # Set up the mock to always return tool calls
    mock_llm_client.generate_tool_calls_mock.return_value = {
        "role": "assistant",
        "content": "I need more information.",
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": "list_tables",
                    "arguments": "{}"
                }
            }
        ]
    }
    
    # Set up the mock to return a final response when generate_response is called
    mock_llm_client.generate_response_mock.return_value = {
        "role": "assistant",
        "content": "This is the final response after max steps."
    }
    
    # Set a low max_reasoning_steps
    agent.max_reasoning_steps = 2
    
    # Process a query
    response = await agent.process_query("What tables are in the ERP database?")
    
    # Check that the response is correct
    assert response == "This is the final response after max steps."
    
    # Check that the LLM client was called the correct number of times
    assert mock_llm_client.generate_tool_calls_mock.call_count == 2
    assert mock_llm_client.generate_response_mock.call_count == 1


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])