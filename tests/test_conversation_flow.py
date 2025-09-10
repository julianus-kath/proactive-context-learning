#!/usr/bin/env python3
"""
Test script for conversation flow improvements
Tests the new context-aware chatbot functionality
"""

import requests
import json
import time
from typing import List, Dict

# Configuration
LANGGRAPH_URL = "http://localhost:5001"
API_KEY = "supersecretapikey"  # Default API key

def test_conversation_flow():
    """Test the conversation flow with context awareness."""
    
    print("🧪 Testing Conversation Flow")
    print("=" * 50)
    
    # Test conversation messages
    messages = []
    
    def send_message(user_input: str) -> Dict:
        """Send a message and get response."""
        # Add user message to conversation
        messages.append({"role": "user", "content": user_input})
        
        payload = {
            "messages": messages.copy(),
            "api_key": API_KEY
        }
        
        print(f"\n📤 Sending: {user_input}")
        print(f"📋 Messages count: {len(messages)}")
        print(f"🔍 Payload preview: {json.dumps(payload['messages'][-2:], indent=2)}")
        
        try:
            response = requests.post(
                f"{LANGGRAPH_URL}/process_conversation",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get("final_response", "No response")
                operation = result.get("operation", "unknown")
                
                print(f"📥 Response ({operation}): {bot_response}")
                
                # Add bot response to conversation
                messages.append({"role": "assistant", "content": bot_response})
                
                return result
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return {"error": str(e)}
    
    # Test 1: Initial query with location
    print("\n🔍 Test 1: Specific query with location")
    result1 = send_message("How many customers in New York?")
    
    # Test 2: Follow-up question using context
    print("\n🔍 Test 2: Follow-up question using context")
    result2 = send_message("What are their names?")
    
    # Test 3: Vague query that should trigger clarification
    print("\n🔍 Test 3: Vague query (should ask for clarification)")
    result3 = send_message("Show me sales data")
    
    # Test 4: Response to clarification
    if result3.get("operation") == "clarify":
        print("\n🔍 Test 4: Responding to clarification")
        result4 = send_message("For last month")
    
    # Test 5: Another context-dependent query
    print("\n🔍 Test 5: Another context query")
    result5 = send_message("How many products do we have?")
    
    print("\n🔍 Test 6: Follow-up about products")
    result6 = send_message("Which category has the most?")
    
    print("\n📊 Test Summary")
    print("=" * 50)
    print(f"Total messages exchanged: {len(messages)}")
    print(f"Final conversation length: {len(messages)} messages")
    
    # Show final conversation
    print("\n💬 Final Conversation:")
    for i, msg in enumerate(messages, 1):
        role = "👤 USER" if msg["role"] == "user" else "🤖 BOT"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        print(f"{i:2d}. {role}: {content}")

def test_service_health():
    """Test if the service is running."""
    try:
        response = requests.get(f"{LANGGRAPH_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ LangGraph service is healthy")
            return True
        else:
            print(f"❌ Service health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to service: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Conversation Flow Test Suite")
    print("Testing context-aware chatbot improvements")
    print("=" * 60)
    
    # Check service health
    if not test_service_health():
        print("\n💡 Make sure to start the services:")
        print("   1. MCP Server: cd mcp_server && python start_server.py")
        print("   2. LangGraph Service: cd chatbot_ui && python langgraph_service.py")
        return
    
    # Run conversation tests
    test_conversation_flow()
    
    print("\n🎉 Test completed!")
    print("\n💡 Next steps:")
    print("   1. Check the logs for payload details")
    print("   2. Test the Streamlit app: cd chatbot_ui && streamlit run app.py")
    print("   3. Try the conversation: 'How many customers in New York?' → 'What are their names?'")

if __name__ == "__main__":
    main()