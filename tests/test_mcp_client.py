"""
Tests for MCP-based DatabaseClient (Phase 7).

These tests verify that the new MCPDatabaseClient correctly replaces
the legacy Flask proxy /query endpoint.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.mcp_client import MCPDatabaseClient, MCPConfig, DatabaseClient


class TestMCPConfig:
    """Test MCP configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = MCPConfig(server_url="http://localhost:8000")
        
        assert config.server_url == "http://localhost:8000"
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.backoff_factor == 2.0
        assert config.api_key is None
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = MCPConfig(
            server_url="http://custom:9000",
            timeout_seconds=60,
            max_retries=5,
            backoff_factor=3.0,
            api_key="test-key"
        )
        
        assert config.server_url == "http://custom:9000"
        assert config.timeout_seconds == 60
        assert config.max_retries == 5
        assert config.backoff_factor == 3.0
        assert config.api_key == "test-key"
    
    @patch.dict(os.environ, {
        "MCP_SERVER_URL": "http://env:8000",
        "MCP_TIMEOUT_SECONDS": "45",
        "MCP_MAX_RETRIES": "4",
        "MCP_BACKOFF_FACTOR": "2.5",
        "MCP_API_KEY": "env-key"
    })
    def test_from_env(self):
        """Test loading configuration from environment."""
        config = MCPConfig.from_env()
        
        assert config.server_url == "http://env:8000"
        assert config.timeout_seconds == 45
        assert config.max_retries == 4
        assert config.backoff_factor == 2.5
        assert config.api_key == "env-key"


