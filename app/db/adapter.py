"""
Database Adapter - Provides async interface using DatabaseClient
Maintains compatibility with existing langgraph_integration code
"""

import asyncio
import logging
from typing import List, Dict, Any
import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.db.client import DatabaseClient

logger = logging.getLogger(__name__)

# Global client instance
_db_client = None


def get_client() -> DatabaseClient:
    """Get or create the global DatabaseClient instance."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client


async def get_database_schema(include_all_schemas: bool = True) -> str:
    """
    Get the database schema as a formatted string.
    
    Args:
        include_all_schemas: If True, includes all schemas (proxy mode ignores this)
        
    Returns:
        Formatted schema information
    """
    try:
        client = get_client()
        
        if client.mode == "proxy":
            # In proxy mode, we can't get detailed schema info directly
            # Instead, we'll query the information_schema tables
            
            # Get all tables
            tables_sql = """
            SELECT table_schema, table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY table_schema, table_name
            """
            
            columns, rows = client.query(tables_sql)
            
            if not rows:
                return "No tables found in database."
            
            # Group by schema
            schemas = {}
            for row in rows:
                schema_name = row[0]  # table_schema
                table_name = row[1]   # table_name
                table_type = row[2]   # table_type
                
                if schema_name not in schemas:
                    schemas[schema_name] = []
                schemas[schema_name].append((table_name, table_type))
            
            # Build formatted schema string
            schema_parts = []
            
            for schema_name, tables in schemas.items():
                schema_parts.append(f"Schema: {schema_name}")
                schema_parts.append("=" * (len(schema_name) + 8))
                
                for table_name, table_type in tables:
                    # Get column information for each table
                    columns_sql = f"""
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
                    
                    try:
                        col_columns, col_rows = client.query(columns_sql)
                        
                        schema_parts.append(f"Table: {schema_name}.{table_name} ({table_type})")
                        schema_parts.append("Columns:")
                        
                        for col_row in col_rows:
                            col_name = col_row[0]      # column_name
                            data_type = col_row[1]     # data_type
                            is_nullable = col_row[2]   # is_nullable
                            col_default = col_row[3]   # column_default
                            max_length = col_row[4]    # character_maximum_length
                            
                            col_info = f"  - {col_name} ({data_type}"
                            if max_length:
                                col_info += f"({max_length})"
                            col_info += ")"
                            
                            if is_nullable == 'NO':
                                col_info += " NOT NULL"
                            if col_default:
                                col_info += f" DEFAULT {col_default}"
                            
                            schema_parts.append(col_info)
                        
                        schema_parts.append("")  # Empty line between tables
                        
                    except Exception as e:
                        logger.warning(f"Failed to get columns for {schema_name}.{table_name}: {e}")
                        schema_parts.append(f"Table: {schema_name}.{table_name} ({table_type})")
                        schema_parts.append("  - Column information unavailable")
                        schema_parts.append("")
                
                schema_parts.append("")  # Empty line between schemas
            
            return "\n".join(schema_parts)
            
        else:
            # Direct mode would use the existing implementation
            raise NotImplementedError("Direct mode schema retrieval not implemented yet")
            
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        return f"Error retrieving schema: {str(e)}"


async def execute_sql_query(sql: str) -> str:
    """
    Execute a SQL query and return formatted results.
    
    Args:
        sql: SQL query to execute
        
    Returns:
        Formatted query results or error information
    """
    try:
        client = get_client()
        columns, rows = client.query(sql)
        
        if not rows:
            return "Query executed successfully. No results returned."
        
        # Format results as a readable string
        if len(rows) == 1 and len(columns) == 1:
            # Single value result
            return f"{columns[0]}: {rows[0][0]}"
        
        # Multiple results - format as table
        if rows:
            formatted_lines = []
            
            # Header
            header = " | ".join(columns)
            formatted_lines.append(header)
            formatted_lines.append("-" * len(header))
            
            # Data rows (limit to first 10 for readability)
            for i, row in enumerate(rows[:10]):
                row_data = " | ".join(str(val) for val in row)
                formatted_lines.append(row_data)
            
            if len(rows) > 10:
                formatted_lines.append(f"... and {len(rows) - 10} more rows")
            
            return "\n".join(formatted_lines)
        
        return "No results found."
        
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return f"QUERY_ERROR: {str(e)}"


async def execute_sql_query_with_retry(sql: str, schema: str, max_retries: int = 2) -> str:
    """
    Execute a SQL query with automatic retry and error correction.
    
    Args:
        sql: SQL query to execute
        schema: Database schema information (for error correction)
        max_retries: Maximum number of retries
        
    Returns:
        Formatted query results or error information
    """
    for attempt in range(max_retries + 1):
        result = await execute_sql_query(sql)
        
        # Check if this is an error that we can potentially fix
        if result.startswith("QUERY_ERROR:"):
            error_msg = result[12:]  # Remove "QUERY_ERROR:" prefix
            
            if attempt < max_retries:
                # Basic query fixing logic
                fixed_sql = _attempt_query_fix(sql, error_msg, schema)
                if fixed_sql and fixed_sql != sql:
                    logger.info(f"Attempting to fix query (attempt {attempt + 1}): {fixed_sql}")
                    sql = fixed_sql  # Use the fixed query for next attempt
                    continue
            
            # If we can't fix it or we've exhausted retries, return the error
            return result
        
        # Success - return the result
        return result
    
    return "QUERY_ERROR: Maximum retry attempts exceeded"


