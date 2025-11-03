"""
MCP-based DatabaseClient (sync wrapper) — consolidated to delegate to the
single async implementation in langgraph_integration.mcp_client via a
SyncMCPClient adapter. This avoids duplicated HTTP/envelope logic.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from langgraph_integration.utils.sync_adapter import SyncMCPClient

logger = logging.getLogger(__name__)


class MCPDatabaseClient:
    """Sync facade delegating to the consolidated async MCP client."""

    def __init__(self) -> None:
        self._sync = SyncMCPClient()
        logger.info("MCPDatabaseClient (sync) delegating to async MCPDatabaseTool")

    def query(self, sql: str, limit: Optional[int] = None, enable_redaction: bool = True) -> Tuple[List[str], List[List[Any]]]:
        # Delegate to bounded query; this returns a list of content blocks, not columns/rows.
        # For legacy API, we return a textual result under a single column when available.
        content = self._sync.query_bounded(sql, max_rows=limit)
        if content and isinstance(content, list) and isinstance(content[0], dict):
            text = content[0].get("text", "")
            return ["result"], [[text]]
        return ["result"], [[""]]

    def search_tables(self, pattern: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        # Map to consolidated search (note: new API uses keyword + pagination; offset unused)
        result = self._sync.search_tables(pattern, page=1, page_size=limit)
        return result if isinstance(result, list) else []

    def describe_table(self, table_name: str) -> Dict[str, Any]:
        result = self._sync.describe_table(table_name)
        return result[0] if isinstance(result, list) and result else {}

    def list_relations(self, table_name: str) -> Dict[str, Any]:
        result = self._sync.list_relations(table_name)
        return result[0] if isinstance(result, list) and result else {}

    def health_check(self) -> bool:
        return self._sync.health_check()


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