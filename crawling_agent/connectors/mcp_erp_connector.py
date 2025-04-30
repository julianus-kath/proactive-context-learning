"""
ERP Connector for executing SQL queries against the ERP MCP server.
"""
import time
import requests
import json
from typing import Dict, List, Any, Optional, Union

from crawling_agent.connectors.base_connector import BaseMCPConnector
from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest


class ERPConnector(BaseMCPConnector):
    """
    Connector for crawling data from an ERP system using SQL queries via MCP.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8001,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the ERP connector.
        
        Args:
            host: Host where the ERP MCP server is running
            port: Port where the ERP MCP server is running
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="erp",
            host=host,
            port=port,
            config_path=config_path,
            mock_mode=mock_mode
        )
    
    def get_tables(self) -> List[str]:
        """
        Get list of tables in the ERP database.
        
        Returns:
            List of table names
        """
        try:
            response = requests.get(f"{self.base_url}/tables")
            response.raise_for_status()
            return response.json().get("tables", [])
        except Exception as e:
            self.logger.error(f"Error getting tables: {str(e)}")
            if self.mock_mode:
                return ["products", "employees", "orders", "order_items"]
            else:
                raise
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary containing the table schema
        """
        try:
            response = requests.get(f"{self.base_url}/schema/{table_name}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting schema for table {table_name}: {str(e)}")
            if self.mock_mode:
                return {"table": table_name, "schema": []}
            else:
                raise
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a SQL query against the ERP database via MCP.
        
        Args:
            query: The DataSourceQuery object containing the SQL query and parameters
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.SQL:
            raise ValueError(f"Invalid query type for ERP connector: {query.query_type}")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing SQL query via MCP: {query.query}")
            self.logger.debug(f"Query parameters: {query.parameters}")
            
            # Prepare the request
            request_data = {
                "query": query.query,
                "query_type": "SQL",
                "parameters": query.parameters,
                "request_id": str(query.query_id) if hasattr(query, 'query_id') else None
            }
            
            # Execute the query
            response = requests.post(
                f"{self.base_url}/query",
                json=request_data
            )
            response.raise_for_status()
            result = response.json()
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Add our own execution time to the metadata
            if "metadata" in result:
                result["metadata"]["total_execution_time_ms"] = execution_time
            
            self.logger.info(f"Query executed successfully via MCP. Retrieved {len(result.get('data', []))} rows in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SQL query via MCP: {str(e)}")
            raise