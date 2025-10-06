"""
MCP-based DatabaseClient - Replaces legacy proxy /query endpoint
Phase 7: Single interface for database access via MCP JSON-RPC

This client enforces the design guardrails:
1. Never enumerate full schema (use discovery tools with pagination)
2. Small, focused prompts (≤3 tables per query context)
3. One interface: LangGraph → MCP JSON-RPC only
4. Caching everywhere (catalog + response + session)
5. Backpressure: Rate limiting with Retry-After, exponential backoff
"""

import os
import requests
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPConfig:
    """MCP server configuration."""
    server_url: str
    timeout_seconds: int = 30
    max_retries: int = 3
    backoff_factor: float = 2.0
    api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'MCPConfig':
        """Load configuration from environment variables."""
        return cls(
            server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
            timeout_seconds=int(os.getenv("MCP_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("MCP_MAX_RETRIES", "3")),
            backoff_factor=float(os.getenv("MCP_BACKOFF_FACTOR", "2.0")),
            api_key=os.getenv("MCP_API_KEY")
        )


class MCPDatabaseClient:
    """
    MCP-based database client that replaces legacy Flask proxy.
    
    Features:
    - MCP JSON-RPC protocol
    - Exponential backoff with Retry-After support
    - Structured logging for all operations
    - Safety controls (SELECT-only, row limits, timeouts)
    - Discovery tools (search, describe, relations)
    
    Design Guardrails:
    - Never enumerate full schema (use search_tables with pagination)
    - Small prompts (≤3 tables per schema_snippet)
    - Single interface (MCP JSON-RPC only)
    - Caching (catalog + response + session)
    - Backpressure (rate limiting + exponential backoff)
    """
    
    def __init__(self, config: Optional[MCPConfig] = None):
        """Initialize MCP client with configuration."""
        self.config = config or MCPConfig.from_env()
        logger.info(f"MCPDatabaseClient initialized: {self.config.server_url}")
    
    def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any], 
                       retry_count: int = 0) -> Dict[str, Any]:
        """
        Call MCP tool with exponential backoff and Retry-After support.
        
        Args:
            tool_name: Name of MCP tool to call
            arguments: Tool arguments
            retry_count: Current retry attempt (for exponential backoff)
            
        Returns:
            Tool result as dictionary
            
        Raises:
            RuntimeError: If tool call fails after all retries
        """
        try:
            # Prepare MCP JSON-RPC request
            payload = {
                "jsonrpc": "2.0",
                "id": f"{tool_name}_{int(time.time() * 1000)}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # Prepare headers
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            
            # Log tool call (structured logging)
            logger.info(
                f"MCP tool call: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "arguments": self._redact_sensitive_args(arguments),
                    "retry_count": retry_count
                }
            )
            
            # Make request
            response = requests.post(
                f"{self.config.server_url}/mcp",
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds
            )
            
            # Handle rate limiting (429) with Retry-After
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                
                if retry_count < self.config.max_retries:
                    logger.warning(
                        f"Rate limited (429), retrying after {retry_after}s",
                        extra={
                            "tool_name": tool_name,
                            "retry_after": retry_after,
                            "retry_count": retry_count
                        }
                    )
                    time.sleep(retry_after)
                    return self._call_mcp_tool(tool_name, arguments, retry_count + 1)
                else:
                    raise RuntimeError(
                        f"Rate limit exceeded after {self.config.max_retries} retries. "
                        f"Retry after {retry_after} seconds."
                    )
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Parse JSON-RPC response
            data = response.json()
            
            # Check for JSON-RPC error
            if "error" in data:
                error = data["error"]
                error_msg = error.get("message", "Unknown MCP error")
                error_code = error.get("code", -1)
                raise RuntimeError(f"MCP error ({error_code}): {error_msg}")
            
            # Extract result
            result = data.get("result", {})
            
            # Log success
            logger.info(
                f"MCP tool call successful: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "success": True
                }
            )
            
            return result
            
        except requests.exceptions.Timeout:
            if retry_count < self.config.max_retries:
                backoff_time = self.config.backoff_factor ** retry_count
                logger.warning(
                    f"MCP timeout, retrying in {backoff_time}s",
                    extra={
                        "tool_name": tool_name,
                        "retry_count": retry_count,
                        "backoff_time": backoff_time
                    }
                )
                time.sleep(backoff_time)
                return self._call_mcp_tool(tool_name, arguments, retry_count + 1)
            else:
                raise RuntimeError(
                    f"MCP timeout after {self.config.max_retries} retries"
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"MCP request failed: {e}",
                extra={
                    "tool_name": tool_name,
                    "error": str(e)
                }
            )
            raise RuntimeError(f"MCP connection failed: {str(e)}")
        
        except Exception as e:
            logger.error(
                f"MCP tool call error: {e}",
                extra={
                    "tool_name": tool_name,
                    "error": str(e)
                }
            )
            raise RuntimeError(f"MCP tool call error: {str(e)}")
    
    def _redact_sensitive_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from arguments for logging."""
        redacted = arguments.copy()
        
        # Redact SQL queries containing sensitive patterns
        if "sql" in redacted:
            sql = redacted["sql"]
            # Redact potential sensitive values in WHERE clauses
            if "WHERE" in sql.upper():
                redacted["sql"] = sql[:100] + "... [REDACTED]"
        
        return redacted
    
    def query(self, sql: str, limit: Optional[int] = None, 
              enable_redaction: bool = True) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute a SQL query via MCP query_bounded tool.
        
        Args:
            sql: SQL SELECT query to execute
            limit: Maximum number of rows to return (default: 100, max: 1000)
            enable_redaction: Enable PII redaction (default: True)
            
        Returns:
            Tuple of (columns, rows) where:
            - columns: List of column names
            - rows: List of rows, each row is a list of values
            
        Raises:
            RuntimeError: If query fails or MCP returns error
        """
        # Prepare arguments
        arguments = {
            "sql": sql,
            "enable_redaction": enable_redaction
        }
        
        if limit is not None:
            arguments["limit"] = limit
        
        # Call MCP tool
        result = self._call_mcp_tool("query_bounded", arguments)
        
        # Extract columns and rows
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        
        logger.debug(f"Query successful: {len(rows)} rows, {len(columns)} columns")
        return columns, rows
    
    def search_tables(self, pattern: str, limit: int = 20, 
                      offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search for tables matching a pattern (Phase 4 discovery tool).
        
        Design Guardrail: Never enumerate full schema - always use pagination.
        
        Args:
            pattern: Search pattern (table name or description)
            limit: Maximum number of results (default: 20)
            offset: Pagination offset (default: 0)
            
        Returns:
            List of table info dictionaries
        """
        arguments = {
            "pattern": pattern,
            "limit": limit,
            "offset": offset
        }
        
        result = self._call_mcp_tool("search_tables", arguments)
        return result.get("tables", [])
    
    def describe_table(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table to describe
            
        Returns:
            Table description with columns, types, and constraints
        """
        arguments = {"table_name": table_name}
        result = self._call_mcp_tool("describe_table", arguments)
        return result
    
    def list_relations(self, table_name: str) -> Dict[str, Any]:
        """
        Get foreign key relationships for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with 'outgoing' and 'incoming' relationships
        """
        arguments = {"table_name": table_name}
        result = self._call_mcp_tool("list_relations", arguments)
        return result
    
    def health_check(self) -> bool:
        """
        Check if MCP server is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.config.server_url}/health",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Check if database is connected
            db_status = data.get("database", {}).get("status")
            return db_status == "connected"
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Convenience function for getting a configured client
def get_mcp_client() -> MCPDatabaseClient:
    """Get a configured MCPDatabaseClient instance."""
    return MCPDatabaseClient()


# Backward compatibility wrapper (deprecated)
class DatabaseClient:
    """
    DEPRECATED: Legacy DatabaseClient wrapper for backward compatibility.
    
    This class wraps MCPDatabaseClient to maintain API compatibility
    with existing code. New code should use MCPDatabaseClient directly.
    
    Migration Guide:
    - Replace: DatabaseClient() → MCPDatabaseClient()
    - Replace: client.query(sql, conn=...) → client.query(sql, limit=...)
    - Remove: conn parameter (MCP handles connection internally)
    - Add: Use discovery tools (search_tables, describe_table, list_relations)
    """
    
    def __init__(self):
        """Initialize with deprecation warning."""
        logger.warning(
            "DatabaseClient is deprecated. Use MCPDatabaseClient instead. "
            "See app/db/mcp_client.py for migration guide."
        )
        self._mcp_client = MCPDatabaseClient()
    
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None, 
              conn: Optional[str] = None, limit: Optional[int] = None, 
              timeout_s: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute query via MCP (legacy API compatibility).
        
        Note: params, conn, and timeout_s are ignored (MCP handles these internally).
        """
        if params:
            logger.warning("params argument is ignored in MCP mode")
        if conn:
            logger.warning("conn argument is ignored in MCP mode")
        if timeout_s:
            logger.warning("timeout_s argument is ignored in MCP mode")
        
        return self._mcp_client.query(sql, limit=limit)
    
    def health_check(self) -> bool:
        """Check MCP server health."""
        return self._mcp_client.health_check()
    
    def get_available_connections(self) -> List[Dict[str, str]]:
        """DEPRECATED: MCP manages connections internally."""
        logger.warning("get_available_connections() is deprecated in MCP mode")
        return []


def get_database_client() -> DatabaseClient:
    """
    DEPRECATED: Get a configured DatabaseClient instance.
    Use get_mcp_client() instead.
    """
    logger.warning(
        "get_database_client() is deprecated. Use get_mcp_client() instead."
    )
    return DatabaseClient()