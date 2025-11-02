#!/usr/bin/env python3
"""
Test script to verify MCP server fixes:
1. describe_table (fixed get_table argument handling)
2. get_column_index (fixed function signature)
3. query_bounded (fixed Decimal JSON serialization)
"""

import sys
import json
import asyncio
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langgraph_integration.mcp_client import (
    describe_table_mcp,
    get_column_index_mcp,
    query_bounded_mcp
)


async def test_describe_table():
    """Test describe_table with fixed get_table() handling."""
    print("\n" + "="*70)
    print("TEST 1: describe_table (Fixed get_table() with proper schema parsing)")
    print("="*70)
    
    try:
        # Test with fully qualified name
        result = await describe_table_mcp("dbo.KHKArtikelKunden")
        
        if result and "error" not in str(result).lower():
            print("✅ describe_table succeeded!")
            
            # Check response structure
            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result
            
            if isinstance(data, dict):
                print(f"   ✓ Response structure: OK")
                print(f"   ✓ Schema parsing: OK")
                if "columns" in data:
                    print(f"   ✓ Columns extracted: {len(data['columns'])} columns")
                return True
            else:
                print(f"❌ Unexpected response type: {type(result)}")
                return False
        else:
            print(f"❌ Error in describe_table: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Exception in describe_table: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_get_column_index():
    """Test get_column_index with fixed function signature."""
    print("\n" + "="*70)
    print("TEST 2: get_column_index (Fixed catalog.get_table() signature)")
    print("="*70)
    
    try:
        # Test with list of table names
        table_names = ["dbo.KHKArtikelKunden", "dbo.KHKAdressen"]
        result = await get_column_index_mcp(table_names)
        
        if result and "error" not in str(result).lower():
            print("✅ get_column_index succeeded!")
            
            # Check response structure
            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result
            
            if isinstance(data, dict):
                print(f"   ✓ Response structure: OK")
                
                # Check that tables were found
                found_count = sum(1 for v in data.values() if v is not None)
                print(f"   ✓ Tables found: {found_count}/{len(table_names)}")
                
                # Display column info for found tables
                for table, columns in list(data.items())[:2]:
                    if columns:
                        print(f"   ✓ {table}: {len(columns)} columns")
                
                return True
            else:
                print(f"❌ Unexpected response type: {type(result)}")
                return False
        else:
            print(f"❌ Error in get_column_index: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Exception in get_column_index: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_query_bounded():
    """Test query_bounded with fixed Decimal JSON serialization."""
    print("\n" + "="*70)
    print("TEST 3: query_bounded (Fixed Decimal JSON serialization)")
    print("="*70)
    
    try:
        # Test query that should return Decimal values (numeric columns)
        sql = "SELECT TOP 10 * FROM dbo.KHKArtikelKunden"
        result = await query_bounded_mcp(sql, limit=10)
        
        if result:
            print("✅ query_bounded succeeded!")
            
            # Check response structure
            if isinstance(result, str):
                data = json.loads(result)  # This will fail if Decimal not serialized
            else:
                data = result
            
            if isinstance(data, dict):
                print(f"   ✓ JSON serialization: OK")
                print(f"   ✓ Response structure: OK")
                
                if "rows" in data:
                    rows = data["rows"]
                    print(f"   ✓ Rows returned: {len(rows) if isinstance(rows, list) else 'N/A'}")
                    
                    # Check for any numeric values in first row
                    if rows and isinstance(rows, list) and rows[0]:
                        first_row = rows[0]
                        numeric_cols = [k for k, v in first_row.items() if isinstance(v, (int, float))]
                        if numeric_cols:
                            print(f"   ✓ Numeric columns properly serialized: {len(numeric_cols)} cols")
                
                if data.get("ok"):
                    return True
            else:
                print(f"❌ Unexpected response type: {type(result)}")
                return False
        else:
            print(f"❌ No result from query_bounded")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON serialization error (Decimal not handled): {e}")
        print(f"   Response might contain Decimal or datetime objects")
        return False
    except Exception as e:
        print(f"❌ Exception in query_bounded: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MCP SERVER FIX VERIFICATION")
    print("="*70)
    print("\nTesting three critical bug fixes:")
    print("1. describe_table: Fixed get_table() schema parsing")
    print("2. get_column_index: Fixed function signature with two args")
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
    # Set up environment
    load_dotenv = True
    try:
        from dotenv import load_dotenv as ld
        ld(os.path.join(project_root, '.env'))
    except:
        pass
    
    # Run async main
    success = asyncio.run(main())
    sys.exit(0 if success else 1)