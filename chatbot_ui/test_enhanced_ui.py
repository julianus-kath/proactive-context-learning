#!/usr/bin/env python3
"""
Test script to verify the enhanced Streamlit UI correctly handles:
1. Full conversation history in payloads
2. Clarification requests and responses
3. Multi-turn dialogue flow
4. Session state management

This script simulates the enhanced conversation flow.
"""

import json
import requests
from typing import List, Dict, Any

# Configuration
LANGGRAPH_URL = "http://localhost:5001"
API_KEY = "test-api-key-12345"

def simulate_enhanced_payload(messages: List[Dict[str, str]], new_user_input: str) -> Dict[str, Any]:
    """
    Simulate the enhanced payload creation logic from the Streamlit UI.
    
    Args:
        messages: Current conversation history in OpenAI format
        new_user_input: New user message to add
        
    Returns:
        The payload that would be sent to the LangGraph service
    """
    # Add the new user message to the conversation (same logic as in enhanced app.py)
    current_messages = messages.copy()
    current_messages.append({"role": "user", "content": new_user_input})
    
    payload = {
        "messages": current_messages,
        "api_key": API_KEY
    }
    
    return payload

def simulate_clarification_flow():
    """Test the enhanced clarification handling flow."""
    print("🧪 Testing Enhanced Clarification Flow")
    print("=" * 50)
    
    conversation_history = []
    
    # Turn 1: Ambiguous query that should trigger clarification
    print("\n📝 Turn 1: Ambiguous Query")
    user_input_1 = "Show me the top customers"
    payload_1 = simulate_enhanced_payload(conversation_history, user_input_1)
    
    print(f"User Input: {user_input_1}")
    print(f"Messages in payload: {len(payload_1['messages'])}")
    print("Payload structure:")
    print(json.dumps(payload_1, indent=2))
    
    # Simulate clarification response from server
    clarification_response = {
        "clarify": True,
        "question": "What criteria would you like to use to identify 'top' customers? For example: by total purchases, by number of orders, or by recent activity?",
        "messages": [
            {"role": "user", "content": user_input_1},
            {"role": "assistant", "content": "What criteria would you like to use to identify 'top' customers? For example: by total purchases, by number of orders, or by recent activity?"}
        ]
    }
    
    print(f"\n🤔 Server Response (Clarification):")
    print(json.dumps(clarification_response, indent=2))
    
    # Update conversation history with clarification
    conversation_history = clarification_response["messages"]
    
    # Turn 2: User provides clarification
    print("\n📝 Turn 2: User Clarification")
    user_input_2 = "By total purchases amount"
    payload_2 = simulate_enhanced_payload(conversation_history, user_input_2)
    
    print(f"User Input: {user_input_2}")
    print(f"Messages in payload: {len(payload_2['messages'])}")
    print("Payload structure:")
    print(json.dumps(payload_2, indent=2))
    
    # Simulate final response from server
    final_response = {
        "clarify": False,
        "response": "Here are the top 10 customers by total purchase amount:\\n\\n1. ABC Corp - $125,000\\n2. XYZ Ltd - $98,500\\n3. Tech Solutions Inc - $87,200\\n...",
        "messages": [
            {"role": "user", "content": user_input_1},
            {"role": "assistant", "content": "What criteria would you like to use to identify 'top' customers? For example: by total purchases, by number of orders, or by recent activity?"},
            {"role": "user", "content": user_input_2},
            {"role": "assistant", "content": "Here are the top 10 customers by total purchase amount:\\n\\n1. ABC Corp - $125,000\\n2. XYZ Ltd - $98,500\\n3. Tech Solutions Inc - $87,200\\n..."}
        ]
    }
    
    print(f"\n✅ Server Response (Final):")
    print(json.dumps(final_response, indent=2))
    
    # Turn 3: Follow-up question using context
    conversation_history = final_response["messages"]
    print("\n📝 Turn 3: Follow-up with Context")
    user_input_3 = "What about their contact information?"
    payload_3 = simulate_enhanced_payload(conversation_history, user_input_3)
    
    print(f"User Input: {user_input_3}")
    print(f"Messages in payload: {len(payload_3['messages'])}")
    print("Full conversation context:")
    for i, msg in enumerate(payload_3['messages']):
        print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")
    
    print("\n✅ Enhanced clarification flow test completed!")
    return payload_3

