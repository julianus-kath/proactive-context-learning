"""
Simplified MCP client for database operations.

Calls the MCP server on Windows which handles the actual MSSQL connection.
"""

import os
import httpx
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Simple HTTP client for the MCP server.

    The MCP server runs on Windows and connects to MSSQL.
    This client just makes HTTP calls to it.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("MCP_API_KEY", "supersecretapikey")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            }
        )
        logger.info(f"MCPClient initialized with base_url={self.base_url}")

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if MCP server is healthy."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool via JSON-RPC 2.0 endpoint.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result as dict
        """
        # JSON-RPC 2.0 format as expected by MCP server
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 1,
        }

        try:
            response = await self._client.post("/mcp", json=payload)
            response.raise_for_status()
            result = response.json()

            # JSON-RPC response has result in "result" field
            if "result" in result:
                return result["result"]
            elif "error" in result:
                return {"error": result["error"].get("message", str(result["error"])), "ok": False}
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP tool call failed: {e.response.status_code} - {e.response.text}")
            return {"error": str(e), "ok": False}
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e), "ok": False}

    async def list_tables(self, page: int = 1, page_size: int = 50) -> str:
        """
        List available tables in the database.

        Returns:
            Formatted string with table information
        """
        result = await self._call_tool("list_tables", {
            "page": page,
            "page_size": page_size,
        })

        # Handle list response format (MCP returns [{"type": "text", "text": "..."}])
        if isinstance(result, list):
            texts = [item.get("text", "") for item in result if isinstance(item, dict)]
            return "\n".join(texts) if texts else "No tables found."

        if isinstance(result, dict):
            if result.get("error"):
                logger.error(f"list_tables failed: {result['error']}")
                return f"Error: {result['error']}"
            # Try to get tables or text
            if "text" in result:
                return result["text"]
            tables = result.get("tables", result.get("data", []))
            if tables:
                return str(tables)

        return str(result) if result else "No tables found."

    async def describe_table(self, table_name: str) -> str:
        """
        Get schema details for a specific table.

        Args:
            table_name: Full table name (e.g., "dbo.Customers")

        Returns:
            Formatted string with column details
        """
        result = await self._call_tool("describe_table", {
            "table_name": table_name,
        })

        # Handle list response format
        if isinstance(result, list):
            texts = [item.get("text", "") for item in result if isinstance(item, dict)]
            return "\n".join(texts) if texts else f"No schema found for {table_name}"

        if isinstance(result, dict):
            if result.get("error"):
                logger.error(f"describe_table failed: {result['error']}")
                return f"Error: {result['error']}"
            if "text" in result:
                return result["text"]

        return str(result) if result else f"No schema found for {table_name}"

    async def execute_query(
        self,
        sql: str,
        limit: int = 100,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Execute a SQL query.

        Args:
            sql: SQL query to execute (must be SELECT)
            limit: Max rows to return
            timeout: Query timeout in seconds

        Returns:
            Dict with ok, rows, columns, row_count, or error info
        """
        # MCP server uses "run_query" tool name
        result = await self._call_tool("run_query", {
            "sql": sql,
            "limit": limit,
            "timeout_ms": timeout * 1000,
        })

        # Handle list response format (text content)
        if isinstance(result, list):
            texts = [item.get("text", "") for item in result if isinstance(item, dict)]
            text = "\n".join(texts) if texts else ""
            # Try to parse if it looks like structured data
            if "error" in text.lower():
                return {"ok": False, "error": text}
            return {"ok": True, "text": text, "rows": [], "row_count": 0}

        if isinstance(result, dict):
            return result

        return {"ok": True, "text": str(result)}

    async def search_tables(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for tables matching a query string.

        Args:
            query: Search query (table name, column name, etc.)
            limit: Max results

        Returns:
            List of matching tables with relevance scores
        """
        result = await self._call_tool("search_tables", {
            "query": query,
            "limit": limit,
        })

        if result.get("error"):
            logger.error(f"search_tables failed: {result['error']}")
            return []

        return result.get("tables", result.get("data", []))


def get_mcp_client() -> MCPClient:
    """Create a new MCP client for each request to avoid event loop issues."""
    return MCPClient()
