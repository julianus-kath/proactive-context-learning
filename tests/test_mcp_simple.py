"""
Simple test for the MCP-compliant Crawling Agent.
"""
import json
import uuid
import pytest
from typing import Dict, Any, List, Optional

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest


class SimpleMockTranslator:
    """Simple mock translator for testing."""
    
    def translate(self, query: str) -> CrawlingContext:
        """Create a simple CrawlingContext for testing."""
        context = CrawlingContext(original_query=query)
        context.update_status("planning")
        
        # Create a simple task instruction
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=query,
            description="Find products with price > 100",
            data_sources=[DataSourceType.ERP],
            queries=[
                DataSourceQuery(
                    source_type=DataSourceType.ERP,
                    query_type=QueryType.SQL,
                    query="SELECT * FROM products WHERE price > 100",
                    parameters={}
                )
            ]
        )
        
        context.task_instruction = task
        context.thought = "I need to find products with price greater than 100 from the ERP system."
        context.plan = {
            "objective": "Find expensive products",
            "data_sources": ["erp"],
            "steps": [
                {
                    "step_number": 1,
                    "action": "Query ERP",
                    "description": "Get products with price > 100"
                }
            ]
        }
        
        # Add an action request
        action = ActionRequest.create_query_action(
            source="translator",
            data_source="erp",
            query="SELECT * FROM products WHERE price > 100",
            query_params={}
        )
        context.add_action_request(action)
        
        return context


class SimpleMockController:
    """Simple mock controller for testing."""
    
    def execute(self, context: CrawlingContext) -> CrawlingContext:
        """Execute the context and add mock observations."""
        context.update_status("acting")
        
        # Process each action request
        for action in context.action_requests:
            # Update action status
            context.update_action_status(action.action_id, "in_progress")
            
            # Create mock result
            mock_result = {
                "data": [
                    {"id": 1, "name": "Expensive Product 1", "price": 150},
                    {"id": 2, "name": "Expensive Product 2", "price": 200}
                ],
                "metadata": {
                    "row_count": 2,
                    "execution_time_ms": 42.5
                }
            }
            
            # Add observation
            context.add_observation(action.action_id, mock_result)
            
            # Update action status
            context.update_action_status(action.action_id, "completed")
        
        # Set final result but don't change status from "acting"
        context.set_final_result({
            "context_id": context.context_id,
            "original_query": context.original_query,
            "observations": context.observations,
            "metadata": {
                "execution_time": context.updated_at,
                "data_sources": ["erp"],
                "action_count": len(context.action_requests),
                "completed_action_count": len([a for a in context.action_requests if a.status == "completed"])
            }
        })
        
        return context


@pytest.fixture
def translator():
    """Fixture for the translator."""
    return SimpleMockTranslator()


@pytest.fixture
def controller():
    """Fixture for the controller."""
    return SimpleMockController()


def test_mcp_crawling_agent(translator, controller):
    """Test the MCP-compliant Crawling Agent with a simple query."""
    # Test query
    query = "Find all products with price greater than 100"
    
    # === PLANNING PHASE ===
    # Translate the query to a CrawlingContext with plan and action requests
    context = translator.translate(query)
    
    # Verify planning phase results
    assert context.status == "planning"
    assert context.original_query == query
    assert context.thought is not None
    assert "objective" in context.plan
    assert "data_sources" in context.plan
    assert len(context.action_requests) > 0
    
    # === ACTING PHASE ===
    # Execute the actions in the context
    updated_context = controller.execute(context)
    
    # Verify acting phase results
    # Note: status will be "completed" because set_final_result updates it
    assert updated_context.status == "completed"
    for action in updated_context.action_requests:
        assert action.status == "completed"
    
    # === OBSERVING PHASE ===
    # Verify observations
    assert "actions" in updated_context.observations
    
    for action_id, observation in updated_context.observations.get("actions", {}).items():
        action = updated_context.get_action_by_id(action_id)
        assert action is not None
        data = observation.get("data", {})
        assert isinstance(data, list)
        assert len(data) > 0
    
    # Verify final result
    assert updated_context.final_result is not None
    assert updated_context.final_result.get("context_id") == updated_context.context_id
    assert "metadata" in updated_context.final_result


# For running as a script
def main():
    """Run the test manually."""
    print("\n=== Testing MCP-Compliant Crawling Agent ===\n")
    
    # Initialize components
    translator = SimpleMockTranslator()
    controller = SimpleMockController()
    
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
        print(f"     Query: {action.parameters.get('query', 'N/A')}")
    
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
                if isinstance(data, list):
                    print(f"    Retrieved {len(data)} records")
                    if data:
                        print(f"    Sample: {data[0]}")
    
    # Print the final result
    if updated_context.final_result:
        print("\nFinal Result:")
        print(f"  Context ID: {updated_context.final_result.get('context_id')}")
        print(f"  Metadata: {json.dumps(updated_context.final_result.get('metadata', {}), indent=2)}")
    
    print("\n=== Test Completed ===\n")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())