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
        config_path: Optional[str] = None
    ):
        """
        Initialize the ERP MCP connector.
        
        Args:
            host: Host of the ERP MCP server
            port: Port of the ERP MCP server
            config_path: Path to the configuration file
        """
        super().__init__(
            server_type="ERP",
            version="1.0.0",
            host=host,
            port=port,
            config_path=config_path
        )
        
        self.logger = logging.getLogger(__name__)
    
    async def get_tables(self) -> List[str]:
        """
        Get list of available tables.
        
        Returns:
            List of table names
        """
        response = await self._make_request(
            "GET",
            "/tables"
        )
        return response["tables"]
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table schema as a dictionary
        """
        response = await self._make_request(
            "GET",
            f"/tables/{table_name}/schema"
        )
        return response["schema"]
    
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            
        Returns:
            Query results as a dictionary
        """
        response = await self._make_request(
            "POST",
            "/query",
            json={
                "query": query,
                "query_type": "SQL"
            }
        )
        return response

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
        
        # If in mock mode, return mock data
        if self.mock_mode:
            self.logger.info(f"Using mock mode for ERP query: {query.query}")
            result = self._mock_execute_query(query)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Add execution time to the metadata
            if "metadata" in result:
                result["metadata"]["total_execution_time_ms"] = execution_time
            
            self.logger.info(f"Mock query executed successfully. Retrieved {len(result.get('data', []))} rows in {execution_time:.2f}ms")
            
            return result
        
        try:
            query_text = query.query if hasattr(query, 'query') else query
            query_params = query.parameters if hasattr(query, 'parameters') else {}
            self.logger.info(f"Executing SQL query via MCP: {query_text}")
            self.logger.debug(f"Query parameters: {query_params}")
            
            # Prepare the request
            request_data = {
                "query": query.query if hasattr(query, 'query') else query,
                "query_type": "SQL",
                "parameters": query.parameters if hasattr(query, 'parameters') else {},
                "request_id": str(query.query_id) if hasattr(query, 'query_id') and query.query_id else str(uuid.uuid4())
            }
            
            # Log the request data for debugging
            self.logger.debug(f"Request data: {json.dumps(request_data)}")
            
            # Execute the query
            response = requests.post(
                f"{self.base_url}/query",
                json=request_data
            )
            
            # Log the response for debugging
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response content: {response.text}")
            
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
            
    def _mock_execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a mock query.
        
        Args:
            query: Query to execute
            
        Returns:
            Mock query results
        """
        # Parse the query to determine what data to return
        query_lower = query.query.lower()
        
        # Handle different types of queries
        if "count" in query_lower and "customer" in query_lower:
            # Count of customers
            return {
                "data": [{"count": 120}],
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
        elif "product" in query_lower and ("expensive" in query_lower or "price" in query_lower):
            # Expensive products
            return {
                "data": self._get_mock_expensive_products(),
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
        elif "employee" in query_lower and "sales" in query_lower:
            # Sales employees
            return {
                "data": self._get_mock_sales_employees(),
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
        elif "order" in query_lower and "complete" in query_lower:
            # Completed orders
            return {
                "data": self._get_mock_completed_orders(),
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
        elif "revenue" in query_lower or "total" in query_lower:
            # Revenue data
            return {
                "data": [{"total_revenue": 125750.50}],
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
        else:
            # Default empty response
            return {
                "data": [],
                "metadata": {
                    "source_type": "erp",
                    "query_type": "SQL",
                    "mock": True
                }
            }
    
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
            },
            {
                "id": 3,
                "name": "Professional Camera",
                "description": "High-resolution camera for professional photography",
                "price": 3299.99,
                "category": "Electronics",
                "stock": 5
            },
            {
                "id": 4,
                "name": "Smart Home System",
                "description": "Complete smart home automation system",
                "price": 1599.99,
                "category": "Home",
                "stock": 12
            },
            {
                "id": 5,
                "name": "Gaming Desktop",
                "description": "High-performance gaming computer",
                "price": 2199.99,
                "category": "Electronics",
                "stock": 10
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
            },
            {
                "id": 3,
                "name": "Michael Brown",
                "email": "michael.brown@example.com",
                "department": "Sales",
                "position": "Sales Representative",
                "hire_date": "2020-07-22T00:00:00Z"
            },
            {
                "id": 4,
                "name": "Sarah Davis",
                "email": "sarah.davis@example.com",
                "department": "Sales",
                "position": "Sales Representative",
                "hire_date": "2021-03-05T00:00:00Z"
            },
            {
                "id": 5,
                "name": "Robert Wilson",
                "email": "robert.wilson@example.com",
                "department": "Sales",
                "position": "Junior Sales Representative",
                "hire_date": "2022-01-18T00:00:00Z"
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
            },
            {
                "id": 3,
                "customer_id": 42,
                "order_date": "2023-04-15T16:45:00Z",
                "status": "Completed",
                "total": 3299.99
            },
            {
                "id": 4,
                "customer_id": 7,
                "order_date": "2023-04-18T11:20:00Z",
                "status": "Completed",
                "total": 1599.99
            },
            {
                "id": 5,
                "customer_id": 35,
                "order_date": "2023-04-20T13:10:00Z",
                "status": "Completed",
                "total": 2199.99
            }
        ]