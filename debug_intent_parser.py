#!/usr/bin/env python3
"""
Debug script for IntentParserAgent
"""
import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_integration.agents.intent_parser.agent import IntentParserAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_intent_parser():
    """Test the intent parser with various queries."""
    agent = IntentParserAgent()

    test_queries = [
        "How many customers do we have?",
        "Show me all customers from New York",
        "What were our total sales last month?",
        "Which products have the highest profit margins?",
        "What tables are available in the database?"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing query: {query}")
        print(f"{'='*60}")

        try:
            result = await agent.parse(query)
            print("✅ SUCCESS:")
            print(f"  operation: {result.get('operation')}")
            print(f"  primary_entities: {result.get('primary_entities', [])}")
            print(f"  metrics: {result.get('metrics', [])}")
            print(f"  filters: {result.get('filters', [])}")
            print(f"  time_window: {result.get('time_window')}")
            print(f"  keywords_for_discovery: {result.get('keywords_for_discovery', [])}")
            print(f"  confidence: {result.get('confidence', 0):.2f}")

        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_intent_parser())
