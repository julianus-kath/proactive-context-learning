#!/usr/bin/env python3
"""
Test script to verify the "A:" prefix issue is fixed.
This script tests the LangGraph service to ensure responses don't start with "A:".
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_langgraph_service():
    """Test the LangGraph service for the A: prefix issue."""
    
    # Service configuration
    service_url = "http://localhost:5001"
    api_key = os.getenv("API_KEY", "supersecretapikey")
    
    # Test queries that previously showed the "A:" prefix
    test_queries = [
        "How many customers do we have?",
        "What tables are in the database?",
        "Show me the database schema",
        "What products do we sell?",
        "How many orders were placed last month?"
    ]
    
    print("🧪 Testing LangGraph Service for 'A:' prefix issue")
    print("=" * 60)
    print(f"Service URL: {service_url}")
    print(f"API Key: {api_key[:10]}...")
    print()
    
    # Check if service is running
    try:
        health_response = requests.get(f"{service_url}/health", timeout=5)
        if health_response.status_code != 200:
            print("❌ LangGraph service is not running or not healthy")
            print("Please start it with: python langgraph_service.py")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to LangGraph service")
        print("Please start it with: python langgraph_service.py")
        return False
    
    print("✅ LangGraph service is running")
    print()
    
    # Test each query
    all_tests_passed = True
    
    for i, query in enumerate(test_queries, 1):
        print(f"🔍 Test {i}: {query}")
        
        try:
            # Send request to LangGraph service
            response = requests.post(
                f"{service_url}/process_query",
                json={
                    "user_input": query,
                    "api_key": api_key
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                final_response = result.get("final_response", "")
                
                # Check if response starts with "A:"
                if final_response.strip().startswith("A:"):
                    print(f"❌ FAILED: Response starts with 'A:'")
                    print(f"   Response: {final_response[:100]}...")
                    all_tests_passed = False
                else:
                    print(f"✅ PASSED: No 'A:' prefix")
                    print(f"   Response: {final_response[:100]}...")
                
            else:
                print(f"❌ HTTP Error {response.status_code}: {response.text}")
                all_tests_passed = False
                
        except requests.exceptions.Timeout:
            print("❌ Request timed out")
            all_tests_passed = False
        except Exception as e:
            print(f"❌ Error: {e}")
            all_tests_passed = False
        
        print()
    
    # Summary
    print("=" * 60)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED: No 'A:' prefix found in responses!")
        print("The fix has been successfully applied.")
    else:
        print("❌ SOME TESTS FAILED: 'A:' prefix still appears in responses")
        print("The LangGraph service may need to be restarted to pick up the changes.")
        print("Try: Ctrl+C to stop the service, then restart with 'python langgraph_service.py'")
    
    return all_tests_passed

def main():
    """Main test function."""
    print("🔧 A: Prefix Fix Verification")
    print("This script tests if the 'A:' prefix issue has been resolved.")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("langgraph_service.py"):
        print("❌ Please run this script from the chatbot_ui directory")
        return
    
    # Run the test
    success = test_langgraph_service()
    
    if success:
        print("\n💡 The fix is working! Your chatbot responses should no longer start with 'A:'")
    else:
        print("\n💡 If tests failed, try restarting the LangGraph service:")
        print("   1. Stop the current service (Ctrl+C)")
        print("   2. Restart with: python langgraph_service.py")
        print("   3. Run this test again: python test_a_prefix_fix.py")

if __name__ == "__main__":
    main()