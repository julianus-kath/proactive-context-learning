"""
MCP ERP Connector implementation.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from crawling_agent.base_connector import BaseMCPConnector


class MCPERPConnector(BaseMCPConnector):
    """
    MCP connector for the ERP Server.
    
    This connector provides methods to interact with the ERP Server via MCP.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8001/sse",
        server_name: str = "ERPServer",
    ):
        """
        Initialize the MCP ERP Connector.

        Args:
            server_url: The URL of the ERP Server (default: "http://localhost:8001/sse")
            server_name: The name of the server (default: "ERPServer")
        """
        super().__init__(server_url=server_url, server_name=server_name)
    
    async def execute_sql_query(self, query: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against the ERP database with a timeout.
        
        Args:
            query: The SQL query to execute
            timeout: Maximum time to wait for a response (in seconds)
            
        Returns:
            The query results as a list of dictionaries
        """
        try:
            result = await self.call_tool("execute_sql_query", {"query": query}, timeout=timeout)
            return json.loads(result)
        except TimeoutError:
            print(f"SQL query execution timed out after {timeout} seconds: {query}")
            raise
    
    async def get_table_schema(self, table_name: str, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Get the schema for a specific table with a timeout.
        
        Args:
            table_name: The name of the table
            timeout: Maximum time to wait for a response (in seconds)
            
        Returns:
            The table schema as a dictionary
        """
        try:
            result = await self.call_tool("get_table_schema", {"table_name": table_name}, timeout=timeout)
            return json.loads(result)
        except TimeoutError:
            print(f"Get table schema timed out after {timeout} seconds: {table_name}")
            raise
    
    async def list_tables(self, timeout: float = 5.0) -> List[str]:
        """
        List all tables in the ERP database with a timeout.
        
        Args:
            timeout: Maximum time to wait for a response (in seconds)
            
        Returns:
            A list of table names
        """
        try:
            result = await self.call_tool("list_tables", {}, timeout=timeout)
            return json.loads(result)["tables"]
        except TimeoutError:
            print(f"List tables timed out after {timeout} seconds")
            raise


async def main():
    """Example usage of the MCP ERP Connector."""
    async with MCPERPConnector() as connector:
        # List all tables
        tables = await connector.list_tables()
        print("Tables:", tables)
        
        if tables:
            # Get the schema for the first table
            schema = await connector.get_table_schema(tables[0])
            print(f"Schema for {tables[0]}:", schema)
            
            # Execute a simple query
            query = f"SELECT * FROM {tables[0]} LIMIT 5"
            results = await connector.execute_sql_query(query)
            print(f"Query results for '{query}':", results)


if __name__ == "__main__":
    asyncio.run(main())