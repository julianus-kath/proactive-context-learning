"""
MCP tools implementation for database operations.
Phase 2: Added query_bounded tool with comprehensive safety controls.
Phase 4: Added discovery tools (list_tables, search_tables, describe_table, list_relations).
Phase 6: Added structured logging and observability.
"""

import logging
import json
from typing import Dict, Any, List
from mcp_server.models import MCPTool, MCPToolResult
from mcp_server.bounded_query import execute_bounded_query
from mcp_server.config import config
from mcp_server.discovery_tools import DiscoveryTools
from mcp_server.observability import log_tool_call

logger = logging.getLogger(__name__)


class MCPTools:
    """MCP tools for database operations."""
    
    @staticmethod
    def get_available_tools() -> List[MCPTool]:
        """Return list of available MCP tools."""
        return [
            MCPTool(
                name="get_schema",
                description="Get database schema information including tables, columns, and relationships",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            MCPTool(
                name="query",
                description="Execute a SELECT query against the database (legacy - use query_bounded for production)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL SELECT query to execute"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default: 100, max: 1000)",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 1000
                        }
                    },
                    "required": ["sql"]
                }
            ),
            MCPTool(
                name="query_bounded",
                description="Execute a bounded SELECT query with comprehensive safety controls (validation, row caps, timeout, redaction)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL SELECT query to execute"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default: 100, max: 1000)",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 1000
                        },
                        "enable_redaction": {
                            "type": "boolean",
                            "description": "Enable sensitive column redaction (default: true)",
                            "default": True
                        }
                    },
                    "required": ["sql"]
                }
            ),
            MCPTool(
                name="get_table_info",
                description="Get detailed information about a specific table (legacy - use describe_table for Phase 4)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table to inspect"
                        }
                    },
                    "required": ["table_name"]
                }
            ),
            # Phase 4: Discovery tools
            MCPTool(
                name="list_tables",
                description="List all database tables with pagination (shows everything, not ranked). Generally NOT RECOMMENDED - use search_tables instead for smarter, ranked results. Only use if you need to browse all tables or filter by schema/pattern.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "page": {
                            "type": "integer",
                            "description": "Page number (1-indexed, default: 1)",
                            "default": 1,
                            "minimum": 1
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of items per page (default: 25, max: 100)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "schema": {
                            "type": "string",
                            "description": "Filter by schema name (optional)"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Filter by table name pattern (optional, case-insensitive)"
                        }
                    },
                    "required": []
                }
            ),
            MCPTool(
                name="search_tables",
                description="Search tables with semantic ranking - intelligently finds relevant tables based on meaning, not just keywords (Phase 7.1 Scout Mode). Returns top matches ranked by relevance with descriptions. RECOMMENDED: Use this instead of list_tables to find tables - much faster and smarter!",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - can be semantic (e.g., 'customers', 'sales transactions', 'inventory'). Returns ranked results based on meaning."
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number (1-indexed, default: 1)",
                            "default": 1,
                            "minimum": 1
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of items per page (default: 25, max: 100) - starts with most relevant, so 5-10 usually sufficient",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["query"]
                }
            ),
            MCPTool(
                name="describe_table",
                description="Get detailed information about a specific table including columns, foreign keys, and primary keys (Phase 4 - catalog-backed, O(1) lookup)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Fully qualified table name (schema.table) or just table name"
                        },
                        "include_sample": {
                            "type": "boolean",
                            "description": "Include sample data (requires DB query, default: false)",
                            "default": False
                        }
                    },
                    "required": ["table_name"]
                }
            ),
            MCPTool(
                name="list_relations",
                description="Get relationships (neighbors) for a specific table with join columns (Phase 4 - catalog-backed, O(1) lookup)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Fully qualified table name (schema.table) or just table name"
                        }
                    },
                    "required": ["table_name"]
                }
            ),
            # Phase 7: Answer-first tools
            MCPTool(
                name="answer_first",
                description="Execute a natural language query using answer-first pipeline (autonomous table discovery, ranking, and execution)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query (e.g., 'Show top 10 products by revenue')"
                        },
                        "include_debug": {
                            "type": "boolean",
                            "description": "Include debug information in response (default: false)",
                            "default": False
                        }
                    },
                    "required": ["query"]
                }
            ),
            MCPTool(
                name="parse_intent",
                description="Parse user query to extract intent, entities, and operations (Phase 7 - answer-first support)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "User query to analyze"
                        }
                    },
                    "required": ["query"]
                }
            ),
            MCPTool(
                name="rank_tables",
                description="Rank database tables by relevance to query intent (Phase 7 - answer-first support)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "Query intent (SEARCH, AGGREGATE, TREND, REPORT, JOIN, FILTER)"
                        },
                        "entities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Entities from query (e.g., ['customer', 'order'])"
                        },
                        "operations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Operations needed (e.g., ['count', 'sum'])"
                        }
                    },
                    "required": ["intent", "entities"]
                }
            ),
            MCPTool(
                name="get_execution_metrics",
                description="Get performance metrics for answer-first query execution (Phase 7 - observability)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
        ]
    
    @staticmethod
    async def execute_tool(tool_name: str, arguments: Dict[str, Any], db_manager=None) -> MCPToolResult:
        """
        Execute a specific tool with structured logging.
        
        Phase 6: All tool calls are logged with:
        - Tool name
        - Duration (ms)
        - Cache hit/miss
        - Row count (if applicable)
        - Error details (if failed)
        """
        # Phase 6: Structured logging
        with log_tool_call(tool_name, arguments) as metrics:
            try:
                result = None
                
                if tool_name == "get_schema":
                    result = await MCPTools._get_schema(arguments, db_manager)
                elif tool_name == "query":
                    result = await MCPTools._query(arguments, db_manager)
                elif tool_name == "query_bounded":
                    result = await MCPTools._query_bounded(arguments, db_manager)
                elif tool_name == "get_table_info":
                    result = await MCPTools._get_table_info(arguments, db_manager)
                elif tool_name == "get_sample_data":
                    result = await MCPTools._get_sample_data(arguments, db_manager)
                elif tool_name == "list_tables":
                    result = await MCPTools._list_tables(arguments, db_manager)
                elif tool_name == "search_tables":
                    result = await MCPTools._search_tables(arguments, db_manager)
                elif tool_name == "describe_table":
                    result = await MCPTools._describe_table(arguments, db_manager)
                elif tool_name == "list_relations":
                    result = await MCPTools._list_relations(arguments, db_manager)
                elif tool_name == "answer_first":
                    result = await MCPTools._answer_first(arguments, db_manager)
                elif tool_name == "parse_intent":
                    result = await MCPTools._parse_intent(arguments, db_manager)
                elif tool_name == "rank_tables":
                    result = await MCPTools._rank_tables(arguments, db_manager)
                elif tool_name == "get_execution_metrics":
                    result = await MCPTools._get_execution_metrics(arguments, db_manager)
                else:
                    metrics.success = False
                    metrics.error_code = "UNKNOWN_TOOL"
                    metrics.error_category = "validation"
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": f"Unknown tool: {tool_name}"
                        }],
                        isError=True
                    )
                
                # Extract metrics from result if available
                if result and hasattr(result, 'content') and result.content:
                    content = result.content[0]
                    if isinstance(content, dict) and content.get('type') == 'text':
                        text = content.get('text', '')
                        # Try to extract row count from result text
                        if 'rows' in text.lower():
                            import re
                            match = re.search(r'(\d+)\s+rows?', text, re.IGNORECASE)
                            if match:
                                metrics.row_count = int(match.group(1))
                
                return result
                
            except Exception as e:
                logger.error(f"Tool execution failed for {tool_name}: {e}")
                metrics.success = False
                metrics.error_message = str(e)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"Tool execution failed: {str(e)}"
                    }],
                    isError=True
                )
    
    @staticmethod
    async def _get_schema(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Get database schema information as JSON."""
        schema = await db_manager.fetch_schema()
        
        # Return schema as JSON (not plain text)
        # This ensures MCP client can parse it with json.loads()
        schema_json = {
            "ok": True,
            "tables": schema,
            "table_count": len(schema),
            "status": "Schema retrieved successfully"
        }
        
        return MCPToolResult(
            content=[{
                "type": "text",
                "text": json.dumps(schema_json)
            }]
        )
    
    @staticmethod
    async def _query(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Execute a SQL query."""
        sql = arguments.get("sql", "").strip()
        limit = min(arguments.get("limit", 100), 1000)  # Cap at 1000 rows
        
        if not sql:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "SQL query is required"
                }],
                isError=True
            )
        
        try:
            results = await db_manager.fetch(sql, limit=limit)
            
            if not results:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": "Query executed successfully but returned no results."
                    }]
                )
            
            # Format results
            result_text = f"Query Results ({len(results)} rows):\n\n"
            
            # Add column headers
            if results:
                columns = list(results[0].keys())
                result_text += " | ".join(columns) + "\n"
                result_text += "-" * (len(" | ".join(columns))) + "\n"
                
                # Add data rows
                for row in results:
                    row_values = [str(row.get(col, "")) for col in columns]
                    result_text += " | ".join(row_values) + "\n"
            
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": result_text
                }]
            )
            
        except Exception as e:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Query execution failed: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _query_bounded(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """
        Execute a bounded SQL query with comprehensive safety controls.
        
        This is the production-ready query tool that provides:
        - Query validation (SELECT-only, single statement)
        - Row cap injection (LIMIT/TOP)
        - Timeout enforcement
        - Column redaction
        - Structured error responses
        """
        sql = arguments.get("sql", "").strip()
        limit = arguments.get("limit", 100)
        enable_redaction = arguments.get("enable_redaction", True)
        
        if not sql:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps({
                        "ok": False,
                        "error_code": "EMPTY_QUERY",
                        "error_message": "SQL query is required"
                    })
                }],
                isError=True
            )
        
        try:
            # Execute bounded query
            response = await execute_bounded_query(
                query=sql,
                db_adapter=db_manager,
                dialect=config.db_dialect,
                max_rows=config.max_query_results,
                query_timeout=config.query_timeout,
                requested_limit=limit,
                enable_redaction=enable_redaction
            )
            
            # Convert response to JSON
            response_dict = response.to_dict()
            
            # Format as human-readable text + JSON
            if response.ok:
                result_text = f"✅ Query executed successfully\n\n"
                result_text += f"Rows returned: {response.row_count}\n"
                result_text += f"Execution time: {response.execution_time_ms}ms\n"
                
                if response.truncated:
                    result_text += f"⚠️ Results truncated (limit: {response.metadata.get('applied_limit')})\n"
                
                if response.redacted_columns:
                    result_text += f"🔒 Redacted columns: {', '.join(response.redacted_columns)}\n"
                
                result_text += f"\nColumns: {', '.join(response.columns)}\n\n"
                
                # Add sample rows (first 5)
                if response.rows:
                    result_text += "Sample rows:\n"
                    for i, row in enumerate(response.rows[:5]):
                        result_text += f"  Row {i+1}: {json.dumps(row)}\n"
                    
                    if len(response.rows) > 5:
                        result_text += f"  ... and {len(response.rows) - 5} more rows\n"
                
                result_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                # Error response
                error_text = f"❌ Query failed\n\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"Error message: {response.error_message}\n"
                error_text += f"Execution time: {response.execution_time_ms}ms\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            logger.error(f"Bounded query execution failed: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps({
                        "ok": False,
                        "error_code": "INTERNAL_ERROR",
                        "error_message": f"Internal error: {str(e)}"
                    })
                }],
                isError=True
            )
    
    @staticmethod
    async def _get_table_info(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Get information about a specific table."""
        table_name = arguments.get("table_name", "").strip()
        
        if not table_name:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "Table name is required"
                }],
                isError=True
            )
        
        try:
            # Get schema for the specific table
            schema = await db_manager.fetch_schema()
            table_info = next((t for t in schema if t['name'] == table_name), None)
            
            if not table_info:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"Table '{table_name}' not found"
                    }],
                    isError=True
                )
            
            # Get row count
            row_count = await db_manager.get_table_count(table_name)
            
            # Format table information
            info_text = f"Table: {table_info['name']}\n"
            info_text += f"Type: {table_info['type']}\n"
            info_text += f"Row Count: {row_count:,}\n\n"
            info_text += "Columns:\n"
            
            for column in table_info['columns']:
                col_info = f"  - {column['name']} ({column['type']})"
                if not column['nullable']:
                    col_info += " NOT NULL"
                if column.get('default'):
                    col_info += f" DEFAULT {column['default']}"
                if column.get('constraint'):
                    col_info += f" [{column['constraint']}]"
                if column.get('references'):
                    ref = column['references']
                    col_info += f" -> {ref['table']}.{ref['column']}"
                info_text += col_info + "\n"
            
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": info_text
                }]
            )
            
        except Exception as e:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Failed to get table info: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _get_sample_data(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Get sample data from a table."""
        table_name = arguments.get("table_name", "").strip()
        limit = min(arguments.get("limit", 5), 50)  # Cap at 50 rows
        
        if not table_name:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "Table name is required"
                }],
                isError=True
            )
        
        try:
            sample_data = await db_manager.get_sample_data(table_name, limit)
            
            if not sample_data:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"No data found in table '{table_name}'"
                    }]
                )
            
            # Format sample data
            result_text = f"Sample data from '{table_name}' ({len(sample_data)} rows):\n\n"
            
            # Add column headers
            columns = list(sample_data[0].keys())
            result_text += " | ".join(columns) + "\n"
            result_text += "-" * (len(" | ".join(columns))) + "\n"
            
            # Add data rows
            for row in sample_data:
                row_values = [str(row.get(col, ""))[:50] for col in columns]  # Truncate long values
                result_text += " | ".join(row_values) + "\n"
            
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": result_text
                }]
            )
            
        except Exception as e:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Failed to get sample data: {str(e)}"
                }],
                isError=True
            )
    
    # Phase 4: Discovery tool implementations
    
    @staticmethod
    async def _list_tables(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """List tables with pagination (Phase 4)."""
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 25)
        schema = arguments.get("schema")
        pattern = arguments.get("pattern")
        
        try:
            response = await DiscoveryTools.list_tables(
                db_adapter=db_manager,
                page=page,
                page_size=page_size,
                schema=schema,
                pattern=pattern
            )
            
            response_dict = response.to_dict()
            
            if response.ok:
                # Format human-readable text
                data = response_dict["data"]
                page_info = response_dict.get("page_info", {})
                
                result_text = f"📋 Database Tables (Page {page_info.get('page', 1)} of {page_info.get('total_pages', 1)})\n\n"
                result_text += f"Total tables: {page_info.get('total_items', 0)}\n"
                
                if schema or pattern:
                    result_text += f"Filters: "
                    if schema:
                        result_text += f"schema={schema} "
                    if pattern:
                        result_text += f"pattern={pattern}"
                    result_text += "\n"
                
                result_text += f"\n"
                
                for table in data.get("tables", []):
                    result_text += f"• {table['full_name']} ({table['type']})\n"
                    result_text += f"  Columns: {table['column_count']}, Rows: ~{table['estimated_rows']:,}\n"
                    if table['has_foreign_keys']:
                        result_text += f"  Has foreign keys\n"
                    if table['has_primary_keys']:
                        result_text += f"  Has primary keys\n"
                    result_text += "\n"
                
                if page_info.get("has_next"):
                    result_text += f"➡️ More results available (use page={page_info.get('page', 1) + 1})\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                error_text = f"❌ list_tables failed\n\n"
                error_text += f"Error: {response.error}\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            logger.error(f"list_tables failed: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Internal error: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _search_tables(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Search tables by keyword (Phase 4)."""
        query = arguments.get("query", "").strip()
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 25)
        
        try:
            response = await DiscoveryTools.search_tables(
                db_adapter=db_manager,
                query=query,
                page=page,
                page_size=page_size
            )
            
            response_dict = response.to_dict()
            
            if response.ok:
                # Format human-readable text
                data = response_dict["data"]
                page_info = response_dict.get("page_info", {})
                
                result_text = f"🔍 Search Results for '{query}' (Page {page_info.get('page', 1)} of {page_info.get('total_pages', 1)})\n\n"
                result_text += f"Total matches: {page_info.get('total_items', 0)}\n\n"
                
                for result in data.get("results", []):
                    result_text += f"• {result['full_name']} ({result['type']}) - Score: {result['relevance_score']}\n"
                    result_text += f"  Columns: {result['column_count']}, Rows: ~{result['estimated_rows']:,}\n"
                    if result.get('matched_columns'):
                        result_text += f"  Matched columns: {', '.join(result['matched_columns'])}\n"
                    result_text += "\n"
                
                if page_info.get("has_next"):
                    result_text += f"➡️ More results available (use page={page_info.get('page', 1) + 1})\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                error_text = f"❌ search_tables failed\n\n"
                error_text += f"Error: {response.error}\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            logger.error(f"search_tables failed: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Internal error: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _describe_table(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Describe a specific table (Phase 4)."""
        table_name = arguments.get("table_name", "").strip()
        include_sample = arguments.get("include_sample", False)
        
        try:
            response = await DiscoveryTools.describe_table(
                db_adapter=db_manager,
                table_name=table_name,
                include_sample=include_sample
            )
            
            response_dict = response.to_dict()
            
            if response.ok:
                # Format human-readable text
                data = response_dict["data"]
                
                result_text = f"📊 Table: {data['full_name']}\n\n"
                result_text += f"Type: {data['type']}\n"
                result_text += f"Estimated rows: ~{data['estimated_rows']:,}\n"
                result_text += f"Columns: {len(data['columns'])}\n\n"
                
                # Primary keys
                if data.get('primary_keys'):
                    result_text += f"🔑 Primary Keys: {', '.join(data['primary_keys'])}\n\n"
                
                # Foreign keys
                if data.get('foreign_keys'):
                    result_text += f"🔗 Foreign Keys ({len(data['foreign_keys'])}):\n"
                    for fk in data['foreign_keys']:
                        result_text += f"  • {fk['column']} → {fk['referenced_full_name']}.{fk['referenced_column']}\n"
                    result_text += "\n"
                
                # Top columns
                result_text += f"📋 Top Columns:\n"
                for col in data.get('top_columns', [])[:10]:
                    col_info = f"  • {col['name']} ({col['type']})"
                    if not col['nullable']:
                        col_info += " NOT NULL"
                    if col['is_primary_key']:
                        col_info += " [PK]"
                    if col['is_foreign_key']:
                        col_info += " [FK]"
                    result_text += col_info + "\n"
                
                # Sample data
                if include_sample and data.get('sample_data'):
                    result_text += f"\n📄 Sample Data ({len(data['sample_data'])} rows):\n"
                    for i, row in enumerate(data['sample_data'][:3]):
                        result_text += f"  Row {i+1}: {json.dumps(row)}\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                error_text = f"❌ describe_table failed\n\n"
                error_text += f"Error: {response.error}\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            logger.error(f"describe_table failed: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Internal error: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _list_relations(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """List relationships for a table (Phase 4)."""
        table_name = arguments.get("table_name", "").strip()
        
        try:
            response = await DiscoveryTools.list_relations(
                db_adapter=db_manager,
                table_name=table_name
            )
            
            response_dict = response.to_dict()
            
            if response.ok:
                # Format human-readable text
                data = response_dict["data"]
                
                result_text = f"🔗 Relationships for {data['table']}\n\n"
                result_text += f"Total neighbors: {data['neighbor_count']}\n\n"
                
                if data['neighbor_count'] > 0:
                    result_text += "Related tables:\n"
                    for neighbor in data.get('neighbors', []):
                        result_text += f"  • {neighbor}\n"
                else:
                    result_text += "No related tables found.\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                error_text = f"❌ list_relations failed\n\n"
                error_text += f"Error: {response.error}\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            logger.error(f"list_relations failed: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Internal error: {str(e)}"
                }],
                isError=True
            )
    
    # Phase 7: Answer-first tools
    
    @staticmethod
    async def _answer_first(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Execute query using answer-first pipeline."""
        try:
            from mcp_server.answer_first_orchestrator import AnswerFirstOrchestrator
            from mcp_server.discovery_tools import DiscoveryTools
            
            query = arguments.get("query", "").strip()
            include_debug = arguments.get("include_debug", False)
            
            if not query:
                return MCPToolResult(
                    content=[{"type": "text", "text": "Query is required"}],
                    isError=True
                )
            
            # Create orchestrator
            discovery_tools = DiscoveryTools(db_manager.catalog)
            orchestrator = AnswerFirstOrchestrator(
                discovery_tools=discovery_tools,
                db_adapter=db_manager,
                catalog=db_manager.catalog,
                dialect=getattr(db_manager, 'dialect', 'mssql')
            )
            
            # Execute answer-first pipeline
            result = await orchestrator.execute_answer_first(query)
            
            response_text = f"Answer-first Query Execution\n"
            response_text += f"=" * 50 + "\n\n"
            response_text += f"Query: {query}\n"
            response_text += f"Intent: {result.intent}\n"
            response_text += f"Success: {result.success}\n\n"
            response_text += f"Answer: {result.answer}\n"
            if result.tables_used:
                response_text += f"Tables: {', '.join(result.tables_used)}\n"
            response_text += f"Execution time: {result.execution_time_ms:.2f}ms\n"
            
            if include_debug and result.debug_info:
                response_text += f"\nDebug Info:\n{json.dumps(result.debug_info, indent=2)}\n"
            
            return MCPToolResult(
                content=[{"type": "text", "text": response_text}],
                isError=not result.success
            )
        
        except Exception as e:
            logger.error(f"answer_first failed: {e}", exc_info=True)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )
    
    @staticmethod
    async def _parse_intent(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Parse user query to extract intent."""
        try:
            from intent_parser import parse_intent
            
            query = arguments.get("query", "").strip()
            if not query:
                return MCPToolResult(
                    content=[{"type": "text", "text": "Query is required"}],
                    isError=True
                )
            
            parsed = parse_intent(query)
            
            response_text = f"Intent Parsing Result\n"
            response_text += f"=" * 50 + "\n\n"
            response_text += f"Query: {query}\n"
            response_text += f"Intent: {parsed.intent.value}\n"
            response_text += f"Confidence: {parsed.confidence:.2f}\n"
            response_text += f"Entities: {', '.join(parsed.entities) if parsed.entities else 'None'}\n"
            response_text += f"Operations: {', '.join(parsed.operations) if parsed.operations else 'None'}\n"
            
            return MCPToolResult(
                content=[{"type": "text", "text": response_text}]
            )
        
        except Exception as e:
            logger.error(f"parse_intent failed: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )
    
    @staticmethod
    async def _rank_tables(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Rank tables by relevance."""
        try:
            from mcp_server.table_ranker import rank_tables
            
            intent = arguments.get("intent", "SEARCH")
            entities = arguments.get("entities", [])
            operations = arguments.get("operations", [])
            
            if not db_manager.catalog:
                return MCPToolResult(
                    content=[{"type": "text", "text": "Catalog not initialized"}],
                    isError=True
                )
            
            # Get all tables from catalog
            all_tables = db_manager.catalog.get_table_list()
            
            # Rank them
            ranked = rank_tables(all_tables, entities, operations, db_manager.catalog)
            
            response_text = f"Table Ranking Results\n"
            response_text += f"=" * 50 + "\n\n"
            response_text += f"Intent: {intent}\n"
            response_text += f"Entities: {', '.join(entities)}\n"
            response_text += f"Top 10 Tables:\n\n"
            
            for i, table in enumerate(ranked[:10], 1):
                response_text += f"{i}. {table.full_name} (score: {table.score:.2f})\n"
                for reason in table.reasons[:2]:
                    response_text += f"   • {reason}\n"
            
            return MCPToolResult(
                content=[{"type": "text", "text": response_text}]
            )
        
        except Exception as e:
            logger.error(f"rank_tables failed: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )
    
    @staticmethod
    async def _get_execution_metrics(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Get answer-first execution metrics."""
        try:
            from mcp_server.observability import answer_first_obs
            
            summary = answer_first_obs.get_execution_summary()
            
            response_text = f"Answer-first Execution Metrics\n"
            response_text += f"=" * 50 + "\n\n"
            response_text += json.dumps(summary, indent=2)
            
            return MCPToolResult(
                content=[{"type": "text", "text": response_text}]
            )
        
        except Exception as e:
            logger.error(f"get_execution_metrics failed: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )