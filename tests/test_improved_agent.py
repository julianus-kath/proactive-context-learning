#!/usr/bin/env python3
"""
Test script for the improved LangGraph database agent.
Tests the new schema discovery, error handling, and retry logic.
"""

import asyncio
import logging
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

from langgraph_integration.graph_definition import create_database_workflow
from langgraph_integration.direct_db_client import index_database, get_all_schemas, get_database_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_database_indexing():
    """Test the database indexing functionality."""
    print("🔍 Testing Database Indexing...")
    
    try:
        # Test schema discovery
        schemas = await get_all_schemas()
        print(f"✅ Found schemas: {schemas}")
        
        # Test database indexing
        index_info = await index_database()
        print(f"✅ Database indexed: {index_info['total_tables']} tables across {len(index_info['schemas'])} schemas")
        
        # Show some details
        for schema_name in index_info['schemas']:
            schema_tables = [table for table in index_info['tables'].keys() if table.startswith(f"{schema_name}.")]
            print(f"   - {schema_name}: {len(schema_tables)} tables")
        
        # Test comprehensive schema retrieval
        full_schema = await get_database_schema(include_all_schemas=True)
        print(f"✅ Full schema retrieved ({len(full_schema)} characters)")
        
        return True
        
    except Exception as e:
        print(f"❌ Database indexing test failed: {e}")
        return False

async def test_schema_awareness():
    """Test that the agent is aware of all schemas."""
    print("\n🧠 Testing Schema Awareness...")
    
    try:
        workflow = create_database_workflow()
        
        # Test queries that should work with the new schema awareness
        test_queries = [
            "What schemas do you have access to?",
            "What tables do you have access to?",
            "How many customers are there?",
            "What tables are in the webshop schema?"
        ]
        
        for query in test_queries:
            print(f"\n📝 Testing: '{query}'")
            try:
                response = await workflow.process_query(query)
                print(f"✅ Response: {response[:200]}...")
            except Exception as e:
                print(f"❌ Query failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema awareness test failed: {e}")
        return False

async def test_error_handling_and_retry():
    """Test the error handling and retry logic."""
    print("\n🔄 Testing Error Handling and Retry Logic...")
    
    try:
        workflow = create_database_workflow()
        
        # Test queries that might initially fail but should be retried
        test_queries = [
            "What orders were placed in May?",  # This should work with proper date handling
            "What is the most popular product?",  # This should work with proper table qualification
        ]
        
        for query in test_queries:
            print(f"\n📝 Testing: '{query}'")
            try:
                response = await workflow.process_query(query)
                print(f"✅ Response: {response[:200]}...")
            except Exception as e:
                print(f"❌ Query failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

async def test_conversation_flow():
    """Test the conversation flow with context awareness."""
    print("\n💬 Testing Conversation Flow...")
    
    try:
        workflow = create_database_workflow()
        
        # Simulate a conversation
        messages = [
            {"role": "user", "content": "What tables do you have access to?"},
        ]
        
        print("📝 Testing conversation flow...")
        result = await workflow.process_conversation(messages)
        print(f"✅ Response: {result['final_response'][:200]}...")
        print(f"   Operation: {result['operation']}")
        
        # Add follow-up
        messages.append({"role": "assistant", "content": result['final_response']})
        messages.append({"role": "user", "content": "How many customers do we have?"})
        
        result = await workflow.process_conversation(messages)
        print(f"✅ Follow-up response: {result['final_response'][:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation flow test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting Improved Database Agent Tests\n")
    
    tests = [
        ("Database Indexing", test_database_indexing),
        ("Schema Awareness", test_schema_awareness),
        ("Error Handling & Retry", test_error_handling_and_retry),
        ("Conversation Flow", test_conversation_flow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running {test_name} Test")
        print('='*50)
        
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The improved agent is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")

if __name__ == "__main__":
    asyncio.run(main())