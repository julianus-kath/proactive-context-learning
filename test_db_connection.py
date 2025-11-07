#!/usr/bin/env python3
"""
Test database connection to Windows MCP server
"""

import asyncio
import aiohttp
import json

async def test_db_connection():
    """Test if MCP server can connect to database"""
    mcp_url = "http://10.255.152.48:8000"

    print("🔍 Testing MCP Server Database Connection...")
    print(f"URL: {mcp_url}")
    print("=" * 50)

    try:
        async with aiohttp.ClientSession() as session:
            # Test a simple query that should work if DB is connected
            print("📊 Testing simple database query...")
            payload = {
                "sql": "SELECT 1 as test",
                "limit": 1
            }

            async with session.post(
                f"{mcp_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "query_bounded",
                    "params": payload
                },
                headers={"Content-Type": "application/json"},
                timeout=15
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("✅ Database connection test successful")
                    print(f"   Response: {result.get('result', {}).get('content', [])[:1]}")
                else:
                    error_text = await response.text()
                    print(f"❌ Database connection test failed: HTTP {response.status}")
                    print(f"   Error: {error_text[:300]}...")

    except Exception as e:
        print(f"❌ Connection test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_db_connection())
