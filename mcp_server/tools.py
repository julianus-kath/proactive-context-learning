"""
MCP tools implementation for database operations.
Phase 2: Added query_bounded tool with comprehensive safety controls.
Phase 4: Added discovery tools (list_tables, search_tables, describe_table, list_relations).
Phase 6: Added structured logging and observability.
"""

import logging
import json
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, date
from mcp_server.models import MCPTool, MCPToolResult
from mcp_server.bounded_query import execute_bounded_query
from mcp_server.config import config
from mcp_server.discovery_tools import DiscoveryTools
from mcp_server.observability import log_tool_call

# Scout Mode imports (lazy loaded)
_scout_runner = None

logger = logging.getLogger(__name__)


def _get_scout_runner(db_manager):
    """
    Get or initialize Scout Runner for catalog access.

    Args:
        db_manager: Database manager instance

    Returns:
        ScoutRunner instance or None if not available
    """
    global _scout_runner
    if _scout_runner is None:
        try:
            from mcp_server.scout_runner import ScoutRunner
            _scout_runner = ScoutRunner(db_adapter=db_manager)
            logger.info("✅ Scout Runner initialized for catalog access")
        except Exception as e:
            logger.warning(f"Failed to initialize Scout Runner: {e}")
            return None
    return _scout_runner