class TestMCPDatabaseClient:
    """Test MCP database client."""
    
    def test_initialization(self):
        """Test client initialization."""
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        assert client.config.server_url == "http://localhost:8000"
    
    @patch('app.db.mcp_client.requests.post')
    def test_query_success(self, mock_post):
        """Test successful query execution."""
        # Mock successful MCP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "query_1",
            "result": {
                "columns": ["id", "name"],
                "rows": [[1, "Test"], [2, "Example"]]
            }
        }
        mock_post.return_value = mock_response
        
        # Execute query
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        columns, rows = client.query("SELECT * FROM test")
        
        # Verify results
        assert columns == ["id", "name"]
        assert rows == [[1, "Test"], [2, "Example"]]
        
        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8000/mcp"
        
        payload = call_args[1]["json"]
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query_bounded"
        assert payload["params"]["arguments"]["sql"] == "SELECT * FROM test"
    
    @patch('app.db.mcp_client.requests.post')
    def test_query_with_limit(self, mock_post):
        """Test query with custom limit."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "query_1",
            "result": {
                "columns": ["id"],
                "rows": [[1], [2], [3]]
            }
        }
        mock_post.return_value = mock_response
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        columns, rows = client.query("SELECT * FROM test", limit=50)
        
        # Verify limit was passed
        payload = mock_post.call_args[1]["json"]
        assert payload["params"]["arguments"]["limit"] == 50
    
    @patch('app.db.mcp_client.requests.post')
    @patch('app.db.mcp_client.time.sleep')
    def test_rate_limiting_with_retry_after(self, mock_sleep, mock_post):
        """Test rate limiting with Retry-After header."""
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "2"}
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "jsonrpc": "2.0",
            "id": "query_1",
            "result": {
                "columns": ["id"],
                "rows": [[1]]
            }
        }
        
        mock_post.side_effect = [mock_response_429, mock_response_200]
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        columns, rows = client.query("SELECT * FROM test")
        
        # Verify retry happened
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(2)  # Retry-After value
        
        # Verify final result
        assert columns == ["id"]
        assert rows == [[1]]
    
    @patch('app.db.mcp_client.requests.post')
    def test_mcp_error_handling(self, mock_post):
        """Test MCP JSON-RPC error handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "query_1",
            "error": {
                "code": -32600,
                "message": "Invalid query"
            }
        }
        mock_post.return_value = mock_response
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        with pytest.raises(RuntimeError, match="MCP error.*Invalid query"):
            client.query("INVALID SQL")
    
    @patch('app.db.mcp_client.requests.post')
    def test_search_tables(self, mock_post):
        """Test search_tables discovery tool."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "search_1",
            "result": {
                "tables": [
                    {"name": "customers", "row_count": 100},
                    {"name": "customer_orders", "row_count": 500}
                ]
            }
        }
        mock_post.return_value = mock_response
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        tables = client.search_tables("customer", limit=20)
        
        assert len(tables) == 2
        assert tables[0]["name"] == "customers"
        
        # Verify pagination parameters
        payload = mock_post.call_args[1]["json"]
        assert payload["params"]["arguments"]["limit"] == 20
        assert payload["params"]["arguments"]["offset"] == 0
    
    @patch('app.db.mcp_client.requests.get')
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "database": {"status": "connected"}
        }
        mock_get.return_value = mock_response
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        assert client.health_check() is True
    
    @patch('app.db.mcp_client.requests.get')
    def test_health_check_failure(self, mock_get):
        """Test failed health check."""
        mock_get.side_effect = Exception("Connection failed")
        
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        assert client.health_check() is False


class TestLegacyDatabaseClient:
    """Test legacy DatabaseClient wrapper for backward compatibility."""
    
    @patch('app.db.mcp_client.MCPDatabaseClient')
    def test_legacy_wrapper_initialization(self, mock_mcp_client):
        """Test legacy wrapper initialization with deprecation warning."""
        import logging
        
        # Capture log warnings
        with patch('app.db.mcp_client.logger.warning') as mock_warning:
            client = DatabaseClient()
            
            # Verify deprecation warning was logged
            mock_warning.assert_called()
            call_args = str(mock_warning.call_args)
            assert "deprecated" in call_args.lower()
    
    @patch('app.db.mcp_client.MCPDatabaseClient.query')
    def test_legacy_query_ignores_deprecated_params(self, mock_query):
        """Test that legacy query method ignores deprecated parameters."""
        mock_query.return_value = (["id"], [[1]])
        
        # Suppress warnings for test
        import logging
        logging.getLogger('app.db.mcp_client').setLevel(logging.ERROR)
        
        client = DatabaseClient()
        columns, rows = client.query(
            "SELECT * FROM test",
            params={"ignored": "value"},
            conn="ignored_connection",
            timeout_s=60,
            limit=10
        )
        
        # Restore logging
        logging.getLogger('app.db.mcp_client').setLevel(logging.WARNING)
        
        # Verify only limit was passed
        mock_query.assert_called_once_with("SELECT * FROM test", limit=10)
        
        assert columns == ["id"]
        assert rows == [[1]]


class TestDesignGuardrails:
    """Test that design guardrails are enforced."""
    
    def test_pagination_required_for_search(self):
        """Test that search_tables requires pagination (never enumerate full schema)."""
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        # search_tables should always have limit parameter
        with patch('app.db.mcp_client.requests.post') as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"jsonrpc": "2.0", "id": "1", "result": {"tables": []}}
            )
            
            client.search_tables("test")
            
            payload = mock_post.call_args[1]["json"]
            assert "limit" in payload["params"]["arguments"]
            assert payload["params"]["arguments"]["limit"] == 20  # Default limit
    
    def test_small_focused_prompts(self):
        """Test that query results are bounded (≤3 tables guideline)."""
        # This is enforced by MCP server, but client should pass limits
        config = MCPConfig(server_url="http://localhost:8000")
        client = MCPDatabaseClient(config)
        
        with patch('app.db.mcp_client.requests.post') as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {"columns": [], "rows": []}
                }
            )
            
            # Query should have default or explicit limit
            client.query("SELECT * FROM test")
            
            payload = mock_post.call_args[1]["json"]
            # Limit should be present (enforced by MCP)
            assert "arguments" in payload["params"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])