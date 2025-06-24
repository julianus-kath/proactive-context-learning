"""
Test script for the ERP server.
"""
import asyncio
import json
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector


async def main():
    """Test the ERP server."""
    print("Testing ERP server...")
    
    async with MCPERPConnector() as connector:
        # List all tables
        tables = await connector.list_tables()
        print("Tables:", tables)
        
        if tables:
            # Get the schema for the first table
            schema = await connector.get_table_schema(tables[0])
            print(f"Schema for {tables[0]}:", json.dumps(schema, indent=2))
            
            # Execute a simple query
            query = f"SELECT * FROM {tables[0]} LIMIT 3"
            results = await connector.execute_sql_query(query)
            print(f"Query results for '{query}':", json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())