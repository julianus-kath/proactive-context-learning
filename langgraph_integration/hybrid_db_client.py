"""
Hybrid Database Client for LangGraph Integration
Handles both SQL database and MongoDB document store operations
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp_server.database.db import db_manager

logger = logging.getLogger(__name__)

class HybridDatabaseClient:
    """Hybrid database client that handles both SQL and MongoDB operations."""
    
    def __init__(self):
        self.sql_initialized = False
        self.mongo_initialized = False
        self.mongo_query_interface = None
    
    async def _ensure_sql_initialized(self):
        """Ensure SQL database connection is initialized."""
        if not self.sql_initialized:
            await db_manager.initialize()
            self.sql_initialized = True
    
    async def _ensure_mongo_initialized(self):
        """Ensure MongoDB connection is initialized."""
        if not self.mongo_initialized:
            try:
                # Add mongodb_document_store to path
                mongodb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mongodb_document_store')
                if mongodb_path not in sys.path:
                    sys.path.append(mongodb_path)
                
                from query_interface import MongoQueryInterface
                self.mongo_query_interface = MongoQueryInterface()
                self.mongo_initialized = True
                logger.info("MongoDB query interface initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MongoDB: {e}")
                self.mongo_query_interface = None
                self.mongo_initialized = False
    
    async def get_schema(self) -> str:
        """
        Get the combined schema information for both SQL and MongoDB.
        
        Returns:
            Formatted schema information for both databases
        """
        schema_parts = []
        
        # Get SQL schema
        try:
            await self._ensure_sql_initialized()
            
            # Get table information
            tables_query = """
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
            """
            
            tables = await db_manager.fetch(tables_query)
            
            schema_parts.append("=== SQL DATABASE SCHEMA ===\n")
            
            for table in tables:
                table_name = table['table_name']
                table_type = table['table_type']
                
                # Get column information
                columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
                """
                
                columns = await db_manager.fetch(columns_query, (table_name,))
                
                schema_parts.append(f"\nTable: {table_name} ({table_type})")
                schema_parts.append("Columns:")
                
                for column in columns:
                    col_info = f"  - {column['column_name']} ({column['data_type']}"
                    if column['character_maximum_length']:
                        col_info += f"({column['character_maximum_length']})"
                    col_info += ")"
                    
                    if column['is_nullable'] == 'NO':
                        col_info += " NOT NULL"
                    if column['column_default']:
                        col_info += f" DEFAULT {column['column_default']}"
                    
                    schema_parts.append(col_info)
                
                # Get foreign key relationships
                fk_query = """
                SELECT 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_name = %s
                    AND tc.table_schema = 'public'
                """
                
                foreign_keys = await db_manager.fetch(fk_query, (table_name,))
                
                if foreign_keys:
                    schema_parts.append("Foreign Keys:")
                    for fk in foreign_keys:
                        schema_parts.append(f"  - {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")
        
        except Exception as e:
            logger.error(f"Error getting SQL schema: {e}")
            schema_parts.append(f"SQL Schema Error: {str(e)}")
        
        # Get MongoDB schema
        try:
            await self._ensure_mongo_initialized()
            
            if self.mongo_query_interface:
                schema_parts.append("\n\n=== MONGODB DOCUMENT STORE SCHEMA ===\n")
                
                # Document collections and their structure
                collections_info = {
                    "product_catalog": {
                        "description": "Enhanced product information with specifications and media",
                        "sample_fields": [
                            "product_id (int) - Links to SQL products table",
                            "name (string) - Product name",
                            "description (string) - Product description", 
                            "detailed_description (string) - Comprehensive description",
                            "category (string) - Product category",
                            "subcategory (string) - Product subcategory",
                            "brand (string) - Product brand",
                            "specifications (object) - Technical specifications",
                            "price (number) - Product price",
                            "availability (object) - Stock information",
                            "images (array) - Product images",
                            "seo_keywords (array) - SEO keywords",
                            "related_products (array) - Related product IDs"
                        ]
                    },
                    "customer_reviews": {
                        "description": "Customer reviews with sentiment analysis and ratings",
                        "sample_fields": [
                            "review_id (string) - Unique review identifier",
                            "product_id (int) - Links to SQL products table",
                            "customer_id (int) - Links to SQL customers table",
                            "title (string) - Review title",
                            "content (string) - Review content",
                            "rating (int) - Rating 1-5",
                            "sentiment (string) - positive/neutral/negative",
                            "review_date (datetime) - Review date",
                            "purchase_verified (boolean) - Verified purchase",
                            "helpful_votes (int) - Helpful votes count",
                            "aspects (object) - Aspect ratings (quality, price, delivery)",
                            "company_response (object) - Company response if any"
                        ]
                    },
                    "support_tickets": {
                        "description": "Customer support tickets with full lifecycle tracking",
                        "sample_fields": [
                            "ticket_id (string) - Unique ticket identifier",
                            "customer_id (int) - Links to SQL customers table",
                            "product_id (int) - Links to SQL products table",
                            "subject (string) - Ticket subject",
                            "description (string) - Issue description",
                            "category (string) - Issue category",
                            "status (string) - open/in_progress/resolved/closed",
                            "priority (string) - low/medium/high/critical",
                            "created_date (datetime) - Creation date",
                            "resolved_date (datetime) - Resolution date",
                            "resolution (object) - Resolution details",
                            "satisfaction_rating (int) - Customer satisfaction rating",
                            "messages (array) - Ticket conversation messages"
                        ]
                    },
                    "marketing_campaigns": {
                        "description": "Marketing campaign data and performance tracking",
                        "sample_fields": [
                            "campaign_id (string) - Unique campaign identifier",
                            "name (string) - Campaign name",
                            "description (string) - Campaign description",
                            "campaign_type (string) - Campaign type",
                            "status (string) - Campaign status",
                            "start_date (datetime) - Campaign start date",
                            "end_date (datetime) - Campaign end date",
                            "target_audience (object) - Audience targeting criteria",
                            "budget (number) - Campaign budget",
                            "performance_metrics (object) - Performance data"
                        ]
                    },
                    "knowledge_base": {
                        "description": "Knowledge base articles and documentation",
                        "sample_fields": [
                            "article_id (string) - Unique article identifier",
                            "title (string) - Article title",
                            "content (string) - Article content",
                            "category (string) - Article category",
                            "tags (array) - Article tags",
                            "author (string) - Article author",
                            "created_date (datetime) - Creation date",
                            "updated_date (datetime) - Last update date",
                            "views (int) - View count",
                            "helpful_votes (int) - Helpful votes count"
                        ]
                    }
                }
                
                for collection_name, info in collections_info.items():
                    schema_parts.append(f"\nCollection: {collection_name}")
                    schema_parts.append(f"Description: {info['description']}")
                    schema_parts.append("Fields:")
                    for field in info['sample_fields']:
                        schema_parts.append(f"  - {field}")
                
                schema_parts.append("\n=== DATA RELATIONSHIPS ===")
                schema_parts.append("- product_id fields in MongoDB link to SQL products.id")
                schema_parts.append("- customer_id fields in MongoDB link to SQL customers.id")
                schema_parts.append("- MongoDB provides rich document data complementing SQL relational data")
                
            else:
                schema_parts.append("\n\n=== MONGODB DOCUMENT STORE ===")
                schema_parts.append("MongoDB connection not available")
        
        except Exception as e:
            logger.error(f"Error getting MongoDB schema: {e}")
            schema_parts.append(f"\nMongoDB Schema Error: {str(e)}")
        
        return "\n".join(schema_parts)
    
    async def execute_sql_query(self, sql: str, limit: int = 100) -> str:
        """Execute SQL query against the relational database."""
        try:
            await self._ensure_sql_initialized()
            results = await db_manager.fetch(sql, limit=limit)
            
            if not results:
                return "Query executed successfully but returned no results."
            
            # Format results as a table
            result_lines = [f"Query Results ({len(results)} rows):\n"]
            
            # Add column headers
            columns = list(results[0].keys())
            result_lines.append(" | ".join(columns))
            result_lines.append("-" * len(" | ".join(columns)))
            
            # Add data rows
            for row in results:
                row_values = [str(row.get(col, "")) for col in columns]
                result_lines.append(" | ".join(row_values))
            
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"SQL query execution failed: {e}")
            return f"SQL query execution failed: {str(e)}"
    
    async def execute_document_query(self, operation: str, **kwargs) -> str:
        """Execute document query against MongoDB."""
        try:
            await self._ensure_mongo_initialized()
            
            if not self.mongo_query_interface:
                return "MongoDB document store is not available"
            
            if operation == "search_products":
                results = await self.mongo_query_interface.search_products(**kwargs)
                if not results:
                    return "No products found matching the criteria."
                
                result_lines = [f"Found {len(results)} products:\n"]
                for product in results:
                    result_lines.append(f"• {product.get('name', 'N/A')} (ID: {product.get('product_id', 'N/A')})")
                    result_lines.append(f"  Category: {product.get('category', 'N/A')}")
                    result_lines.append(f"  Price: ${product.get('price', 'N/A')}")
                    result_lines.append(f"  In Stock: {product.get('availability', {}).get('in_stock', 'N/A')}")
                    result_lines.append(f"  Description: {product.get('description', 'N/A')[:100]}...")
                    result_lines.append("")
                
                return "\n".join(result_lines)
            
            elif operation == "get_product_reviews":
                results = await self.mongo_query_interface.get_product_reviews(**kwargs)
                if not results:
                    return f"No reviews found for product {kwargs.get('product_id', 'N/A')}."
                
                result_lines = [f"Found {len(results)} reviews for product {kwargs.get('product_id')}:\n"]
                for review in results:
                    result_lines.append(f"• Rating: {review.get('rating', 'N/A')}/5 - {review.get('sentiment', 'N/A')}")
                    result_lines.append(f"  Title: {review.get('title', 'N/A')}")
                    result_lines.append(f"  Customer: {review.get('customer_id', 'N/A')}")
                    result_lines.append(f"  Date: {review.get('review_date', 'N/A')}")
                    result_lines.append(f"  Content: {review.get('content', 'N/A')[:150]}...")
                    result_lines.append("")
                
                return "\n".join(result_lines)
            
            elif operation == "search_support_tickets":
                results = await self.mongo_query_interface.search_support_tickets(**kwargs)
                if not results:
                    return "No support tickets found matching the criteria."
                
                result_lines = [f"Found {len(results)} support tickets:\n"]
                for ticket in results:
                    result_lines.append(f"• Ticket: {ticket.get('ticket_id', 'N/A')}")
                    result_lines.append(f"  Subject: {ticket.get('subject', 'N/A')}")
                    result_lines.append(f"  Status: {ticket.get('status', 'N/A')} | Priority: {ticket.get('priority', 'N/A')}")
                    result_lines.append(f"  Customer: {ticket.get('customer_id', 'N/A')}")
                    result_lines.append(f"  Created: {ticket.get('created_date', 'N/A')}")
                    result_lines.append(f"  Description: {ticket.get('description', 'N/A')[:100]}...")
                    result_lines.append("")
                
                return "\n".join(result_lines)
            
            elif operation == "get_review_analytics":
                results = await self.mongo_query_interface.get_review_analytics(**kwargs)
                
                product_text = f" for product {kwargs.get('product_id')}" if kwargs.get('product_id') else " (overall)"
                result_lines = [f"Review Analytics{product_text}:\n"]
                result_lines.append(f"Total Reviews: {results.get('total_reviews', 0)}")
                result_lines.append(f"Average Rating: {results.get('average_rating', 0)}/5\n")
                
                sentiment_counts = results.get('sentiment_counts', {})
                result_lines.append("Sentiment Breakdown:")
                result_lines.append(f"  • Positive: {sentiment_counts.get('positive', 0)}")
                result_lines.append(f"  • Neutral: {sentiment_counts.get('neutral', 0)}")
                result_lines.append(f"  • Negative: {sentiment_counts.get('negative', 0)}\n")
                
                rating_dist = results.get('rating_distribution', {})
                result_lines.append("Rating Distribution:")
                for i in range(5, 0, -1):
                    result_lines.append(f"  • {i} stars: {rating_dist.get(f'{i}_star', 0)}")
                
                return "\n".join(result_lines)
            
            elif operation == "search_knowledge_base":
                results = await self.mongo_query_interface.search_knowledge_base(**kwargs)
                if not results:
                    return "No knowledge base articles found matching the criteria."
                
                result_lines = [f"Found {len(results)} knowledge base articles:\n"]
                for article in results:
                    result_lines.append(f"• {article.get('title', 'N/A')}")
                    result_lines.append(f"  Category: {article.get('category', 'N/A')}")
                    result_lines.append(f"  Views: {article.get('views', 0)} | Helpful: {article.get('helpful_votes', 0)}")
                    result_lines.append(f"  Content: {article.get('content', 'N/A')[:150]}...")
                    result_lines.append("")
                
                return "\n".join(result_lines)
            
            else:
                return f"Unknown document operation: {operation}"
                
        except Exception as e:
            logger.error(f"Document query execution failed: {e}")
            return f"Document query execution failed: {str(e)}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of both database connections."""
        health_status = {
            "sql_database": {"status": "unknown", "error": None},
            "mongodb": {"status": "unknown", "error": None}
        }
        
        # Check SQL database
        try:
            await self._ensure_sql_initialized()
            # Simple query to test connection
            await db_manager.fetch("SELECT 1 as test", limit=1)
            health_status["sql_database"]["status"] = "healthy"
        except Exception as e:
            health_status["sql_database"]["status"] = "unhealthy"
            health_status["sql_database"]["error"] = str(e)
        
        # Check MongoDB
        try:
            await self._ensure_mongo_initialized()
            if self.mongo_query_interface:
                # Try a simple operation
                await self.mongo_query_interface.search_products(limit=1)
                health_status["mongodb"]["status"] = "healthy"
            else:
                health_status["mongodb"]["status"] = "unavailable"
                health_status["mongodb"]["error"] = "MongoDB interface not initialized"
        except Exception as e:
            health_status["mongodb"]["status"] = "unhealthy"
            health_status["mongodb"]["error"] = str(e)
        
        return health_status

