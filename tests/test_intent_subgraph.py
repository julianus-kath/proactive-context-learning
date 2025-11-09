#!/usr/bin/env python3
"""
Test script for the new IntentParserAgent LangGraph subgraph.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables from .env file
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

from langgraph_integration.agents.intent_parser.agent import IntentParserAgent
from langgraph_integration.contracts.state import BaseState

async def test_intent_subgraph():
    """Test the IntentParserAgent subgraph with various queries."""
    print("🧠 Testing IntentParserAgent LangGraph Subgraph")
    print("=" * 60)

    # Initialize the agent
    agent = IntentParserAgent()
    print("✅ IntentParserAgent initialized")

    # Build the subgraph
    subgraph = agent.build_subgraph()
    print("✅ Subgraph built")

    # Test queries
    test_queries = [
        "How many customers do we have?",
        "What tables are available?",
        "Show me sales last month",
        "Which products have inventory below 100?",
        "Is the database healthy?",  # Should trigger fast path
        "This is an unclear query that doesn't make sense",  # Should trigger clarification
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {query}")
        print(f"{'='*60}")

        try:
            # Create initial state
            initial_state = BaseState(user_input=query)

            # Run the subgraph
            result = await subgraph.ainvoke(initial_state)

            # Extract intent
            intent = result.get("intent", {})
            needs_clarification = intent.get("needs_clarification", False)

            print("📋 Intent Results:")
            print(f"   Operation: {intent.get('operation')}")
            print(f"   Confidence: {intent.get('confidence', 0):.2f}")
            print(f"   Primary Entities: {intent.get('primary_entities', [])}")
            print(f"   Keywords: {intent.get('keywords_for_discovery', [])}")
            print(f"   Needs Clarification: {needs_clarification}")

            if needs_clarification:
                print(f"   Clarification Question: {intent.get('clarification_question', 'N/A')}")
                print(f"   Suggested Options: {intent.get('suggested_options', [])}")
                print(f"   Reason: {intent.get('ambiguity_reason', 'N/A')}")

            print("✅ Test passed")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("🎉 IntentParserAgent subgraph testing complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(test_intent_subgraph())
