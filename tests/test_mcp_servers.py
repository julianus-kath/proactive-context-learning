"""
Tests for MCP servers.
"""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from crawling_agent.servers.erp_server import ERPServer
from crawling_agent.servers.document_storage_server import DocumentStorageServer
from crawling_agent.servers.knowledge_graph_server import KnowledgeGraphServer
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector
from crawling_agent.custom_resource import CustomResource


class TestMCPServers(unittest.TestCase):
    """Tests for MCP servers."""
    
    def test_erp_server_initialization(self):
        """Test that the ERP server initializes correctly."""
        # Mock the database path
        db_path = "mock_db.db"
        
        # Mock the sqlite3 connection
        with patch("sqlite3.connect") as mock_connect:
            # Mock the cursor
            mock_cursor = MagicMock()
            mock_connect.return_value.cursor.return_value = mock_cursor
            
            # Mock the table list query
            mock_cursor.fetchall.return_value = [("customers",), ("products",)]
            
            # Initialize the server
            server = ERPServer(db_path=db_path)
            
            # Check that the server was initialized correctly
            self.assertEqual(server.name, "ERPServer")
            self.assertEqual(server.db_path, db_path)
            
            # Check that the database was queried for tables
            mock_connect.assert_called_with(db_path)
            mock_cursor.execute.assert_called_with("SELECT name FROM sqlite_master WHERE type='table';")
    
    def test_document_storage_server_initialization(self):
        """Test that the Document Storage server initializes correctly."""
        # Mock the JSON path
        json_path = "mock_data.json"
        
        # Mock the JSON data
        mock_data = {
            "collection1": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"}
            ],
            "collection2": [
                {"id": 3, "name": "Item 3"},
                {"id": 4, "name": "Item 4"}
            ]
        }
        
        # Mock the open function
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(mock_data))):
            # Initialize the server
            server = DocumentStorageServer(json_path=json_path)
            
            # Check that the server was initialized correctly
            self.assertEqual(server.name, "DocumentStorageServer")
            self.assertEqual(server.json_path, json_path)
            self.assertEqual(server.documents, mock_data)
    
    def test_knowledge_graph_server_initialization(self):
        """Test that the Knowledge Graph server initializes correctly."""
        # Initialize the server
        server = KnowledgeGraphServer()
        
        # Check that the server was initialized correctly
        self.assertEqual(server.name, "KnowledgeGraphServer")
        self.assertIsNotNone(server.graph_data)
        self.assertIn("nodes", server.graph_data)
        self.assertIn("relationships", server.graph_data)


@pytest.mark.asyncio
async def test_erp_connector():
    """Test the ERP connector."""
    # Mock the ClientSession
    with patch("crawling_agent.base_connector.sse_client") as mock_sse_client, \
         patch("crawling_agent.base_connector.ClientSession") as mock_session_class:
        
        # Mock the read and write streams
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_sse_client.return_value = (mock_read_stream, mock_write_stream)
        
        # Mock the session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock the initialize method
        mock_session.initialize = MagicMock(return_value=None)
        
        # Mock the list_tools method
        mock_tools_result = MagicMock()
        mock_tools_result.tools = ["execute_sql_query", "get_table_schema", "list_tables"]
        mock_session.list_tools = MagicMock(return_value=mock_tools_result)
        
        # Mock the call_tool method for list_tables
        mock_list_tables_result = MagicMock()
        mock_list_tables_result.content = [MagicMock(text=json.dumps({"tables": ["customers", "products"]}))]
        mock_session.call_tool.return_value = mock_list_tables_result
        
        # Initialize the connector
        connector = MCPERPConnector()
        
        # Connect to the server
        await connector.connect()
        
        # List tables
        tables = await connector.list_tables()
        
        # Check that the correct tables were returned
        assert tables == ["customers", "products"]
        
        # Check that the correct tool was called
        mock_session.call_tool.assert_called_with("list_tables", {})


@pytest.mark.asyncio
async def test_document_storage_connector():
    """Test the Document Storage connector."""
    # Mock the ClientSession
    with patch("crawling_agent.base_connector.sse_client") as mock_sse_client, \
         patch("crawling_agent.base_connector.ClientSession") as mock_session_class:
        
        # Mock the read and write streams
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_sse_client.return_value = (mock_read_stream, mock_write_stream)
        
        # Mock the session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock the initialize method
        mock_session.initialize = MagicMock(return_value=None)
        
        # Mock the list_tools method
        mock_tools_result = MagicMock()
        mock_tools_result.tools = ["find_documents", "list_collections", "get_collection_info"]
        mock_session.list_tools = MagicMock(return_value=mock_tools_result)
        
        # Mock the call_tool method for list_collections
        mock_list_collections_result = MagicMock()
        mock_list_collections_result.content = [MagicMock(text=json.dumps({"collections": ["collection1", "collection2"]}))]
        mock_session.call_tool.return_value = mock_list_collections_result
        
        # Initialize the connector
        connector = MCPDocumentStorageConnector()
        
        # Connect to the server
        await connector.connect()
        
        # List collections
        collections = await connector.list_collections()
        
        # Check that the correct collections were returned
        assert collections == ["collection1", "collection2"]
        
        # Check that the correct tool was called
        mock_session.call_tool.assert_called_with("list_collections", {})


@pytest.mark.asyncio
async def test_knowledge_graph_connector():
    """Test the Knowledge Graph connector."""
    # Mock the ClientSession
    with patch("crawling_agent.base_connector.sse_client") as mock_sse_client, \
         patch("crawling_agent.base_connector.ClientSession") as mock_session_class:
        
        # Mock the read and write streams
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_sse_client.return_value = (mock_read_stream, mock_write_stream)
        
        # Mock the session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock the initialize method
        mock_session.initialize = MagicMock(return_value=None)
        
        # Mock the list_tools method
        mock_tools_result = MagicMock()
        mock_tools_result.tools = ["query_nodes", "query_relationships", "get_node_types", "get_relationship_types"]
        mock_session.list_tools = MagicMock(return_value=mock_tools_result)
        
        # Mock the call_tool method for get_node_types
        mock_get_node_types_result = MagicMock()
        mock_get_node_types_result.content = [MagicMock(text=json.dumps({"node_types": ["Product", "Customer", "Supplier"]}))]
        mock_session.call_tool.return_value = mock_get_node_types_result
        
        # Initialize the connector
        connector = MCPKnowledgeGraphConnector()
        
        # Connect to the server
        await connector.connect()
        
        # Get node types
        node_types = await connector.get_node_types()
        
        # Check that the correct node types were returned
        assert node_types == ["Product", "Customer", "Supplier"]
        
        # Check that the correct tool was called
        mock_session.call_tool.assert_called_with("get_node_types", {})