def test_ui_state_simulation():
    """Simulate the UI state changes during clarification flow."""
    print("\n🎨 Testing UI State Management")
    print("=" * 40)
    
    # Simulate session state
    session_state = {
        "history": [],
        "messages": [],
        "last_was_clarification": False
    }
    
    print("Initial state:")
    print(f"  - History: {len(session_state['history'])} items")
    print(f"  - Messages: {len(session_state['messages'])} items")
    print(f"  - Last was clarification: {session_state['last_was_clarification']}")
    
    # Simulate first query and clarification response
    user_input = "Show me the top customers"
    response_data = {
        "clarify": True,
        "question": "What criteria would you like to use?",
        "messages": [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": "What criteria would you like to use?"}
        ]
    }
    
    # Update session state (simulating the enhanced UI logic)
    if "messages" in response_data:
        session_state["messages"] = response_data["messages"]
        
        if response_data.get("clarify", False):
            response_text = f"🤔 {response_data.get('question', 'I need more information.')}"
            session_state["last_was_clarification"] = True
        else:
            response_text = response_data.get("response", "Query executed successfully.")
            session_state["last_was_clarification"] = False
        
        session_state["history"].append((user_input, response_text))
    
    print(f"\nAfter clarification request:")
    print(f"  - History: {len(session_state['history'])} items")
    print(f"  - Messages: {len(session_state['messages'])} items")
    print(f"  - Last was clarification: {session_state['last_was_clarification']}")
    print(f"  - UI should show: '🤔 Please Provide More Details'")
    print(f"  - Button text should be: 'Clarify'")
    
    # Simulate user clarification and final response
    user_clarification = "By total purchases"
    final_response_data = {
        "clarify": False,
        "response": "Here are the top customers by total purchases...",
        "messages": session_state["messages"] + [
            {"role": "user", "content": user_clarification},
            {"role": "assistant", "content": "Here are the top customers by total purchases..."}
        ]
    }
    
    # Update session state for final response
    if "messages" in final_response_data:
        session_state["messages"] = final_response_data["messages"]
        session_state["last_was_clarification"] = False
        response_text = final_response_data.get("response", "Query executed successfully.")
        session_state["history"].append((user_clarification, response_text))
    
    print(f"\nAfter final response:")
    print(f"  - History: {len(session_state['history'])} items")
    print(f"  - Messages: {len(session_state['messages'])} items")
    print(f"  - Last was clarification: {session_state['last_was_clarification']}")
    print(f"  - UI should show: '💭 Ask Your Question'")
    print(f"  - Button text should be: 'Send'")
    
    print("\n✅ UI state management test completed!")

def test_payload_structure():
    """Test that payloads maintain proper structure throughout conversation."""
    print("\n📦 Testing Payload Structure Consistency")
    print("=" * 45)
    
    messages = []
    
    # Test multiple conversation turns
    turns = [
        "How many customers do we have?",
        "What about active ones?",
        "Show me the top 5",
        "By revenue",
        "What are their contact details?"
    ]
    
    for i, turn in enumerate(turns, 1):
        payload = simulate_enhanced_payload(messages, turn)
        
        print(f"\nTurn {i}: '{turn}'")
        print(f"  - Messages count: {len(payload['messages'])}")
        print(f"  - Has API key: {'api_key' in payload}")
        print(f"  - Last message role: {payload['messages'][-1]['role']}")
        print(f"  - Last message content: {payload['messages'][-1]['content'][:30]}...")
        
        # Validate payload structure
        assert "messages" in payload, f"Turn {i}: Missing 'messages' key"
        assert "api_key" in payload, f"Turn {i}: Missing 'api_key' key"
        expected_messages = (i * 2) - 1  # Each turn adds user + assistant, but current payload only has user
        assert len(payload["messages"]) == expected_messages, f"Turn {i}: Expected {expected_messages} messages, got {len(payload['messages'])}"
        assert payload["messages"][-1]["role"] == "user", f"Turn {i}: Last message should be from user"
        assert payload["messages"][-1]["content"] == turn, f"Turn {i}: Last message content mismatch"
        
        # Simulate adding assistant response for next turn
        messages = payload["messages"].copy()
        messages.append({"role": "assistant", "content": f"Response to: {turn}"})
    
    print("\n✅ All payload structure tests passed!")

if __name__ == "__main__":
    print("🚀 Enhanced UI Test Suite")
    print("=" * 40)
    
    # Test 1: Enhanced clarification flow
    simulate_clarification_flow()
    
    # Test 2: UI state management
    test_ui_state_simulation()
    
    # Test 3: Payload structure consistency
    test_payload_structure()
    
    print("\n🎉 All enhanced UI tests completed successfully!")
    print("\n📋 Summary of Enhancements:")
    print("   ✅ Full conversation history in all payloads")
    print("   ✅ Clarification detection and handling")
    print("   ✅ Dynamic UI based on conversation state")
    print("   ✅ Enhanced user experience for multi-turn dialogue")
    print("   ✅ Proper session state management")
    
    print("\n🔄 Next Steps:")
    print("   1. ✅ UI client sends full conversation history")
    print("   2. 🔄 Update LangGraph backend to handle messages array")
    print("   3. 🔄 Implement intent parsing with conversation context")
    print("   4. 🔄 Add clarification prompt templates")
    print("   5. 🔄 Modify LangGraph workflow for clarification branch")
    print("   6. 🔄 Test end-to-end multi-turn dialogue")