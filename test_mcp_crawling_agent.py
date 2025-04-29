"""
Test script for the MCP-compliant Crawling Agent.
"""
import sys
import json
import uuid
from typing import Dict, Any

from crawling_agent.translator.query_translator import QueryTranslator
from crawling_agent.controller.crawling_controller import CrawlingAgentController
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
from crawling_agent.models.task_instruction import DataSourceType


def main():
    """Test the MCP-compliant Crawling Agent with a simple query."""
    print("\n=== Testing MCP-Compliant Crawling Agent ===\n")
    
    # Initialize components
    translator = QueryTranslator(use_mock=True)
    controller = CrawlingAgentController(mock_mode=True)
    
    # Test query
    query = "Find all products with price greater than 100"
    print(f"Query: {query}")
    
    # === PLANNING PHASE ===
    print("\n--- PLANNING PHASE ---")
    
    # Translate the query to a CrawlingContext with plan and action requests
    context = translator.translate(query)
    
    # Print the context details
    print(f"Context ID: {context.context_id}")
    print(f"Status: {context.status}")
    print(f"Thought: {context.thought}")
    print("\nPlan:")
    print(f"  Objective: {context.plan.get('objective', 'N/A')}")
    print(f"  Data Sources: {', '.join(context.plan.get('data_sources', []))}")
    print("\nAction Requests:")
    for i, action in enumerate(context.action_requests):
        print(f"  {i+1}. {action.action_type} (ID: {action.action_id})")
        print(f"     Query: {action.parameters.get('query', 'N/A')[:60]}...")
    
    # === ACTING PHASE ===
    print("\n--- ACTING PHASE ---")
    
    # Execute the actions in the context
    updated_context = controller.execute(context)
    
    # Print the execution results
    print(f"Updated Context Status: {updated_context.status}")
    print(f"Action Statuses:")
    for action in updated_context.action_requests:
        print(f"  {action.action_type}: {action.status}")
    
    # === OBSERVING PHASE ===
    print("\n--- OBSERVING PHASE ---")
    
    # Print the observations
    if "actions" in updated_context.observations:
        print("Observations:")
        for action_id, observation in updated_context.observations.get("actions", {}).items():
            action = updated_context.get_action_by_id(action_id)
            if action:
                print(f"  {action.action_type}:")
                data = observation.get("data", {})
                if "data" in data:
                    print(f"    Retrieved {len(data['data'])} records")
                    if data['data']:
                        print(f"    Sample: {data['data'][0]}")
    
    # Print the final result
    if updated_context.final_result:
        print("\nFinal Result:")
        print(f"  Context ID: {updated_context.final_result.get('context_id')}")
        print(f"  Metadata: {json.dumps(updated_context.final_result.get('metadata', {}), indent=2)}")
    
    print("\n=== Test Completed ===\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())