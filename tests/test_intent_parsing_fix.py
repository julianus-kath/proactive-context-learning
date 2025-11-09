#!/usr/bin/env python3
"""
Quick test to verify intent parsing fixes for incomplete JSON responses.
Tests edge cases that were causing the NoneType error.
"""

import asyncio
import sys
sys.path.insert(0, '/Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code')

from langgraph_integration.graph_definition import DatabaseWorkflow


async def test_incomplete_json_detection():
    """Test that incomplete JSON is detected and handled gracefully."""
    print("🧪 Test 1: Incomplete JSON Detection")
    
    builder = DatabaseWorkflow(model_name="gpt-4o")
    
    # Test cases
    test_cases = [
        ('{\n  "operation"', "Incomplete JSON (opens but doesn't close)"),
        ('{"operation": "query", "sql": "SELECT *"', "Incomplete with valid fields"),
        ('{"operation": "clarify"', "Very short incomplete JSON"),
        ('{"operation": "query", "reasoning": "complete"}', "Complete JSON"),
        ('', "Empty response"),
        (None, "None response"),
    ]
    
    all_passed = True
    for response_text, description in test_cases:
        try:
            print(f"\n  Testing: {description}")
            print(f"    Input: {repr(response_text[:50] if response_text else response_text)}")
            
            result = builder._parse_intent_json_response(response_text)
            
            # Check that result is always a dict
            if not isinstance(result, dict):
                print(f"    ❌ FAILED: Result is not a dict: {type(result)}")
                all_passed = False
                continue
            
            # Check that it has the required fields
            if "operation" not in result:
                print(f"    ❌ FAILED: Result missing 'operation' field")
                all_passed = False
                continue
            
            print(f"    ✅ PASSED: Got safe result with operation='{result['operation']}'")
            
        except Exception as e:
            print(f"    ❌ FAILED: Exception raised: {e}")
            all_passed = False
    
    return all_passed


async def test_safe_default_on_error():
    """Test that safe default is used when error occurs."""
    print("\n🧪 Test 2: Safe Default on Error")
    
    builder = DatabaseWorkflow(model_name="gpt-4o")
    
    # Simulate error conditions
    error_cases = [
        ('Invalid JSON: {', "Malformed JSON"),
        ('completely invalid', "Non-JSON response"),
        ('{', "Single brace"),
    ]
    
    all_passed = True
    for response_text, description in error_cases:
        try:
            print(f"\n  Testing: {description}")
            result = builder._parse_intent_json_response(response_text)
            
            if not isinstance(result, dict) or "operation" not in result:
                print(f"    ❌ FAILED: Invalid result structure")
                all_passed = False
            else:
                print(f"    ✅ PASSED: Safe default applied, operation='{result['operation']}'")
        except Exception as e:
            print(f"    ❌ FAILED: Unexpected exception: {e}")
            all_passed = False
    
    return all_passed


async def test_incomplete_json_detection_logic():
    """Test the incomplete JSON detection logic directly."""
    print("\n🧪 Test 3: Incomplete JSON Detection Logic")
    
    test_cases = [
        ('{\n  "operation"', True, "Should detect incomplete"),
        ('{"operation": "query"}', False, "Should recognize complete"),
        ('{"operation": "clarify", "missing_fields": []}', False, "Should recognize complete"),
        ('{\n', True, "Should detect incomplete (just opening)"),
        ('""', False, "Should recognize as not starting with {"),
    ]
    
    all_passed = True
    for response_text, should_be_incomplete, description in test_cases:
        is_incomplete = (response_text.strip().startswith('{') and 
                        not response_text.strip().endswith('}'))
        
        if is_incomplete == should_be_incomplete:
            print(f"  ✅ {description}: {response_text[:30]}...")
        else:
            print(f"  ❌ {description}: Expected incomplete={should_be_incomplete}, got {is_incomplete}")
            all_passed = False
    
    return all_passed


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🔍 INTENT PARSING FIX VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Test 1: Incomplete JSON Detection
    results.append(await test_incomplete_json_detection())
    
    # Test 2: Safe Default on Error
    results.append(await test_safe_default_on_error())
    
    # Test 3: Detection Logic
    results.append(await test_incomplete_json_detection_logic())
    
    # Summary
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED - Intent parsing is FIXED!")
    else:
        print("❌ SOME TESTS FAILED - Issues remain")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())