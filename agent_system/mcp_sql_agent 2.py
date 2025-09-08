"""
MCP-enabled SQL Agent for interacting with the ERP database through the MCP server.

This module provides SQL agent functions that use the MCP (Model Context Protocol)
server instead of direct database connections, providing better security and
standardization.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from agent_system.mcp_client import create_mcp_client, MCPResponse

logger = logging.getLogger(__name__)


class MCPSQLAgent:
    """
    SQL Agent that uses MCP server for database operations.
    
    This agent provides the same interface as the original SQL agent but
    uses the MCP server for all database operations, providing better
    security, standardization, and separation of concerns.
    """
    
    def __init__(
        self,
        server_url: str = "http://localhost:8000",
        api_key: str = "supersecretapikey",
        timeout: int = 30
    ):
        """
        Initialize the MCP SQL Agent.
        
        Args:
            server_url: URL of the MCP server
            api_key: API key for MCP server authentication
            timeout: Request timeout in seconds
        """
        self.client = create_mcp_client(
            server_url=server_url,
            api_key=api_key,
            timeout=timeout,
            sync=True  # Use sync client for compatibility with LangChain tools
        )
        
    def _format_mcp_response(self, response: MCPResponse, operation: str) -> str:
        """
        Format MCP response for agent consumption.
        
        Args:
            response: MCP response object
            operation: Name of the operation for error context
            
        Returns:
            Formatted response string
        """
        if not response.success:
            error_msg = f"MCP {operation} failed: {response.error}"
            logger.error(error_msg)
            return error_msg
        
        if response.data is None:
            return f"No data returned from MCP {operation}"
        
        # Handle different response formats
        if isinstance(response.data, dict):
            if "content" in response.data:
                # MCP tool response format
                content = response.data["content"]
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", str(content))
                return str(content)
            else:
                # Direct data response
                return json.dumps(response.data, indent=2)
        
        return str(response.data)
    
    def run_sql_query(self, query: str) -> str:
        """
        Run a SQL query against the ERP database via MCP server.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query results as a formatted string
        """
        try:
            response = self.client.query(query)
            return self._format_mcp_response(response, "query")
        except Exception as e:
            error_msg = f"Error executing SQL query: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def get_table_info(self, table_name: str = None) -> str:
        """
        Get information about database tables via MCP server.
        
        Args:
            table_name: Optional name of a specific table
            
        Returns:
            Table information as a formatted string
        """
        try:
            if table_name:
                # Get specific table info
                response = self.client.get_table_info(table_name)
                return self._format_mcp_response(response, f"table info for {table_name}")
            else:
                # Get schema for all tables
                response = self.client.get_schema()
                return self._format_mcp_response(response, "database schema")
        except Exception as e:
            error_msg = f"Error getting table info: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def get_database_schema(self) -> str:
        """
        Get the complete database schema via MCP server.
        
        Returns:
            Database schema as a formatted string
        """
        try:
            response = self.client.get_schema()
            return self._format_mcp_response(response, "database schema")
        except Exception as e:
            error_msg = f"Error getting database schema: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def get_sample_data(self, table_name: str, limit: int = 10) -> str:
        """
        Get sample data from a table via MCP server.
        
        Args:
            table_name: Name of the table
            limit: Maximum number of rows to return
            
        Returns:
            Sample data as a formatted string
        """
        try:
            response = self.client.get_sample_data(table_name, limit)
            return self._format_mcp_response(response, f"sample data from {table_name}")
        except Exception as e:
            error_msg = f"Error getting sample data: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def health_check(self) -> str:
        """
        Check MCP server health.
        
        Returns:
            Health status as a formatted string
        """
        try:
            response = self.client.health_check()
            if response.success:
                return f"MCP Server is healthy: {response.data}"
            else:
                return f"MCP Server health check failed: {response.error}"
        except Exception as e:
            error_msg = f"Error checking MCP server health: {str(e)}"
            logger.error(error_msg)
            return error_msg


# Global MCP SQL Agent instance
_mcp_sql_agent = None


def get_mcp_sql_agent(
    server_url: str = "http://localhost:8000",
    api_key: str = "supersecretapikey",
    timeout: int = 30
) -> MCPSQLAgent:
    """
    Get or create the global MCP SQL Agent instance.
    
    Args:
        server_url: URL of the MCP server
        api_key: API key for MCP server authentication
        timeout: Request timeout in seconds
        
    Returns:
        MCPSQLAgent instance
    """
    global _mcp_sql_agent
    
    if _mcp_sql_agent is None:
        _mcp_sql_agent = MCPSQLAgent(server_url, api_key, timeout)
    
    return _mcp_sql_agent


# Agent tool functions (compatible with existing agent system)
def run_sql_query(query: str) -> str:
    """
    Run a SQL query against the ERP database via MCP server.
    
    This function maintains compatibility with the existing agent system
    while using the MCP server for database operations.
    
    Args:
        query: SQL query to execute
        
    Returns:
        Query results as a formatted string
    """
    agent = get_mcp_sql_agent()
    return agent.run_sql_query(query)


def get_table_info(table_name: str = None) -> str:
    """
    Get information about database tables via MCP server.
    
    This function maintains compatibility with the existing agent system
    while using the MCP server for database operations.
    
    Args:
        table_name: Optional name of a specific table
        
    Returns:
        Table information as a formatted string
    """
    agent = get_mcp_sql_agent()
    return agent.get_table_info(table_name)


def get_database_schema() -> str:
    """
    Get the complete database schema via MCP server.
    
    This function maintains compatibility with the existing agent system
    while using the MCP server for database operations.
    
    Returns:
        Database schema as a formatted string
    """
    agent = get_mcp_sql_agent()
    return agent.get_database_schema()


def get_sample_data(table_name: str, limit: int = 10) -> str:
    """
    Get sample data from a table via MCP server.
    
    Args:
        table_name: Name of the table
        limit: Maximum number of rows to return
        
    Returns:
        Sample data as a formatted string
    """
    agent = get_mcp_sql_agent()
    return agent.get_sample_data(table_name, limit)


def check_mcp_server_health() -> str:
    """
    Check MCP server health.
    
    Returns:
        Health status as a formatted string
    """
    agent = get_mcp_sql_agent()
    return agent.health_check()


# Configuration and testing
def configure_mcp_agent(
    server_url: str = "http://localhost:8000",
    api_key: str = "supersecretapikey",
    timeout: int = 30
):
    """
    Configure the global MCP SQL Agent with custom settings.
    
    Args:
        server_url: URL of the MCP server
        api_key: API key for MCP server authentication
        timeout: Request timeout in seconds
    """
    global _mcp_sql_agent
    _mcp_sql_agent = MCPSQLAgent(server_url, api_key, timeout)


def test_mcp_connection() -> Dict[str, Any]:
    """
    Test the MCP server connection and basic functionality.
    
    Returns:
        Dictionary with test results
    """
    results = {
        "health_check": False,
        "schema_access": False,
        "query_execution": False,
        "errors": []
    }
    
    try:
        agent = get_mcp_sql_agent()
        
        # Test health check
        health_result = agent.health_check()
        if "healthy" in health_result.lower():
            results["health_check"] = True
        else:
            results["errors"].append(f"Health check failed: {health_result}")
        
        # Test schema access
        schema_result = agent.get_database_schema()
        if "error" not in schema_result.lower() and len(schema_result) > 0:
            results["schema_access"] = True
        else:
            results["errors"].append(f"Schema access failed: {schema_result}")
        
        # Test query execution
        query_result = agent.run_sql_query("SELECT 1 as test")
        if "error" not in query_result.lower():
            results["query_execution"] = True
        else:
            results["errors"].append(f"Query execution failed: {query_result}")
    
    except Exception as e:
        results["errors"].append(f"Connection test failed: {str(e)}")
    
    return results


# Example usage and testing
if __name__ == "__main__":
    # Test the MCP SQL Agent
    print("Testing MCP SQL Agent...")
    
    # Run connection test
    test_results = test_mcp_connection()
    print(f"Test results: {json.dumps(test_results, indent=2)}")
    
    if all([test_results["health_check"], test_results["schema_access"], test_results["query_execution"]]):
        print("✅ All tests passed! MCP SQL Agent is working correctly.")
        
        # Demonstrate functionality
        print("\n--- Database Schema ---")
        print(get_database_schema())
        
        print("\n--- Sample Query ---")
        print(run_sql_query("SELECT COUNT(*) as total_customers FROM customers"))
        
    else:
        print("❌ Some tests failed. Check MCP server status.")
        for error in test_results["errors"]:
            print(f"  - {error}")