#!/usr/bin/env python3
"""
Debug MCP server status and catalog issues
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

async def check_mcp_status():
    """Check MCP server health and catalog status"""
    mcp_url = "http://10.255.152.48:8000"  # Windows MCP server over VPN

    print("🔍 Checking MCP Server Status...")
    print(f"URL: {mcp_url}")
    print("=" * 50)

    try:
        async with aiohttp.ClientSession() as session:
            # Check health endpoint
            print("📊 Checking /health endpoint...")
            async with session.get(f"{mcp_url}/health", timeout=10) as response:
                if response.status == 200:
                    health_data = await response.json()
                    print("✅ Health check successful")
                    print(f"   Status: {health_data.get('status', 'unknown')}")

                    catalog_info = health_data.get('catalog', {})
                    print("   Catalog Info:")
                    print(f"     - Tables: {catalog_info.get('tables_count', 'N/A')}")
                    print(f"     - Views: {catalog_info.get('views_count', 'N/A')}")
                    print(f"     - Age: {catalog_info.get('catalog_age_s', 'N/A')} seconds")
                    print(f"     - Valid: {catalog_info.get('is_valid', 'N/A')}")
                else:
                    print(f"❌ Health check failed: HTTP {response.status}")
                    return

            # Try a simple search_tables call
            print("\n🔍 Testing search_tables endpoint...")
            payload = {
                "query": "customers",
                "page": 1,
                "page_size": 5
            }

            async with session.post(
                f"{mcp_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "search_tables",
                    "params": payload
                },
                headers={"Content-Type": "application/json"},
                timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("✅ search_tables call successful")
                    print(f"   Response type: {type(result)}")

                    if isinstance(result, dict):
                        result_data = result.get('result', {})
                        if isinstance(result_data, dict):
                            content = result_data.get('content', [])
                            print(f"   Content items: {len(content) if isinstance(content, list) else 'N/A'}")

                            if isinstance(content, list) and len(content) > 0:
                                first_item = content[0]
                                print(f"   First item type: {type(first_item)}")
                                if isinstance(first_item, dict):
                                    print(f"   First item keys: {list(first_item.keys())[:3]}...")
                                else:
                                    print(f"   First item: {first_item}")
                        else:
                            print(f"   Result data type: {type(result_data)}")
                    else:
                        print(f"   Unexpected response format: {result}")

                else:
                    print(f"❌ search_tables failed: HTTP {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text[:200]}...")

    except aiohttp.ClientConnectorError as e:
        print(f"❌ Connection failed: Cannot connect to MCP server at {mcp_url}")
        print(f"   Make sure MCP server is running on Windows")
    except asyncio.TimeoutError:
        print(f"❌ Timeout: MCP server not responding within 10 seconds")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_mcp_status())
