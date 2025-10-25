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
import json
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "supersecretapikey")

logger = logging.getLogger(__name__)

# Import debug logger for comprehensive logging
try:
    from .debug_logger import get_debug_logger
    debug_logger = get_debug_logger()
except ImportError:
    debug_logger = None


def _extract_json_from_text(content: str) -> Dict[str, Any]:
    """
    Extract JSON from pretty-printed text that contains 'Full response (JSON): {…}'.
    
    This handles the case where MCP server returns decorated text like:
        "Full response (JSON): {\"data\": {\"tables\": [...], \"page_info\": {...}}}"
    
    Supports multiple formats:
    - With "Full response (JSON):" marker
    - With markdown code fences (```json ... ```)
    - Plain JSON
    - Already-parsed dictionaries
    
    Args:
        content: Text content potentially containing JSON
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If no valid JSON object found or parsing fails
    """
    # If it's already a dict, return it
    if isinstance(content, dict):
        return content
    
    if not isinstance(content, str):
        raise ValueError(f"Content must be str or dict, got {type(content).__name__}")
    
    # Trim whitespace
    original_content = content
    content = content.strip()
    
    if not content:
        raise ValueError("Content is empty after stripping whitespace")
    
    # Remove common markdown markers
    content = content.replace("```json", "").replace("```", "")
    
    # Look for the JSON marker and extract what comes after it
    # Try exact matches first (in priority order)
    markers_to_try = [
        "📊 Full response (JSON):",  # With emoji (current format)
        "Full response (JSON):",      # Without emoji (legacy format)
        "📊 Full response (json):",   # Emoji + lowercase
        "Full response (json):",      # Lowercase only
        "JSON Response:",             # Alternative format
        "json response:",             # Alternative lowercase
    ]
    
    marker_found = False
    for marker in markers_to_try:
        if marker in content:
            parts = content.split(marker, 1)
            if len(parts) > 1:
                content = parts[1].strip()
                marker_found = True
                logger.debug(f"[EXTRACT_MARKER] Found marker: '{marker}'")
                break
    
    if not marker_found:
        logger.debug(f"[EXTRACT_MARKER] No marker found in content, will extract first JSON object")
    
    # Try to find JSON object boundaries
    start = content.find("{")
    end = content.rfind("}")
    
    if start == -1:
        raise ValueError(f"No JSON object found (no opening brace '{{') in content: {content[:200]}")
    
    if end == -1 or end <= start:
        raise ValueError(f"No JSON object found (mismatched or no closing brace '}}') in content: {content[:200]}")
    
    # Extract the JSON string
    json_str = content[start:end+1]
    
    # Validate it's not empty
    if not json_str or json_str.strip() == "{}":
        # Empty JSON might still be valid, but let's try to find if there's better content
        if json_str == "{}":
            logger.debug("Extracted empty JSON object: {}")
        else:
            raise ValueError(f"Extracted JSON appears empty or malformed: {json_str[:100]}")
    
    # Try to parse it
    try:
        logger.debug(f"Attempting to parse JSON string (length: {len(json_str)}, start_pos: {start}, end_pos: {end})")
        logger.debug(f"[EXTRACT_JSON_PREVIEW] First 200 chars: {json_str[:200]}")
        parsed = json.loads(json_str)
        logger.debug(f"[EXTRACT_SUCCESS] Successfully parsed JSON with keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'NOT_DICT'}")
        return parsed
    except json.JSONDecodeError as e:
        # Provide detailed error information
        error_details = f"JSON decode error at line {e.lineno}, column {e.colno}: {e.msg}"
        problematic_section = json_str[max(0, e.pos-50):min(len(json_str), e.pos+50)]
        logger.error(f"[EXTRACT_JSON_ERROR] {error_details}\n   Context: ...{problematic_section}...")
        raise ValueError(f"{error_details}\n   Context: ...{problematic_section}...")


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
        # Log tool call initiation
        if debug_logger:
            debug_logger.tool_call(tool_name, arguments)
        
        start_time = time.time()
        
        # Initialize if not already done
        if not self._initialized:
            if not await self.initialize():
                error_msg = "Failed to initialize MCP session"
                if debug_logger:
                    debug_logger.tool_result(tool_name, None, error=error_msg)
                raise ValueError(error_msg)
        
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
                # Use longer timeout for schema operations (they can be slow on first run)
                # Default 30s, but 120s for get_schema (expensive operation)
                timeout_seconds = 120 if tool_name == "get_schema" else 30
                
                async with session.post(
                    f"{self.mcp_url}/mcp", 
                    json=payload, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds)
                ) as response:
                    # Set proper content-type check
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        logger.warning(f"Unexpected content-type: {content_type}")
                    
                    response.raise_for_status()
                    
                    # Safely parse JSON
                    try:
                        data = await response.json()
                    except ValueError as json_err:
                        error_msg = f"Failed to parse JSON response: {json_err}"
                        logger.error(error_msg)
                        logger.error(f"Response text: {await response.text()}")
                        if debug_logger:
                            debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
                        raise ValueError(f"Invalid JSON from MCP server: {json_err}")
                    
                    if data is None or not isinstance(data, dict):
                        error_msg = f"Invalid response data type: {type(data)}"
                        logger.error(f"MCP call failed: {error_msg}")
                        if debug_logger:
                            debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
                        raise ValueError("MCP call failed: No response data or invalid type")
                    
                    # Check for JSON-RPC errors (standard envelope)
                    if "error" in data and data["error"] is not None:
                        error_info = data["error"]
                        if isinstance(error_info, dict):
                            error_msg = error_info.get("message", "Unknown MCP error")
                            error_code = error_info.get("code", -1)
                            logger.error(f"MCP server error (code {error_code}): {error_msg}")
                        else:
                            error_msg = str(error_info)
                            logger.error(f"MCP server error: {error_msg}")
                        if debug_logger:
                            debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
                        raise ValueError(f"MCP server error: {error_msg}")
                    
                    # Return the content from the result - handle both formats
                    result = data.get("result", {})
                    
                    # If result is empty or None, this is likely an error state
                    if not result:
                        logger.warning("MCP result is empty, checking for alternative response format")
                        if "data" in data:
                            # Alternative format support
                            result = {"content": [{"type": "text", "text": json.dumps(data["data"])}]}
                        else:
                            error_msg = "MCP response has empty result and no alternative data format"
                            if debug_logger:
                                debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
                            raise ValueError(error_msg)
                    
                    # Ensure content is a list
                    content = result.get("content", [])
                    if not isinstance(content, list):
                        logger.warning(f"Content is not a list, converting: {type(content)}")
                        content = [{"type": "text", "text": str(content)}]
                    
                    duration_ms = (time.time() - start_time) * 1000
                    logger.info(f"✅ MCP tool call successful, received {len(content)} content items")
                    
                    if debug_logger:
                        debug_logger.tool_result(tool_name, {"content_items": len(content)}, duration_ms=duration_ms)
                    
                    return content
                    
        except asyncio.TimeoutError as e:
            error_msg = f"MCP server timeout (>{timeout_seconds}s) - server at {self.mcp_url} may be unreachable or overloaded"
            logger.error(f"⏱️  TIMEOUT: {error_msg}")
            logger.error(f"   → Check Windows MCP server is running and accessible")
            logger.error(f"   → Verify MCP_SERVER_URL={self.mcp_url} is correct")
            logger.error(f"   → Check network connectivity to the Windows machine")
            if debug_logger:
                debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
            raise ValueError(error_msg) from e
        except aiohttp.ClientError as e:
            error_msg = f"HTTP error: {e}"
            logger.error(f"HTTP error calling MCP server: {e}")
            if debug_logger:
                debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
            raise
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"Validation error in MCP call: {e}")
            if debug_logger:
                debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error calling MCP server: {e}", exc_info=True)
            if debug_logger:
                debug_logger.tool_result(tool_name, None, error=error_msg, duration_ms=(time.time()-start_time)*1000)
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
    ) -> Dict[str, Any]:
        """
        List tables with pagination and filtering (Phase 4 discovery tool).
        Properly handles JSON extraction and returns structured response with pagination info.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of tables per page (max 100)
            schema: Optional schema filter
            pattern: Optional table name pattern (SQL LIKE syntax)
            
        Returns:
            Dictionary with {
                "ok": bool,
                "data": {
                    "tables": [...],
                    "pagination": {"total_items": N, "total_pages": P, "page": page, "page_size": page_size}
                }
            }
        """
        arguments = {"page": page, "page_size": page_size}
        if schema:
            arguments["schema"] = schema
        if pattern:
            arguments["pattern"] = pattern
        
        result = await self.call_tool("list_tables", arguments)
        
        try:
            # Extract and parse JSON from content
            if result and len(result) > 0:
                content_item = result[0]
                content_text = content_item.get("text", "")
                
                # Parse JSON, handling "Full response (JSON):" marker
                payload = _extract_json_from_text(content_text)
                
                # Extract tables and pagination info
                tables = payload.get("data", {}).get("tables", [])
                page_info = payload.get("data", {}).get("page_info", {})
                total_items = page_info.get("total_items", len(tables))
                total_pages = page_info.get("total_pages", 1)
                
                # Log scout mode operation with CORRECT total_items
                if debug_logger:
                    tables_found = [t.get("name", "") or t.get("full_name", "") for t in tables]
                    debug_logger.scout_mode_operation(
                        "list_tables",
                        f"page={page}, page_size={page_size}",
                        tables_found if tables_found else ["(no tables)"],
                        {"total_tables": total_items, "total_pages": total_pages, "current_page": page}
                    )
                
                logger.info(f"✅ list_tables: page {page}/{total_pages}, showing {len(tables)} of {total_items} total tables")
                
                return {
                    "ok": True,
                    "data": {
                        "tables": tables,
                        "pagination": {
                            "total_items": total_items,
                            "total_pages": total_pages,
                            "page": page,
                            "page_size": page_size
                        }
                    }
                }
            else:
                return {"ok": False, "error": "Empty result from MCP server"}
                
        except Exception as e:
            error_msg = f"Failed to parse list_tables response: {e}"
            logger.error(f"❌ {error_msg}")
            if debug_logger:
                debug_logger.tool_error("list_tables", error_msg)
            return {"ok": False, "error": error_msg}
    
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
        result = await self.call_tool("search_tables", {
            "keyword": keyword,
            "page": page,
            "page_size": page_size
        })
        
        # Log scout mode operation
        if debug_logger and result:
            try:
                # Parse result to extract matched tables and rankings
                tables_found = []
                if result and len(result) > 0:
                    result_text = result[0].get("text", "")
                    import json as json_lib
                    try:
                        result_data = json_lib.loads(result_text) if isinstance(result_text, str) else result_text
                        if isinstance(result_data, dict) and "results" in result_data:
                            tables_found = [r.get("table_name", "") for r in result_data.get("results", [])[:5]]
                        elif isinstance(result_data, dict) and "tables" in result_data:
                            tables_found = [t.get("name", "") for t in result_data.get("tables", [])[:5]]
                        elif isinstance(result_data, list):
                            tables_found = [t.get("table_name", t.get("name", "")) if isinstance(t, dict) else str(t) for t in result_data[:5]]
                    except:
                        tables_found = [str(result)]
                
                debug_logger.scout_mode_operation(
                    "search_tables",
                    f"keyword='{keyword}'",
                    tables_found if tables_found else ["(no matches)"],
                    {"matches": len(tables_found)}
                )
            except Exception as e:
                logger.debug(f"Error logging scout mode operation: {e}")
        
        return result
    
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
        result = await self.call_tool("describe_table", {
            "table_name": table_name,
            "include_sample": include_sample
        })
        
        # Log schema discovery
        if debug_logger and result:
            try:
                if result and len(result) > 0:
                    result_text = result[0].get("text", "")
                    import json as json_lib
                    try:
                        result_data = json_lib.loads(result_text) if isinstance(result_text, str) else result_text
                        if isinstance(result_data, dict):
                            columns = result_data.get("columns", [])
                            row_count = result_data.get("row_count")
                            relationships = result_data.get("relationships", [])
                            debug_logger.schema_discovered(
                                table_name,
                                columns[:5] if len(columns) > 5 else columns,
                                row_count=row_count,
                                relationships=relationships
                            )
                    except:
                        logger.debug(f"Could not parse describe_table result for logging")
            except Exception as e:
                logger.debug(f"Error logging schema discovery: {e}")
        
        return result
    
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
    Properly extracts JSON from MCP responses and reports actual table counts.
    
    Returns:
        Dictionary containing the schema index with:
        - status: "SUCCESS" or "FAILED"
        - total_tables: actual count from page_info.total_items
        - tables: indexed table data
        - error: (if FAILED) error message
    """
    tool = MCPDatabaseTool()
    try:
        logger.info("📋 Fetching schema from MCP server...")
        schema_content = await tool.get_schema()
        
        # Debug: Show what we got from get_schema()
        logger.debug(f"   Schema content type: {type(schema_content)}")
        logger.debug(f"   Schema content length: {len(schema_content) if isinstance(schema_content, list) else 'N/A'}")
        
        if not schema_content or len(schema_content) == 0:
            error_msg = "MCP server returned empty schema content"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "FAILED",
                "error": error_msg,
                "tables": {},
                "total_tables": 0,
                "debug_info": "get_schema() returned empty list"
            }
        
        # Extract text from first content item
        first_item = schema_content[0]
        logger.debug(f"   First content item keys: {list(first_item.keys()) if isinstance(first_item, dict) else 'N/A'}")
        
        schema_text = first_item.get("text", "") if isinstance(first_item, dict) else ""
        
        # Debug: Show the raw schema text
        text_length = len(schema_text) if schema_text else 0
        logger.debug(f"   Schema text length: {text_length} bytes")
        if text_length > 0:
            logger.debug(f"   Schema text preview (first 300 chars):\n{schema_text[:300]}")
        else:
            logger.error(f"❌ Schema text is empty. First item: {first_item}")
            return {
                "status": "FAILED",
                "error": "Schema text is empty",
                "tables": {},
                "total_tables": 0,
                "debug_info": f"First item: {str(first_item)[:200]}"
            }
        
        # Parse JSON using the extraction helper
        try:
            logger.debug("   Attempting to extract JSON from schema text...")
            payload = _extract_json_from_text(schema_text)
            logger.debug(f"   ✓ JSON extraction successful")
            
            # Extract tables and page info
            tables_list = payload.get("data", {}).get("tables", [])
            page_info = payload.get("data", {}).get("page_info", {})
            total_items = page_info.get("total_items", len(tables_list))
            
            logger.debug(f"   Found {len(tables_list)} tables on current page")
            logger.debug(f"   Page info: {page_info}")
            
            index = {
                "status": "SUCCESS",
                "tables": {},
                "total_tables": total_items,  # Use actual total, not content_items count!
                "indexed_at": None,
                "page_info": {
                    "total_pages": page_info.get("total_pages", 1),
                    "current_page": page_info.get("page", 1)
                }
            }
            
            # Build table index from current page
            for table in tables_list:
                table_name = table.get("name", "") or table.get("full_name", "")
                if table_name:
                    index["tables"][table_name] = {
                        "columns": table.get("columns", []),
                        "column_count": len(table.get("columns", [])),
                        "row_count": table.get("row_count", 0)
                    }
            
            logger.info(f"✅ Database indexed: {len(tables_list)} tables on page 1 of {total_items} total")
            return index
                
        except ValueError as parse_err:
            # JSON parsing failed - likely format issue
            error_msg = f"Failed to parse schema JSON: {parse_err}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Schema text (full, up to 500 chars):\n{schema_text[:500]}")
            
            # Try to identify the problem more specifically
            if not schema_text.strip():
                logger.error(f"   → Problem: Schema text is empty or whitespace only")
            elif "{" not in schema_text:
                logger.error(f"   → Problem: No JSON object found (no opening brace)")
            elif "}" not in schema_text:
                logger.error(f"   → Problem: No JSON object found (no closing brace)")
            elif "Full response (JSON):" not in schema_text:
                logger.error(f"   → Problem: Expected 'Full response (JSON):' marker not found")
                logger.error(f"   → The response might be in a different format")
            
            return {
                "status": "FAILED",
                "error": error_msg,
                "tables": {},
                "total_tables": 0,
                "debug_info": f"JSON parse error: {str(parse_err)[:200]}"
            }
        
        except json.JSONDecodeError as json_err:
            # Fallback for JSON decode errors
            error_msg = f"JSON decode error: {json_err}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Problematic text: {schema_text[:500]}")
            return {
                "status": "FAILED",
                "error": error_msg,
                "tables": {},
                "total_tables": 0,
                "debug_info": f"JSON error at line {json_err.lineno}, col {json_err.colno}"
            }
        
    except ValueError as e:
        # This is likely a timeout or connection error from call_tool
        error_str = str(e)
        logger.error(f"❌ Error indexing database: {error_str}")
        if "timeout" in error_str.lower():
            logger.error(f"   🔧 MCP server timeout. Check:")
            logger.error(f"      1. Windows MCP server is running (start_mcp_server_windows.bat)")
            logger.error(f"      2. Network connectivity to Windows machine")
            logger.error(f"      3. MCP_SERVER_URL in .env is correct (currently: {MCP_URL})")
        return {
            "status": "FAILED",
            "error": error_str, 
            "tables": {}, 
            "total_tables": 0,
            "debug_info": "Connection or timeout error"
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error indexing database: {e}", exc_info=True)
        return {
            "status": "FAILED",
            "error": str(e), 
            "tables": {}, 
            "total_tables": 0,
            "debug_info": f"Unexpected error: {type(e).__name__}"
        }


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
        # list_tables() returns a dict, not a list
        response = await tool.list_tables(page, page_size, schema, pattern)
        # Already properly formatted by MCPDatabaseTool.list_tables()
        return response
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
            # content is List[Dict] from call_tool
            response_text = content[0].get("text", "{}")
            # Use the extraction function to handle "Full response (JSON):" marker
            return _extract_json_from_text(response_text)
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
            # content is List[Dict] from call_tool
            response_text = content[0].get("text", "{}")
            # Use the extraction function to handle "Full response (JSON):" marker
            return _extract_json_from_text(response_text)
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
                # content is List[Dict] from call_tool
                response_text = content[0].get("text", "{}")
                # Use the extraction function to handle "Full response (JSON):" marker
                results[table_name] = _extract_json_from_text(response_text)
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
            # content is List[Dict] from call_tool
            response_text = content[0].get("text", "{}")
            # Use the extraction function to handle "Full response (JSON):" marker
            return _extract_json_from_text(response_text)
        return {"ok": False, "error": "No response from MCP server"}
    except Exception as e:
        logger.error(f"Error listing relations: {e}")
        return {"ok": False, "error": str(e)}


async def query_bounded_mcp(
    sql: str, 
    max_rows: Optional[int] = None, 
    timeout_ms: Optional[int] = None
) -> tuple:
    """
    Execute a bounded SQL query (Phase 2/4 tool).
    
    Args:
        sql: SQL query to execute
        max_rows: Maximum number of rows (default: 1000)
        timeout_ms: Query timeout in milliseconds (default: 30000)
        
    Returns:
        Tuple of (formatted_results: str, row_count: int)
        - formatted_results: Formatted query results for display
        - row_count: Actual number of rows returned by the query
    """
    tool = MCPDatabaseTool()
    try:
        content = await tool.query_bounded(sql, max_rows, timeout_ms)
        if content and len(content) > 0:
            result_text = content[0].get("text", "No results")
            
            # Try to extract actual row_count from the MCP JSON response
            row_count = 1  # Default for COUNT queries and simple results
            
            try:
                # Parse JSON from result to get actual row count
                result_data = _extract_json_from_text(result_text)
                logger.debug(f"[EXTRACT_DEBUG] Parsed JSON keys: {list(result_data.keys()) if isinstance(result_data, dict) else 'NOT A DICT'}")
                logger.debug(f"[EXTRACT_DEBUG] Full parsed JSON: {result_data}")
                
                if isinstance(result_data, dict):
                    # Look for row_count in various possible locations
                    if "row_count" in result_data:
                        row_count = result_data.get("row_count", 1)
                        logger.debug(f"[EXTRACT_DEBUG] ✓ Found row_count at top level: {row_count}")
                    elif "data" in result_data and isinstance(result_data["data"], dict):
                        if "row_count" in result_data["data"]:
                            row_count = result_data["data"].get("row_count", 1)
                            logger.debug(f"[EXTRACT_DEBUG] ✓ Found row_count in data section: {row_count}")
                        # For array results, count the items
                        elif "rows" in result_data["data"] and isinstance(result_data["data"]["rows"], list):
                            row_count = len(result_data["data"]["rows"])
                            logger.debug(f"[EXTRACT_DEBUG] ✓ Counted rows in data.rows: {row_count}")
                    else:
                        # Fallback: check if we have 'rows' at top level
                        if "rows" in result_data and isinstance(result_data["rows"], list):
                            row_count = len(result_data["rows"])
                            logger.debug(f"[EXTRACT_DEBUG] ✓ Counted rows at top level: {row_count}")
                        else:
                            logger.debug(f"[EXTRACT_DEBUG] ✗ No row_count or rows found. Keys available: {list(result_data.keys())}")
                    
                    logger.info(f"[ROW_COUNT_EXTRACTED] sql={sql[:80]}, extracted_row_count={row_count}")
            except Exception as parse_err:
                logger.error(f"[EXTRACT_ERROR] Could not extract row_count from MCP response: {parse_err}")
                logger.error(f"[EXTRACT_ERROR] Result text (first 1000 chars): {result_text[:1000]}")
                logger.error(f"[EXTRACT_ERROR] Result text (total length): {len(result_text)}")
                # Fall back to 1 (safe default)
                row_count = 1
            
            return (result_text, row_count)
        return ("No results", 0)
    except Exception as e:
        logger.error(f"Error executing bounded query: {e}")
        return (f"Error executing query: {str(e)}", 0)


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