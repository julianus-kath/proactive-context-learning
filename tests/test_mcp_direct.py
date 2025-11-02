#!/usr/bin/env python3
"""
Direct test of MCP server endpoints to verify fixes.
"""

import sys
import json
import asyncio
import aiohttp
import os
from pathlib import Path

# Configuration
MCP_HOST = os.getenv("MCP_SERVER_URL", "http://192.168.1.35:8000")
MCP_ENDPOINT = f"{MCP_HOST}/mcp"

print(f"🔗 MCP Endpoint: {MCP_ENDPOINT}\n")


async def call_mcp_tool(tool_name: str, arguments: dict):
    """Call MCP tool directly via HTTP."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(MCP_ENDPOINT, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                result = await resp.json()
                return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}


async def test_describe_table():
    """Test describe_table tool."""
    print("="*70)
    print("TEST 1: describe_table (Fixed get_table() schema parsing)")
    print("="*70)
    
    try:
        result = await call_mcp_tool("describe_table", {"table_name": "dbo.KHKArtikelKunden"})
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return False
        
        # Check for valid response structure
        if result.get("result") and result["result"].get("content"):
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get("text", "")
                if "Internal error" in text or "string indices" in text:
                    print(f"❌ Still getting 'string indices' error")
                    print(f"   Error: {text[:200]}")
                    return False
                else:
                    print(f"✅ describe_table succeeded!")
                    
                    # Try to extract JSON from response
                    if "Full response (JSON)" in text:
                        print(f"   ✓ Response contains valid JSON section")
                    
                    # Check for key info
                    if "📊 Table:" in text:
                        print(f"   ✓ Table information present")
                    if "📋 Top Columns:" in text:
                        print(f"   ✓ Column information present")
                    
                    return True
        
        print(f"❌ Unexpected response structure")
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


async def test_get_column_index():
    """Test get_column_index tool."""
    print("\n" + "="*70)
    print("TEST 2: get_column_index (Fixed catalog.get_table() signature)")
    print("="*70)
    
    try:
        result = await call_mcp_tool(
            "get_column_index",
            {"table_names": ["dbo.KHKArtikelKunden", "dbo.KHKAdressen"]}
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return False
        
        # Check for valid response
        if result.get("result") and result["result"].get("content"):
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get("text", "")
                
                # Try to parse JSON
                try:
                    # Extract JSON from text if needed
                    if "{" in text:
                        json_start = text.find("{")
                        json_text = text[json_start:]
                        if "}" in json_text:
                            json_text = json_text[:json_text.rfind("}")+1]
                            data = json.loads(json_text)
                            
                            if data.get("ok"):
                                column_index = data.get("data", {})
                                if column_index:
                                    print(f"✅ get_column_index succeeded!")
                                    print(f"   ✓ Tables found: {len(column_index)}")
                                    for table, cols in list(column_index.items())[:2]:
                                        if cols:
                                            print(f"   ✓ {table}: {len(cols)} columns")
                                    return True
                except Exception as e:
                    pass
                
                print(f"❌ Failed to parse response")
                print(f"   Response: {text[:300]}")
                return False
        
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_query_bounded():
    """Test query_bounded tool."""
    print("\n" + "="*70)
    print("TEST 3: query_bounded (Fixed Decimal JSON serialization)")
    print("="*70)
    
    try:
        result = await call_mcp_tool(
            "query_bounded",
            {"sql": "SELECT TOP 10 * FROM dbo.KHKArtikelKunden"}
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return False
        
        # Check for valid response
        if result.get("result") and result["result"].get("content"):
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get("text", "")
                
                # Check for Decimal serialization errors
                if "Decimal" in text or "not JSON serializable" in text:
                    print(f"❌ Decimal serialization error still present")
                    print(f"   Error: {text[:200]}")
                    return False
                
                # Try to parse JSON from response
                try:
                    if "{" in text:
                        json_start = text.find("{")
                        json_text = text[json_start:]
                        if "}" in json_text:
                            # Find the last closing brace
                            last_brace = json_text.rfind("}")
                            json_text = json_text[:last_brace+1]
                            data = json.loads(json_text)
                            
                            if data.get("ok"):
                                rows = data.get("rows", [])
                                print(f"✅ query_bounded succeeded!")
                                print(f"   ✓ JSON serialization: OK")
                                print(f"   ✓ Rows returned: {len(rows)}")
                                
                                # Check for numeric values
                                if rows:
                                    first_row = rows[0]
                                    numeric_cols = [k for k, v in first_row.items() 
                                                  if isinstance(v, (int, float))]
                                    if numeric_cols:
                                        print(f"   ✓ Numeric columns properly serialized: {len(numeric_cols)} cols")
                                
                                return True
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parse error (Decimal might not be serialized): {e}")
                    print(f"   Response start: {text[:300]}")
                    return False
        
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MCP SERVER FIX VERIFICATION (Direct HTTP Tests)")
    print("="*70)
    print("\nTesting three critical bug fixes:")
    print("1. describe_table: Fixed get_table() schema parsing")
    print("2. get_column_index: Fixed function signature")
    print("3. query_bounded: Fixed Decimal JSON serialization")
    
    results = []
    
    # Run tests
    results.append(("describe_table", await test_describe_table()))
    results.append(("get_column_index", await test_get_column_index()))
    results.append(("query_bounded", await test_query_bounded()))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)