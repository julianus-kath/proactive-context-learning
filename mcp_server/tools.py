"""
MCP tools implementation for database operations.
"""

import logging
from typing import Dict, Any, List
from models import MCPTool, MCPToolResult

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
                description="Execute a SELECT query against the database",
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
            # MongoDB Document Store Tools
            MCPTool(
                name="search_products",
                description="Search products in MongoDB document store with filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text search query for product name/description"
                        },
                        "category": {
                            "type": "string",
                            "description": "Product category filter"
                        },
                        "price_min": {
                            "type": "number",
                            "description": "Minimum price filter"
                        },
                        "price_max": {
                            "type": "number",
                            "description": "Maximum price filter"
                        },
                        "in_stock": {
                            "type": "boolean",
                            "description": "Filter by stock availability"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 20)",
                            "default": 20
                        }
                    },
                    "required": []
                }
            ),
            MCPTool(
                name="get_product_reviews",
                description="Get customer reviews for a specific product",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "integer",
                            "description": "Product ID to get reviews for"
                        },
                        "sentiment": {
                            "type": "string",
                            "description": "Filter by sentiment (positive, neutral, negative)"
                        },
                        "min_rating": {
                            "type": "integer",
                            "description": "Minimum rating filter (1-5)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of reviews (default: 50)",
                            "default": 50
                        }
                    },
                    "required": ["product_id"]
                }
            ),
            MCPTool(
                name="search_support_tickets",
                description="Search support tickets with various filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "integer",
                            "description": "Filter by customer ID"
                        },
                        "product_id": {
                            "type": "integer",
                            "description": "Filter by product ID"
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by ticket status (open, in_progress, resolved, closed)"
                        },
                        "priority": {
                            "type": "string",
                            "description": "Filter by priority (low, medium, high, critical)"
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by ticket category"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tickets (default: 50)",
                            "default": 50
                        }
                    },
                    "required": []
                }
            ),
            MCPTool(
                name="get_review_analytics",
                description="Get review analytics for a product or overall",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "integer",
                            "description": "Product ID for analytics (optional, if not provided returns overall analytics)"
                        }
                    },
                    "required": []
                }
            ),
            MCPTool(
                name="search_knowledge_base",
                description="Search knowledge base articles",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for articles"
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by article category"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of articles (default: 20)",
                            "default": 20
                        }
                    },
                    "required": []
                }
            ),
        ]
    
    @staticmethod
    async def execute_tool(tool_name: str, arguments: Dict[str, Any], db_manager=None, mongo_query_interface=None) -> MCPToolResult:
        """Execute a specific tool."""
        try:
            # SQL Database tools
            if tool_name == "get_schema":
                return await MCPTools._get_schema(arguments, db_manager)
            elif tool_name == "query":
                return await MCPTools._query(arguments, db_manager)
            elif tool_name == "get_table_info":
                return await MCPTools._get_table_info(arguments, db_manager)
            elif tool_name == "get_sample_data":
                return await MCPTools._get_sample_data(arguments, db_manager)
            # MongoDB Document Store tools
            elif tool_name == "search_products":
                return await MCPTools._search_products(arguments, mongo_query_interface)
            elif tool_name == "get_product_reviews":
                return await MCPTools._get_product_reviews(arguments, mongo_query_interface)
            elif tool_name == "search_support_tickets":
                return await MCPTools._search_support_tickets(arguments, mongo_query_interface)
            elif tool_name == "get_review_analytics":
                return await MCPTools._get_review_analytics(arguments, mongo_query_interface)
            elif tool_name == "search_knowledge_base":
                return await MCPTools._search_knowledge_base(arguments, mongo_query_interface)
            else:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"Unknown tool: {tool_name}"
                    }],
                    isError=True
                )
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"Tool execution failed: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _get_schema(arguments: Dict[str, Any], db_manager) -> MCPToolResult:
        """Get database schema information."""
        schema = await db_manager.fetch_schema()
        
        # Format schema information
        schema_text = "Database Schema:\n\n"
        for table in schema:
            schema_text += f"Table: {table['name']} ({table['type']})\n"
            schema_text += "Columns:\n"
            
            for column in table['columns']:
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
                schema_text += col_info + "\n"
            
            schema_text += "\n"
        
        return MCPToolResult(
            content=[{
                "type": "text",
                "text": schema_text
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
    
    # MongoDB Document Store Methods
    @staticmethod
    async def _search_products(arguments: Dict[str, Any], mongo_query_interface) -> MCPToolResult:
        """Search products in MongoDB document store."""
        if not mongo_query_interface:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "MongoDB query interface not available"
                }],
                isError=True
            )
        
        try:
            results = await mongo_query_interface.search_products(
                query=arguments.get("query"),
                category=arguments.get("category"),
                price_min=arguments.get("price_min"),
                price_max=arguments.get("price_max"),
                in_stock=arguments.get("in_stock"),
                limit=arguments.get("limit", 20)
            )
            
            if not results:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": "No products found matching the criteria."
                    }]
                )
            
            # Format results
            result_text = f"Found {len(results)} products:\n\n"
            for product in results:
                result_text += f"• {product.get('name', 'N/A')} (ID: {product.get('product_id', 'N/A')})\n"
                result_text += f"  Category: {product.get('category', 'N/A')}\n"
                result_text += f"  Price: ${product.get('price', 'N/A')}\n"
                result_text += f"  In Stock: {product.get('availability', {}).get('in_stock', 'N/A')}\n"
                result_text += f"  Description: {product.get('description', 'N/A')[:100]}...\n\n"
            
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
                    "text": f"Failed to search products: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _get_product_reviews(arguments: Dict[str, Any], mongo_query_interface) -> MCPToolResult:
        """Get product reviews from MongoDB document store."""
        if not mongo_query_interface:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "MongoDB query interface not available"
                }],
                isError=True
            )
        
        product_id = arguments.get("product_id")
        if not product_id:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "Product ID is required"
                }],
                isError=True
            )
        
        try:
            results = await mongo_query_interface.get_product_reviews(
                product_id=product_id,
                sentiment=arguments.get("sentiment"),
                min_rating=arguments.get("min_rating"),
                limit=arguments.get("limit", 50)
            )
            
            if not results:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"No reviews found for product {product_id}."
                    }]
                )
            
            # Format results
            result_text = f"Found {len(results)} reviews for product {product_id}:\n\n"
            for review in results:
                result_text += f"• Rating: {review.get('rating', 'N/A')}/5 - {review.get('sentiment', 'N/A')}\n"
                result_text += f"  Title: {review.get('title', 'N/A')}\n"
                result_text += f"  Customer: {review.get('customer_id', 'N/A')}\n"
                result_text += f"  Date: {review.get('review_date', 'N/A')}\n"
                result_text += f"  Content: {review.get('content', 'N/A')[:150]}...\n\n"
            
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
                    "text": f"Failed to get product reviews: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _search_support_tickets(arguments: Dict[str, Any], mongo_query_interface) -> MCPToolResult:
        """Search support tickets in MongoDB document store."""
        if not mongo_query_interface:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "MongoDB query interface not available"
                }],
                isError=True
            )
        
        try:
            results = await mongo_query_interface.search_support_tickets(
                customer_id=arguments.get("customer_id"),
                product_id=arguments.get("product_id"),
                status=arguments.get("status"),
                priority=arguments.get("priority"),
                category=arguments.get("category"),
                limit=arguments.get("limit", 50)
            )
            
            if not results:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": "No support tickets found matching the criteria."
                    }]
                )
            
            # Format results
            result_text = f"Found {len(results)} support tickets:\n\n"
            for ticket in results:
                result_text += f"• Ticket: {ticket.get('ticket_id', 'N/A')}\n"
                result_text += f"  Subject: {ticket.get('subject', 'N/A')}\n"
                result_text += f"  Status: {ticket.get('status', 'N/A')} | Priority: {ticket.get('priority', 'N/A')}\n"
                result_text += f"  Customer: {ticket.get('customer_id', 'N/A')}\n"
                result_text += f"  Created: {ticket.get('created_date', 'N/A')}\n"
                result_text += f"  Description: {ticket.get('description', 'N/A')[:100]}...\n\n"
            
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
                    "text": f"Failed to search support tickets: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _get_review_analytics(arguments: Dict[str, Any], mongo_query_interface) -> MCPToolResult:
        """Get review analytics from MongoDB document store."""
        if not mongo_query_interface:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "MongoDB query interface not available"
                }],
                isError=True
            )
        
        try:
            results = await mongo_query_interface.get_review_analytics(
                product_id=arguments.get("product_id")
            )
            
            # Format results
            product_text = f" for product {arguments.get('product_id')}" if arguments.get('product_id') else " (overall)"
            result_text = f"Review Analytics{product_text}:\n\n"
            result_text += f"Total Reviews: {results.get('total_reviews', 0)}\n"
            result_text += f"Average Rating: {results.get('average_rating', 0)}/5\n\n"
            
            sentiment_counts = results.get('sentiment_counts', {})
            result_text += "Sentiment Breakdown:\n"
            result_text += f"  • Positive: {sentiment_counts.get('positive', 0)}\n"
            result_text += f"  • Neutral: {sentiment_counts.get('neutral', 0)}\n"
            result_text += f"  • Negative: {sentiment_counts.get('negative', 0)}\n\n"
            
            rating_dist = results.get('rating_distribution', {})
            result_text += "Rating Distribution:\n"
            for i in range(5, 0, -1):
                result_text += f"  • {i} stars: {rating_dist.get(f'{i}_star', 0)}\n"
            
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
                    "text": f"Failed to get review analytics: {str(e)}"
                }],
                isError=True
            )
    
    @staticmethod
    async def _search_knowledge_base(arguments: Dict[str, Any], mongo_query_interface) -> MCPToolResult:
        """Search knowledge base articles in MongoDB document store."""
        if not mongo_query_interface:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": "MongoDB query interface not available"
                }],
                isError=True
            )
        
        try:
            results = await mongo_query_interface.search_knowledge_base(
                query=arguments.get("query"),
                category=arguments.get("category"),
                limit=arguments.get("limit", 20)
            )
            
            if not results:
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": "No knowledge base articles found matching the criteria."
                    }]
                )
            
            # Format results
            result_text = f"Found {len(results)} knowledge base articles:\n\n"
            for article in results:
                result_text += f"• {article.get('title', 'N/A')}\n"
                result_text += f"  Category: {article.get('category', 'N/A')}\n"
                result_text += f"  Views: {article.get('views', 0)} | Helpful: {article.get('helpful_votes', 0)}\n"
                result_text += f"  Content: {article.get('content', 'N/A')[:150]}...\n\n"
            
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
                    "text": f"Failed to search knowledge base: {str(e)}"
                }],
                isError=True
            )