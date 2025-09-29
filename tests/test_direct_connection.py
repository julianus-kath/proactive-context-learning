#!/usr/bin/env python3
"""
Test the direct database client with fresh initialization.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

from langgraph_integration.direct_db_client import DirectDatabaseClient

async def test_direct_connection():
    """Test direct connection with fresh client."""
    print("🔍 Testing Direct Database Connection")
    print("="*50)
    
    # Create a fresh client instance
    client = DirectDatabaseClient()
    
    try:
        # Test health check
        print("\n1️⃣ Health check...")
        is_healthy = await client.health_check()
        print(f"Health check: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
        
        # Test schema discovery
        print("\n2️⃣ Schema discovery...")
        schemas = await client.get_all_schemas()
        print(f"Found schemas: {schemas}")
        
        # Test database indexing
        print("\n3️⃣ Database indexing...")
        index_info = await client.index_database()
        print(f"Indexed: {index_info['total_tables']} tables across {len(index_info['schemas'])} schemas")
        
        for schema_name in index_info['schemas']:
            schema_tables = {k: v for k, v in index_info['tables'].items() 
                           if k.startswith(f"{schema_name}.")}
            print(f"  - {schema_name}: {len(schema_tables)} tables")
            
            # Show table names
            for table_name in schema_tables.keys():
                print(f"    • {table_name}")
        
        # Test specific queries if webshop schema exists
        if 'webshop' in index_info['schemas']:
            print("\n4️⃣ Testing webshop queries...")
            
            # Count customers
            result = await client.execute_query("SELECT COUNT(*) as count FROM webshop.customer")
            print(f"Customer count query result: {result}")
            
            # List tables in webshop
            result = await client.execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'webshop' 
                ORDER BY table_name
            """)
            print(f"Webshop tables query result: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_connection())