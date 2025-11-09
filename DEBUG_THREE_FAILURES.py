#!/usr/bin/env python3
"""
DEEP DIAGNOSTIC: Trace all three failures through the orchestrator pipeline

This script traces exactly where each failure occurs:
1. Wrong Data: Scout/Discovery returning payroll instead of sales
2. SQL Gap: Join_SQL not generating SQL for temporal queries
3. 500 Errors: Unhandled exceptions in agent subgraphs
"""

import asyncio
import logging
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/debug_three_failures.log')
    ]
)
logger = logging.getLogger(__name__)

from langgraph_integration.orchestrator import create_query_orchestrator
from langgraph_integration.contracts.state import BaseState


async def debug_failure_2_temporal_sql():
    """Deep dive: Why doesn't temporal SUM query generate SQL?"""
    print("\n" + "="*100)
    print("🔍 FAILURE 2 DEEP DIVE: Temporal SQL Generation")
    print("="*100)
    
    query = "How have our sales improved from September to October?"
    print(f"❓ Query: {query}\n")
    
    orchestrator = create_query_orchestrator()
    
    # Step 1: Check intent parsing
    print("📍 Step 1: Intent Parsing")
    print("-" * 60)
    intent_subgraph = orchestrator.intent_parser.build_subgraph()
    intent_result = await intent_subgraph.ainvoke(BaseState(user_input=query))
    intent = intent_result.get("intent", {})
    
    print(f"✅ Intent extracted:")
    print(f"  - required_action: {intent.get('required_action')}")
    print(f"  - metrics: {intent.get('metrics')}")
    print(f"  - primary_entities: {intent.get('primary_entities')}")
    print(f"  - extra_keywords: {intent_result.get('extra_keywords', [])}")
    
    if intent.get('required_action') != 'sum_with_period':
        print(f"❌ BUG: Expected 'sum_with_period', got '{intent.get('required_action')}'")
        return
    
    print(f"\n✅ Intent routing correct (required_action={intent.get('required_action')})")
    
    # Step 2: Discovery
    print("\n📍 Step 2: Discovery Agent")
    print("-" * 60)
    discovery_input = BaseState(
        user_input=query,
        intent=intent,
        messages=[],
        session_described_tables={}
    )
    discovery_result = await orchestrator._discovery_node(discovery_input)
    relevant_tables = discovery_result.get("relevant_tables", [])
    
    print(f"✅ Discovery found {len(relevant_tables)} tables:")
    for t in relevant_tables[:5]:
        print(f"  - {t}")
    
    if not relevant_tables:
        print(f"❌ BUG: Discovery found NO tables!")
        return
    
    # Step 3: SQL Generation
    print("\n📍 Step 3: SQL Generation (Join_SQL Agent)")
    print("-" * 60)
    join_sql_input = BaseState(
        user_input=query,
        intent=intent,
        relevant_tables=relevant_tables,
        candidate_views=discovery_result.get("candidate_views", []),
        messages=[],
        session_described_tables={}
    )
    
    # Build and run join_sql subgraph directly
    join_graph = orchestrator.join_sql_agent.build_subgraph()
    join_result = await join_graph.ainvoke(join_sql_input)
    
    sql_query = join_result.get("sql_query", "")
    join_plan = join_result.get("join_plan", {})
    error_info = join_result.get("error_info", None)
    
    print(f"✅ Join_SQL agent finished:")
    print(f"  - join_plan: {join_plan}")
    print(f"  - sql_query length: {len(sql_query)}")
    print(f"  - error_info: {error_info}")
    
    if not sql_query:
        print(f"\n❌ BUG: SQL generation returned EMPTY query!")
        print(f"   Error: {error_info}")
        
        # Debug: Check if routing happened
        print(f"\n🔍 Debugging SQL generation routing:")
        print(f"   - required_action: {intent.get('required_action')}")
        print(f"   - Should route to: _generate_sum_with_period_sql")
        print(f"   - Check if join_plan.primary_table exists: {join_plan.get('primary_table')}")
        return
    
    print(f"\n✅ SQL generated successfully:")
    print(f"   {sql_query[:200]}...")
    
    # Full end-to-end
    print("\n📍 Step 4: Full End-to-End")
    print("-" * 60)
    full_result = await orchestrator.process_query(query)
    print(f"Final answer:\n{full_result.get('final_answer', full_result)}")


