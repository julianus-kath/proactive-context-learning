#!/usr/bin/env python3
"""
Test to verify the row count extraction fix handles emoji markers correctly.
"""

import sys
import json
sys.path.insert(0, '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

from langgraph_integration.mcp_client import _extract_json_from_text

def test_emoji_marker_extraction():
    """Test that extraction handles emoji in 'Full response (JSON):' marker."""
    
    # Simulate actual MCP response with emoji marker
    mcp_response = """✅ Query executed successfully

Rows returned: 1
Execution time: 92.04ms

Columns: TotalCustomers

Sample rows:
  Row 1: {"TotalCustomers": 419}

📊 Full response (JSON):
{
  "ok": true,
  "rows": [{"TotalCustomers": 419}],
  "columns": ["TotalCustomers"],
  "row_count": 1,
  "execution_time_ms": 92.04,
  "truncated": false
}"""

    print("=" * 80)
    print("Testing row count extraction with emoji marker")
    print("=" * 80)
    
    try:
        # Extract JSON
        result = _extract_json_from_text(mcp_response)
        
        print(f"\n✅ JSON extraction successful!")
        print(f"   Extracted keys: {list(result.keys())}")
        print(f"   Full response: {json.dumps(result, indent=2)}")
        
        # Check for row_count
        if "row_count" in result:
            row_count = result["row_count"]
            print(f"\n✅ Found row_count at top level: {row_count}")
            assert row_count == 1, f"Expected row_count=1, got {row_count}"
        else:
            print(f"\n❌ FAILED: row_count not found in extracted JSON")
            print(f"   Available keys: {list(result.keys())}")
            return False
        
        # Check that we got the right data
        assert result.get("ok") == True, "ok should be True"
        assert len(result.get("rows", [])) == 1, "Should have 1 row"
        assert result["rows"][0]["TotalCustomers"] == 419, "Row should contain TotalCustomers=419"
        
        print("\n✅ All assertions passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_legacy_marker_extraction():
    """Test that extraction still handles legacy format without emoji."""
    
    # Simulate legacy MCP response without emoji marker
    mcp_response_legacy = """✅ Query executed successfully

Rows returned: 1
Execution time: 92.04ms

Columns: TotalCustomers

Sample rows:
  Row 1: {"TotalCustomers": 419}

Full response (JSON):
{
  "ok": true,
  "rows": [{"TotalCustomers": 419}],
  "columns": ["TotalCustomers"],
  "row_count": 1,
  "execution_time_ms": 92.04,
  "truncated": false
}"""

    print("\n" + "=" * 80)
    print("Testing row count extraction with LEGACY marker (no emoji)")
    print("=" * 80)
    
    try:
        result = _extract_json_from_text(mcp_response_legacy)
        
        print(f"\n✅ JSON extraction successful!")
        print(f"   Extracted keys: {list(result.keys())}")
        
        # Check for row_count
        if "row_count" in result:
            row_count = result["row_count"]
            print(f"✅ Found row_count at top level: {row_count}")
            assert row_count == 1, f"Expected row_count=1, got {row_count}"
        else:
            print(f"❌ FAILED: row_count not found")
            return False
        
        print("✅ All assertions passed!")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test1_passed = test_emoji_marker_extraction()
    test2_passed = test_legacy_marker_extraction()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Emoji marker test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Legacy marker test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n✅ All tests passed! The emoji marker fix is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)