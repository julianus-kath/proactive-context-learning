"""
Base MCP Connector implementation.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import nest_asyncio
from fastmcp.client.client import ClientSession
from mcp.client.sse import sse_client


# Apply nest_asyncio to allow nested event loops (needed for interactive environments)
nest_asyncio.apply()


class BaseMCPConnector:
    """Base class for all MCP connectors in the crawling agent system."""

    def __init__(
        self,
        server_url: str,
        server_name: str,
    ):
        """
        Initialize the base MCP connector.

        Args:
            server_url: The URL of the MCP server to connect to
            server_name: The name of the server
        """
        self.server_url = server_url
        self.server_name = server_name
        self.session = None
        self.read_stream = None
        self.write_stream = None

    async def connect(self):
        """Connect to the MCP server."""
        if self.session:
            # Already connected
            return self.session
            
        # Create the SSE client context manager
        self.sse_ctx = sse_client(self.server_url)
        # Enter the context manager to get the read and write streams
        self.read_stream, self.write_stream = await self.sse_ctx.__aenter__()
        # Create the client session
        self.session = ClientSession(self.read_stream, self.write_stream)
        # Initialize the session
        await self.session.initialize()
        
        return self.session

    async def disconnect(self):
        """Disconnect from the MCP server."""
        # Close the session if it exists
        if self.session:
            await self.session.close()
            self.session = None
        
        # Exit the SSE client context manager
        if hasattr(self, 'sse_ctx'):
            await self.sse_ctx.__aexit__(None, None, None)
            self.read_stream = None
            self.write_stream = None

    async def list_tools(self):
        """List all available tools on the server."""
        if not self.session:
            raise RuntimeError("Connection not established. Use 'async with' to create a connection.")
        
        tools_result = await self.session.list_tools()
        return tools_result.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 5.0):
        """
        Call a tool on the server with a timeout.

        Args:
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            timeout: Maximum time to wait for a response (in seconds)

        Returns:
            The result of the tool call
        """
        if not self.session:
            raise RuntimeError("Connection not established. Use 'async with' to create a connection.")
        
        try:
            # Create a task for the tool call
            task = asyncio.create_task(self.session.call_tool(tool_name, arguments=arguments))
            
            # Wait for the task to complete with a timeout
            start_time = time.time()
            result = await asyncio.wait_for(task, timeout=timeout)
            
            # Log the execution time
            execution_time = time.time() - start_time
            print(f"Tool call '{tool_name}' executed in {execution_time:.2f} seconds")
            
            return result.content[0].text
            
        except asyncio.TimeoutError:
            # Cancel the task if it times out
            task.cancel()
            raise TimeoutError(f"Tool call '{tool_name}' timed out after {timeout} seconds")

    async def __aenter__(self):
        """Async context manager entry."""
        # Create the SSE client context manager
        self.sse_ctx = sse_client(self.server_url)
        # Enter the context manager to get the read and write streams
        self.read_stream, self.write_stream = await self.sse_ctx.__aenter__()
        # Create the client session
        self.session = ClientSession(self.read_stream, self.write_stream)
        # Initialize the session
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Close the session if it exists
        if self.session:
            await self.session.close()
            self.session = None
        
        # Exit the SSE client context manager
        if hasattr(self, 'sse_ctx'):
            await self.sse_ctx.__aexit__(exc_type, exc_val, exc_tb)
            self.read_stream = None
            self.write_stream = None