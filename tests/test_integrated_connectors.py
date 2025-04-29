"""
Integration test for all connectors working together.
"""
import pytest
import uuid
from typing import Dict, Any, List

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
from crawling_agent.connectors.erp_connector import ERPConnector
from crawling_agent.connectors.document_storage_connector import DocumentStorageConnector
from crawling_agent.connectors.knowledge_graph_connector import KnowledgeGraphConnector
from crawling_agent.translator.query_translator import QueryTranslator
from crawling_agent.controller.crawling_controller import CrawlingAgentController


class TestIntegratedConnectors:
    """Test class for integrated connector testing."""
    
    @pytest.fixture
    def mock_connectors(self):
        """Create mock connectors for testing."""
        return {
            "erp": ERPConnector(mock_mode=True),
            "document_storage": DocumentStorageConnector(mock_mode=True),
            "knowledge_graph": KnowledgeGraphConnector(mock_mode=True)
        }
    
    @pytest.fixture
    def mock_translator(self):
        """Create a mock translator for testing."""
        return QueryTranslator(use_mock=True)
    
    @pytest.fixture
    def mock_controller(self):
        """Create a mock controller for testing."""
        return CrawlingAgentController(mock_mode=True)
    
    def test_product_query_all_connectors(self, mock_connectors):
        """Test a product query against all connectors."""
        # Natural language query
        nl_query = "Find all products with price greater than 100"
        
        # Create a task instruction with queries for all data sources
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=nl_query,
            description="Find expensive products across all data sources",
            data_sources=[
                DataSourceType.ERP, 
                DataSourceType.DOCUMENT_STORAGE, 
                DataSourceType.KNOWLEDGE_GRAPH
            ],
            queries=[
                # ERP query
                DataSourceQuery(
                    source_type=DataSourceType.ERP,
                    query_type=QueryType.SQL,
                    query="SELECT * FROM products WHERE price > 100",
                    parameters={}
                ),
                # Document Storage query
                DataSourceQuery(
                    source_type=DataSourceType.DOCUMENT_STORAGE,
                    query_type=QueryType.MONGODB,
                    query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
                    parameters={}
                ),
                # Knowledge Graph query
                DataSourceQuery(
                    source_type=DataSourceType.KNOWLEDGE_GRAPH,
                    query_type=QueryType.SPARQL,
                    query="""
                    PREFIX product: <http://example.org/product#>
                    SELECT ?product ?name ?price
                    WHERE {
                        ?product product:price ?price .
                        ?product product:name ?name .
                        FILTER (?price > 100)
                    }
                    """,
                    parameters={}
                )
            ]
        )
        
        # Create a context
        context = CrawlingContext(original_query=nl_query, task_instruction=task)
        
        # Add action requests for each data source
        actions = []
        
        # ERP action
        erp_action = ActionRequest.create_query_action(
            source="test",
            data_source="erp",
            query="SELECT * FROM products WHERE price > 100",
            query_params={}
        )
        context.add_action_request(erp_action)
        actions.append((erp_action, DataSourceType.ERP))
        
        # Document Storage action
        doc_action = ActionRequest.create_query_action(
            source="test",
            data_source="document_storage",
            query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
            query_params={}
        )
        context.add_action_request(doc_action)
        actions.append((doc_action, DataSourceType.DOCUMENT_STORAGE))
        
        # Knowledge Graph action
        kg_action = ActionRequest.create_query_action(
            source="test",
            data_source="knowledge_graph",
            query="""
            PREFIX product: <http://example.org/product#>
            SELECT ?product ?name ?price
            WHERE {
                ?product product:price ?price .
                ?product product:name ?name .
                FILTER (?price > 100)
            }
            """,
            query_params={}
        )
        context.add_action_request(kg_action)
        actions.append((kg_action, DataSourceType.KNOWLEDGE_GRAPH))
        
        # Execute each action and add observations
        for action, source_type in actions:
            # Get the appropriate connector
            if source_type == DataSourceType.ERP:
                connector = mock_connectors["erp"]
            elif source_type == DataSourceType.DOCUMENT_STORAGE:
                connector = mock_connectors["document_storage"]
            else:  # Knowledge Graph
                connector = mock_connectors["knowledge_graph"]
            
            # Find the matching query
            query = None
            for q in task.queries:
                if q.source_type == source_type:
                    query = q
                    break
            
            assert query is not None, f"No query found for source type {source_type}"
            
            # Execute the query
            result = connector.execute_query(query)
            
            # Add the observation to the context
            context.add_observation(action.action_id, result)
            
            # Verify the result
            assert result is not None
            assert "data" in result
            assert isinstance(result["data"], list)
            
            # Check that the observation was added to the context
            assert "actions" in context.observations
            assert action.action_id in context.observations["actions"]
        
        # Verify all observations are present
        assert len(context.observations["actions"]) == 3
        
        # Check that each action has an observation
        for action, _ in actions:
            assert action.action_id in context.observations["actions"]
    
    def test_full_flow_with_translator_and_controller(self, mock_translator, mock_controller):
        """Test the full flow from translation to execution."""
        # Natural language query
        nl_query = "Find all products with price greater than 100"
        
        # === PLANNING PHASE ===
        # Translate the query to a CrawlingContext with plan and action requests
        context = mock_translator.translate(nl_query)
        
        # Verify planning phase results
        assert context.status == "planning"
        assert context.original_query == nl_query
        assert context.thought is not None
        assert "objective" in context.plan
        assert "data_sources" in context.plan
        assert len(context.action_requests) > 0
        
        # === ACTING PHASE ===
        # Execute the actions in the context
        updated_context = mock_controller.execute(context)
        
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
            assert "data" in data
            assert isinstance(data["data"], list)
        
        # Verify final result
        assert updated_context.final_result is not None
        assert updated_context.final_result.get("context_id") == updated_context.context_id
        assert "metadata" in updated_context.final_result


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])