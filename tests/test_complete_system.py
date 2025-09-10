#!/usr/bin/env python3
"""
Complete System Test - Phase 3 Blueprint
Tests the entire chatbot system end-to-end.
"""

import requests
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:5001")
API_KEY = os.getenv("API_KEY", "supersecretapikey")

def test_query(query: str) -> dict:
    """Test a single query against the LangGraph service."""
    try:
        response = requests.post(
            f"{LANGGRAPH_URL}/process_query",
            json={
                "user_input": query,
                "api_key": API_KEY
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "response": response.json()
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """Test the complete system with the blueprint queries."""
    print("🤖 ERP Chatbot System - Complete Test")
    print("=" * 60)
    
    # Test queries from the blueprint
    test_queries = [
        "How many customers do we have?",
        "What's our top-selling product?",
        "Show me all tables in the database",
        "What is the database schema?",
        "Show me sample data from the customers table"
    ]
    
    print(f"🔗 Testing LangGraph service at: {LANGGRAPH_URL}")
    print(f"🔑 Using API key: {API_KEY[:10]}...")
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"📝 Test {i}: {query}")
        print("-" * 40)
        
        result = test_query(query)
        
        if result["success"]:
            response_data = result["response"]
            final_response = response_data.get("final_response", "No response")
            status = response_data.get("status", "unknown")
            
            print(f"✅ Status: {status}")
            print(f"🤖 Response: {final_response[:200]}...")
            if len(final_response) > 200:
                print("    (truncated)")
        else:
            print(f"❌ Error: {result['error']}")
        
        print()
        time.sleep(1)  # Brief pause between queries
    
    print("🎉 System test completed!")
    print()
    print("📋 Next Steps:")
    print("1. Start Streamlit UI: streamlit run app.py")
    print("2. Open browser to: http://localhost:8501")
    print("3. Test the queries in the web interface")
    print()
    print("🔧 Services Status:")
    
    # Check service health
    try:
        health_response = requests.get(f"{LANGGRAPH_URL}/health", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ LangGraph Service: {health_data.get('status', 'unknown')}")
            print(f"   Workflow Ready: {health_data.get('workflow_ready', False)}")
        else:
            print(f"❌ LangGraph Service: HTTP {health_response.status_code}")
    except Exception as e:
        print(f"❌ LangGraph Service: {e}")
    
    # Check MCP server
    try:
        mcp_response = requests.get("http://localhost:8000/health", timeout=5)
        if mcp_response.status_code == 200:
            mcp_data = mcp_response.json()
            print(f"✅ MCP Server: {mcp_data.get('status', 'unknown')}")
            print(f"   Database: {mcp_data.get('database', 'unknown')}")
        else:
            print(f"❌ MCP Server: HTTP {mcp_response.status_code}")
    except Exception as e:
        print(f"❌ MCP Server: {e}")

if __name__ == "__main__":
    main()