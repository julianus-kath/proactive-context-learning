"""
DIAGNOSTIC TEST: Identify the three failure modes

Failure modes from production:
1. Wrong data returned (payroll instead of sales)
2. SQL generation failure → no handler for time comparisons
3. 500 errors → unhandled exceptions or missing data contracts
"""

import asyncio
import logging
import pytest
from langgraph_integration.orchestrator import create_query_orchestrator

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_failure_mode_1():
    """Failure Mode 1: Wrong data returned"""
    print("\n" + "="*80)
    print("FAILURE MODE 1: Wrong Data Returned")
    print("Query: 'Show me our top 5 products by sales'")
    print("Expected: Sales/product data")
    print("Actual: Payroll data (Lohnart*, AHV, ALV, etc.)")
    print("="*80)
    
    orchestrator = create_query_orchestrator()
    result = await orchestrator.process_query("Show me our top 5 products by sales")
    
    # Examine result structure
    print(f"\n📊 Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"📊 Result keys: {result.keys()}")
        print(f"📊 Intent: {result.get('intent', {})}")
        print(f"📊 Relevant tables: {result.get('relevant_tables', [])}")
        print(f"📊 SQL Query:\n{result.get('sql_query', 'N/A')}")
        print(f"📊 Final answer:\n{result.get('final_answer', 'N/A')}")
    else:
        print(f"📊 String response:\n{result}")

@pytest.mark.asyncio
async def test_failure_mode_2():
    """Failure Mode 2: Can't generate SQL"""
    print("\n" + "="*80)
    print("FAILURE MODE 2: Can't Generate SQL (Time Comparison)")
    print("Query: 'How have our sales improved from September to October?'")
    print("Expected: SUM(sales) grouped by month, calculated comparison")
    print("Actual: 'Could not generate SQL query'")
    print("="*80)
    
    orchestrator = create_query_orchestrator()
    result = await orchestrator.process_query("How have our sales improved from September to October?")
    
    print(f"\n📊 Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"📊 Result keys: {result.keys()}")
        print(f"📊 Intent: {result.get('intent', {})}")
        print(f"📊 Intent required_action: {result.get('intent', {}).get('required_action', 'N/A')}")
        print(f"📊 Relevant tables: {result.get('relevant_tables', [])}")
        print(f"📊 SQL Query: {result.get('sql_query', 'EMPTY')}")
        print(f"📊 Error info: {result.get('error_info', 'N/A')}")
        print(f"📊 Final answer:\n{result.get('final_answer', 'N/A')}")

@pytest.mark.asyncio
async def test_failure_mode_3():
    """Failure Mode 3: 500 errors"""
    print("\n" + "="*80)
    print("FAILURE MODE 3: 500 Errors (Unhandled Exceptions)")
    print("Query: 'When do we have to order new parts of 56 mm diameter?'")
    print("Expected: Data or graceful error")
    print("Actual: 500 Connection error")
    print("="*80)
    
    orchestrator = create_query_orchestrator()
    try:
        result = await orchestrator.process_query("When do we have to order new parts of 56 mm diameter?")
        print(f"\n📊 Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"📊 Result keys: {result.keys()}")
            print(f"📊 Intent: {result.get('intent', {})}")
            print(f"📊 Error info: {result.get('error_info', {})}")
            print(f"📊 Final answer:\n{result.get('final_answer', 'N/A')}")
    except Exception as e:
        print(f"❌ Exception caught: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

@pytest.mark.asyncio
async def test_successful_query():
    """Control: This should work"""
    print("\n" + "="*80)
    print("CONTROL: Successful Query")
    print("Query: 'How many clients do we have?'")
    print("="*80)
    
    orchestrator = create_query_orchestrator()
    result = await orchestrator.process_query("How many clients do we have?")
    
    print(f"\n📊 Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"📊 Result keys: {result.keys()}")
        print(f"📊 Intent: {result.get('intent', {})}")
        print(f"📊 Relevant tables: {result.get('relevant_tables', [])}")
        print(f"📊 Final answer:\n{result.get('final_answer', 'N/A')}")
    else:
        print(f"📊 String response:\n{result}")

async def main():
    """Run all diagnostic tests"""
    print("\n🔍 STARTING DIAGNOSTIC TESTS FOR PRODUCTION FAILURES\n")
    
    try:
        await test_successful_query()
    except Exception as e:
        print(f"❌ Control test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        await test_failure_mode_1()
    except Exception as e:
        print(f"❌ Failure mode 1 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        await test_failure_mode_2()
    except Exception as e:
        print(f"❌ Failure mode 2 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        await test_failure_mode_3()
    except Exception as e:
        print(f"❌ Failure mode 3 test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Diagnostic tests complete\n")

if __name__ == "__main__":
    asyncio.run(main())