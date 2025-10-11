"""
Direct SQL Server connector for MCP server.
Uses pyodbc with connection pooling, timeouts, and read-only enforcement.
"""

import pyodbc
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MSSQLConnector:
    """
    Direct SQL Server connector with connection pooling and safety features.
    
    Features:
    - Connection pooling via pyodbc
    - Statement timeouts (30s default)
    - Read-only enforcement
    - Row limits (max 1000)
    - Automatic reconnection on failure
    """
    
    def __init__(
        self,
        server: str,
        database: str,
        username: str,
        password: str,
        driver: str = "ODBC Driver 17 for SQL Server",
        timeout: int = 30,
        max_rows: int = 1000
    ):
        """
        Initialize MSSQL connector.
        
        Args:
            server: SQL Server hostname or IP
            database: Database name
            username: Database username
            password: Database password
            driver: ODBC driver name (default: ODBC Driver 17 for SQL Server)
            timeout: Query timeout in seconds (default: 30)
            max_rows: Maximum rows to return (default: 1000)
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.timeout = timeout
        self.max_rows = max_rows
        
        # Build connection string
        # TrustServerCertificate=yes is required for internal SQL Servers with self-signed certs
        # Force TCP/IP protocol to avoid Named Pipes issues
        self.connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER=tcp:{server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"Connection Timeout={timeout};"
        )
        
        # Connection pool (pyodbc doesn't have built-in pooling, so we manage a single connection)
        self._connection: Optional[pyodbc.Connection] = None
        
        logger.info(f"MSSQLConnector initialized for {server}/{database}")
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get or create a database connection."""
        if self._connection is None or not self._is_connection_alive():
            logger.info("Creating new MSSQL connection...")
            self._connection = pyodbc.connect(
                self.connection_string,
                timeout=self.timeout,
                readonly=True  # Read-only mode
            )
            # Set additional connection properties
            self._connection.timeout = self.timeout
            logger.info("✅ MSSQL connection established")
        
        return self._connection
    
    def _is_connection_alive(self) -> bool:
        """Check if the connection is still alive."""
        if self._connection is None:
            return False
        
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
    
    @contextmanager
    def _get_cursor(self):
        """Context manager for getting a cursor with automatic cleanup."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
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
        # Enforce SELECT-only queries
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        # Apply row limit
        effective_limit = min(limit or self.max_rows, self.max_rows)
        
        try:
            with self._get_cursor() as cursor:
                # Execute query with parameters
                # (timeout is already set on the connection level)
                if params:
                    # pyodbc requires positional parameters (list/tuple), not dict
                    if isinstance(params, dict):
                        # Convert dict to list (order must match ? placeholders in SQL)
                        param_list = list(params.values())
                        cursor.execute(sql, param_list)
                    else:
                        cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                # Fetch results with limit
                rows = cursor.fetchmany(effective_limit)
                
                # Extract column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Convert rows to list of lists
                result_rows = [list(row) for row in rows]
                
                logger.debug(f"Query executed: {len(result_rows)} rows, {len(columns)} columns")
                
                return columns, result_rows
        
        except pyodbc.Error as e:
            logger.error(f"MSSQL query failed: {e}")
            # Reset connection on error
            self._connection = None
            raise RuntimeError(f"MSSQL query failed: {str(e)}")
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
                TABLE_SCHEMA,
                TABLE_NAME,
                TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
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
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """
                
                try:
                    col_columns, col_rows = await self.query(
                        columns_query,
                        params=[schema_name, table_name],  # Use list for positional params
                        limit=1000
                    )
                    
                    table_columns = []
                    for col_row in col_rows:
                        table_columns.append({
                            'name': col_row[0],
                            'type': col_row[1],
                            'nullable': col_row[2] == 'YES',
                            'default': col_row[3]
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
    
    def close(self):
        """Close the database connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("MSSQL connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()