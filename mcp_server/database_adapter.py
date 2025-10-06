"""
Database adapter for MCP server with direct database connectors.
Supports both PostgreSQL (dev) and SQL Server (production) via DB_DIALECT.

Architecture:
- On Mac: MCP server connects to local PostgreSQL for development
- On Windows: MCP server connects to SQL Server via VPN for production
- Mac services (Web UI, LangGraph) call MCP server via HTTP
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv

# Load environment variables from the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

from config import config
from db_postgres import PostgresConnector
from db_mssql import MSSQLConnector
from catalog import SchemaCatalog

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """
    Database adapter with support for multiple database backends.
    
    Supported Dialects:
    - postgres: Direct PostgreSQL connection (dev mode)
    - mssql: Direct SQL Server connection (production mode)
    
    Features:
    - Direct PostgreSQL connector (asyncpg)
    - Direct SQL Server connector (pyodbc)
    - Schema caching with Phase 3 catalog
    - Read-only enforcement
    - Connection pooling
    - Statement timeouts
    """
    
    def __init__(self):
        """Initialize the database adapter based on DB_DIALECT."""
        # Get database dialect from config
        self.dialect = config.db_dialect
        
        if self.dialect == "postgres":
            self.connector = PostgresConnector(
                host=config.postgres_host,
                port=config.postgres_port,
                database=config.postgres_database,
                user=config.postgres_user,
                password=config.postgres_password,
                timeout=config.query_timeout,
                max_rows=config.max_query_results,
                min_pool_size=config.min_pool_size,
                max_pool_size=config.max_pool_size
            )
            logger.info(f"✅ DatabaseAdapter initialized with PostgreSQL connector: {config.postgres_host}:{config.postgres_port}/{config.postgres_database}")
        
        elif self.dialect == "mssql":
            self.connector = MSSQLConnector(
                server=config.mssql_server,
                database=config.mssql_database,
                username=config.mssql_user,
                password=config.mssql_password,
                driver=config.mssql_driver,
                timeout=config.query_timeout,
                max_rows=config.max_query_results
            )
            logger.info(f"✅ DatabaseAdapter initialized with MSSQL connector: {config.mssql_server}/{config.mssql_database}")
        
        else:
            raise ValueError(f"Unsupported database dialect: {self.dialect}. Must be 'postgres' or 'mssql'")
        
        # Phase 3: Schema catalog (replaces simple cache)
        self.catalog: Optional[SchemaCatalog] = None
        
        # Legacy schema cache (kept for backward compatibility)
        self._schema_cache = {
            "data": None,
            "timestamp": None,
            "hits": 0,
            "ttl": 300  # Cache for 5 minutes
        }
        
        logger.info(f"DatabaseAdapter initialized in {self.dialect} mode")
    
    async def initialize(self):
        """Initialize the database adapter and test connection."""
        try:
            # Test the connection
            is_healthy = await self.connector.test_connection()
            if not is_healthy:
                raise RuntimeError(f"{self.dialect} connection test failed")
            logger.info(f"✅ {self.dialect.upper()} connection verified")
            
            # Phase 3: Initialize catalog with warmup
            logger.info("🔄 Initializing Phase 3 catalog...")
            cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
            self.catalog = SchemaCatalog(
                connector=self.connector,
                dialect=self.dialect,
                cache_dir=cache_dir,
                ttl=3600,  # 1 hour TTL
                auto_warmup=False
            )
            await self.catalog.warmup()
            logger.info(f"✅ Phase 3 catalog initialized: {self.catalog.get_metrics()['table_count']} tables")
            
        except Exception as e:
            logger.error(f"❌ {self.dialect.upper()} connection failed: {e}")
            raise
    
    async def close(self):
        """Close the database adapter and cleanup connections."""
        try:
            if self.dialect == "postgres" and self.connector:
                await self.connector.close()
            elif self.dialect == "mssql" and self.connector:
                self.connector.close()
            logger.info(f"{self.dialect.upper()} connection closed")
        except Exception as e:
            logger.warning(f"Error closing {self.dialect} connection: {e}")
    
    async def fetch_schema(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch database schema information with caching.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
        
        Returns:
            List of table dictionaries with schema, name, type, and columns
        """
        # Check cache first
        if not force_refresh and self._schema_cache["data"] is not None:
            cache_age = time.time() - self._schema_cache["timestamp"]
            if cache_age < self._schema_cache["ttl"]:
                self._schema_cache["hits"] += 1
                logger.info(f"Schema cache hit (age: {cache_age:.1f}s, hits: {self._schema_cache['hits']})")
                return self._schema_cache["data"]
        
        logger.info("Fetching fresh schema data...")
        
        try:
            # Use the connector's fetch_schema method
            schema = await self.connector.fetch_schema()
            
            # Cache the schema
            self._schema_cache["data"] = schema
            self._schema_cache["timestamp"] = time.time()
            logger.info(f"✅ Schema cached: {len(schema)} tables")
            
            return schema
            
        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}")
            # Return cached data if available, even if stale
            if self._schema_cache["data"] is not None:
                logger.warning("⚠️ Returning stale cached schema due to error")
                return self._schema_cache["data"]
            return []
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query to execute (must be SELECT)
            params: Query parameters (optional)
            limit: Result limit (default: 100)
        
        Returns:
            List of dictionaries, one per row
        """
        try:
            # Convert params list to dict if needed
            params_dict = None
            if params:
                # For now, we'll pass params as-is
                # The connectors will handle parameter conversion
                params_dict = params if isinstance(params, dict) else {}
            
            # Execute query via connector
            columns, rows = await self.connector.query(query, params=params_dict, limit=limit)
            
            # Convert to list of dictionaries
            result = []
            for row in rows:
                row_dict = {}
                for i, column_name in enumerate(columns):
                    value = row[i] if i < len(row) else None
                    
                    # Handle special types that aren't JSON serializable
                    if hasattr(value, 'isoformat'):  # datetime objects
                        row_dict[column_name] = value.isoformat()
                    elif isinstance(value, (bytes, bytearray)):
                        row_dict[column_name] = value.decode('utf-8', errors='ignore')
                    else:
                        row_dict[column_name] = value
                
                result.append(row_dict)
            
            logger.debug(f"Query returned {len(result)} rows")
            return result
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def get_table_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
        
        Returns:
            Number of rows in the table
        """
        try:
            # Use dialect-appropriate syntax
            if self.dialect == "mssql":
                query = f"SELECT COUNT(*) as count FROM [{table_name}]"
            else:  # postgres
                query = f"SELECT COUNT(*) as count FROM {table_name}"
            
            columns, rows = await self.connector.query(query, limit=1)
            
            if rows and len(rows) > 0:
                return rows[0][0]  # First column of first row
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get table count for {table_name}: {e}")
            return 0
    
    async def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample data from a table.
        
        Args:
            table_name: Name of the table
            limit: Number of rows to return (default: 5)
        
        Returns:
            List of row dictionaries
        """
        try:
            # Use dialect-appropriate syntax
            if self.dialect == "mssql":
                query = f"SELECT TOP {limit} * FROM [{table_name}]"
            else:  # postgres
                query = f"SELECT * FROM {table_name} LIMIT {limit}"
            
            return await self.fetch(query, limit=limit)
            
        except Exception as e:
            logger.error(f"Failed to get sample data for {table_name}: {e}")
            return []
    
    @property
    def pool(self):
        """Compatibility property for health checks."""
        # Return the connector (truthy if initialized)
        return self.connector
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get schema cache statistics.
        
        Returns:
            Dictionary with cache stats: age_s, hits, ttl
        """
        # Phase 3: Return catalog metrics if available
        if self.catalog:
            return self.catalog.get_metrics()
        
        # Legacy cache stats
        if self._schema_cache["timestamp"] is None:
            return {"age_s": None, "hits": 0, "ttl": self._schema_cache["ttl"]}
        
        age_s = time.time() - self._schema_cache["timestamp"]
        return {
            "age_s": round(age_s, 1),
            "hits": self._schema_cache["hits"],
            "ttl": self._schema_cache["ttl"]
        }
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dictionary with pool stats: size, min_size, max_size, free_connections
        """
        if not self.connector:
            return {"error": "Connector not initialized"}
        
        # PostgreSQL pool stats
        if self.dialect == "postgres" and hasattr(self.connector, '_pool') and self.connector._pool:
            pool = self.connector._pool
            return {
                "dialect": "postgres",
                "size": pool.get_size(),
                "min_size": pool.get_min_size(),
                "max_size": pool.get_max_size(),
                "free_connections": pool.get_idle_size()
            }
        
        # MSSQL doesn't have a pool in the same way
        elif self.dialect == "mssql":
            return {
                "dialect": "mssql",
                "note": "MSSQL uses pyodbc connection pooling (managed by driver)"
            }
        
        return {"error": "Pool not initialized"}
    
    def get_last_error(self) -> Optional[Dict[str, Any]]:
        """
        Get last database error (if any).
        
        Returns:
            Dictionary with error info or None
        """
        # This would require tracking errors in the connector
        # For now, return None (can be enhanced later)
        return None
    
    # === Phase 3: Catalog API ===
    
    async def get_catalog_table_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all tables from catalog (no DB hit).
        
        Returns:
            List of table info dicts
        """
        if not self.catalog:
            logger.warning("Catalog not initialized, falling back to fetch_schema")
            return await self.fetch_schema()
        
        # Refresh catalog if needed
        await self.catalog.refresh_if_needed()
        
        return self.catalog.get_table_list()
    
    async def get_catalog_table(self, schema: str, table: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed table info from catalog (no DB hit).
        
        Args:
            schema: Schema name
            table: Table name
        
        Returns:
            Table info dict or None
        """
        if not self.catalog:
            logger.warning("Catalog not initialized")
            return None
        
        # Refresh catalog if needed
        await self.catalog.refresh_if_needed()
        
        return self.catalog.get_table(schema, table)
    
    async def get_catalog_neighbors(self, schema: str, table: str) -> List[str]:
        """
        Get related tables via foreign keys (no DB hit).
        
        Args:
            schema: Schema name
            table: Table name
        
        Returns:
            List of related table names
        """
        if not self.catalog:
            logger.warning("Catalog not initialized")
            return []
        
        # Refresh catalog if needed
        await self.catalog.refresh_if_needed()
        
        return self.catalog.get_neighbors(schema, table)
    
    async def get_catalog_top_columns(self, schema: str, table: str, limit: int = 5) -> List[str]:
        """
        Get top N columns for a table (no DB hit).
        
        Args:
            schema: Schema name
            table: Table name
            limit: Number of columns to return
        
        Returns:
            List of column names
        """
        if not self.catalog:
            logger.warning("Catalog not initialized")
            return []
        
        # Refresh catalog if needed
        await self.catalog.refresh_if_needed()
        
        return self.catalog.get_top_columns(schema, table, limit)
    
    async def search_catalog_tables(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for tables by name (no DB hit).
        
        Args:
            query: Search query
        
        Returns:
            List of matching table info dicts
        """
        if not self.catalog:
            logger.warning("Catalog not initialized")
            return []
        
        # Refresh catalog if needed
        await self.catalog.refresh_if_needed()
        
        return self.catalog.search_tables(query)
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """
        Get catalog summary with statistics (no DB hit).
        
        Returns:
            Summary dict with table count, metrics, etc.
        """
        if not self.catalog:
            return {"error": "Catalog not initialized"}
        
        return self.catalog.get_summary()