#!/usr/bin/env python
"""
Test script for the OpenAI-powered agent.
"""
import os
import json
import asyncio
import argparse
from typing import List, Dict, Any

import aiohttp


async def test_query(session: aiohttp.ClientSession, query: str) -> Dict[str, Any]:
    """
    Test a natural language query.
    
    Args:
        session: HTTP session
        query: Natural language query
        
    Returns:
        Query result
    """
    url = "http://localhost:8000/query"
    
    payload = {
        "query": query,
        "query_id": "test-query",
        "context": {}
    }
    
    async with session.post(url, json=payload) as response:
        return await response.json()


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test the OpenAI-powered agent")
    parser.add_argument("--query", type=str, help="Natural language query to test")
    args = parser.parse_args()
    
    # Example queries
    example_queries = [
        "How many customers do we have?",
        "Find all expensive products",
        "Show me all employees in the sales department",
        "List all completed orders",
        "What is the total revenue from orders this month?"
    ]
    
    # Use the provided query or run all example queries
    queries_to_test = [args.query] if args.query else example_queries
    
    async with aiohttp.ClientSession() as session:
        for query in queries_to_test:
            print(f"\n\n{'=' * 80}")
            print(f"Testing query: {query}")
            print(f"{'=' * 80}\n")
            
            try:
                result = await test_query(session, query)
                
                # Print the thought process
                print("\nThought Process:")
                print("-" * 40)
                print(result.get("thought_process", "No thought process available"))
                
                # Print the structured queries
                print("\nStructured Queries:")
                print("-" * 40)
                for i, query in enumerate(result.get("structured_queries", [])):
                    print(f"Query {i+1} (Tool: {query.get('tool_name', 'unknown')}):")
                    parameters = query.get("parameters", {})
                    if "query" in parameters:
                        print(f"  Query: {parameters['query']}")
                    print(f"  Parameters: {json.dumps(parameters, indent=2)}")
                    print()
                
                # Print the results
                print("\nResults:")
                print("-" * 40)
                results = result.get("results", [])
                if results:
                    print(json.dumps(results[:5], indent=2))
                    if len(results) > 5:
                        print(f"\n... and {len(results) - 5} more results")
                else:
                    print("No results available")
                
                # Print execution time
                print(f"\nExecution Time: {result.get('execution_time_ms', 0):.2f} ms")
                
            except Exception as e:
                print(f"Error testing query: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())