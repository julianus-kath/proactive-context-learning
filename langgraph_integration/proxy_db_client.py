"""
Proxy Database Client for LangGraph Integration
Uses the MCPDatabaseClient for ERP database access

PHASE 7 MIGRATION: Updated to use MCPDatabaseClient (MCP-only architecture)
----------------------------------------------------------------------------
This module now uses MCP JSON-RPC protocol exclusively for all database access.
Legacy proxy mode has been removed in favor of the single MCP interface.

PHASE 1 ENHANCEMENT: Schema Caching & Selective Loading
--------------------------------------------------------
This module integrates with the schema cache to eliminate archive
schema discovery calls and supports selective table loading for smaller prompts.

Changes:
- PHASE 7: Migrated from DatabaseClient to MCPDatabaseClient
- PHASE 7: Removed proxy mode checks (MCP-only now)
- PHASE 7: Use MCP discovery tools (search_tables, describe_table)
- Added schema caching via app.db.schema_cache
- Modified get_schema() to use cache when available
- Added build_schema_index() to create structured schema index
- Existing get_table_info() method now cache-aware
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
import sys
import os
from dotenv import load_dotenv

# Load environment variables from project root
project_root = os.path.join(os.path.dirname(__file__), '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Add the project root to the path
sys.path.append(project_root)

# Import MCPDatabaseClient with proper path handling
try:
    from app.db.mcp_client import MCPDatabaseClient
    from app.db.schema_cache import get_schema_cache, TableInfo
except ImportError:
    # Alternative import path if running from different directory
    sys.path.append(os.path.join(project_root, 'app'))
    from db.mcp_client import MCPDatabaseClient
    from db.schema_cache import get_schema_cache, TableInfo

logger = logging.getLogger(__name__)

class ProxyDatabaseClient:
    """Database client that uses MCPDatabaseClient for ERP access via MCP protocol."""
    
    def __init__(self):
        self.client = MCPDatabaseClient()
        logger.info("ProxyDatabaseClient initialized with MCP-only architecture")
        logger.info(f"MCP Server URL: {self.client.config.server_url}")
    
    async def get_all_schemas(self) -> List[str]:
        """
        Get all available schemas in the database.
        
        PHASE 7: Uses MCP search_tables to discover schemas from table names.
        
        Returns:
            List of schema names
        """
        try:
            # Use MCP's search_tables to get all tables
            tables = self.client.search_tables("", limit=100)
            
            # Extract unique schemas from qualified table names
            schemas = set()
            for table in tables:
                if '.' in table:
                    schema_name = table.split('.')[0]
                    schemas.add(schema_name)
                else:
                    schemas.add('public')  # Default schema
            
            return sorted(list(schemas))
                
        except Exception as e:
            logger.error(f"Error getting schemas: {e}")
            return ['dbo']  # fallback to default schema
    
    async def get_schema(self, include_all_schemas: bool = True, force_refresh: bool = False) -> str:
        """
        Get the database schema as a formatted string.
        
        PHASE 1 ENHANCEMENT: Now uses schema cache to avoid archive discovery.
        First call indexes the schema, subsequent calls use cached data.
        
        Args:
            include_all_schemas: If True, includes all schemas, otherwise just default
            force_refresh: If True, bypasses cache and fetches fresh schema
        
        Returns:
            Formatted schema information
        """
        try:
            # Get cache instance
            cache = get_schema_cache()
            
            # Check cache first (unless force_refresh)
            if not force_refresh and cache.is_cached():
                schema_text, schema_index = cache.get_schema()
                if schema_text:
                    logger.info("Using cached schema (cache hit)")
                    return schema_text
            
            # Cache miss or force refresh - fetch from database
            logger.info("Fetching schema from database using MCP discovery tools (cache miss or refresh)")
            
            # PHASE 7: Use MCP discovery tools instead of raw SQL queries
            # This is more efficient and respects design guardrails
            
            # Get all tables using MCP search_tables
            all_tables = self.client.search_tables("", limit=200)
            
            if not all_tables:
                return "No tables found in database."
            
            # Group tables by schema
            schemas_dict = {}
            for qualified_name in all_tables:
                if '.' in qualified_name:
                    schema_name, table_name = qualified_name.split('.', 1)
                else:
                    schema_name = 'public'
                    table_name = qualified_name
                
                if schema_name not in schemas_dict:
                    schemas_dict[schema_name] = []
                schemas_dict[schema_name].append(qualified_name)
            
            # Filter schemas if needed
            if not include_all_schemas:
                # Keep only first schema (usually 'dbo' or 'public')
                first_schema = list(schemas_dict.keys())[0] if schemas_dict else 'public'
                schemas_dict = {first_schema: schemas_dict.get(first_schema, [])}
            
            all_schema_parts = []
            schema_index = {}  # Build index while fetching
            
            for schema_name, table_list in schemas_dict.items():
                schema_parts = [f"Schema: {schema_name}"]
                schema_parts.append("=" * (len(schema_name) + 8))
                
                for qualified_table_name in table_list:
                    try:
                        # Use MCP's describe_table for column information
                        table_info = self.client.describe_table(qualified_table_name)
                        
                        # Build column list for index
                        columns_list = []
                        for col in table_info.get('columns', []):
                            columns_list.append({
                                'column_name': col.get('name', 'unknown'),
                                'data_type': col.get('type', 'unknown'),
                                'is_nullable': 'YES' if col.get('nullable', True) else 'NO',
                                'column_default': col.get('default'),
                                'character_maximum_length': col.get('max_length')
                            })
                        
                        # Store in schema index
                        table_name = qualified_table_name.split('.')[-1]
                        schema_index[qualified_table_name] = TableInfo(
                            schema_name=schema_name,
                            table_name=table_name,
                            table_type='BASE TABLE',  # MCP doesn't distinguish types yet
                            columns=columns_list,
                            primary_keys=table_info.get('primary_keys', []),
                            foreign_keys=table_info.get('foreign_keys', [])
                        )
                        
                        # Format table information for text output
                        schema_parts.append(f"Table: {qualified_table_name}")
                        schema_parts.append("Columns:")
                        
                        for col_dict in columns_list:
                            col_name = col_dict['column_name']
                            data_type = col_dict['data_type']
                            is_nullable = col_dict['is_nullable']
                            column_default = col_dict['column_default']
                            max_length = col_dict['character_maximum_length']
                            
                            col_info = f"  - {col_name} ({data_type}"
                            if max_length:
                                col_info += f"({max_length})"
                            col_info += ")"
                            
                            if is_nullable == 'NO':
                                col_info += " NOT NULL"
                            if column_default:
                                col_info += f" DEFAULT {column_default}"
                            
                            schema_parts.append(col_info)
                        
                        schema_parts.append("")  # Empty line between tables
                        
                    except Exception as e:
                        logger.warning(f"Could not describe table {qualified_table_name}: {e}")
                        schema_parts.append(f"Table: {qualified_table_name}")
                        schema_parts.append("  - [Column details unavailable]")
                        schema_parts.append("")
                
                all_schema_parts.extend(schema_parts)
                all_schema_parts.append("")  # Empty line between schemas
            
            # Build final schema text
            schema_text = "\n".join(all_schema_parts)
            
            # Cache the schema
            cache.set_schema(schema_text, schema_index)
            logger.info(f"Schema cached using MCP: {len(schema_index)} tables indexed")
            
            return schema_text
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return f"Error retrieving schema: {str(e)}"
    
    async def get_schema_index(self, force_refresh: bool = False) -> Dict[str, TableInfo]:
        """
        Get the structured schema index.
        
        PHASE 1 NEW METHOD: Returns the schema index for table selection.
        
        Args:
            force_refresh: If True, bypasses cache and fetches fresh schema
        
        Returns:
            Dictionary mapping table names to TableInfo objects
        """
        cache = get_schema_cache()
        
        # Check cache first
        if not force_refresh and cache.is_cached():
            _, schema_index = cache.get_schema()
            if schema_index:
                return schema_index
        
        # Cache miss - fetch schema (which will populate the cache)
        await self.get_schema(force_refresh=force_refresh)
        
        # Now get from cache
        _, schema_index = cache.get_schema()
        return schema_index or {}
    
    async def get_selective_schema(self, table_names: List[str]) -> str:
        """
        Get schema information for specific tables only.
        
        PHASE 1 NEW METHOD: Returns compact schema for selected tables.
        This is used to build smaller prompts with only relevant tables.
        
        Args:
            table_names: List of table names (schema-qualified)
        
        Returns:
            Formatted schema snippet containing only specified tables
        """
        from app.db.table_selector import build_schema_snippet
        
        # Get schema index
        schema_index = await self.get_schema_index()
        
        if not schema_index:
            logger.warning("Schema index not available")
            return "Schema not available"
        
        # Build snippet for selected tables
        snippet = build_schema_snippet(table_names, schema_index)
        logger.info(f"Built schema snippet for {len(table_names)} tables")
        
        return snippet
    
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
            # Execute the query
            columns, rows = self.client.query(sql, limit=1000)
            
            if not rows:
                return "Query executed successfully. No results returned."
            
            # Format results as a readable string
            if len(rows) == 1 and len(columns) == 1:
                # Single value result
                value = rows[0][0]
                return f"{columns[0]}: {value}"
            
            # Multiple results - format as table
            if rows:
                # Create formatted table
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
            
            # Fix schema qualification issues for SQL Server
            if self.client.mode == "proxy":
                if "invalid object name" in error_msg.lower() or "object name" in error_msg.lower():
                    # Try to qualify table names with schema
                    schemas = await self.get_all_schemas()
                    for schema_name in schemas:
                        # Replace unqualified table references
                        import re
                        # Find table names that might need schema qualification
                        table_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
                        matches = re.findall(table_pattern, sql)
                        
                        for match in matches:
                            if match.lower() not in ['select', 'from', 'where', 'and', 'or', 'order', 'by', 'group', 'having', 'limit', 'offset', 'inner', 'left', 'right', 'join', 'on', 'as', 'count', 'sum', 'avg', 'max', 'min', 'top']:
                                # Check if this table exists in the schema
                                qualified_name = f"{schema_name}.{match}"
                                if qualified_name in schema:
                                    fixed_sql = fixed_sql.replace(f" {match} ", f" {qualified_name} ")
                                    fixed_sql = fixed_sql.replace(f" {match}\n", f" {qualified_name}\n")
                                    fixed_sql = fixed_sql.replace(f"FROM {match}", f"FROM {qualified_name}")
                                    fixed_sql = fixed_sql.replace(f"JOIN {match}", f"JOIN {qualified_name}")
                
                # Fix LIMIT to TOP for SQL Server
                if "limit" in error_msg.lower():
                    import re
                    # Extract the limit number first
                    limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
                    if limit_match:
                        limit_num = limit_match.group(1)
                        # Remove LIMIT clause
                        fixed_sql = re.sub(r'\s+LIMIT\s+\d+', '', fixed_sql, flags=re.IGNORECASE)
                        # Add TOP clause
                        if 'SELECT' in fixed_sql.upper():
                            fixed_sql = re.sub(r'SELECT\s+', f'SELECT TOP {limit_num} ', fixed_sql, flags=re.IGNORECASE)
            
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
            table_name: Name of the table (can include schema)
            
        Returns:
            Formatted table information
        """
        try:
            # Parse schema and table name
            if '.' in table_name:
                schema_name, table_name = table_name.split('.', 1)
            else:
                schema_name = 'dbo' if self.client.mode == "proxy" else 'public'
            
            # Get table structure
            if self.client.mode == "proxy":
                # SQL Server syntax
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
            else:
                # PostgreSQL syntax
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
            
            columns, rows = self.client.query(columns_query, limit=1000)
            
            if not rows:
                return f"Table '{schema_name}.{table_name}' not found."
            
            # Get row count
            try:
                if self.client.mode == "proxy":
                    count_query = f"SELECT COUNT(*) as count FROM [{schema_name}].[{table_name}]"
                else:
                    count_query = f"SELECT COUNT(*) as count FROM {schema_name}.{table_name}"
                
                count_columns, count_rows = self.client.query(count_query, limit=1)
                row_count = count_rows[0][0] if count_rows else 0
            except Exception as e:
                logger.warning(f"Could not get row count for {table_name}: {e}")
                row_count = "Unknown"
            
            # Format information
            info_lines = [
                f"Table: {schema_name}.{table_name}",
                f"Rows: {row_count}",
                "Columns:"
            ]
            
            for row in rows:
                col_name = row[0]
                data_type = row[1]
                is_nullable = row[2]
                column_default = row[3]
                
                col_info = f"  - {col_name} ({data_type})"
                if is_nullable == 'NO':
                    col_info += " NOT NULL"
                if column_default:
                    col_info += f" DEFAULT {column_default}"
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
            return self.client.health_check()
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
                if self.client.mode == "proxy":
                    tables_query = f"""
                    SELECT table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = '{schema_name}' 
                    ORDER BY table_name
                    """
                else:
                    tables_query = f"""
                    SELECT table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = '{schema_name}' 
                    ORDER BY table_name
                    """
                
                columns, rows = self.client.query(tables_query, limit=1000)
                
                schema_tables = []
                for row in rows:
                    table_name = row[0]
                    table_type = row[1]
                    
                    # Get column count for this table
                    try:
                        if self.client.mode == "proxy":
                            col_count_query = f"""
                            SELECT COUNT(*) as col_count 
                            FROM information_schema.columns 
                            WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                            """
                        else:
                            col_count_query = f"""
                            SELECT COUNT(*) as col_count 
                            FROM information_schema.columns 
                            WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
                            """
                        
                        col_columns, col_rows = self.client.query(col_count_query, limit=1)
                        column_count = col_rows[0][0] if col_rows else 0
                        
                        table_info = {
                            "name": table_name,
                            "type": table_type,
                            "schema": schema_name,
                            "column_count": column_count
                        }
                        
                        schema_tables.append(table_info)
                        index_info["total_columns"] += column_count
                        
                    except Exception as e:
                        logger.warning(f"Could not get column count for {schema_name}.{table_name}: {e}")
                        schema_tables.append({
                            "name": table_name,
                            "type": table_type,
                            "schema": schema_name,
                            "column_count": 0
                        })
                
                index_info["tables"][schema_name] = schema_tables
                index_info["total_tables"] += len(schema_tables)
            
            logger.info(f"Database indexed: {index_info['total_tables']} tables, {index_info['total_columns']} columns across {len(schemas)} schemas")
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