# Global client instance
hybrid_client = HybridDatabaseClient()

# Convenience functions for backward compatibility
async def get_database_schema() -> str:
    """Get combined database schema."""
    return await hybrid_client.get_schema()

async def execute_sql_query(sql: str, limit: int = 100) -> str:
    """Execute SQL query."""
    return await hybrid_client.execute_sql_query(sql, limit)

async def execute_document_query(operation: str, **kwargs) -> str:
    """Execute document query."""
    return await hybrid_client.execute_document_query(operation, **kwargs)

async def health_check() -> Dict[str, Any]:
    """Health check for both databases."""
    return await hybrid_client.health_check()

# Legacy functions for compatibility
async def get_table_information(table_name: str) -> str:
    """Get information about a specific table (SQL only)."""
    try:
        await hybrid_client._ensure_sql_initialized()
        
        # Get column information
        columns_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
        """
        
        columns = await db_manager.fetch(columns_query, (table_name,))
        
        if not columns:
            return f"Table '{table_name}' not found"
        
        # Get row count
        count_query = f"SELECT COUNT(*) as count FROM {table_name}"
        count_result = await db_manager.fetch(count_query)
        row_count = count_result[0]['count'] if count_result else 0
        
        result_lines = [f"Table: {table_name}"]
        result_lines.append(f"Row Count: {row_count:,}\n")
        result_lines.append("Columns:")
        
        for column in columns:
            col_info = f"  - {column['column_name']} ({column['data_type']}"
            if column['character_maximum_length']:
                col_info += f"({column['character_maximum_length']})"
            col_info += ")"
            
            if column['is_nullable'] == 'NO':
                col_info += " NOT NULL"
            if column['column_default']:
                col_info += f" DEFAULT {column['column_default']}"
            
            result_lines.append(col_info)
        
        return "\n".join(result_lines)
        
    except Exception as e:
        logger.error(f"Error getting table information: {e}")
        return f"Error getting table information: {str(e)}"