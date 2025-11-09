#!/usr/bin/env python3
"""
Diagnostic script to trace where "no data" is coming from.
Run this after restarting the backend to check current code.
"""

import asyncio
import sys
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_field_mapping():
    """Test that exec_recovery is returning 'data' field, not 'rows'."""
    from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
    from langgraph_integration.contracts.state import BaseState
    
    # Create a simple test
    agent = ExecAndRecoveryAgent()
    
    # Create a test state with a simple COUNT query
    state = BaseState(
        user_input="How many items do we have?",
        sql_query="SELECT COUNT(*) AS count",  # Simple test query
        retry_count=0,
    )
    
    # Run the agent
    try:
        result = await agent(state)
        exec_result = result.get("exec_result")
        
        print("\n" + "="*80)
        print("DIAGNOSTIC: exec_recovery output")
        print("="*80)
        
        if exec_result:
            print(f"✅ exec_result received")
            print(f"   Keys: {list(exec_result.keys())}")
            print(f"   'data' present: {'data' in exec_result}")
            print(f"   'rows' present: {'rows' in exec_result}")
            
            if "data" in exec_result:
                data = exec_result["data"]
                print(f"   'data' value type: {type(data)}")
                print(f"   'data' length: {len(data) if isinstance(data, (list, dict)) else 'N/A'}")
                print(f"   'data' value: {data}")
            else:
                print(f"   ⚠️  'data' key NOT FOUND!")
                print(f"   Full exec_result: {json.dumps(exec_result, indent=2, default=str)}")
        else:
            print(f"❌ No exec_result in state")
            print(f"   error_info: {result.get('error_info')}")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

async def test_orchestrator_flow():
    """Test that orchestrator can read the data field."""
    print("\n" + "="*80)
    print("DIAGNOSTIC: orchestrator data reading")
    print("="*80)
    
    # Simulate what orchestrator does
    exec_result = {
        "ok": True,
        "data": [{"count": 1234}],  # Should be "data", not "rows"
        "row_count": 1,
        "execution_time_ms": 50,
        "truncated": False,
    }
    
    # This is what orchestrator does
    data = exec_result.get("data", [])
    
    print(f"✅ orchestrator.get('data') returns: {data}")
    if not data:
        print(f"   ⚠️  DATA IS EMPTY! This triggers 'no data' message")
    else:
        print(f"   ✅ Data is present, should format correctly")

async def main():
    print("\n" + "="*80)
    print("PHASE 10b DIAGNOSTIC: Tracing 'no data' issue")
    print("="*80)
    print("\nThis script checks if the Phase 10b fix is actually applied.")
    print("\n1. Testing exec_recovery field mapping...")
    
    try:
        await test_field_mapping()
    except ImportError as e:
        print(f"⚠️  Could not import exec_recovery: {e}")
        print("   Make sure backend is running and dependencies installed")
    
    print("\n2. Testing orchestrator data reading...")
    await test_orchestrator_flow()
    
    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print("""
If you see:
  ✅ 'data' present: YES
  ✅ orchestrator gets data correctly
  
  → Phase 10b fix is WORKING
  → Restart the backend server completely (stop + start)
  → Try querying again
  
If you see:
  ⚠️ 'data' NOT FOUND
  ⚠️ DATA IS EMPTY
  
  → Fix not applied or not picked up
  → Check if exec_recovery/agent.py lines 860, 891, 929 have "data" not "rows"
  → Clear Python cache: find . -type d -name __pycache__ -exec rm -rf {} +
  → Restart backend with fresh imports
""")

if __name__ == "__main__":
    asyncio.run(main())