"""
Base MCP Server implementation.
"""
from typing import Any, Dict, List, Optional, Type
from fastmcp import FastMCP


class BaseMCPServer:
    """Base class for all MCP servers in the crawling agent system."""

    def __init__(
        self,
        name: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        description: Optional[str] = None,
    ):
        """
        Initialize the base MCP server.

        Args:
            name: The name of the server
            host: The host to bind to (default: "0.0.0.0")
            port: The port to listen on (default: 8000)
            description: Optional description of the server
        """
        self.name = name
        self.host = host
        self.port = port
        self.description = description or f"{name} MCP Server"
        
        # Initialize the FastMCP server
        self.mcp = FastMCP(
            name=self.name,
            host=self.host,
            port=self.port,
            description=self.description,
        )

    def run(self, transport: str = "sse"):
        """
        Run the MCP server with the specified transport.

        Args:
            transport: The transport to use (default: "sse")
        """
        print(f"Running {self.name} server with {transport} transport on {self.host}:{self.port}")
        self.mcp.run(transport=transport)