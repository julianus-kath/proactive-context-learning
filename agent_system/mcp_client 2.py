"""
MCP (Model Context Protocol) Client for connecting to the MCP database server.

This module provides a reusable client for agents to interact with the MCP server
that provides standardized access to the PostgreSQL database.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class MCPResponse:
    """Response from MCP server."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MCPClient:
    """
    Client for connecting to the MCP (Model Context Protocol) database server.
    
    This client provides a clean interface for agents to interact with the database
    through the MCP server, following the JSON-RPC 2.0 protocol.
    """
    
    def __init__(
        self, 
        server_url: str = "http://localhost:8000",
        api_key: str = "supersecretapikey",
        timeout: int = 30
    ):
        """
        Initialize the MCP client.
        
        Args:
            server_url: URL of the MCP server
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_id = 0
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    async def connect(self):
        """Establish connection to the MCP server."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def disconnect(self):
        """Close connection to the MCP server."""
        if self.session:
            await self.session.close()
            self.session = None
            
    def _get_next_request_id(self) -> int:
        """Get the next request ID for JSON-RPC."""
        self._request_id += 1
        return self._request_id
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    async def _make_request(self, method: str, params: Dict[str, Any]) -> MCPResponse:
        """
        Make a JSON-RPC request to the MCP server.
        
        Args:
            method: JSON-RPC method name
            params: Method parameters
            
        Returns:
            MCPResponse with the result
        """
        if not self.session:
            await self.connect()
            
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._get_next_request_id()
        }
        
        try:
            async with self.session.post(
                f"{self.server_url}/mcp",
                json=request_data,
                headers=self._get_headers()
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    return MCPResponse(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}"
                    )
                
                result = await response.json()
                
                if "error" in result:
                    return MCPResponse(
                        success=False,
                        error=result["error"].get("message", "Unknown error"),
                        metadata={"error_code": result["error"].get("code")}
                    )
                
                return MCPResponse(
                    success=True,
                    data=result.get("result"),
                    metadata={"request_id": result.get("id")}
                )
                
        except asyncio.TimeoutError:
            return MCPResponse(
                success=False,
                error=f"Request timeout after {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            return MCPResponse(
                success=False,
                error=f"Request failed: {str(e)}"
            )
    
    async def health_check(self) -> MCPResponse:
        """
        Check if the MCP server is healthy.
        
        Returns:
            MCPResponse with health status
        """
        if not self.session:
            await self.connect()
            
        try:
            async with self.session.get(
                f"{self.server_url}/health",
                headers=self._get_headers()
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return MCPResponse(success=True, data=data)
                else:
                    error_text = await response.text()
                    return MCPResponse(
                        success=False,
                        error=f"Health check failed: HTTP {response.status}: {error_text}"
                    )
                    
        except Exception as e:
            return MCPResponse(
                success=False,
                error=f"Health check failed: {str(e)}"
            )
    
    async def get_schema(self) -> MCPResponse:
        """
        Get the complete database schema.
        
        Returns:
            MCPResponse with schema information
        """
        return await self._make_request("call_tool", {
            "name": "get_schema",
            "arguments": {}
        })
    
    async def query(self, sql: str) -> MCPResponse:
        """
        Execute a SQL query.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            MCPResponse with query results
        """
        return await self._make_request("call_tool", {
            "name": "query",
            "arguments": {"sql": sql}
        })
    
    async def get_table_info(self, table_name: str) -> MCPResponse:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            MCPResponse with table information
        """
        return await self._make_request("call_tool", {
            "name": "get_table_info",
            "arguments": {"table_name": table_name}
        })
    
    async def get_sample_data(self, table_name: str, limit: int = 10) -> MCPResponse:
        """
        Get sample data from a table.
        
        Args:
            table_name: Name of the table
            limit: Maximum number of rows to return
            
        Returns:
            MCPResponse with sample data
        """
        return await self._make_request("call_tool", {
            "name": "get_sample_data",
            "arguments": {
                "table_name": table_name,
                "limit": limit
            }
        })
    
    async def list_tools(self) -> MCPResponse:
        """
        List available MCP tools.
        
        Returns:
            MCPResponse with available tools
        """
        return await self._make_request("list_tools", {})


class SyncMCPClient:
    """
    Synchronous wrapper for MCPClient to use in non-async contexts.
    
    This wrapper allows the MCP client to be used in synchronous code
    by running async operations in an event loop.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with same arguments as MCPClient."""
        self._client_args = args
        self._client_kwargs = kwargs
        self._loop = None
        
    def _get_loop(self):
        """Get or create an event loop."""
        try:
            # Try to get the current loop
            loop = asyncio.get_running_loop()
            return loop
        except RuntimeError:
            # No loop running, create a new one
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop
    
    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        loop = self._get_loop()
        
        # If we're already in an async context, we need to run in a new thread
        try:
            # Check if we're in an async context
            asyncio.get_running_loop()
            # We're in an async context, use run_coroutine_threadsafe
            import concurrent.futures
            import threading
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # Not in an async context, run normally
            return loop.run_until_complete(coro)
    
    async def _async_operation(self, operation_name: str, *args, **kwargs):
        """Run an async operation with the MCP client."""
        async with MCPClient(*self._client_args, **self._client_kwargs) as client:
            method = getattr(client, operation_name)
            return await method(*args, **kwargs)
    
    def health_check(self) -> MCPResponse:
        """Synchronous health check."""
        return self._run_async(self._async_operation("health_check"))
    
    def get_schema(self) -> MCPResponse:
        """Synchronous schema retrieval."""
        return self._run_async(self._async_operation("get_schema"))
    
    def query(self, sql: str) -> MCPResponse:
        """Synchronous query execution."""
        return self._run_async(self._async_operation("query", sql))
    
    def get_table_info(self, table_name: str) -> MCPResponse:
        """Synchronous table info retrieval."""
        return self._run_async(self._async_operation("get_table_info", table_name))
    
    def get_sample_data(self, table_name: str, limit: int = 10) -> MCPResponse:
        """Synchronous sample data retrieval."""
        return self._run_async(self._async_operation("get_sample_data", table_name, limit))
    
    def list_tools(self) -> MCPResponse:
        """Synchronous tools listing."""
        return self._run_async(self._async_operation("list_tools"))


# Convenience function for creating a sync client
def create_mcp_client(
    server_url: str = "http://localhost:8000",
    api_key: str = "supersecretapikey",
    timeout: int = 30,
    sync: bool = True
) -> Union[MCPClient, SyncMCPClient]:
    """
    Create an MCP client.
    
    Args:
        server_url: URL of the MCP server
        api_key: API key for authentication
        timeout: Request timeout in seconds
        sync: If True, return a synchronous client; if False, return async client
        
    Returns:
        MCP client instance
    """
    if sync:
        return SyncMCPClient(server_url, api_key, timeout)
    else:
        return MCPClient(server_url, api_key, timeout)


# Example usage
if __name__ == "__main__":
    async def test_async_client():
        """Test the async MCP client."""
        async with MCPClient() as client:
            # Health check
            health = await client.health_check()
            print(f"Health check: {health}")
            
            # Get schema
            schema = await client.get_schema()
            print(f"Schema: {schema}")
            
            # Run a query
            query_result = await client.query("SELECT COUNT(*) as total_customers FROM customers")
            print(f"Query result: {query_result}")
    
    def test_sync_client():
        """Test the sync MCP client."""
        client = SyncMCPClient()
        
        # Health check
        health = client.health_check()
        print(f"Health check: {health}")
        
        # Get schema
        schema = client.get_schema()
        print(f"Schema: {schema}")
        
        # Run a query
        query_result = client.query("SELECT COUNT(*) as total_customers FROM customers")
        print(f"Query result: {query_result}")
    
    print("Testing async client:")
    asyncio.run(test_async_client())
    
    print("\nTesting sync client:")
    test_sync_client()