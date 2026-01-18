#!/usr/bin/env python3
"""
Test script for the Simple SQL Agent.

Run this to verify the agent works correctly.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_mcp_connection():
    """Test MCP server connectivity."""
    print("\n" + "=" * 60)
    print("TEST 1: MCP Server Connectivity")
    print("=" * 60)

    from simple_sql_agent.db.mcp_client import get_mcp_client

    client = get_mcp_client()
    print(f"MCP URL: {client.base_url}")

    is_healthy = await client.health_check()
    print(f"Health check: {'PASSED' if is_healthy else 'FAILED'}")

    if not is_healthy:
        print("WARNING: MCP server is not reachable. Make sure it's running on Windows.")
        return False

    return True


async def test_list_tables():
    """Test listing tables."""
    print("\n" + "=" * 60)
    print("TEST 2: List Tables")
    print("=" * 60)

    from simple_sql_agent.tools.db_tools import list_tables

    result = list_tables.invoke({})
    print(result[:500] + "..." if len(result) > 500 else result)

    if "Error" in result or "No tables found" in result:
        print("WARNING: Could not list tables")
        return False

    return True


async def test_agent_simple_query():
    """Test the agent with a simple query."""
    print("\n" + "=" * 60)
    print("TEST 3: Simple Agent Query")
    print("=" * 60)

    from simple_sql_agent.agent import create_sql_agent

    agent = create_sql_agent()

    question = "How many tables are in the database?"
    print(f"Question: {question}")

    result = await agent.arun(question)

    print(f"\nAnswer: {result['answer'][:500]}")
    print(f"Success: {result['success']}")

    return result['success']


async def test_agent_business_query():
    """Test the agent with a business query."""
    print("\n" + "=" * 60)
    print("TEST 4: Business Query (Top Customers)")
    print("=" * 60)

    from simple_sql_agent.agent import create_sql_agent

    agent = create_sql_agent()

    question = "Who are our top 3 customers by revenue?"
    print(f"Question: {question}")

    result = await agent.arun(question)

    print(f"\nAnswer: {result['answer'][:800]}")
    if result.get('sql_query'):
        print(f"\nSQL: {result['sql_query']}")
    print(f"Success: {result['success']}")

    return result['success']


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SIMPLE SQL AGENT - TEST SUITE")
    print("=" * 60)

    results = {}

    # Test 1: MCP connectivity
    try:
        results['mcp'] = await test_mcp_connection()
    except Exception as e:
        print(f"MCP test failed with error: {e}")
        results['mcp'] = False

    if not results['mcp']:
        print("\nStopping tests - MCP server not available")
        return

    # Test 2: List tables
    try:
        results['list_tables'] = await test_list_tables()
    except Exception as e:
        print(f"List tables test failed: {e}")
        results['list_tables'] = False

    # Test 3: Simple query
    try:
        results['simple_query'] = await test_agent_simple_query()
    except Exception as e:
        print(f"Simple query test failed: {e}")
        results['simple_query'] = False

    # Test 4: Business query
    try:
        results['business_query'] = await test_agent_business_query()
    except Exception as e:
        print(f"Business query test failed: {e}")
        results['business_query'] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {test_name}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")


if __name__ == "__main__":
    asyncio.run(main())
