#!/usr/bin/env python3
"""
Debug script to identify why queries are failing in the LangGraph workflow.
"""

import asyncio
import sys
import os
import logging

# Add the langgraph_integration directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'langgraph_integration'))

from langgraph_integration.mcp_client import execute_sql_query
from langgraph_integration.graph_definition import create_database_workflow

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_mcp_direct():
    """Test MCP server directly."""
    print("=== Testing MCP Server Directly ===")
    try:
        result = await execute_sql_query("SELECT COUNT(*) as total_customers FROM customers")
        print(f"✅ MCP Direct Result: {result}")
        return True
    except Exception as e:
        print(f"❌ MCP Direct Error: {e}")
        return False

async def test_langgraph_workflow():
    """Test LangGraph workflow."""
    print("\n=== Testing LangGraph Workflow ===")
    try:
        workflow = create_database_workflow()
        result = await workflow.process_query("How many customers are in New York city?")
        print(f"✅ LangGraph Result: {result}")
        return True
    except Exception as e:
        print(f"❌ LangGraph Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specific_query():
    """Test a specific query that's failing."""
    print("\n=== Testing Specific Query ===")
    try:
        result = await execute_sql_query("SELECT customer_id FROM customers WHERE city = 'New York'")
        print(f"✅ Specific Query Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Specific Query Error: {e}")
        return False

async def main():
    """Run all tests."""
    print("🔍 Debugging Query Failures\n")
    
    # Test MCP server directly
    mcp_ok = await test_mcp_direct()
    
    # Test specific query
    query_ok = await test_specific_query()
    
    # Test LangGraph workflow
    workflow_ok = await test_langgraph_workflow()
    
    print("\n=== Summary ===")
    print(f"MCP Server: {'✅ OK' if mcp_ok else '❌ FAILED'}")
    print(f"Specific Query: {'✅ OK' if query_ok else '❌ FAILED'}")
    print(f"LangGraph Workflow: {'✅ OK' if workflow_ok else '❌ FAILED'}")
    
    if mcp_ok and query_ok and not workflow_ok:
        print("\n🔍 Issue is in the LangGraph workflow, not the MCP server.")
    elif not mcp_ok:
        print("\n🔍 Issue is with the MCP server connection.")
    else:
        print("\n🔍 All components working - issue might be intermittent.")

if __name__ == "__main__":
    asyncio.run(main())