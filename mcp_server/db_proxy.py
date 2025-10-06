"""
Proxy connector for MCP server.
Routes database queries through the Windows proxy for VPN-tunneled access.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ProxyConnector:
    """
    Proxy connector that routes database queries through the Windows proxy.
    
    This connector is used when DB_MODE=proxy to access databases over VPN
    without requiring direct database credentials on the Mac.
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_conn: Optional[str] = None,
        timeout: int = 30,
        max_rows: int = 1000
    ):
        """
        Initialize the proxy connector.
        
        Args:
            base_url: Base URL of the proxy (e.g., http://192.168.1.35:5000)
            api_key: API key for proxy authentication
            default_conn: Default connection name (optional)
            timeout: Query timeout in seconds
            max_rows: Maximum rows to return
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.default_conn = default_conn
        self.timeout = timeout
        self.max_rows = max_rows
        
        logger.info(f"ProxyConnector initialized: {self.base_url}")
        if self.default_conn:
            logger.info(f"Default connection: {self.default_conn}")
    
    async def test_connection(self) -> bool:
        """Test the proxy connection."""
        try:
            headers = {"X-API-Key": self.api_key}
            response = requests.get(
                f"{self.base_url}/health",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info("✅ Proxy connection test successful")
                    return True
            
            logger.error(f"❌ Proxy health check failed: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Proxy connection test failed: {e}")
            return False
    
    async def fetch_schema(self) -> List[Dict[str, Any]]:
        """
        Fetch database schema from the proxy using SQL queries.
        
        Since the proxy doesn't have a dedicated /schema endpoint,
        we query information_schema tables to get the schema.
        
        Returns:
            List of table schemas
        """
        try:
            # Query to get all tables and their columns
            schema_query = """
            SELECT 
                t.table_name,
                t.table_type,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c 
                ON t.table_name = c.table_name 
                AND t.table_schema = c.table_schema
            WHERE t.table_schema NOT IN ('information_schema', 'sys', 'pg_catalog')
            ORDER BY t.table_name, c.ordinal_position
            """
            
            # Execute query via proxy
            results = await self.execute_query(schema_query, limit=10000)
            
            # Group by table
            tables_dict = {}
            for row in results:
                table_name = row.get('table_name')
                if not table_name:
                    continue
                
                if table_name not in tables_dict:
                    tables_dict[table_name] = {
                        "name": table_name,
                        "type": row.get('table_type', 'BASE TABLE'),
                        "columns": []
                    }
                
                # Add column if present
                column_name = row.get('column_name')
                if column_name:
                    tables_dict[table_name]["columns"].append({
                        "name": column_name,
                        "type": row.get('data_type'),
                        "nullable": row.get('is_nullable') == 'YES',
                        "default": row.get('column_default')
                    })
            
            tables = list(tables_dict.values())
            logger.info(f"Fetched schema: {len(tables)} tables")
            return tables
            
        except Exception as e:
            logger.error(f"Failed to fetch schema from proxy: {e}")
            # Return empty list instead of raising to allow graceful degradation
            logger.warning("Returning empty schema list")
            return []
    
    async def execute_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query via the proxy.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            limit: Result limit (optional, defaults to max_rows)
            
        Returns:
            List of result rows as dictionaries
        """
        try:
            # Apply limit
            if limit is None:
                limit = self.max_rows
            
            # Prepare headers
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Prepare payload
            payload = {
                "sql": query,
                "params": params or [],
                "limit": limit,
                "timeout_s": self.timeout
            }
            
            if self.default_conn:
                payload["conn"] = self.default_conn
            
            # Make request
            response = requests.post(
                f"{self.base_url}/query",
                json=payload,
                headers=headers,
                timeout=self.timeout + 5  # Add buffer for network latency
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Check for proxy-level errors
            if not data.get("ok"):
                error_msg = data.get("error", "Unknown proxy error")
                raise RuntimeError(f"Proxy query failed: {error_msg}")
            
            # Convert columns + rows format to list of dicts
            columns = data.get("columns", [])
            rows = data.get("rows", [])
            
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i] if i < len(row) else None
                results.append(row_dict)
            
            logger.debug(f"Query executed successfully: {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed via proxy: {e}")
            raise
    
    async def get_table_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        results = await self.execute_query(query, limit=1)
        return results[0]['count'] if results else 0
    
    async def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from a table."""
        query = f"SELECT * FROM {table_name}"
        return await self.execute_query(query, limit=limit)
    
    async def close(self):
        """Close the proxy connector (no-op for HTTP client)."""
        logger.info("ProxyConnector closed")