#!/usr/bin/env python3
"""
Test script to verify MCP server can connect to proxy.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add mcp_server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp_server'))

from database_adapter import DatabaseAdapter


async def test_proxy_connection():
    """Test the proxy connection through MCP server."""
    print("=" * 60)
    print("Testing MCP Server Proxy Connection")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Environment Variables:")
    print(f"   DB_MODE: {os.getenv('DB_MODE')}")
    print(f"   PROXY_BASE_URL: {os.getenv('PROXY_BASE_URL')}")
    print(f"   PROXY_DEFAULT_CONN: {os.getenv('PROXY_DEFAULT_CONN')}")
    print(f"   PROXY_API_KEY: {'***' if os.getenv('PROXY_API_KEY') else 'NOT SET'}")
    
    # Initialize database adapter
    print("\n2. Initializing DatabaseAdapter...")
    try:
        adapter = DatabaseAdapter()
        print(f"   ✅ DatabaseAdapter created in {adapter.dialect} mode")
    except Exception as e:
        print(f"   ❌ Failed to create DatabaseAdapter: {e}")
        return False
    
    # Test connection
    print("\n3. Testing connection...")
    try:
        await adapter.initialize()
        print("   ✅ Connection test successful")
    except Exception as e:
        print(f"   ❌ Connection test failed: {e}")
        return False
    
    # Fetch schema
    print("\n4. Fetching schema...")
    try:
        schema = await adapter.fetch_schema()
        print(f"   ✅ Schema fetched: {len(schema)} tables")
        
        # Show first few tables
        if schema:
            print("\n   Sample tables:")
            for table in schema[:5]:
                print(f"      - {table['name']} ({len(table.get('columns', []))} columns)")
    except Exception as e:
        print(f"   ❌ Schema fetch failed: {e}")
        return False
    
    # Test query
    print("\n5. Testing query execution...")
    try:
        # Try a simple query
        results = await adapter.execute_query("SELECT 1 as test", limit=1)
        print(f"   ✅ Query executed: {len(results)} rows")
    except Exception as e:
        print(f"   ❌ Query execution failed: {e}")
        return False
    
    # Cleanup
    print("\n6. Cleaning up...")
    try:
        await adapter.close()
        print("   ✅ Connection closed")
    except Exception as e:
        print(f"   ⚠️  Cleanup warning: {e}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_proxy_connection())
    sys.exit(0 if success else 1)