async def debug_failure_1_wrong_data():
    """Deep dive: Why does Scout return payroll data for sales query?"""
    print("\n" + "="*100)
    print("🔍 FAILURE 1 DEEP DIVE: Wrong Data (Scout Ranking)")
    print("="*100)
    
    query = "Show me our top 5 products by sales"
    print(f"❓ Query: {query}\n")
    
    orchestrator = create_query_orchestrator()
    
    # Step 1: Intent
    print("📍 Step 1: Intent Parsing")
    print("-" * 60)
    intent_subgraph = orchestrator.intent_parser.build_subgraph()
    intent_result = await intent_subgraph.ainvoke(BaseState(user_input=query))
    intent = intent_result.get("intent", {})
    
    print(f"✅ Intent extracted:")
    print(f"  - required_action: {intent.get('required_action')}")
    print(f"  - extra_keywords: {intent_result.get('extra_keywords', [])}")
    
    # Step 2: Discovery
    print("\n📍 Step 2: Discovery Agent (Scout Ranking)")
    print("-" * 60)
    discovery_input = BaseState(
        user_input=query,
        intent=intent,
        messages=[],
        session_described_tables={}
    )
    discovery_result = await orchestrator._discovery_node(discovery_input)
    relevant_tables = discovery_result.get("relevant_tables", [])
    
    print(f"✅ Discovery found {len(relevant_tables)} tables:")
    for i, t in enumerate(relevant_tables[:10]):
        name = t if isinstance(t, str) else t.get("name", str(t))
        print(f"  {i+1}. {name}")
    
    # Check if payroll tables are in the list (the BUG)
    payroll_names = ["lohnart", "ahv", "alv", "quellensteuer"]
    for t in relevant_tables:
        name = (t if isinstance(t, str) else t.get("name", "")).lower()
        for pname in payroll_names:
            if pname in name:
                print(f"\n❌ BUG CONFIRMED: Found payroll table '{name}' in rank {relevant_tables.index(t)+1}")
                print(f"   This should NOT be in sales query results!")
                break
    
    # Check if sales/product tables are present
    sales_names = ["vkposition", "rechnung", "artikel", "maartikel"]
    found_sales = False
    for t in relevant_tables[:5]:
        name = (t if isinstance(t, str) else t.get("name", "")).lower()
        for sname in sales_names:
            if sname in name:
                print(f"\n✅ Found expected sales/product table: '{name}'")
                found_sales = True
                break
    
    if not found_sales:
        print(f"\n⚠️  WARNING: Expected sales/product tables not in top 5!")


async def debug_failure_3_500_errors():
    """Deep dive: Why do some queries throw 500 errors?"""
    print("\n" + "="*100)
    print("🔍 FAILURE 3 DEEP DIVE: 500 Errors (Unhandled Exceptions)")
    print("="*100)
    
    queries = [
        "What table did you get that from?",
        "When do we have to order new parts of 56 mm diameter?"
    ]
    
    orchestrator = create_query_orchestrator()
    
    for query in queries:
        print(f"\n❓ Query: {query}")
        print("-" * 60)
        
        try:
            result = await orchestrator.process_query(query)
            print(f"✅ No exception, result:")
            if isinstance(result, dict):
                print(f"  - error_info: {result.get('error_info', 'None')}")
                print(f"  - final_answer: {result.get('final_answer', '')[:100]}...")
            else:
                print(f"  - {str(result)[:100]}...")
        except Exception as e:
            print(f"❌ Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run all diagnostics"""
    try:
        await debug_failure_2_temporal_sql()
        await debug_failure_1_wrong_data()
        await debug_failure_3_500_errors()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())