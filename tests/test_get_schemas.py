#!/usr/bin/env python3
"""
Test the get_all_schemas method directly.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

# Load environment variables
load_dotenv()

from langgraph_integration.direct_db_client import DirectDatabaseClient

async def test_get_schemas():
    """Test the get_all_schemas method."""
    print("🔍 Testing get_all_schemas Method")
    print("="*50)
    
    client = DirectDatabaseClient()
    
    try:
        # Test the method
        print("\n1️⃣ Using get_all_schemas() method:")
        schemas = await client.get_all_schemas()
        print(f"Returned schemas: {schemas}")
        
        # Test the raw query directly
        print("\n2️⃣ Using raw query directly:")
        await client._ensure_initialized()
        
        schemas_query = """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name
        """
        
        result = await client.db_manager.fetch(schemas_query)
        print(f"Raw query result: {result}")
        
        schema_names = [schema['schema_name'] for schema in result]
        print(f"Extracted schema names: {schema_names}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_get_schemas())