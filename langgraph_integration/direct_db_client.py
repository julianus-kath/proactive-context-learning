"""
Direct Database Client for LangGraph Integration
Bypasses HTTP layer and connects directly to the database
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp_server.db import db_manager

logger = logging.getLogger(__name__)

class DirectDatabaseClient:
    """Direct database client that bypasses HTTP layer."""
    
    def __init__(self):
        self.initialized = False
    
    async def _ensure_initialized(self):
        """Ensure database connection is initialized."""
        if not self.initialized:
            await db_manager.initialize()
            self.initialized = True
    
    async def get_schema(self) -> str:
        """
        Get the database schema as a formatted string.
        
        Returns:
            Formatted schema information
        """
        try:
            await self._ensure_initialized()
            
            # Get table information
            tables_query = """
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
            """
            
            tables = await db_manager.fetch(tables_query)
            
            schema_parts = []
            
            for table in tables:
                table_name = table['table_name']
                table_type = table['table_type']
                
                # Get column information for each table
                columns_query = f"""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = '{table_name}'
                ORDER BY ordinal_position
                """
                
                columns = await db_manager.fetch(columns_query)
                
                # Format table information
                schema_parts.append(f"Table: {table_name} ({table_type})")
                schema_parts.append("Columns:")
                
                for col in columns:
                    col_info = f"  - {col['column_name']} ({col['data_type']}"
                    if col['character_maximum_length']:
                        col_info += f"({col['character_maximum_length']})"
                    col_info += ")"
                    
                    if col['is_nullable'] == 'NO':
                        col_info += " NOT NULL"
                    if col['column_default']:
                        col_info += f" DEFAULT {col['column_default']}"
                    
                    schema_parts.append(col_info)
                
                schema_parts.append("")  # Empty line between tables
            
            return "\n".join(schema_parts)
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return f"Error retrieving schema: {str(e)}"
    
    async def execute_query(self, sql: str) -> str:
        """
        Execute a SQL query and return formatted results.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Formatted query results
        """
        try:
            await self._ensure_initialized()
            
            # Execute the query
            results = await db_manager.fetch(sql)
            
            if not results:
                return "Query executed successfully. No results returned."
            
            # Format results as a readable string
            if len(results) == 1 and len(results[0]) == 1:
                # Single value result
                key = list(results[0].keys())[0]
                value = results[0][key]
                return f"{key}: {value}"
            
            # Multiple results - format as table
            if results:
                # Get column names
                columns = list(results[0].keys())
                
                # Create formatted table
                formatted_lines = []
                
                # Header
                header = " | ".join(columns)
                formatted_lines.append(header)
                formatted_lines.append("-" * len(header))
                
                # Data rows (limit to first 10 for readability)
                for i, row in enumerate(results[:10]):
                    row_data = " | ".join(str(row[col]) for col in columns)
                    formatted_lines.append(row_data)
                
                if len(results) > 10:
                    formatted_lines.append(f"... and {len(results) - 10} more rows")
                
                return "\n".join(formatted_lines)
            
            return "No results found."
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return f"Query execution failed: {str(e)}"
    
    async def get_table_info(self, table_name: str) -> str:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Formatted table information
        """
        try:
            await self._ensure_initialized()
            
            # Get table structure
            columns_query = f"""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = '{table_name}'
            ORDER BY ordinal_position
            """
            
            columns = await db_manager.fetch(columns_query)
            
            if not columns:
                return f"Table '{table_name}' not found."
            
            # Get row count
            count_query = f"SELECT COUNT(*) as count FROM {table_name}"
            count_result = await db_manager.fetch(count_query)
            row_count = count_result[0]['count'] if count_result else 0
            
            # Format information
            info_lines = [
                f"Table: {table_name}",
                f"Rows: {row_count}",
                "Columns:"
            ]
            
            for col in columns:
                col_info = f"  - {col['column_name']} ({col['data_type']})"
                if col['is_nullable'] == 'NO':
                    col_info += " NOT NULL"
                info_lines.append(col_info)
            
            return "\n".join(info_lines)
            
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            return f"Error getting table information: {str(e)}"
    
    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._ensure_initialized()
            # Simple test query
            await db_manager.fetch("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

# Global instance
_direct_client = DirectDatabaseClient()

# Utility functions that match the MCP client interface
async def get_database_schema() -> str:
    """Get the database schema as a formatted string."""
    return await _direct_client.get_schema()

async def execute_sql_query(sql: str) -> str:
    """Execute a SQL query and return formatted results."""
    return await _direct_client.execute_query(sql)

async def get_table_information(table_name: str) -> str:
    """Get detailed information about a specific table."""
    return await _direct_client.get_table_info(table_name)

async def health_check() -> bool:
    """Check if the database connection is healthy."""
    return await _direct_client.health_check()