async def _search_tables_from_catalog(catalog: Dict[str, Any], query: str, page: int, page_size: int, intent_data: Dict[str, Any] = None) -> MCPToolResult:
    """
    Search tables using Scout catalog data with semantic ranking.

    Args:
        catalog: Scout catalog data
        query: Search query (keywords from intent parser)
        page: Page number
        page_size: Results per page
        intent_data: Intent parsing results for semantic ranking

    Returns:
        MCPToolResult with semantically ranked search results
    """
    import time
    from mcp_server.table_ranker import TableRanker

    start_time = time.time()

    logger.info(f"🔍 SEMANTIC SEARCH CALLED: query='{query}', intent_data={bool(intent_data)}")

    try:
        # Get tables from catalog
        tables = catalog.get("tables", {})
        views = catalog.get("views", {})

        # Combine tables and views for comprehensive search
        all_entities = []
        for name, data in tables.items():
            all_entities.append({
                "name": name,
                "schema": data.get("schema", "dbo"),
                "type": "table",
                **data
            })

        for name, data in views.items():
            all_entities.append({
                "name": name,
                "schema": data.get("schema", "dbo"),
                "type": "view",
                **data
            })

        # Extract entities and operations from intent data
        entities = []
        operations = []

        if intent_data:
            # Primary entities from intent parser
            entities.extend(intent_data.get("primary_entities", []))
            entities.extend(intent_data.get("secondary_entities", []))

            # Keywords for discovery
            entities.extend(intent_data.get("keywords_for_discovery", []))

            # Operations/metrics
            operations.extend(intent_data.get("metrics", []))
            operations.extend(intent_data.get("filters", []))

            # If no entities found, fall back to query keywords
            if not entities:
                entities = query.split()

        # If still no entities, use the raw query
        if not entities:
            entities = [query]

        # 🔧 USE SCOUT CATALOG SEMANTIC INFORMATION
        # The TableRanker will use fuzzy matching against actual German table/column names
        # No hard-coded translations - rely on semantic matching in TableRanker

        logger.info(f"🔍 Semantic search - Entities: {entities}, Operations: {operations}")

        # Use TableRanker for semantic ranking
        ranker = TableRanker()
        ranked_tables = ranker.rank_tables(all_entities, entities, operations)

        # Convert to result format
        matching_tables = []
        for ranked in ranked_tables[:page_size]:  # Limit results
            table_data = tables.get(ranked.full_name, views.get(ranked.full_name, {}))

            result = {
                "schema": ranked.schema,
                "name": ranked.name,
                "full_name": ranked.full_name,
                "type": "TABLE" if ranked.full_name in tables else "VIEW",
                "estimated_rows": ranked.estimated_rows,
                "column_count": ranked.column_count,
                "fk_count": ranked.fk_count,
                "relevance_score": ranked.score,
                "ranking_reasons": ranked.reasons,
                "matched_columns": [],  # Will be filled below
                "description": table_data.get("description", "")
            }

            # Find matched columns based on entity matches
            columns = table_data.get("columns", [])
            matched_cols = []
            for col in columns:
                col_name = col.get("name", "").lower()
                for entity in entities:
                    if entity.lower() in col_name:
                        matched_cols.append(col["name"])
                        break
            result["matched_columns"] = matched_cols[:5]  # Limit to 5

            matching_tables.append(result)

        # Sort by relevance score
        matching_tables.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Paginate results
        total_items = len(matching_tables)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_results = matching_tables[start_idx:end_idx]

        # Calculate pagination info
        total_pages = (total_items + page_size - 1) // page_size

        # Format response similar to DiscoveryTools
        response_dict = {
            "ok": True,
            "data": {
                "results": page_results
            },
            "page_info": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "execution_time_ms": (time.time() - start_time) * 1000,
            "cached": True,
            "source": "scout_catalog"
        }

        # Format human-readable text
        page_info = response_dict["page_info"]
        data = response_dict["data"]

        result_text = f"🔍 Search Results for '{query}' (Page {page_info['page']} of {page_info['total_pages']})\n\n"
        result_text += f"Total matches: {page_info['total_items']}\n\n"

        for result in data.get("results", []):
            result_text += f"• {result['full_name']} ({result['type']}) - Score: {result['relevance_score']:.2f}\n"
            result_text += f"  Columns: {result['column_count']}, Rows: ~{result['estimated_rows']:,}\n"
            if result.get('matched_columns'):
                result_text += f"  Matched columns: {', '.join(result['matched_columns'])}\n"
            result_text += "\n"

        if page_info.get("has_next"):
            result_text += f"➡️ More results available (use page={page_info['page'] + 1})\n"

        result_text += f"\n⏱️ Execution time: {response_dict['execution_time_ms']:.2f}ms (cached from Scout catalog)"

        result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"

        return MCPToolResult(
            content=[{
                "type": "text",
                "text": result_text
            }],
            isError=False
        )

    except Exception as e:
        logger.error(f"Catalog search failed: {e}")
        return MCPToolResult(
            content=[{
                "type": "text",
                "text": f"Internal error during catalog search: {str(e)}"
            }],
            isError=True
        )


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal and other non-standard types."""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        elif isinstance(o, (datetime, date)):
            return o.isoformat() if hasattr(o, 'isoformat') else str(o)
        return super().default(o)


class MCPTools:
    """MCP tools for database operations."""
    
    @staticmethod
    def _make_json_safe(obj: Any) -> Any:
        """
        Recursively convert non-JSON-serializable types to JSON-safe equivalents.
        
        Handles Decimal, datetime, date, and nested structures.
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
        elif isinstance(obj, dict):
            return {k: MCPTools._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [MCPTools._make_json_safe(item) for item in obj]
        else:
            return obj
    
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
                        },
                        "include_empty": {
                            "type": "boolean",
                            "description": "Include tables with zero rows (default: false)",
                            "default": False
                        },
                        "min_rows": {
                            "type": "integer",
                            "description": "Minimum estimated rows required to include a table (default: 1)",
                            "default": 1,
                            "minimum": 0
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
                description="Get relationships (neighbors) for a specific table with join columns",
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
                description="Rank database tables by relevance to query intent",
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
                name="list_views",
                description="List views with pagination and optional filtering; prefer search_views for ranked matching",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "page": {"type":"integer","description":"Page number (1-indexed, default: 1)","default":1,"minimum":1},
                        "page_size": {"type":"integer","description":"Items per page (default: 25, max: 100)","default":25,"minimum":1,"maximum":100},
                        "schema": {"type":"string","description":"Filter by schema (optional)"},
                        "pattern": {"type":"string","description":"Case-insensitive name filter (optional)"},
                        "include_empty": {"type":"boolean","description":"Include views with zero rows (default: false)","default": False}
                    },
                    "required": []
                }
            ),
            MCPTool(
                name="search_views",
                description="Search and rank business views by relevance to the query (views-first discovery)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type":"string","description":"Natural language query"},
                        "page": {"type":"integer","description":"Page number (1-indexed, default: 1)","default":1,"minimum":1},
                        "page_size": {"type":"integer","description":"Items per page (default: 10, max: 50)","default":10,"minimum":1,"maximum":50},
                        "include_empty": {"type":"boolean","description":"Include views with zero rows (default: false)","default": False}
                    },
                    "required": ["query"]
                }
            ),
            MCPTool(
                name="describe_view",
                description="Get detailed information about a specific view (columns, keys, estimated rows)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {"type":"string","description":"Fully qualified view name (schema.view) or view name"},
                        "include_sample": {"type":"boolean","description":"Include sample data (requires DB query, default: false)","default": False}
                    },
                    "required": ["view_name"]
                }
            ),
            MCPTool(
                name="list_view_dependencies",
                description="List dependencies for a view (upstream tables/views) when available",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {"type":"string","description":"Fully qualified view name (schema.view) or view name"}
                    },
                    "required": ["view_name"]
                }
            ),
            MCPTool(
                name="list_empty_tables",
                description="List empty tables from Scout Catalog (views-first policy: use list_views for views)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema": {"type": "string", "description": "Filter by schema (optional)"},
                        "pattern": {"type": "string", "description": "Case-insensitive name filter (optional)"},
                        "page": {"type":"integer","default":1,"minimum":1},
                        "page_size": {"type":"integer","default":25,"minimum":1,"maximum":100}
                    },
                    "required": []
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
            MCPTool(
                name="get_column_index",
                description="Get structured list of available columns for tables (Phase 7.1 - prevents column hallucination by providing exact column names)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of table names to get columns for (e.g., ['dbo.KHKAdressen', 'dbo.Orders']). Can be just table name or schema.table format."
                        }
                    },
                    "required": ["table_names"]
                }
            ),
            # Phase 9 Tier 1 Enhancements
            MCPTool(
                name="get_view_dependencies",
                description="Get view dependencies and materialization status (Tier 1 - enables smarter view-first decisions). Returns which tables/views a view depends on and whether it's materialized for performance optimization.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "view_name": {
                            "type": "string",
                            "description": "Fully qualified view name (schema.view) or just view name"
                        }
                    },
                    "required": ["view_name"]
                }
            ),
            MCPTool(
                name="get_fk_cardinality",
                description="Get foreign key cardinality patterns for a table (Tier 1 - improves join planning). Identifies 1:1, 1:N, and N:N relationships with ratio estimates.",
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
            MCPTool(
                name="get_domain_clusters",
                description="Get business domain clusters (Tier 1 - improves ranking and ambiguity resolution). Identifies which domain (Sales, Inventory, HR, etc.) each table belongs to.",
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
                elif tool_name == "list_views":
                    result = await MCPTools._list_views(arguments, db_manager)
                elif tool_name == "search_views":
                    result = await MCPTools._search_views(arguments, db_manager)
                elif tool_name == "describe_view":
                    result = await MCPTools._describe_view(arguments, db_manager)
                elif tool_name == "list_view_dependencies":
                    result = await MCPTools._list_view_dependencies(arguments, db_manager)
                elif tool_name == "answer_first":
                    result = await MCPTools._answer_first(arguments, db_manager)
                elif tool_name == "parse_intent":
                    result = await MCPTools._parse_intent(arguments, db_manager)
                elif tool_name == "rank_tables":
                    result = await MCPTools._rank_tables(arguments, db_manager)
                elif tool_name == "list_empty_tables":
                    result = await MCPTools._list_empty_tables(arguments, db_manager)
                elif tool_name == "get_execution_metrics":
                    result = await MCPTools._get_execution_metrics(arguments, db_manager)
                elif tool_name == "get_column_index":
                    result = await MCPTools._get_column_index(arguments, db_manager)
                # Phase 9 Tier 1 Enhancements
                elif tool_name == "get_view_dependencies":
                    result = await MCPTools._get_view_dependencies(arguments, db_manager)
                elif tool_name == "get_fk_cardinality":
                    result = await MCPTools._get_fk_cardinality(arguments, db_manager)
                elif tool_name == "get_domain_clusters":
                    result = await MCPTools._get_domain_clusters(arguments, db_manager)
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
                
                # Extract metrics from result if available and align success with response.ok
                if result and hasattr(result, 'content') and result.content:
                    content = result.content[0]
                    if isinstance(content, dict) and content.get('type') == 'text':
                        text = content.get('text', '')
                        # Attempt to parse JSON envelope from tool response
                        try:
                            payload = json.loads(text)
                            if isinstance(payload, dict):
                                # Align success with "ok" when present
                                if 'ok' in payload:
                                    metrics.success = bool(payload.get('ok', False))
                                    if not metrics.success:
                                        metrics.error_code = payload.get('error_code') or payload.get('code')
                                        metrics.error_message = payload.get('error_message') or payload.get('error')
                                # Common execution metrics from bounded query
                                if 'row_count' in payload and isinstance(payload.get('row_count'), int):
                                    metrics.row_count = payload['row_count']
                                if bool(payload.get('truncated')):
                                    metrics.truncated = True
                        except Exception:
                            # Fallback: extract row count heuristically from human text
                            if 'rows' in text.lower():
                                import re
                                match = re.search(r'(\d+)\s+rows?', text, re.IGNORECASE)
                                if match:
                                    metrics.row_count = int(match.group(1))
                
                # Fallback: align success with isError flag when available
                try:
                    metrics.success = not bool(getattr(result, 'isError', False))
                except Exception:
                    pass
                
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
                "text": json.dumps(schema_json, cls=DecimalEncoder)
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
                    }, cls=DecimalEncoder)
                }],
                isError=True
            )
        
        try:
            # Log the incoming SQL query for monitoring
            logger.info(f"🔍 QUERY_BOUNDED TOOL CALLED")
            logger.info(f"📝 Original SQL Query: {sql}")
            logger.info(f"📊 Requested limit: {limit}, Redaction: {enable_redaction}")
            
            # Diagnostic check for incomplete queries
            sql_stripped = sql.strip()
            if len(sql_stripped) <= 10:
                logger.warning(f"🚨 POTENTIAL INCOMPLETE QUERY: Very short SQL detected ({len(sql_stripped)} chars)")
                logger.warning(f"📋 This may indicate an issue in the calling agent workflow")
            elif sql_stripped.upper() in ['SELECT', 'SELECT DISTINCT']:
                logger.error(f"🚨 INCOMPLETE QUERY CONFIRMED: SQL is just '{sql_stripped}'")
                logger.error(f"📋 Agent workflow is sending incomplete queries - investigate SQL generation")
            
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
            
            # Convert response to JSON and ensure it's JSON-safe (handles Decimals, datetime, etc.)
            response_dict = response.to_dict()
            response_dict = MCPTools._make_json_safe(response_dict)
            
            # Format as human-readable text + JSON
            if response.ok:
                # Log query results for debugging/monitoring
                logger.info(f"✅ QUERY EXECUTED SUCCESSFULLY")
                logger.info(f"📊 Results: {response.row_count} rows, {response.execution_time_ms}ms execution time")
                if response.truncated:
                    applied_limit = response.metadata.get('applied_limit') if response.metadata else None
                    logger.info(f"⚠️ Results truncated to {applied_limit} rows")
                if response.redacted_columns:
                    logger.info(f"🔒 Redacted {len(response.redacted_columns)} sensitive columns")

                # Log sample of results (truncated for log readability)
                if response.rows and len(response.rows) > 0:
                    sample_size = min(3, len(response.rows))  # Log first 3 rows max
                    logger.info(f"📋 Sample results ({sample_size}/{len(response.rows)} rows):")
                    for i, row in enumerate(response.rows[:sample_size]):
                        # Create a truncated version for logging
                        safe_row = MCPTools._make_json_safe(row) if row else {}
                        # Truncate long values in log
                        truncated_row = {}
                        for k, v in safe_row.items():
                            if isinstance(v, str) and len(v) > 50:
                                truncated_row[k] = v[:47] + "..."
                            else:
                                truncated_row[k] = v
                        logger.info(f"   Row {i+1}: {json.dumps(truncated_row, cls=DecimalEncoder)}")
                elif response.row_count == 0:
                    logger.info(f"📋 No rows returned (empty result set)")

                result_text = f"✅ Query executed successfully\n\n"
                result_text += f"Rows returned: {response.row_count}\n"
                result_text += f"Execution time: {response.execution_time_ms}ms\n"

                if response.truncated:
                    applied_limit = response.metadata.get('applied_limit') if response.metadata else None
                    result_text += f"⚠️ Results truncated (limit: {applied_limit})\n"

                if response.redacted_columns:
                    result_text += f"🔒 Redacted columns: {', '.join(response.redacted_columns)}\n"

                columns_text = ', '.join(response.columns) if response.columns else "(no columns)"
                result_text += f"\nColumns: {columns_text}\n\n"
                
                # Add sample rows (first 5)
                if response.rows:
                    result_text += "Sample rows:\n"
                    for i, row in enumerate(response.rows[:5]):
                        # Ensure each row is JSON-safe
                        safe_row = MCPTools._make_json_safe(row) if row else {}
                        result_text += f"  Row {i+1}: {json.dumps(safe_row, cls=DecimalEncoder)}\n"
                    
                    if len(response.rows) > 5:
                        result_text += f"  ... and {len(response.rows) - 5} more rows\n"
                
                # Ensure response_dict is fully JSON-safe one more time before final dump
                response_dict = MCPTools._make_json_safe(response_dict)
                result_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": result_text
                    }],
                    isError=False
                )
            else:
                # Log query failure
                logger.error(f"❌ QUERY FAILED")
                logger.error(f"📊 Error: {response.error_code} - {response.error_message}")
                logger.error(f"⏱️ Execution time: {response.execution_time_ms}ms")

                # Error response
                error_text = f"❌ Query failed\n\n"
                error_text += f"Error code: {response.error_code}\n"
                error_text += f"Error message: {response.error_message}\n"
                error_text += f"Execution time: {response.execution_time_ms}ms\n"
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            import traceback
            logger.error(f"Bounded query execution failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps({
                        "ok": False,
                        "error_code": "INTERNAL_ERROR",
                        "error_message": f"Internal error: {str(e)}"
                    }, cls=DecimalEncoder)
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
        from mcp_server.config import config as mcp_cfg
        include_empty = arguments.get("include_empty", mcp_cfg.include_empty_by_default)
        min_rows = arguments.get("min_rows", 1)
        
        try:
            response = await DiscoveryTools.list_tables(
                db_adapter=db_manager,
                page=page,
                page_size=page_size,
                schema=schema,
                pattern=pattern,
                include_empty=include_empty,
                min_rows=min_rows
            )
            
            response_dict = response.to_dict()
            response_dict = MCPTools._make_json_safe(response_dict)
            
            if response.ok:
                # Format human-readable text - with defensive checks
                if not isinstance(response_dict, dict) or "data" not in response_dict:
                    logger.error(f"list_tables: response structure invalid")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Response structure corrupted"
                        }],
                        isError=True
                    )
                
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
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
        """Search tables by keyword (Phase 4) - Scout Mode aware with semantic ranking."""
        query = arguments.get("query", "").strip()
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 25)
        intent_data = arguments.get("intent_data")  # Extract intent data for semantic ranking

        try:
            # Phase 1: Try Scout catalog first for instant results with NEW consolidated semantic search
            scout_runner = _get_scout_runner(db_manager)
            if scout_runner and scout_runner.is_ready():
                logger.info(f"🔍 Using ScoutRunner.search() for '{query}' with intent-aware ranking")

                # Use the NEW semantic search method from consolidated ScoutRunner
                search_results = scout_runner.search(
                    query=query,
                    top_k=page_size,
                    intent_data=intent_data
                )
                
                if search_results:
                    # Format results as MCP response
                    formatted_text = f"🔍 Search Results for '{query}'\n\n"
                    formatted_text += f"Total matches: {len(search_results)}\n\n"
                    
                    for i, result in enumerate(search_results, 1):
                        formatted_text += f"{i}. {result['full_name']}\n"
                        formatted_text += f"   Type: {result['type']}, Rows: {result['estimated_rows']}, Cols: {result['column_count']}\n"
                        formatted_text += f"   Score: {result['relevance_score']:.3f}, Reasons: {', '.join(result['reasons'])}\n\n"
                    
                    # Return both human-readable and JSON
                    formatted_text += f"\n📊 Full response (JSON):\n{json.dumps({'ok': True, 'data': {'results': search_results}, 'page_info': {'page': page, 'page_size': page_size, 'total_items': len(search_results)}, 'execution_time_ms': 0, 'cached': True, 'source': 'scout_runner'}, indent=2)}"
                    
                    return MCPToolResult(
                        content=[{"type": "text", "text": formatted_text}],
                        isError=False
                    )
                else:
                    logger.warning(f"ScoutRunner.search() returned no results for '{query}'")

            # Fallback to live database search
            logger.debug("Scout catalog not available, using live search")
            response = await DiscoveryTools.search_tables(
                db_adapter=db_manager,
                query=query,
                page=page,
                page_size=page_size
            )
            
            response_dict = response.to_dict()
            response_dict = MCPTools._make_json_safe(response_dict)
            
            if response.ok:
                # Format human-readable text - with defensive checks
                if not isinstance(response_dict, dict) or "data" not in response_dict:
                    logger.error(f"search_tables: response structure invalid")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Response structure corrupted"
                        }],
                        isError=True
                    )
                
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
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
    async def _list_empty_tables(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """List empty tables from catalog (no live INFORMATION_SCHEMA queries)."""
        schema = arguments.get("schema")
        pattern = arguments.get("pattern")
        page = max(1, arguments.get("page", 1))
        page_size = min(max(1, arguments.get("page_size", 25)), 100)
        
        try:
            if not getattr(db_manager, 'catalog', None):
                return MCPToolResult(content=[{"type":"text","text":"Catalog not initialized"}], isError=True)
            items = db_manager.catalog.get_table_list()
            empties = []
            # Pre-threshold stats
            total_candidates = 0
            empty_candidates = 0
            for t in items:
                # Only tables here; views are handled by list_views/search_views
                if str(t.get('type','')).upper() != 'TABLE':
                    continue
                if schema and t['schema'].lower() != schema.lower():
                    continue
                if pattern and pattern.lower() not in t['name'].lower():
                    continue
                est = int(t.get('estimated_rows') or 0)
                total_candidates += 1
                if est == 0:
                    empty_candidates += 1
                # Include only empties
                if est == 0:
                    empties.append({
                        "schema": t['schema'],
                        "name": t['name'],
                        "full_name": t['full_name'],
                        "estimated_rows": est,
                        "column_count": t.get('column_count', 0)
                    })
            total = len(empties)
            start = (page-1)*page_size
            end = start + page_size
            page_items = empties[start:end]
            total_pages = (total + page_size - 1)//page_size if total>0 else 1
            payload = {
                "ok": True,
                "data": {
                    "tables": page_items,
                    "filters": {"schema": schema, "pattern": pattern},
                    "stats": {
                        "total_candidates": total_candidates,
                        "empty_candidates": empty_candidates,
                        "empty_ratio": (empty_candidates/total_candidates) if total_candidates>0 else 0.0
                    }
                },
                "page_info": {"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages, "has_next": page<total_pages, "has_prev": page>1}
            }
            return MCPToolResult(content=[{"type":"text","text": json.dumps(payload, cls=DecimalEncoder)}], isError=False)
        except Exception as e:
            logger.error(f"list_empty_tables failed: {e}")
            return MCPToolResult(content=[{"type":"text","text": f"Internal error: {e}"}], isError=True)
    
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
            
            # Validate response via duck-typing instead of strict class check
            if not hasattr(response, 'to_dict'):
                logger.error(f"describe_table: response missing to_dict(), type={type(response).__name__}")
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"Internal error: Invalid response object from describe_table"
                    }],
                    isError=True
                )
            
            # Ensure response is JSON-safe before processing
            try:
                response_dict = response.to_dict()
                if not isinstance(response_dict, dict):
                    logger.error(f"response.to_dict() returned {type(response_dict).__name__} instead of dict")
                    response_dict = {"ok": response.ok, "error": "Response structure corrupted"}
            except Exception as to_dict_err:
                logger.error(f"Error calling response.to_dict(): {to_dict_err}")
                response_dict = {"ok": response.ok, "error": f"Failed to serialize response: {str(to_dict_err)}"}
            
            response_dict = MCPTools._make_json_safe(response_dict)
            
            if response.ok:
                # Format human-readable text - with defensive checks
                if not isinstance(response_dict, dict):
                    logger.error(f"response_dict is not a dict after _make_json_safe: {type(response_dict).__name__}")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Response structure corrupted (non-dict after processing)"
                        }],
                        isError=True
                    )
                
                if "data" not in response_dict:
                    logger.error(f"response_dict missing 'data' key. Keys: {list(response_dict.keys())}")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Response structure missing data field"
                        }],
                        isError=True
                    )
                
                data = response_dict["data"]
                
                if not isinstance(data, dict):
                    logger.error(f"response_dict['data'] is not a dict: {type(data).__name__}")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": f"Internal error: Data field corrupted (type: {type(data).__name__})"
                        }],
                        isError=True
                    )
                
                # Safe field access with defaults
                full_name = data.get('full_name', 'Unknown')
                table_type = data.get('type', 'Unknown')
                est_rows = data.get('estimated_rows', 0)
                columns = data.get('columns', [])
                
                result_text = f"📊 Table: {full_name}\n\n"
                result_text += f"Type: {table_type}\n"
                try:
                    result_text += f"Estimated rows: ~{est_rows:,}\n"
                except (TypeError, ValueError):
                    result_text += f"Estimated rows: {est_rows}\n"
                result_text += f"Columns: {len(columns)}\n\n"
                
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
                all_columns = {col['name']: col for col in data.get('columns', [])}
                for col_name in data.get('top_columns', [])[:10]:
                    if col_name in all_columns:
                        col = all_columns[col_name]
                        col_info = f"  • {col['name']} ({col['type']})"
                        if not col.get('nullable', True):
                            col_info += " NOT NULL"
                        if col.get('is_primary_key', False):
                            col_info += " [PK]"
                        if col.get('is_foreign_key', False):
                            col_info += " [FK]"
                        result_text += col_info + "\n"
                    else:
                        # Fallback if column not found (shouldn't happen)
                        result_text += f"  • {col_name}\n"
                
                # Sample data
                if include_sample and data.get('sample_data'):
                    result_text += f"\n📄 Sample Data ({len(data['sample_data'])} rows):\n"
                    for i, row in enumerate(data['sample_data'][:3]):
                        result_text += f"  Row {i+1}: {json.dumps(row, cls=DecimalEncoder)}\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": error_text
                    }],
                    isError=True
                )
                
        except Exception as e:
            import traceback
            logger.error(f"describe_table failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Internal error: {str(e)}\n\nDetails: {traceback.format_exc()}"
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
            response_dict = MCPTools._make_json_safe(response_dict)
            
            if response.ok:
                # Format human-readable text - with defensive checks
                if not isinstance(response_dict, dict) or "data" not in response_dict:
                    logger.error(f"list_relations: response structure invalid. Keys: {list(response_dict.keys()) if isinstance(response_dict, dict) else type(response_dict).__name__}")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Response structure corrupted"
                        }],
                        isError=True
                    )
                
                data = response_dict["data"]
                
                if not isinstance(data, dict):
                    logger.error(f"list_relations: data field is not a dict: {type(data).__name__}")
                    return MCPToolResult(
                        content=[{
                            "type": "text",
                            "text": "Internal error: Data field corrupted"
                        }],
                        isError=True
                    )
                
                table_name = data.get('table', 'Unknown')
                neighbor_count = data.get('neighbor_count', 0)
                
                result_text = f"🔗 Relationships for {table_name}\n\n"
                result_text += f"Total neighbors: {neighbor_count}\n\n"
                
                if neighbor_count > 0:
                    result_text += "Related tables:\n"
                    for neighbor in data.get('neighbors', []):
                        result_text += f"  • {neighbor}\n"
                else:
                    result_text += "No related tables found.\n"
                
                result_text += f"\n⏱️ Execution time: {response.execution_time_ms:.2f}ms"
                if response.cached:
                    result_text += " (cached)"
                
                result_text += f"\n\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
                error_text += f"\n📊 Full response (JSON):\n{json.dumps(response_dict, indent=2, cls=DecimalEncoder)}"
                
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
    async def _list_views(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """List views with pagination (Phase 1: Scout catalog-aware)."""
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 25)
        schema = arguments.get("schema")
        pattern = arguments.get("pattern")
        include_empty = arguments.get("include_empty", False)

        try:
            # Phase 1: Try Scout catalog first for instant results
            scout_runner = _get_scout_runner(db_manager)
            if scout_runner and scout_runner.is_ready():
                catalog = scout_runner.get_catalog()
                if catalog and "views" in catalog:
                    # Use Scout catalog views
                    views_dict = catalog["views"]
                    views = list(views_dict.values())
                else:
                    views = []
            else:
                # Fallback to legacy catalog
                if not getattr(db_manager, 'catalog', None):
                    return MCPToolResult(content=[{"type":"text","text":"Catalog not initialized"}], isError=True)

                # Pull all items and filter to views
                all_items = db_manager.catalog.get_table_list()
                views = [t for t in all_items if str(t.get('type','')).upper() == 'VIEW']

            # Apply filters
            filtered_views = []
            total_candidates = 0
            empty_candidates = 0

            for view in views:
                view_name = view.get('name', '')
                view_schema = view.get('schema', '')

                if schema and view_schema.lower() != schema.lower():
                    continue
                if pattern and pattern.lower() not in view_name.lower():
                    continue

                est = int(view.get('estimated_rows', 0) or 0)
                total_candidates += 1
                if est == 0:
                    empty_candidates += 1
                # empty filtering uses estimated_rows
                if not include_empty and est <= 0:
                    continue
                filtered_views.append({
                    "schema": view_schema,
                    "name": view_name,
                    "full_name": view.get('full_name', f"{view_schema}.{view_name}"),
                    "estimated_rows": est,
                    "column_count": view.get('column_count', 0),
                    "role_coverage": view.get('role_coverage', {}),
                    "complexity": view.get('complexity', {})
                })
            total = len(filtered_views)
            page = max(1, page)
            page_size = min(max(1, page_size), 100)
            start = (page-1)*page_size
            end = start + page_size
            page_views = filtered_views[start:end]
            total_pages = (total + page_size - 1) // page_size if total>0 else 1
            
            text = {
                "ok": True,
                "data": {
                    "views": page_views,
                    "filters": {"schema": schema, "pattern": pattern, "include_empty": include_empty},
                    "stats": {
                        "total_candidates": total_candidates,
                        "empty_candidates": empty_candidates,
                        "empty_ratio": (empty_candidates / total_candidates) if total_candidates > 0 else 0.0
                    }
                },
                "page_info": {"page": page, "page_size": page_size, "total_items": total, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page>1}
            }
            return MCPToolResult(content=[{"type":"text","text": json.dumps(text, cls=DecimalEncoder)}])
        except Exception as e:
            logger.error(f"list_views failed: {e}")
            return MCPToolResult(content=[{"type":"text","text": f"Internal error: {e}"}], isError=True)
    
    @staticmethod
    async def _search_views(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Search and rank views using views-first ranker (catalog-only)."""
        from mcp_server.table_ranker import rank_views
        from mcp_server.config import config as mcp_cfg
        
        query = arguments.get("query", "").strip()
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 10)
        include_empty = arguments.get("include_empty", mcp_cfg.include_empty_by_default)
        
        if not query:
            return MCPToolResult(content=[{"type":"text","text":"Query is required"}], isError=True)
        if not getattr(db_manager, 'catalog', None):
            return MCPToolResult(content=[{"type":"text","text":"Catalog not initialized"}], isError=True)
        
        try:
            # Collect candidate views from catalog where type == VIEW
            items = db_manager.catalog.get_table_list()
            raw_views = [t for t in items if str(t.get('type','')).upper()== 'VIEW']
            # Enrich minimal dicts for ranker (columns/tags/def may be missing; ranker handles gracefully)
            # For now we pass through basic fields and estimated_rows
            # Build views dict expected by rank_views(views_dict, entities, operations)
            views_dict = {}
            for v in raw_views:
                est = int(v.get("estimated_rows", 0) or 0)
                if not include_empty and est <= 0:
                    continue
                key = v.get("full_name") or f"{v.get('schema','dbo')}.{v.get('name','')}"
                if not key:
                    continue
                views_dict[key] = {
                    "schema": v.get("schema", ""),
                    "name": v.get("name", ""),
                    "full_name": key,
                    "estimated_rows": est,
                    "column_count": v.get("column_count", 0),
                    "has_rows": est > 0,
                    "role_coverage": v.get("role_coverage", {}),
                    "complexity": v.get("complexity", {})
                }

            # Naive entity extraction from query (split words); ranker has synonyms internally
            entities = [w for w in (query.split() if query else []) if len(w) > 1]
            ranked = rank_views(views=views_dict, entities=entities, operations=[])
            total = len(ranked)
            page = max(1, page)
            page_size = min(max(1, page_size), 50)
            start = (page-1)*page_size
            end = start + page_size
            page_ranked = ranked[start:end]
            data = {
                "results": [
                    {
                        "schema": r.schema,
                        "name": r.name,
                        "full_name": r.full_name,
                        "relevance_score": r.score,
                        "role_coverage": r.role_coverage,
                        "estimated_rows": r.estimated_rows,
                        "has_rows": r.has_rows,
                        "reasons": r.reasons,
                    } for r in page_ranked
                ]
            }
            envelope = {
                "ok": True,
                "data": data,
                "page_info": {"page": page, "page_size": page_size, "total_items": total, "total_pages": (total + page_size - 1)//page_size if total>0 else 1, "has_next": start+page_size < total, "has_prev": page>1}
            }
            return MCPToolResult(content=[{"type":"text","text": json.dumps(envelope, cls=DecimalEncoder)}])
        except Exception as e:
            logger.error(f"search_views failed: {e}")
            return MCPToolResult(content=[{"type":"text","text": f"Internal error: {e}"}], isError=True)
    
    @staticmethod
    async def _describe_view(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Describe a view using catalog (columns, keys, est rows)."""
        view_name = arguments.get("view_name", "").strip()
        include_sample = arguments.get("include_sample", False)
        try:
            if not view_name:
                return MCPToolResult(content=[{"type":"text","text":"view_name is required"}], isError=True)
            if not getattr(db_manager, 'catalog', None):
                return MCPToolResult(content=[{"type":"text","text":"Catalog not initialized"}], isError=True)
            
            # Resolve schema/name
            if '.' in view_name:
                schema, name = view_name.split('.', 1)
            else:
                # Best-effort find by name among views
                items = db_manager.catalog.get_table_list()
                candidates = [t for t in items if str(t.get('type','')).upper()=='VIEW' and t['name'].lower()==view_name.lower()]
                if not candidates:
                    return MCPToolResult(content=[{"type":"text","text":"View not found"}], isError=True)
                schema, name = candidates[0]['schema'], candidates[0]['name']
            detail = db_manager.catalog.get_table(schema, name)
            if not detail or str(detail.get('type','')).upper()!='VIEW':
                return MCPToolResult(content=[{"type":"text","text":"View not found"}], isError=True)
            
            # Build description payload with richer metadata if available
            definition = detail.get('definition') or ""
            deps = detail.get('dependencies') or detail.get('view_dependencies') or []
            role_cov = detail.get('role_coverage') or {}
            complexity = detail.get('complexity') or {}
            payload = {
                "schema": detail['schema'],
                "name": detail['name'],
                "full_name": detail['full_name'],
                "type": detail['type'],
                "estimated_rows": detail.get('estimated_rows', 0),
                "has_rows": detail.get('has_rows', None),
                "columns": detail.get('columns', []),
                "primary_keys": detail.get('primary_keys', []),
                "foreign_keys": detail.get('foreign_keys', []),
                "dependencies": deps,
                "role_coverage": role_cov,
                "complexity": complexity,
                "definition_preview": definition[:500] if isinstance(definition, str) else None
            }
            # Optional sample is not recommended for views here; keep read-only safety
            return MCPToolResult(content=[{"type":"text","text": json.dumps({"ok": True, "data": payload}, cls=DecimalEncoder)}])
        except Exception as e:
            logger.error(f"describe_view failed: {e}")
            return MCPToolResult(content=[{"type":"text","text": f"Internal error: {e}"}], isError=True)
    
    @staticmethod
    async def _list_view_dependencies(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """List upstream dependencies for a view if available in catalog.
        Placeholder until dependencies are ingested."""
        view_name = arguments.get("view_name", "").strip()
        try:
            if not view_name:
                return MCPToolResult(content=[{"type":"text","text":"view_name is required"}], isError=True)
            if not getattr(db_manager, 'catalog', None):
                return MCPToolResult(content=[{"type":"text","text":"Catalog not initialized"}], isError=True)
            # Try to resolve and load
            if '.' in view_name:
                schema, name = view_name.split('.', 1)
            else:
                items = db_manager.catalog.get_table_list()
                candidates = [t for t in items if str(t.get('type','')).upper()=='VIEW' and t['name'].lower()==view_name.lower()]
                if not candidates:
                    return MCPToolResult(content=[{"type":"text","text":"View not found"}], isError=True)
                schema, name = candidates[0]['schema'], candidates[0]['name']
            detail = db_manager.catalog.get_table(schema, name)
            deps = detail.get('dependencies') if detail else None
            payload = {"ok": True, "data": {"view": f"{schema}.{name}", "dependencies": deps or []}}
            return MCPToolResult(content=[{"type":"text","text": json.dumps(payload, cls=DecimalEncoder)}])
        except Exception as e:
            logger.error(f"list_view_dependencies failed: {e}")
            return MCPToolResult(content=[{"type":"text","text": f"Internal error: {e}"}], isError=True)
    
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
                response_text += f"\nDebug Info:\n{json.dumps(result.debug_info, indent=2, cls=DecimalEncoder)}\n"
            
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
            response_text += json.dumps(summary, indent=2, cls=DecimalEncoder)
            
            return MCPToolResult(
                content=[{"type": "text", "text": response_text}]
            )
        
        except Exception as e:
            logger.error(f"get_execution_metrics failed: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )
    
    @staticmethod
    async def _get_column_index(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """
        Get structured column lists for multiple tables (Phase 7.1).
        
        Prevents column hallucination by providing exact column names from Scout Catalog.
        Returns a mapping of table names to column lists.
        """
        try:
            table_names = arguments.get("table_names", [])
            
            if not table_names:
                return MCPToolResult(
                    content=[{"type": "text", "text": json.dumps({"ok": False, "error": "table_names is required"}, cls=DecimalEncoder)}],
                    isError=True
                )
            
            # Delegate to DiscoveryTools which uses the catalog
            result = await DiscoveryTools.get_column_index(db_manager, table_names)
            
            # Ensure response is JSON-safe before dumping
            result_dict = MCPTools._make_json_safe(result.to_dict())
            
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(result_dict, cls=DecimalEncoder)}]
            )
        
        except Exception as e:
            import traceback
            logger.error(f"get_column_index failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_response = {
                "ok": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(error_response)}],
                isError=True
            )
    
    # =====================================================
    # Phase 9 Tier 1 Enhancement Tools
    # =====================================================
    
    @staticmethod
    async def _get_view_dependencies(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """
        Get view dependencies and materialization status (Tier 1 Enhancement).
        """
        try:
            view_name = arguments.get("view_name")
            
            if not view_name:
                return MCPToolResult(
                    content=[{"type": "text", "text": json.dumps({"ok": False, "error": "view_name is required"}, cls=DecimalEncoder)}],
                    isError=True
                )
            
            # Delegate to DiscoveryTools
            result = await DiscoveryTools.get_view_dependencies(db_manager, view_name)
            
            # Ensure response is JSON-safe
            result_dict = MCPTools._make_json_safe(result.to_dict())
            
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(result_dict, cls=DecimalEncoder)}]
            )
        
        except Exception as e:
            import traceback
            logger.error(f"get_view_dependencies failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_response = {
                "ok": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(error_response)}],
                isError=True
            )
    
    @staticmethod
    async def _get_fk_cardinality(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """
        Get foreign key cardinality patterns for a table (Tier 1 Enhancement).
        """
        try:
            table_name = arguments.get("table_name")
            
            if not table_name:
                return MCPToolResult(
                    content=[{"type": "text", "text": json.dumps({"ok": False, "error": "table_name is required"}, cls=DecimalEncoder)}],
                    isError=True
                )
            
            # Delegate to DiscoveryTools
            result = await DiscoveryTools.get_fk_cardinality(db_manager, table_name)
            
            # Ensure response is JSON-safe
            result_dict = MCPTools._make_json_safe(result.to_dict())
            
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(result_dict, cls=DecimalEncoder)}]
            )
        
        except Exception as e:
            import traceback
            logger.error(f"get_fk_cardinality failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_response = {
                "ok": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(error_response)}],
                isError=True
            )
    
    @staticmethod
    async def _get_domain_clusters(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """
        Get business domain clusters (Tier 1 Enhancement).
        """
        try:
            # Delegate to DiscoveryTools
            result = await DiscoveryTools.get_domain_clusters(db_manager)
            
            # Ensure response is JSON-safe
            result_dict = MCPTools._make_json_safe(result.to_dict())
            
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(result_dict, cls=DecimalEncoder)}]
            )
        
        except Exception as e:
            import traceback
            logger.error(f"get_domain_clusters failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_response = {
                "ok": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(error_response)}],
                isError=True
            )