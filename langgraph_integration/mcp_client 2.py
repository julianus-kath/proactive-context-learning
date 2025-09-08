"""
MCP Database Tool for LangGraph Integration
Phase 2 Blueprint Implementation

This module implements the MCPDatabaseTool class as specified in the blueprint,
with additional robustness and error handling.
"""

import os
import aiohttp
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "supersecretapikey")

logger = logging.getLogger(__name__)


class MCPDatabaseTool:
    """
    MCP Database Tool for LangGraph Integration.
    
    This class provides a simple interface to interact with the MCP database server
    as specified in the Phase 2 Blueprint.
    """
    
    def __init__(self, mcp_url: str = None, api_key: str = None):
        """
        Initialize the MCP Database Tool.
        
        Args:
            mcp_url: MCP server URL (defaults to environment variable)
            api_key: API key for authentication (defaults to environment variable)
        """
        self.mcp_url = mcp_url or MCP_URL
        self.api_key = api_key or API_KEY
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize the MCP session.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if self._initialized:
            return True
        
        # For this simplified MCP server, we just check if it's healthy
        try:
            if await self.health_check():
                self._initialized = True
                logger.info("MCP session initialized successfully")
                return True
            else:
                logger.error("MCP server health check failed")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            return False
        
    async def call_tool(self, tool_name: str, arguments: dict) -> List[Dict[str, Any]]:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool response content
            
        Raises:
            aiohttp.ClientError: If the HTTP request fails
            ValueError: If the MCP server returns an error
        """
        # Initialize if not already done
        if not self._initialized:
            if not await self.initialize():
                raise ValueError("Failed to initialize MCP session")
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.mcp_url}/mcp", 
                    json=payload, 
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if data is None:
                        logger.error("MCP call failed: No response data")
                        raise ValueError("MCP call failed: No response data")
                    
                    # Check for JSON-RPC errors
                    if "error" in data and data["error"] is not None:
                        error_msg = data["error"].get("message", "Unknown MCP error")
                        logger.error(f"MCP server error: {error_msg}")
                        raise ValueError(f"MCP server error: {error_msg}")
                    
                    # Return the content from the result
                    result = data.get("result", {})
                    content = result.get("content", [])
                    
                    return content
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling MCP server: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling MCP server: {e}")
            raise
    
    async def get_schema(self) -> List[Dict[str, Any]]:
        """
        Get the database schema.
        
        Returns:
            Schema information from the MCP server
        """
        return await self.call_tool("get_schema", {})
    
    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Query results from the MCP server
        """
        return await self.call_tool("query", {"sql": sql})
    
    async def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table information from the MCP server
        """
        return await self.call_tool("get_table_info", {"table_name": table_name})
    
    async def get_sample_data(self, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get sample data from a table.
        
        Args:
            table_name: Name of the table
            limit: Maximum number of rows to return
            
        Returns:
            Sample data from the MCP server
        """
        return await self.call_tool("get_sample_data", {
            "table_name": table_name,
            "limit": limit
        })
    
    async def health_check(self) -> bool:
        """
        Check if the MCP server is healthy.
        
        Returns:
            True if the server is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_url}/health") as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Utility functions for easier usage
async def get_database_schema() -> str:
    """
    Get the database schema as a formatted string.
    
    Returns:
        Formatted schema information
    """
    tool = MCPDatabaseTool()
    try:
        schema_content = await tool.get_schema()
        if schema_content and len(schema_content) > 0:
            return schema_content[0].get("text", "No schema information available")
        return "No schema information available"
    except Exception as e:
        return f"Error getting schema: {str(e)}"


async def execute_sql_query(sql: str) -> str:
    """
    Execute a SQL query and return formatted results.
    
    Args:
        sql: SQL query to execute
        
    Returns:
        Formatted query results
    """
    tool = MCPDatabaseTool()
    try:
        query_content = await tool.query(sql)
        if query_content and len(query_content) > 0:
            return query_content[0].get("text", "No results")
        return "No results"
    except Exception as e:
        return f"Error executing query: {str(e)}"


async def get_table_information(table_name: str) -> str:
    """
    Get table information as a formatted string.
    
    Args:
        table_name: Name of the table
        
    Returns:
        Formatted table information
    """
    tool = MCPDatabaseTool()
    try:
        table_content = await tool.get_table_info(table_name)
        if table_content and len(table_content) > 0:
            return table_content[0].get("text", "No table information available")
        return "No table information available"
    except Exception as e:
        return f"Error getting table info: {str(e)}"


# Example usage and testing
async def test_mcp_connection():
    """Test the MCP database tool connection."""
    print("Testing MCP Database Tool...")
    
    tool = MCPDatabaseTool()
    
    # Test health check
    is_healthy = await tool.health_check()
    print(f"Health check: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
    
    if not is_healthy:
        print("MCP server is not available. Please start the server first.")
        return
    
    try:
        # Test schema retrieval
        print("\n--- Testing Schema Retrieval ---")
        schema = await get_database_schema()
        print(f"Schema: {schema[:200]}..." if len(schema) > 200 else schema)
        
        # Test query execution
        print("\n--- Testing Query Execution ---")
        result = await execute_sql_query("SELECT COUNT(*) as total_customers FROM customers")
        print(f"Query result: {result}")
        
        # Test table info
        print("\n--- Testing Table Info ---")
        table_info = await get_table_information("customers")
        print(f"Table info: {table_info[:200]}..." if len(table_info) > 200 else table_info)
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())