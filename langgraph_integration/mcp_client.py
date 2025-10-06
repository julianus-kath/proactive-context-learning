"""
MCP Database Tool for LangGraph Integration
Phase 2 Blueprint Implementation
Phase 5 Enhancement: Added Phase 4 discovery tools support

This module implements the MCPDatabaseTool class as specified in the blueprint,
with additional robustness and error handling.
"""

import os
import aiohttp
import asyncio
import logging
import time
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
    
    # ========== PHASE 4 DISCOVERY TOOLS ==========
    
    async def list_tables(
        self, 
        page: int = 1, 
        page_size: int = 25, 
        schema: Optional[str] = None, 
        pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List tables with pagination and filtering (Phase 4 discovery tool).
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of tables per page (max 100)
            schema: Optional schema filter
            pattern: Optional table name pattern (SQL LIKE syntax)
            
        Returns:
            Paged list of table summaries
        """
        arguments = {"page": page, "page_size": page_size}
        if schema:
            arguments["schema"] = schema
        if pattern:
            arguments["pattern"] = pattern
        return await self.call_tool("list_tables", arguments)
    
    async def search_tables(
        self, 
        keyword: str, 
        page: int = 1, 
        page_size: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Search tables by keyword with relevance ranking (Phase 4 discovery tool).
        
        Args:
            keyword: Search keyword (searches table names, columns, types)
            page: Page number (1-indexed)
            page_size: Number of results per page (max 100)
            
        Returns:
            Ranked list of matching tables
        """
        return await self.call_tool("search_tables", {
            "keyword": keyword,
            "page": page,
            "page_size": page_size
        })
    
    async def describe_table(
        self, 
        table_name: str, 
        include_sample: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get detailed table information (Phase 4 discovery tool).
        
        Args:
            table_name: Fully qualified table name (schema.table) or simple name
            include_sample: Whether to include sample data (requires DB query)
            
        Returns:
            Detailed table information including columns, foreign keys, primary keys
        """
        return await self.call_tool("describe_table", {
            "table_name": table_name,
            "include_sample": include_sample
        })
    
    async def list_relations(
        self, 
        table_name: str
    ) -> List[Dict[str, Any]]:
        """
        List all tables related to the given table via foreign keys (Phase 4 discovery tool).
        
        Args:
            table_name: Fully qualified table name (schema.table) or simple name
            
        Returns:
            List of related tables with relationship information
        """
        return await self.call_tool("list_relations", {
            "table_name": table_name
        })
    
    async def query_bounded(
        self, 
        sql: str, 
        max_rows: Optional[int] = None, 
        timeout_ms: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a bounded SQL query with safety controls (Phase 2/4 tool).
        
        Args:
            sql: SQL query to execute (SELECT only)
            max_rows: Maximum number of rows to return (default: 1000)
            timeout_ms: Query timeout in milliseconds (default: 30000)
            
        Returns:
            Query results with safety guarantees
        """
        arguments = {"sql": sql}
        if max_rows is not None:
            arguments["max_rows"] = max_rows
        if timeout_ms is not None:
            arguments["timeout_ms"] = timeout_ms
        return await self.call_tool("query_bounded", arguments)
    
    async def call_tool_with_retry(
        self, 
        tool_name: str, 
        arguments: dict, 
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Call a tool with retry logic and backoff for 429 (rate limit) errors.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tool response content
            
        Raises:
            ValueError: If all retries are exhausted
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self.call_tool(tool_name, arguments)
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limit error
                    # Extract Retry-After header if available
                    retry_after = e.headers.get("Retry-After", str(2 ** attempt))
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 2 ** attempt  # Exponential backoff
                    
                    logger.warning(f"Rate limited (429), retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    raise  # Re-raise non-429 errors immediately
            except Exception as e:
                last_error = e
                logger.warning(f"Tool call attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        raise ValueError(f"Tool call failed after {max_retries} attempts: {str(last_error)}")


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


async def execute_sql_query_with_retry(sql: str, max_retries: int = 3) -> str:
    """
    Execute a SQL query with retry logic.
    
    Args:
        sql: SQL query to execute
        max_retries: Maximum number of retry attempts
        
    Returns:
        Formatted query results
    """
    tool = MCPDatabaseTool()
    last_error = None
    
    for attempt in range(max_retries):
        try:
            query_content = await tool.query(sql)
            if query_content and len(query_content) > 0:
                return query_content[0].get("text", "No results")
            return "No results"
        except Exception as e:
            last_error = e
            logger.warning(f"Query attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
    
    return f"Error executing query after {max_retries} attempts: {str(last_error)}"


async def health_check() -> bool:
    """
    Check if the MCP server is healthy.
    
    Returns:
        True if the server is healthy, False otherwise
    """
    tool = MCPDatabaseTool()
    return await tool.health_check()


async def index_database() -> Dict[str, Any]:
    """
    Index the database schema for faster lookups.
    
    Returns:
        Dictionary containing the schema index
    """
    tool = MCPDatabaseTool()
    try:
        schema_content = await tool.get_schema()
        if schema_content and len(schema_content) > 0:
            schema_text = schema_content[0].get("text", "")
            
            # Parse schema text to build index
            # This is a simplified version - you may want to enhance this
            import json
            try:
                schema_data = json.loads(schema_text)
                if isinstance(schema_data, list):
                    index = {
                        "tables": {},
                        "total_tables": len(schema_data),
                        "indexed_at": None
                    }
                    
                    for table in schema_data:
                        table_name = table.get("name", "")
                        if table_name:
                            index["tables"][table_name] = {
                                "columns": table.get("columns", []),
                                "column_count": len(table.get("columns", []))
                            }
                    
                    return index
            except json.JSONDecodeError:
                # If schema is not JSON, create a simple index
                return {
                    "tables": {},
                    "total_tables": 0,
                    "indexed_at": None,
                    "raw_schema": schema_text[:500]  # First 500 chars
                }
        
        return {"tables": {}, "total_tables": 0, "indexed_at": None}
    except Exception as e:
        logger.error(f"Error indexing database: {e}")
        return {"error": str(e), "tables": {}, "total_tables": 0}


async def get_all_schemas() -> List[str]:
    """
    Get all available schemas in the database.
    
    Returns:
        List of schema names
    """
    tool = MCPDatabaseTool()
    try:
        # Try to query for schemas
        query = """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'sys')
        ORDER BY schema_name
        """
        
        result_content = await tool.query(query)
        if result_content and len(result_content) > 0:
            result_text = result_content[0].get("text", "")
            
            # Parse result to extract schema names
            import json
            try:
                result_data = json.loads(result_text)
                if isinstance(result_data, list):
                    return [row.get("schema_name", "") for row in result_data if row.get("schema_name")]
            except json.JSONDecodeError:
                pass
        
        # Fallback to default schema
        return ["public"]
    except Exception as e:
        logger.error(f"Error getting schemas: {e}")
        return ["public"]


async def get_schema_index() -> Dict[str, Any]:
    """
    Get the schema index (alias for index_database).
    
    Returns:
        Dictionary containing the schema index
    """
    return await index_database()


async def get_selective_schema(table_names: List[str]) -> str:
    """
    Get schema information for specific tables only.
    
    DEPRECATED: Use describe_table_batch() for Phase 5 instead.
    
    Args:
        table_names: List of table names to get schema for
        
    Returns:
        Formatted schema information for selected tables
    """
    tool = MCPDatabaseTool()
    try:
        # Get full schema first
        schema_content = await tool.get_schema()
        if not schema_content or len(schema_content) == 0:
            return "No schema information available"
        
        schema_text = schema_content[0].get("text", "")
        
        # Try to parse as JSON
        import json
        try:
            schema_data = json.loads(schema_text)
            if isinstance(schema_data, list):
                # Filter to only requested tables
                filtered_tables = [
                    table for table in schema_data
                    if table.get("name", "") in table_names
                ]
                
                if filtered_tables:
                    return json.dumps(filtered_tables, indent=2)
                else:
                    return f"No schema information found for tables: {', '.join(table_names)}"
        except json.JSONDecodeError:
            # If not JSON, try to filter text-based schema
            lines = schema_text.split('\n')
            filtered_lines = []
            include = False
            
            for line in lines:
                # Simple heuristic: include lines that mention the table names
                if any(table_name in line for table_name in table_names):
                    include = True
                    filtered_lines.append(line)
                elif include and (line.strip() == '' or line.startswith('Table:')):
                    include = False
                elif include:
                    filtered_lines.append(line)
            
            if filtered_lines:
                return '\n'.join(filtered_lines)
            else:
                return f"No schema information found for tables: {', '.join(table_names)}"
        
        return schema_text
    except Exception as e:
        logger.error(f"Error getting selective schema: {e}")
        return f"Error getting selective schema: {str(e)}"


# ========== PHASE 5: DISCOVERY TOOL UTILITY FUNCTIONS ==========

async def list_tables_mcp(
    page: int = 1, 
    page_size: int = 25, 
    schema: Optional[str] = None, 
    pattern: Optional[str] = None
) -> Dict[str, Any]:
    """
    List tables with pagination (Phase 4 discovery tool).
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of tables per page (max 100)
        schema: Optional schema filter
        pattern: Optional table name pattern
        
    Returns:
        Dictionary with tables, pagination info, and metadata
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.list_tables(page, page_size, schema, pattern)
        if content and len(content) > 0:
            import json
            # Parse JSON response
            response_text = content[0].get("text", "{}")
            return json.loads(response_text)
        return {"ok": False, "error": "No response from MCP server"}
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return {"ok": False, "error": str(e)}


async def search_tables_mcp(
    keyword: str, 
    page: int = 1, 
    page_size: int = 25
) -> Dict[str, Any]:
    """
    Search tables by keyword (Phase 4 discovery tool).
    
    Args:
        keyword: Search keyword
        page: Page number (1-indexed)
        page_size: Number of results per page (max 100)
        
    Returns:
        Dictionary with ranked search results
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.search_tables(keyword, page, page_size)
        if content and len(content) > 0:
            import json
            response_text = content[0].get("text", "{}")
            return json.loads(response_text)
        return {"ok": False, "error": "No response from MCP server"}
    except Exception as e:
        logger.error(f"Error searching tables: {e}")
        return {"ok": False, "error": str(e)}


async def describe_table_mcp(
    table_name: str, 
    include_sample: bool = False
) -> Dict[str, Any]:
    """
    Get detailed table information (Phase 4 discovery tool).
    
    Args:
        table_name: Fully qualified table name or simple name
        include_sample: Whether to include sample data
        
    Returns:
        Dictionary with table details (columns, foreign keys, primary keys)
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.describe_table(table_name, include_sample)
        if content and len(content) > 0:
            import json
            response_text = content[0].get("text", "{}")
            return json.loads(response_text)
        return {"ok": False, "error": "No response from MCP server"}
    except Exception as e:
        logger.error(f"Error describing table: {e}")
        return {"ok": False, "error": str(e)}


async def describe_table_batch(table_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Describe multiple tables in batch (Phase 5 helper).
    
    Args:
        table_names: List of table names to describe (max 3 recommended)
        
    Returns:
        Dictionary mapping table names to their descriptions
    """
    tool = MCPDatabaseTool()
    results = {}
    
    for table_name in table_names[:3]:  # Limit to 3 tables max
        try:
            content = await tool.describe_table(table_name, include_sample=False)
            if content and len(content) > 0:
                import json
                response_text = content[0].get("text", "{}")
                results[table_name] = json.loads(response_text)
            else:
                results[table_name] = {"ok": False, "error": "No response"}
        except Exception as e:
            logger.error(f"Error describing table {table_name}: {e}")
            results[table_name] = {"ok": False, "error": str(e)}
    
    return results


async def list_relations_mcp(table_name: str) -> Dict[str, Any]:
    """
    List related tables (Phase 4 discovery tool).
    
    Args:
        table_name: Fully qualified table name or simple name
        
    Returns:
        Dictionary with related tables and relationship information
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.list_relations(table_name)
        if content and len(content) > 0:
            import json
            response_text = content[0].get("text", "{}")
            return json.loads(response_text)
        return {"ok": False, "error": "No response from MCP server"}
    except Exception as e:
        logger.error(f"Error listing relations: {e}")
        return {"ok": False, "error": str(e)}


async def query_bounded_mcp(
    sql: str, 
    max_rows: Optional[int] = None, 
    timeout_ms: Optional[int] = None
) -> str:
    """
    Execute a bounded SQL query (Phase 2/4 tool).
    
    Args:
        sql: SQL query to execute
        max_rows: Maximum number of rows (default: 1000)
        timeout_ms: Query timeout in milliseconds (default: 30000)
        
    Returns:
        Formatted query results
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.query_bounded(sql, max_rows, timeout_ms)
        if content and len(content) > 0:
            return content[0].get("text", "No results")
        return "No results"
    except Exception as e:
        logger.error(f"Error executing bounded query: {e}")
        return f"Error executing query: {str(e)}"


def build_schema_snippet(table_descriptions: Dict[str, Dict[str, Any]]) -> str:
    """
    Build a compact schema snippet from table descriptions (Phase 5 helper).
    
    Args:
        table_descriptions: Dictionary of table descriptions from describe_table_batch
        
    Returns:
        Formatted schema snippet string (compact, ≤3 tables)
    """
    import json
    
    snippet_parts = []
    
    for table_name, desc in table_descriptions.items():
        if not desc.get("ok", False):
            continue
        
        data = desc.get("data", {})
        table_info = data.get("table", {})
        columns = data.get("columns", [])
        primary_keys = data.get("primary_keys", [])
        foreign_keys = data.get("foreign_keys", [])
        
        # Format table header
        full_name = table_info.get("full_name", table_name)
        snippet_parts.append(f"\nTable: {full_name}")
        
        # Format columns
        snippet_parts.append("Columns:")
        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "")
            nullable = " NULL" if col.get("nullable", True) else " NOT NULL"
            snippet_parts.append(f"  - {col_name}: {col_type}{nullable}")
        
        # Format primary keys
        if primary_keys:
            pk_cols = [pk.get("column", "") for pk in primary_keys]
            snippet_parts.append(f"Primary Key: {', '.join(pk_cols)}")
        
        # Format foreign keys
        if foreign_keys:
            snippet_parts.append("Foreign Keys:")
            for fk in foreign_keys:
                fk_col = fk.get("column", "")
                ref_table = fk.get("referenced_table", "")
                ref_col = fk.get("referenced_column", "")
                snippet_parts.append(f"  - {fk_col} -> {ref_table}.{ref_col}")
    
    return "\n".join(snippet_parts) if snippet_parts else "No schema information available"


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