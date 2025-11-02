#!/usr/bin/env python3
"""
Quick test to verify the async node wrapper fix.
Ensures graph nodes can be invoked without "No synchronous function provided" errors.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_orchestrator_initialization():
    """Test that orchestrator initializes without async errors."""
    print("🧪 Testing orchestrator initialization...")
    
    try:
        from langgraph_integration.orchestrator import create_query_orchestrator
        
        print("   ✅ Import successful")
        
        # Create orchestrator
        orchestrator = create_query_orchestrator()
        print("   ✅ Orchestrator created")
        
        # Check graph exists and is compiled
        if orchestrator.graph is None:
            print("   ❌ Graph is None")
            return False
        
        print("   ✅ Graph compiled successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_async_invoke():
    """Test that async invoke works without sync/async conflicts."""
    print("\n🧪 Testing async graph invocation...")
    
    try:
        from langgraph_integration.orchestrator import create_query_orchestrator
        from langgraph_integration.contracts.state import BaseState
        
        orchestrator = create_query_orchestrator()
        print("   ✅ Orchestrator created")
        
        # Test with simple query
        test_query = "How many customers do we have?"
        print(f"   📝 Testing with query: {test_query}")
        
        result = await orchestrator.process_query(test_query)
        print(f"   ✅ Got response: {result[:100]}...")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("Async Node Fix Validation Tests")
    print("=" * 60)
    
    results = []
    
    # Test 1: Initialization
    result1 = test_orchestrator_initialization()
    results.append(("Orchestrator Init", result1))
    
    # Test 2: Async invoke
    try:
        result2 = asyncio.run(test_async_invoke())
        results.append(("Async Invoke", result2))
    except Exception as e:
        print(f"❌ Failed to run async test: {e}")
        results.append(("Async Invoke", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)