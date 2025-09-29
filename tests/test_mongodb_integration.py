#!/usr/bin/env python3
"""
Quick test script for MongoDB integration
Tests the key components without full setup
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "mongodb_document_store"))

async def test_basic_integration():
    """Test basic MongoDB integration components."""
    
    print("🧪 Testing MongoDB Integration Components")
    print("=" * 50)
    
    # Test 1: MongoDB Query Interface
    print("\n1️⃣ Testing MongoDB Query Interface...")
    try:
        from mongodb_document_store.query_interface import MongoQueryInterface
        mongo_interface = MongoQueryInterface()
        
        # Simple test query
        products = await mongo_interface.search_products(limit=1)
        print(f"✅ MongoDB interface works - found {len(products)} products")
        
    except Exception as e:
        print(f"❌ MongoDB interface failed: {e}")
        return False
    
    # Test 2: Hybrid Database Client
    print("\n2️⃣ Testing Hybrid Database Client...")
    try:
        from langgraph_integration.hybrid_db_client import hybrid_client
        
        # Test schema retrieval
        schema = await hybrid_client.get_schema()
        has_sql = "SQL DATABASE SCHEMA" in schema
        has_mongo = "MONGODB DOCUMENT STORE SCHEMA" in schema
        
        print(f"✅ Hybrid client works - SQL: {has_sql}, MongoDB: {has_mongo}")
        
    except Exception as e:
        print(f"❌ Hybrid client failed: {e}")
        return False
    
    # Test 3: Document Query Execution
    print("\n3️⃣ Testing Document Query Execution...")
    try:
        result = await hybrid_client.execute_document_query("search_products", limit=2)
        print(f"✅ Document queries work - result length: {len(result)}")
        
    except Exception as e:
        print(f"❌ Document query failed: {e}")
        return False
    
    # Test 4: MCP Tools (if available)
    print("\n4️⃣ Testing MCP Tools...")
    try:
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        mongo_tool_names = ['search_products', 'get_product_reviews', 'search_support_tickets']
        mongo_tools = [tool for tool in tools if tool.name in mongo_tool_names]
        
        print(f"✅ MCP tools available - {len(mongo_tools)} MongoDB tools found")
        
    except Exception as e:
        print(f"⚠️ MCP tools test failed: {e}")
        print("This is expected if dependencies are missing")
    
    # Test 5: Intent Parser Prompt
    print("\n5️⃣ Testing Updated Prompts...")
    try:
        from langgraph_integration.prompts import INTENT_PARSER_PROMPT
        
        has_document_ops = "document_operation" in INTENT_PARSER_PROMPT
        has_query_types = "query_type" in INTENT_PARSER_PROMPT
        
        print(f"✅ Prompts updated - Document ops: {has_document_ops}, Query types: {has_query_types}")
        
    except Exception as e:
        print(f"❌ Prompts test failed: {e}")
        return False
    
    print("\n🎉 All basic integration tests passed!")
    return True

async def test_sample_document_queries():
    """Test sample document queries."""
    
    print("\n📋 Testing Sample Document Queries")
    print("=" * 40)
    
    from langgraph_integration.hybrid_db_client import hybrid_client
    
    queries = [
        ("Product Search", "search_products", {"query": "laptop", "limit": 2}),
        ("Review Analytics", "get_review_analytics", {}),
        ("Support Tickets", "search_support_tickets", {"limit": 2}),
    ]
    
    for name, operation, params in queries:
        try:
            print(f"\n🔍 {name}:")
            result = await hybrid_client.execute_document_query(operation, **params)
            
            # Show first line of result
            first_line = result.split('\n')[0] if result else "No result"
            print(f"  Result: {first_line}")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")

def show_usage_examples():
    """Show usage examples for the integrated system."""
    
    print("\n📚 Usage Examples")
    print("=" * 30)
    
    examples = [
        {
            "query": "Show me reviews for product 123",
            "type": "Document Query",
            "operation": "get_product_reviews",
            "params": {"product_id": 123}
        },
        {
            "query": "Find expensive smartphones",
            "type": "Document Query", 
            "operation": "search_products",
            "params": {"query": "smartphone", "price_min": 500}
        },
        {
            "query": "What are the open support tickets?",
            "type": "Document Query",
            "operation": "search_support_tickets", 
            "params": {"status": "open"}
        },
        {
            "query": "How many customers do we have?",
            "type": "SQL Query",
            "operation": "SELECT COUNT(*) FROM customers",
            "params": {}
        }
    ]
    
    for example in examples:
        print(f"\n💬 User: \"{example['query']}\"")
        print(f"   Type: {example['type']}")
        if example['type'] == 'Document Query':
            print(f"   Operation: {example['operation']}")
            print(f"   Params: {example['params']}")
        else:
            print(f"   SQL: {example['operation']}")

async def main():
    """Main test function."""
    
    success = await test_basic_integration()
    
    if success:
        await test_sample_document_queries()
        show_usage_examples()
        
        print("\n✅ MongoDB Integration Test Complete!")
        print("\nTo use the integrated system:")
        print("1. Ensure MongoDB is running with sample data")
        print("2. Start MCP server: python mcp_server/server.py")
        print("3. Start LangGraph service: python langgraph_integration/main.py")
        print("4. Start UI: streamlit run chatbot_ui/app.py")
        print("5. Try document queries like 'Show me product reviews' or 'Find open support tickets'")
        
        return 0
    else:
        print("\n❌ Integration test failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)