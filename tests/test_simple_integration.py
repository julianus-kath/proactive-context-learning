"""
Simple integration test for the MCP-compliant Crawling Agent.
"""
import pytest
import uuid
from typing import Dict, Any, List, Optional

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest


class TestSimpleIntegration:
    """Test class for simple integration testing."""
    
    def test_simple_flow(self):
        """Test a simple flow from planning to execution."""
        # Natural language query
        nl_query = "Find all products with price greater than 100"
        
        # === PLANNING PHASE ===
        # Create a context manually
        context = CrawlingContext(original_query=nl_query)
        context.update_status("planning")
        
        # Create a simple task instruction
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=nl_query,
            description="Find products with price > 100",
            data_sources=[DataSourceType.ERP, DataSourceType.DOCUMENT_STORAGE],
            queries=[
                DataSourceQuery(
                    source_type=DataSourceType.ERP,
                    query_type=QueryType.SQL,
                    query="SELECT * FROM products WHERE price > 100",
                    parameters={}
                ),
                DataSourceQuery(
                    source_type=DataSourceType.DOCUMENT_STORAGE,
                    query_type=QueryType.MONGODB,
                    query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
                    parameters={}
                )
            ]
        )
        
        context.task_instruction = task
        context.thought = "I need to find products with price greater than 100 from all data sources."
        context.plan = {
            "objective": "Find expensive products",
            "data_sources": ["erp", "document_storage"],
            "steps": [
                {
                    "step_number": 1,
                    "action": "Query all data sources",
                    "description": "Get products with price > 100"
                }
            ]
        }
        
        # Add action requests
        erp_action = ActionRequest.create_query_action(
            source="translator",
            data_source="erp",
            query="SELECT * FROM products WHERE price > 100",
            query_params={}
        )
        context.add_action_request(erp_action)
        
        doc_action = ActionRequest.create_query_action(
            source="translator",
            data_source="document_storage",
            query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
            query_params={}
        )
        context.add_action_request(doc_action)
        
        # Verify planning phase results
        assert context.status == "planning"
        assert context.original_query == nl_query
        assert context.thought is not None
        assert "objective" in context.plan
        assert "data_sources" in context.plan
        assert len(context.action_requests) == 2
        
        # === ACTING PHASE ===
        # Create a simple controller
        class SimpleController:
            def execute(self, ctx):
                ctx.update_status("acting")
                
                # Process each action request
                for action in ctx.action_requests:
                    # Update action status
                    ctx.update_action_status(action.action_id, "in_progress")
                    
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
                    ctx.add_observation(action.action_id, mock_result)
                    
                    # Update action status
                    ctx.update_action_status(action.action_id, "completed")
                
                # Set final result
                ctx.set_final_result({
                    "context_id": ctx.context_id,
                    "original_query": ctx.original_query,
                    "observations": ctx.observations,
                    "metadata": {
                        "execution_time": ctx.updated_at,
                        "data_sources": ["erp", "document_storage"],
                        "action_count": len(ctx.action_requests),
                        "completed_action_count": len([a for a in ctx.action_requests if a.status == "completed"])
                    }
                })
                
                return ctx
        
        # Execute the actions in the context
        controller = SimpleController()
        updated_context = controller.execute(context)
        
        # Verify acting phase results
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
            assert isinstance(data["data"], list)
            assert len(data["data"]) > 0
        
        # Verify final result
        assert updated_context.final_result is not None
        assert updated_context.final_result.get("context_id") == updated_context.context_id
        assert "metadata" in updated_context.final_result


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])