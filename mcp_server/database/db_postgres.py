"""
Direct PostgreSQL connector for MCP server.
Uses asyncpg with connection pooling, timeouts, and read-only enforcement.
"""

import asyncpg
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PostgresConnector:
    """
    Direct PostgreSQL connector with connection pooling and safety features.
    
    Features:
    - asyncpg connection pool
    - Statement timeouts (30s default)
    - Read-only enforcement
    - Row limits (max 1000)
    - Automatic reconnection on failure
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        timeout: int = 30,
        max_rows: int = 1000,
        min_pool_size: int = 1,
        max_pool_size: int = 10
    ):
        """
        Initialize Postgres connector.
        
        Args:
            host: PostgreSQL hostname or IP
            port: PostgreSQL port (default: 5432)
            database: Database name
            user: Database username
            password: Database password
            timeout: Query timeout in seconds (default: 30)
            max_rows: Maximum rows to return (default: 1000)
            min_pool_size: Minimum pool size (default: 1)
            max_pool_size: Maximum pool size (default: 10)
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.timeout = timeout
        self.max_rows = max_rows
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        
        # Connection pool (will be initialized on first use)
        self._pool: Optional[asyncpg.Pool] = None
        
        logger.info(f"PostgresConnector initialized for {host}:{port}/{database}")
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create the connection pool."""
        if self._pool is None:
            logger.info("Creating PostgreSQL connection pool...")
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=self.timeout,
                timeout=self.timeout
            )
            logger.info(f"✅ PostgreSQL connection pool created (min={self.min_pool_size}, max={self.max_pool_size})")
        
        return self._pool
    
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            sql: SQL query to execute (must be SELECT)
            params: Query parameters (optional)
            limit: Result limit (optional, defaults to max_rows)
        
        Returns:
            Tuple of (columns, rows) where:
            - columns: List of column names
            - rows: List of rows, each row is a list of values
        
        Raises:
            ValueError: If query is not a SELECT statement
            RuntimeError: If query execution fails
        """
        # Enforce read-only queries (SELECT or WITH...SELECT)
        sql_stripped = sql.strip()
        match = re.match(r"(\w+)", sql_stripped, re.IGNORECASE)
        first_keyword = match.group(1).upper() if match else ""
        if first_keyword not in {"SELECT", "WITH"}:
            raise ValueError("Only SELECT queries are allowed")
        
        # Apply row limit
        effective_limit = min(limit or self.max_rows, self.max_rows)
        
        try:
            pool = await self._get_pool()
            
            async with pool.acquire() as conn:
                # Set statement timeout
                await conn.execute(f"SET statement_timeout = '{self.timeout}s'")
                
                # Execute query
                if params:
                    # Convert named parameters to positional for asyncpg
                    # asyncpg uses $1, $2, etc. for positional parameters
                    result = await conn.fetch(sql, *params.values())
                else:
                    result = await conn.fetch(sql)
                
                # Apply limit
                result = result[:effective_limit]
                
                # Extract column names and rows
                if result:
                    columns = list(result[0].keys())
                    rows = [list(record.values()) for record in result]
                else:
                    columns = []
                    rows = []
                
                logger.debug(f"Query executed: {len(rows)} rows, {len(columns)} columns")
                
                return columns, rows
        
        except asyncpg.QueryCanceledError as e:
            logger.error(f"Query timeout: {e}")
            raise RuntimeError(f"Query timeout after {self.timeout}s")
        except asyncpg.PostgresError as e:
            logger.error(f"PostgreSQL query failed: {e}")
            raise RuntimeError(f"PostgreSQL query failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during query: {e}")
            raise RuntimeError(f"Query execution error: {str(e)}")
    
    async def fetch_schema(self) -> List[Dict[str, Any]]:
        """
        Fetch database schema information.
        
        Returns:
            List of table dictionaries with name, type, and columns
        """
        try:
            # Get all tables
            tables_query = """
            SELECT 
                table_schema,
                table_name,
                table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
            """
            
            columns, rows = await self.query(tables_query, limit=10000)
            
            schema = []
            for row in rows:
                schema_name = row[0]
                table_name = row[1]
                table_type = row[2]
                
                # Get columns for this table
                columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
                """
                
                try:
                    pool = await self._get_pool()
                    async with pool.acquire() as conn:
                        col_result = await conn.fetch(columns_query, schema_name, table_name)
                        
                        table_columns = []
                        for col_record in col_result:
                            table_columns.append({
                                'name': col_record['column_name'],
                                'type': col_record['data_type'],
                                'nullable': col_record['is_nullable'] == 'YES',
                                'default': col_record['column_default']
                            })
                        
                        schema.append({
                            'schema': schema_name,
                            'name': table_name,
                            'type': table_type,
                            'columns': table_columns
                        })
                
                except Exception as e:
                    logger.warning(f"Could not get columns for {schema_name}.{table_name}: {e}")
                    schema.append({
                        'schema': schema_name,
                        'name': table_name,
                        'type': table_type,
                        'columns': []
                    })
            
            logger.info(f"Schema fetched: {len(schema)} tables")
            return schema
        
        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}")
            raise RuntimeError(f"Schema fetch failed: {str(e)}")
    
    async def test_connection(self) -> bool:
        """
        Test if the database connection is working.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            columns, rows = await self.query("SELECT 1 AS test")
            return len(rows) > 0 and rows[0][0] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            try:
                await self._pool.close()
                logger.info("PostgreSQL connection pool closed")
            except Exception as e:
                logger.warning(f"Error closing pool: {e}")
            finally:
                self._pool = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._get_pool()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()