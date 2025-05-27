"""
ERP Connector for executing SQL queries against the ERP MCP server.
"""
import time
import uuid
import requests
import json
from typing import Dict, List, Any, Optional, Union
import logging

from crawling_agent.connectors.base_connector import BaseMCPConnector
from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest


class ERPConnector(BaseMCPConnector):
    """
    Connector for ERP data source.
    Provides SQL query capabilities.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8001,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the ERP MCP connector.
        
        Args:
            host: Host of the ERP MCP server
            port: Port of the ERP MCP server
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="ERP",
            host=host,
            port=port,
            config_path=config_path,
            mock_mode=mock_mode
        )
        
        self.logger = logging.getLogger(__name__)
    
    async def get_tables(self) -> List[str]:
        """
        Get list of available tables.
        
        Returns:
            List of table names
        """
        try:
            if self.mock_mode:
                return ["products", "employees", "orders", "order_items", "customers"]
            
            response = await self._make_request(
                "GET",
                "/tables"
            )
            return response["tables"]
        except Exception as e:
            self.logger.error(f"Error getting tables: {str(e)}")
            if self.mock_mode:
                return ["products", "employees", "orders", "order_items", "customers"]
            raise
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table schema as a dictionary
        """
        try:
            if self.mock_mode:
                return {"table": table_name, "schema": []}
            
            response = await self._make_request(
                "GET",
                f"/tables/{table_name}/schema"
            )
            return response["schema"]
        except Exception as e:
            self.logger.error(f"Error getting schema for table {table_name}: {str(e)}")
            if self.mock_mode:
                return {"table": table_name, "schema": []}
            raise
    
    async def execute_query(self, query: Union[str, DataSourceQuery]) -> Dict[str, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string or DataSourceQuery object
            
        Returns:
            Query results as a dictionary
        """
        try:
            # Handle both string queries and DataSourceQuery objects
            if isinstance(query, DataSourceQuery):
                query_str = query.query
                query_type = query.query_type.value if hasattr(query.query_type, 'value') else query.query_type
                parameters = query.parameters
                self.logger.info(f"Executing {query_type} query with parameters")
                self.logger.info(f"Query: {query_str}")
                self.logger.info(f"Parameters: {json.dumps(parameters, indent=2)}")
            else:
                query_str = query
                query_type = "SQL"
                parameters = {}
                self.logger.info(f"Executing raw SQL query: {query_str}")
            
            if self.mock_mode:
                self.logger.info("Running in mock mode, returning mock data")
                # Return mock data based on the query
                if "COUNT" in query_str.upper() and "customers" in query_str.lower():
                    mock_result = {
                        "data": [{"count": 120}],
                        "metadata": {
                            "source_type": "erp",
                            "query_type": "SQL",
                            "mock": True
                        }
                    }
                    self.logger.info(f"Mock result: {json.dumps(mock_result, indent=2)}")
                    return mock_result
                return {"data": [], "metadata": {"mock": True}}
            
            self.logger.info("Sending query to ERP server")
            response = await self._make_request(
                "POST",
                "/query",
                json={
                    "query": query_str,
                    "query_type": query_type,
                    "parameters": parameters
                }
            )
            
            # Log the response details
            row_count = len(response.get("data", []))
            self.logger.info(f"Query executed successfully. Retrieved {row_count} rows.")
            
            if row_count > 0:
                # Log a sample of the data (first row)
                self.logger.info("Sample data (first row):")
                self.logger.info(json.dumps(response["data"][0], indent=2))
            
            # Log any metadata
            if "metadata" in response:
                self.logger.info("Query metadata:")
                self.logger.info(json.dumps(response["metadata"], indent=2))
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing query: {str(e)}")
            if self.mock_mode:
                error_response = {"data": [], "metadata": {"mock": True, "error": str(e)}}
                self.logger.info(f"Returning mock error response: {json.dumps(error_response, indent=2)}")
                return error_response
            raise
    
    def _get_mock_expensive_products(self) -> List[Dict[str, Any]]:
        """
        Get mock expensive products.
        
        Returns:
            List of mock expensive products
        """
        return [
            {
                "id": 1,
                "name": "Premium Laptop",
                "description": "High-end laptop with the latest specifications",
                "price": 1899.99,
                "category": "Electronics",
                "stock": 15
            },
            {
                "id": 2,
                "name": "Designer Watch",
                "description": "Luxury watch with premium materials",
                "price": 2499.99,
                "category": "Accessories",
                "stock": 8
            }
        ]
    
    def _get_mock_sales_employees(self) -> List[Dict[str, Any]]:
        """
        Get mock sales employees.
        
        Returns:
            List of mock sales employees
        """
        return [
            {
                "id": 1,
                "name": "John Smith",
                "email": "john.smith@example.com",
                "department": "Sales",
                "position": "Sales Manager",
                "hire_date": "2018-05-15T00:00:00Z"
            },
            {
                "id": 2,
                "name": "Emily Johnson",
                "email": "emily.johnson@example.com",
                "department": "Sales",
                "position": "Senior Sales Representative",
                "hire_date": "2019-02-10T00:00:00Z"
            }
        ]
    
    def _get_mock_completed_orders(self) -> List[Dict[str, Any]]:
        """
        Get mock completed orders.
        
        Returns:
            List of mock completed orders
        """
        return [
            {
                "id": 1,
                "customer_id": 15,
                "order_date": "2023-04-10T14:30:00Z",
                "status": "Completed",
                "total": 2499.99
            },
            {
                "id": 2,
                "customer_id": 28,
                "order_date": "2023-04-12T09:15:00Z",
                "status": "Completed",
                "total": 1899.99
            }
        ]