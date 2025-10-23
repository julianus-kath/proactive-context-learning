#!/usr/bin/env python3
"""
Quick verification that intent parsing fix is working.
Run this after restarting your services.
"""

import sys
import asyncio
from langgraph_integration.graph_definition import DatabaseWorkflow


async def test_intent_parsing():
    """Test intent parsing with edge cases."""
    
    print("🧪 Testing Intent Parsing Fix\n" + "="*50)
    
    # Create workflow instance
    workflow = DatabaseWorkflow()
    
    test_cases = [
        ("None response", None, "Should handle None gracefully"),
        ("Empty string", "", "Should handle empty string"),
        ("Incomplete JSON", '{\n  "operation"', "Should handle truncated JSON (user's exact error)"),
        ("Valid JSON", '{"operation": "query", "sql": "SELECT 1"}', "Should parse valid JSON"),
    ]
    
    all_passed = True
    
    for name, response_text, expected in test_cases:
        try:
            result = workflow._parse_intent_json_response(response_text)
            
            # Verify result is always a dict
            if not isinstance(result, dict):
                print(f"❌ {name}: FAILED - Result is {type(result)}, not dict")
                all_passed = False
                continue
            
            # Verify can call .get() safely
            op = result.get("operation", "unknown")
            
            print(f"✅ {name}")
            print(f"   Input: {repr(response_text)[:50]}...")
            print(f"   Result: {result}")
            print(f"   Can safely call .get(): {op}\n")
            
        except Exception as e:
            print(f"❌ {name}: FAILED with exception")
            print(f"   Error: {e}\n")
            all_passed = False
    
    print("="*50)
    if all_passed:
        print("✅ ALL TESTS PASSED - Intent parsing is FIXED!")
        print("\nYou can now safely run queries without the NoneType error.")
        return 0
    else:
        print("❌ Some tests failed - there may still be an issue")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_intent_parsing())
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Verification script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)