# Global client instance
_client = None

async def get_database_schema() -> str:
    """Get database schema information."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.get_schema()

async def execute_sql_query(sql: str) -> str:
    """Execute a SQL query."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.execute_query(sql)

async def execute_sql_query_with_retry(sql: str, schema: str, max_retries: int = 2) -> str:
    """Execute a SQL query with retry logic."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    
    for attempt in range(max_retries + 1):
        result = await _client.execute_query(sql)
        
        if not result.startswith("QUERY_ERROR:"):
            return result
        
        if attempt < max_retries:
            # Try to fix the query
            error_msg = result[12:]  # Remove "QUERY_ERROR: " prefix
            fixed_sql = await _client.validate_and_fix_query(sql, error_msg, schema)
            
            if fixed_sql:
                logger.info(f"Retrying with fixed query: {fixed_sql}")
                sql = fixed_sql
            else:
                break
    
    return result

async def get_table_information(table_name: str) -> str:
    """Get information about a specific table."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.get_table_info(table_name)

async def health_check() -> bool:
    """Check database health."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.health_check()

async def index_database() -> Dict[str, Any]:
    """Index the database."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.index_database()

async def get_all_schemas() -> List[str]:
    """Get all database schemas."""
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.get_all_schemas()

async def get_schema_index(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get the structured schema index.
    
    PHASE 1 NEW FUNCTION: Exposes schema index for table selection.
    """
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.get_schema_index(force_refresh=force_refresh)

async def get_selective_schema(table_names: List[str]) -> str:
    """
    Get schema for specific tables only.
    
    PHASE 1 NEW FUNCTION: Returns compact schema snippet.
    """
    global _client
    if _client is None:
        _client = ProxyDatabaseClient()
    return await _client.get_selective_schema(table_names)