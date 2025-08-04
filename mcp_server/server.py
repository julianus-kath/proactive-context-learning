"""
MCP Server for PostgreSQL ERP Database.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

from .config import config
from .database import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server
server = Server(config.server_name)

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available database resources."""
    resources = []
    
    # Add database schema as a resource
    resources.append(Resource(
        uri="schema://database",
        name="Database Schema",
        description="Complete database schema with table and column information",
        mimeType="application/json"
    ))
    
    # Add each table as a resource
    table_info = db_manager.get_table_info()
    for table_name, info in table_info.items():
        resources.append(Resource(
            uri=f"table://{table_name}",
            name=f"Table: {table_name}",
            description=f"Table {table_name} with {info['row_count']} rows",
            mimeType="application/json"
        ))
    
    # Add table relationships as a resource
    resources.append(Resource(
        uri="relationships://database",
        name="Table Relationships",
        description="Foreign key relationships between tables",
        mimeType="application/json"
    ))
    
    return resources

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific database resource."""
    try:
        if uri == "schema://database":
            # Return complete database schema
            schema_info = db_manager.get_table_info()
            return json.dumps(schema_info, indent=2)
        
        elif uri.startswith("table://"):
            # Return sample data from a specific table
            table_name = uri.replace("table://", "")
            sample_data = db_manager.get_sample_data(table_name, limit=10)
            return json.dumps(sample_data, indent=2)
        
        elif uri == "relationships://database":
            # Return table relationships
            relationships = db_manager.get_table_relationships()
            return json.dumps(relationships, indent=2)
        
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
            
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        return json.dumps({"error": str(e)})

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available database tools."""
    return [
        Tool(
            name="execute_sql_query",
            description="Execute a SQL query against the ERP database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional query parameters",
                        "additionalProperties": True
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_table_info",
            description="Get detailed information about a specific table",
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
        Tool(
            name="search_tables",
            description="Search for tables by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Term to search for in table names"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="get_sample_data",
            description="Get sample data from a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of sample rows to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="analyze_query_performance",
            description="Analyze the performance of a SQL query using EXPLAIN",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to analyze"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "execute_sql_query":
            query = arguments["query"]
            params = arguments.get("params")
            
            # Execute the query
            result = db_manager.execute_query(query, params)
            
            # Format the response
            if result["type"] == "select":
                response = f"Query executed successfully!\n\n"
                response += f"Columns: {', '.join(result['columns'])}\n"
                response += f"Rows returned: {result['row_count']}\n"
                if result.get("truncated"):
                    response += f"(Results truncated to {config.max_query_results} rows)\n"
                response += f"\nData:\n{json.dumps(result['data'], indent=2)}"
            elif result["type"] == "modification":
                response = result["message"]
            else:  # error
                response = f"Error: {result['message']}\nDetails: {result['error']}"
            
            return [TextContent(type="text", text=response)]
        
        elif name == "get_table_info":
            table_name = arguments["table_name"]
            table_info = db_manager.get_table_info()
            
            if table_name in table_info:
                info = table_info[table_name]
                response = f"Table: {table_name}\n"
                response += f"Row count: {info['row_count']}\n\n"
                response += "Columns:\n"
                for col in info['columns']:
                    response += f"  - {col['name']} ({col['type']})"
                    if col['primary_key']:
                        response += " [PRIMARY KEY]"
                    if col['foreign_key']:
                        response += f" [FOREIGN KEY -> {col.get('references', 'unknown')}]"
                    if not col['nullable']:
                        response += " [NOT NULL]"
                    response += "\n"
            else:
                response = f"Table '{table_name}' not found."
            
            return [TextContent(type="text", text=response)]
        
        elif name == "search_tables":
            search_term = arguments["search_term"]
            matching_tables = db_manager.search_tables(search_term)
            
            if matching_tables:
                response = f"Tables matching '{search_term}':\n"
                for table in matching_tables:
                    table_info = db_manager.get_table_info()[table]
                    response += f"  - {table} ({table_info['row_count']} rows)\n"
            else:
                response = f"No tables found matching '{search_term}'"
            
            return [TextContent(type="text", text=response)]
        
        elif name == "get_sample_data":
            table_name = arguments["table_name"]
            limit = arguments.get("limit", 5)
            
            sample_data = db_manager.get_sample_data(table_name, limit)
            
            if sample_data["type"] == "select":
                response = f"Sample data from {table_name} (showing {sample_data['row_count']} rows):\n\n"
                response += json.dumps(sample_data["data"], indent=2)
            else:
                response = f"Error getting sample data: {sample_data.get('message', 'Unknown error')}"
            
            return [TextContent(type="text", text=response)]
        
        elif name == "analyze_query_performance":
            query = arguments["query"]
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            
            result = db_manager.execute_query(explain_query)
            
            if result["type"] == "select" and result["data"]:
                explain_data = result["data"][0]["QUERY PLAN"]
                response = f"Query Performance Analysis:\n\n"
                response += json.dumps(explain_data, indent=2)
            else:
                response = f"Error analyzing query: {result.get('message', 'Unknown error')}"
            
            return [TextContent(type="text", text=response)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]

async def main():
    """Main server function."""
    # Initialize the database connection
    try:
        # Test database connection
        table_info = db_manager.get_table_info()
        logger.info(f"Connected to database with {len(table_info)} tables")
        
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=config.server_name,
                    server_version=config.server_version,
                    capabilities=server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())