def _attempt_query_fix(sql: str, error_msg: str, schema: str) -> str:
    """
    Attempt to fix a SQL query based on the error message.
    
    Args:
        sql: Original SQL query
        error_msg: Error message from failed execution
        schema: Database schema information
        
    Returns:
        Fixed SQL query or original if cannot be fixed
    """
    try:
        fixed_sql = sql
        error_lower = error_msg.lower()
        
        # Fix common issues
        if "relation" in error_lower and "does not exist" in error_lower:
            # Try to qualify table names with schema
            import re
            # Simple fix: try adding 'public.' prefix to unqualified table names
            # This is a basic implementation - could be more sophisticated
            words = sql.split()
            for i, word in enumerate(words):
                if word.lower() in ['from', 'join'] and i + 1 < len(words):
                    next_word = words[i + 1]
                    if '.' not in next_word and next_word.isalpha():
                        words[i + 1] = f"public.{next_word}"
            fixed_sql = ' '.join(words)
        
        # Fix INTERVAL syntax issues
        if "interval" in error_lower:
            import re
            # Fix unquoted intervals
            fixed_sql = re.sub(r"INTERVAL\s+(\d+\s+\w+)", r"INTERVAL '\1'", fixed_sql, flags=re.IGNORECASE)
        
        return fixed_sql
        
    except Exception as e:
        logger.error(f"Error in query fixing: {e}")
        return sql


async def get_table_information(table_name: str) -> str:
    """
    Get detailed information about a specific table.
    
    Args:
        table_name: Name of the table
        
    Returns:
        Formatted table information
    """
    try:
        client = get_client()
        
        # Get table structure
        columns_sql = f"""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = '{table_name}'
        ORDER BY ordinal_position
        """
        
        columns, rows = client.query(columns_sql)
        
        if not rows:
            return f"Table '{table_name}' not found."
        
        # Get row count
        count_sql = f"SELECT COUNT(*) as count FROM {table_name}"
        try:
            count_columns, count_rows = client.query(count_sql)
            row_count = count_rows[0][0] if count_rows else 0
        except:
            row_count = "Unknown"
        
        # Format information
        info_lines = [
            f"Table: {table_name}",
            f"Rows: {row_count}",
            "Columns:"
        ]
        
        for row in rows:
            col_name = row[0]      # column_name
            data_type = row[1]     # data_type
            is_nullable = row[2]   # is_nullable
            col_default = row[3]   # column_default
            
            col_info = f"  - {col_name} ({data_type})"
            if is_nullable == 'NO':
                col_info += " NOT NULL"
            if col_default:
                col_info += f" DEFAULT {col_default}"
            info_lines.append(col_info)
        
        return "\n".join(info_lines)
        
    except Exception as e:
        logger.error(f"Error getting table info: {e}")
        return f"Error getting table information: {str(e)}"


async def health_check() -> bool:
    """
    Check if the database connection is healthy.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        client = get_client()
        return client.health_check()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


async def index_database() -> Dict[str, Any]:
    """
    Perform comprehensive database indexing on startup.
    
    Returns:
        Dictionary with database structure information
    """
    try:
        client = get_client()
        
        # Get all schemas
        schemas_sql = """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name
        """
        
        columns, rows = client.query(schemas_sql)
        schemas = [row[0] for row in rows] if rows else ['public']
        
        index_info = {
            "schemas": schemas,
            "tables": {},
            "total_tables": 0,
            "total_columns": 0
        }
        
        for schema_name in schemas:
            # Get tables in this schema
            tables_sql = f"""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = '{schema_name}' 
            ORDER BY table_name
            """
            
            table_columns, table_rows = client.query(tables_sql)
            
            for table_row in table_rows:
                table_name = table_row[0]
                table_type = table_row[1]
                
                full_table_name = f"{schema_name}.{table_name}"
                
                # Get column count for this table
                col_count_sql = f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                """
                
                try:
                    count_columns, count_rows = client.query(col_count_sql)
                    column_count = count_rows[0][0] if count_rows else 0
                except:
                    column_count = 0
                
                index_info["tables"][full_table_name] = {
                    "schema": schema_name,
                    "name": table_name,
                    "type": table_type,
                    "columns": column_count
                }
                
                index_info["total_tables"] += 1
                index_info["total_columns"] += column_count
        
        logger.info(f"Database indexed: {index_info['total_tables']} tables, {index_info['total_columns']} columns")
        return index_info
        
    except Exception as e:
        logger.error(f"Error indexing database: {e}")
        return {
            "schemas": [],
            "tables": {},
            "total_tables": 0,
            "total_columns": 0,
            "error": str(e)
        }


async def get_all_schemas() -> List[str]:
    """
    Get all available schemas in the database.
    
    Returns:
        List of schema names
    """
    try:
        client = get_client()
        
        schemas_sql = """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name
        """
        
        columns, rows = client.query(schemas_sql)
        return [row[0] for row in rows] if rows else ['public']
        
    except Exception as e:
        logger.error(f"Error getting schemas: {e}")
        return ['public']  # fallback to public schema