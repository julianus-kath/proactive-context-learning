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

from mcp_server.db import DatabaseManager

logger = logging.getLogger(__name__)

class DirectDatabaseClient:
    """Direct database client that bypasses HTTP layer."""
    
    def __init__(self):
        self.initialized = False
        self.db_manager = DatabaseManager()
    
    async def _ensure_initialized(self):
        """Ensure database connection is initialized."""
        if not self.initialized:
            await self.db_manager.initialize()
            self.initialized = True
    
    async def get_all_schemas(self) -> List[str]:
        """
        Get all available schemas in the database.
        
        Returns:
            List of schema names
        """
        try:
            await self._ensure_initialized()
            
            schemas_query = """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
            """
            
            schemas = await self.db_manager.fetch(schemas_query)
            return [schema['schema_name'] for schema in schemas]
            
        except Exception as e:
            logger.error(f"Error getting schemas: {e}")
            return ['public']  # fallback to public schema
    
    async def get_schema(self, include_all_schemas: bool = True) -> str:
        """
        Get the database schema as a formatted string.
        
        Args:
            include_all_schemas: If True, includes all schemas, otherwise just public
        
        Returns:
            Formatted schema information
        """
        try:
            await self._ensure_initialized()
            
            if include_all_schemas:
                schemas = await self.get_all_schemas()
            else:
                schemas = ['public']
            
            all_schema_parts = []
            
            for schema_name in schemas:
                # Get table information for this schema
                tables_query = f"""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = '{schema_name}' 
                ORDER BY table_name
                """
                
                tables = await self.db_manager.fetch(tables_query)
                
                if not tables:
                    continue  # Skip empty schemas
                
                schema_parts = [f"Schema: {schema_name}"]
                schema_parts.append("=" * (len(schema_name) + 8))
                
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
                    WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                    ORDER BY ordinal_position
                    """
                    
                    columns = await self.db_manager.fetch(columns_query)
                    
                    # Format table information
                    schema_parts.append(f"Table: {schema_name}.{table_name} ({table_type})")
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
                
                all_schema_parts.extend(schema_parts)
                all_schema_parts.append("")  # Empty line between schemas
            
            return "\n".join(all_schema_parts)
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return f"Error retrieving schema: {str(e)}"
    
    async def execute_query(self, sql: str, max_retries: int = 2) -> str:
        """
        Execute a SQL query and return formatted results with error handling and retry logic.
        
        Args:
            sql: SQL query to execute
            max_retries: Maximum number of retries for syntax errors
            
        Returns:
            Formatted query results or error information
        """
        try:
            await self._ensure_initialized()
            
            # Execute the query
            results = await self.db_manager.fetch(sql)
            
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
            error_msg = str(e).lower()
            logger.error(f"Error executing query: {e}")
            
            # Return structured error information for the workflow to handle
            return f"QUERY_ERROR: {str(e)}"
    
    async def validate_and_fix_query(self, sql: str, error_msg: str, schema: str) -> Optional[str]:
        """
        Attempt to validate and fix a SQL query based on the error message.
        
        Args:
            sql: Original SQL query
            error_msg: Error message from failed execution
            schema: Database schema information
            
        Returns:
            Fixed SQL query or None if cannot be fixed
        """
        try:
            # Common SQL fixes based on error patterns
            fixed_sql = sql
            
            # Fix schema qualification issues
            if "relation" in error_msg and "does not exist" in error_msg:
                # Try to qualify table names with schema
                schemas = await self.get_all_schemas()
                for schema_name in schemas:
                    if schema_name != 'public':
                        # Replace unqualified table references
                        import re
                        # Find table names that might need schema qualification
                        table_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
                        matches = re.findall(table_pattern, sql)
                        
                        for match in matches:
                            if match.lower() not in ['select', 'from', 'where', 'and', 'or', 'order', 'by', 'group', 'having', 'limit', 'offset', 'inner', 'left', 'right', 'join', 'on', 'as', 'count', 'sum', 'avg', 'max', 'min']:
                                # Check if this table exists in the schema
                                qualified_name = f"{schema_name}.{match}"
                                if qualified_name in schema:
                                    fixed_sql = fixed_sql.replace(f" {match} ", f" {qualified_name} ")
                                    fixed_sql = fixed_sql.replace(f" {match}\n", f" {qualified_name}\n")
                                    fixed_sql = fixed_sql.replace(f"FROM {match}", f"FROM {qualified_name}")
                                    fixed_sql = fixed_sql.replace(f"JOIN {match}", f"JOIN {qualified_name}")
            
            # Fix INTERVAL syntax issues
            if "interval" in error_msg.lower():
                import re
                # Fix unquoted intervals
                fixed_sql = re.sub(r"INTERVAL\s+(\d+\s+\w+)", r"INTERVAL '\1'", fixed_sql, flags=re.IGNORECASE)
            
            # Fix quote issues
            if "syntax error" in error_msg.lower():
                # Replace double quotes with single quotes for string literals
                import re
                fixed_sql = re.sub(r'"([^"]*)"', r"'\1'", fixed_sql)
            
            return fixed_sql if fixed_sql != sql else None
            
        except Exception as e:
            logger.error(f"Error in query validation: {e}")
            return None
    
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
            await self.db_manager.fetch("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def index_database(self) -> Dict[str, Any]:
        """
        Perform comprehensive database indexing on startup.
        
        Returns:
            Dictionary with database structure information
        """
        try:
            await self._ensure_initialized()
            
            # Get all schemas
            schemas = await self.get_all_schemas()
            
            index_info = {
                "schemas": schemas,
                "tables": {},
                "total_tables": 0,
                "total_columns": 0
            }
            
            for schema_name in schemas:
                # Get tables in this schema
                tables_query = f"""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = '{schema_name}' 
                ORDER BY table_name
                """
                
                tables = await self.db_manager.fetch(tables_query)
                
                for table in tables:
                    table_name = table['table_name']
                    full_table_name = f"{schema_name}.{table_name}"
                    
                    # Get column information
                    columns_query = f"""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                    ORDER BY ordinal_position
                    """
                    
                    columns = await self.db_manager.fetch(columns_query)
                    
                    # Get row count (with error handling for large tables)
                    try:
                        count_query = f"SELECT COUNT(*) as count FROM {full_table_name}"
                        count_result = await self.db_manager.fetch(count_query)
                        row_count = count_result[0]['count'] if count_result else 0
                    except Exception:
                        row_count = "Unknown"
                    
                    index_info["tables"][full_table_name] = {
                        "schema": schema_name,
                        "table_name": table_name,
                        "table_type": table['table_type'],
                        "columns": [col['column_name'] for col in columns],
                        "column_details": columns,
                        "row_count": row_count
                    }
                    
                    index_info["total_tables"] += 1
                    index_info["total_columns"] += len(columns)
            
            logger.info(f"Database indexed: {index_info['total_tables']} tables across {len(schemas)} schemas")
            return index_info
            
        except Exception as e:
            logger.error(f"Error indexing database: {e}")
            return {
                "schemas": ["public"],
                "tables": {},
                "total_tables": 0,
                "total_columns": 0,
                "error": str(e)
            }

# Global instance
_direct_client = DirectDatabaseClient()

# Utility functions that match the MCP client interface
async def get_database_schema(include_all_schemas: bool = True) -> str:
    """Get the database schema as a formatted string."""
    return await _direct_client.get_schema(include_all_schemas)

async def execute_sql_query(sql: str) -> str:
    """Execute a SQL query and return formatted results."""
    return await _direct_client.execute_query(sql)

async def execute_sql_query_with_retry(sql: str, schema: str, max_retries: int = 2) -> str:
    """Execute a SQL query with automatic retry and error correction."""
    for attempt in range(max_retries + 1):
        result = await _direct_client.execute_query(sql)
        
        # Check if this is an error that we can potentially fix
        if result.startswith("QUERY_ERROR:"):
            error_msg = result[12:]  # Remove "QUERY_ERROR:" prefix
            
            if attempt < max_retries:
                # Try to fix the query
                fixed_sql = await _direct_client.validate_and_fix_query(sql, error_msg, schema)
                if fixed_sql:
                    logger.info(f"Attempting to fix query (attempt {attempt + 1}): {fixed_sql}")
                    sql = fixed_sql  # Use the fixed query for next attempt
                    continue
            
            # If we can't fix it or we've exhausted retries, return the error
            return result
        
        # Success - return the result
        return result
    
    return "QUERY_ERROR: Maximum retry attempts exceeded"

async def get_table_information(table_name: str) -> str:
    """Get detailed information about a specific table."""
    return await _direct_client.get_table_info(table_name)

async def health_check() -> bool:
    """Check if the database connection is healthy."""
    return await _direct_client.health_check()

async def index_database() -> Dict[str, Any]:
    """Perform comprehensive database indexing."""
    return await _direct_client.index_database()

async def get_all_schemas() -> List[str]:
    """Get all available schemas in the database."""
    return await _direct_client.get_all_schemas()