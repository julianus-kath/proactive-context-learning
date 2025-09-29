"""
DatabaseClient - Centralized database interface for agent repo
Supports proxy mode (default) and optional direct mode for development
"""

import os
import requests
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseClient:
    """
    Centralized database client that abstracts database calls behind a unified interface.
    
    Modes:
    - proxy: Routes calls through the SQL proxy (default, secure for VPN environments)
    - direct: Direct PostgreSQL connection (for development)
    """
    
    def __init__(self):
        self.mode = os.getenv("DB_MODE", "proxy")  # proxy | direct
        
        if self.mode == "proxy":
            # Proxy mode configuration
            self.base_url = os.getenv("PROXY_BASE_URL")  # e.g. https://10.255.152.48:5000
            self.api_key = os.getenv("PROXY_API_KEY")
            self.verify = os.getenv("PROXY_TLS_VERIFY", "true").lower() == "true"
            self.ca_bundle = os.getenv("PROXY_CA_BUNDLE")  # optional path to CA bundle
            self.default_conn = os.getenv("PROXY_DEFAULT_CONN")  # optional default connection
            
            # Request configuration
            self.timeout = int(os.getenv("PROXY_TIMEOUT", "30"))
            self.max_retries = int(os.getenv("PROXY_MAX_RETRIES", "3"))
            
            # Validate proxy configuration
            if not self.base_url:
                raise RuntimeError("PROXY_BASE_URL environment variable is required for proxy mode")
            if not self.api_key:
                raise RuntimeError("PROXY_API_KEY environment variable is required for proxy mode")
                
            logger.info(f"DatabaseClient initialized in proxy mode: {self.base_url}")
            if self.default_conn:
                logger.info(f"Default connection: {self.default_conn}")
            
        else:
            # Direct mode configuration (for development)
            # Reuse existing environment variables from mcp_server
            self.db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'synthetic_erp_data'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres')
            }
            
            logger.info(f"DatabaseClient initialized in direct mode: {self.db_config['host']}:{self.db_config['port']}")
    
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None, conn: Optional[str] = None, 
              limit: Optional[int] = None, timeout_s: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute a SQL query and return results.
        
        Args:
            sql: SQL query to execute
            params: Query parameters (optional)
            conn: Connection name for proxy mode (optional, uses default if not specified)
            limit: Result limit (optional)
            timeout_s: Query timeout in seconds (optional)
            
        Returns:
            Tuple of (columns, rows) where:
            - columns: List of column names
            - rows: List of rows, each row is a list of values
            
        Raises:
            RuntimeError: If query fails or proxy returns error
        """
        if self.mode == "proxy":
            return self._query_proxy(sql, params, conn, limit, timeout_s)
        else:
            return self._query_direct(sql, params, limit, timeout_s)
    
    def _query_proxy(self, sql: str, params: Optional[Dict[str, Any]] = None, 
                     conn: Optional[str] = None, limit: Optional[int] = None, 
                     timeout_s: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
        """Execute query via proxy."""
        try:
            # Use default connection if none specified
            if conn is None:
                conn = self.default_conn
            
            # Use configured timeout if none specified
            if timeout_s is None:
                timeout_s = self.timeout
            
            # Prepare headers
            headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
            
            # Prepare SSL verification
            verify = self.ca_bundle if self.ca_bundle else self.verify
            
            # Prepare payload
            payload = {
                "sql": sql,
                "params": params or {}
            }
            
            # Add optional parameters
            if conn:
                payload["conn"] = conn
            else:
                # Use default connection from environment if available
                default_conn = os.getenv("PROXY_DEFAULT_CONN")
                if default_conn:
                    payload["conn"] = default_conn
            
            if limit:
                payload["limit"] = limit
            if timeout_s:
                payload["timeout_s"] = timeout_s
            
            # Make request with appropriate timeout
            request_timeout = (10, (timeout_s or 30) + 5)  # (connect_timeout, read_timeout)
            
            response = requests.post(
                f"{self.base_url}/query",
                json=payload,
                headers=headers,
                verify=verify,
                timeout=request_timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Check for proxy-level errors
            if not data.get("ok"):
                error_msg = data.get("error", "Unknown proxy error")
                raise RuntimeError(f"Proxy query failed: {error_msg}")
            
            # Extract columns and rows
            columns = data.get("columns", [])
            rows = data.get("rows", [])
            
            logger.debug(f"Proxy query successful: {len(rows)} rows, {len(columns)} columns")
            return columns, rows
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Proxy request failed: {e}")
            raise RuntimeError(f"Proxy connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Proxy query error: {e}")
            raise RuntimeError(f"Proxy query error: {str(e)}")
    
    def _query_direct(self, sql: str, params: Optional[Dict[str, Any]] = None, 
                      limit: Optional[int] = None, timeout_s: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
        """Execute query via direct PostgreSQL connection."""
        # This is a placeholder for direct mode implementation
        # In a real implementation, you would use psycopg2 or asyncpg here
        raise NotImplementedError(
            "Direct mode not implemented yet. "
            "Use proxy mode (DB_MODE=proxy) or implement direct PostgreSQL connection here."
        )
    
    def health_check(self) -> bool:
        """
        Check if the database connection is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if self.mode == "proxy":
                # Use the /diag endpoint for health check
                headers = {"X-API-Key": self.api_key}
                verify = self.ca_bundle if self.ca_bundle else self.verify
                
                response = requests.get(
                    f"{self.base_url}/diag",
                    headers=headers,
                    verify=verify,
                    timeout=10
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Check if we have connections available
                connections = data.get("connections", [])
                return len(connections) > 0
                
            else:
                # Direct mode health check would go here
                raise NotImplementedError("Direct mode health check not implemented yet")
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_available_connections(self) -> List[Dict[str, str]]:
        """
        Get list of available database connections (proxy mode only).
        
        Returns:
            List of connection info dictionaries with 'name' and 'type' keys
        """
        if self.mode != "proxy":
            logger.warning("get_available_connections() only available in proxy mode")
            return []
        
        try:
            headers = {"X-API-Key": self.api_key}
            verify = self.ca_bundle if self.ca_bundle else self.verify
            
            response = requests.get(
                f"{self.base_url}/diag",
                headers=headers,
                verify=verify,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get("connections", [])
            
        except Exception as e:
            logger.error(f"Failed to get available connections: {e}")
            return []


# Convenience function for getting a configured client
def get_database_client() -> DatabaseClient:
    """Get a configured DatabaseClient instance."""
    return DatabaseClient()