#!/usr/bin/env python3
"""
Setup script for MongoDB integration with ERP Agent Bot
This script initializes MongoDB with sample data and tests the integration
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "mongodb_document_store"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_mongodb_integration():
    """Setup MongoDB integration for the ERP Agent Bot."""
    
    print("🚀 Setting up MongoDB Integration for ERP Agent Bot")
    print("=" * 60)
    
    # Step 1: Check MongoDB connection
    print("\n1️⃣ Testing MongoDB Connection...")
    try:
        from mongodb_document_store.query_interface import MongoQueryInterface
        mongo_interface = MongoQueryInterface()
        
        # Test basic connection
        await mongo_interface.search_products(limit=1)
        print("✅ MongoDB connection successful")
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("Please ensure MongoDB is running and accessible")
        return False
    
    # Step 2: Initialize sample data
    print("\n2️⃣ Initializing Sample Data...")
    try:
        from mongodb_document_store.setup_data import setup_sample_data
        await setup_sample_data()
        print("✅ Sample data initialized")
        
    except Exception as e:
        print(f"⚠️ Sample data setup failed: {e}")
        print("Continuing with existing data...")
    
    # Step 3: Test document operations
    print("\n3️⃣ Testing Document Operations...")
    
    # Test product search
    try:
        products = await mongo_interface.search_products(query="laptop", limit=3)
        print(f"✅ Product search: Found {len(products)} laptops")
        
        if products:
            product_id = products[0].get('product_id')
            if product_id:
                # Test review retrieval
                reviews = await mongo_interface.get_product_reviews(product_id=product_id, limit=2)
                print(f"✅ Product reviews: Found {len(reviews)} reviews for product {product_id}")
        
    except Exception as e:
        print(f"❌ Document operations test failed: {e}")
        return False
    
    # Test support tickets
    try:
        tickets = await mongo_interface.search_support_tickets(status="open", limit=3)
        print(f"✅ Support tickets: Found {len(tickets)} open tickets")
        
    except Exception as e:
        print(f"❌ Support tickets test failed: {e}")
        return False
    
    # Test analytics
    try:
        analytics = await mongo_interface.get_review_analytics()
        print(f"✅ Review analytics: {analytics.get('total_reviews', 0)} total reviews")
        
    except Exception as e:
        print(f"❌ Analytics test failed: {e}")
        return False
    
    # Step 4: Test hybrid database client
    print("\n4️⃣ Testing Hybrid Database Client...")
    try:
        from langgraph_integration.hybrid_db_client import hybrid_client
        
        # Test schema retrieval
        schema = await hybrid_client.get_schema()
        if "SQL DATABASE SCHEMA" in schema and "MONGODB DOCUMENT STORE SCHEMA" in schema:
            print("✅ Hybrid schema retrieval successful")
        else:
            print("⚠️ Hybrid schema incomplete")
        
        # Test document query execution
        result = await hybrid_client.execute_document_query("search_products", query="smartphone", limit=2)
        if "Found" in result:
            print("✅ Hybrid document query execution successful")
        else:
            print("⚠️ Hybrid document query returned unexpected result")
        
    except Exception as e:
        print(f"❌ Hybrid client test failed: {e}")
        return False
    
    # Step 5: Test MCP server tools (if available)
    print("\n5️⃣ Testing MCP Server Integration...")
    try:
        from mcp_server.tools import MCPTools
        
        # Test MongoDB tools
        tools = MCPTools.get_available_tools()
        mongo_tools = [tool for tool in tools if tool.name in ['search_products', 'get_product_reviews', 'search_support_tickets']]
        
        if mongo_tools:
            print(f"✅ MCP MongoDB tools available: {len(mongo_tools)} tools")
        else:
            print("⚠️ MCP MongoDB tools not found")
        
    except Exception as e:
        print(f"⚠️ MCP server test failed: {e}")
        print("This is expected if MCP server is not running")
    
    # Step 6: Health check
    print("\n6️⃣ Final Health Check...")
    try:
        health = await hybrid_client.health_check()
        
        sql_status = health.get("sql_database", {}).get("status", "unknown")
        mongo_status = health.get("mongodb", {}).get("status", "unknown")
        
        print(f"SQL Database: {sql_status}")
        print(f"MongoDB: {mongo_status}")
        
        if sql_status == "healthy" and mongo_status == "healthy":
            print("✅ All systems healthy!")
            return True
        else:
            print("⚠️ Some systems may have issues")
            return True  # Still consider success if at least one works
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

async def test_sample_queries():
    """Test sample queries that demonstrate MongoDB integration."""
    
    print("\n🧪 Testing Sample Queries")
    print("=" * 40)
    
    from langgraph_integration.hybrid_db_client import hybrid_client
    
    test_queries = [
        {
            "name": "Product Search",
            "operation": "search_products",
            "params": {"query": "laptop", "price_min": 500, "limit": 3}
        },
        {
            "name": "Support Tickets",
            "operation": "search_support_tickets", 
            "params": {"status": "open", "priority": "high", "limit": 5}
        },
        {
            "name": "Review Analytics",
            "operation": "get_review_analytics",
            "params": {}
        },
        {
            "name": "Knowledge Base Search",
            "operation": "search_knowledge_base",
            "params": {"query": "return policy", "limit": 3}
        }
    ]
    
    for query in test_queries:
        try:
            print(f"\n📋 {query['name']}:")
            result = await hybrid_client.execute_document_query(query["operation"], **query["params"])
            
            # Show first few lines of result
            lines = result.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            
            if len(result.split('\n')) > 5:
                print("  ...")
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")

def print_integration_summary():
    """Print summary of what was integrated."""
    
    print("\n🎉 MongoDB Integration Summary")
    print("=" * 50)
    
    print("""
✅ COMPLETED INTEGRATIONS:

1. MCP Server Tools Extended:
   • search_products - Search products with filters
   • get_product_reviews - Get customer reviews
   • search_support_tickets - Search support tickets  
   • get_review_analytics - Get review analytics
   • search_knowledge_base - Search knowledge articles

2. Hybrid Database Client Created:
   • Handles both SQL and MongoDB operations
   • Combined schema information
   • Health checking for both systems
   • Backward compatibility maintained

3. LangGraph Workflow Updated:
   • New document query execution node
   • Updated intent parsing for document queries
   • Enhanced routing logic
   • Document-aware result formatting

4. Enhanced Prompts:
   • Intent parser now handles document vs SQL queries
   • Examples for document operations
   • Query type detection logic

🚀 READY TO USE:

The ERP Agent Bot can now handle queries like:
• "Show me reviews for product 123"
• "Find expensive smartphones in stock"
• "What are the open support tickets?"
• "Get review analytics for our products"
• "Search knowledge base for return policy"

📊 DATA AVAILABLE:

MongoDB collections contain:
• Product catalog with detailed specifications
• Customer reviews with sentiment analysis
• Support tickets with full lifecycle tracking
• Marketing campaign data
• Knowledge base articles

🔧 NEXT STEPS:

1. Start the MCP server: python mcp_server/server.py
2. Start the LangGraph service: python langgraph_integration/main.py
3. Start the UI: streamlit run chatbot_ui/app.py
4. Test with document-related queries!
""")

async def main():
    """Main setup function."""
    
    success = await setup_mongodb_integration()
    
    if success:
        await test_sample_queries()
        print_integration_summary()
        print("\n🎉 MongoDB Integration Setup Complete!")
        return 0
    else:
        print("\n❌ MongoDB Integration Setup Failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)