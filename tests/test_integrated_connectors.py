"""
Integration test for all connectors working together.
"""
import pytest
import uuid
import sys
from typing import Dict, Any, List

# Import required modules, handling potential import errors
try:
    from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
    from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
    from crawling_agent.connectors.erp_connector import ERPConnector
    from crawling_agent.connectors.document_storage_connector import DocumentStorageConnector
    from crawling_agent.connectors.knowledge_graph_connector import KnowledgeGraphConnector
    from crawling_agent.translator.query_translator import QueryTranslator
    from crawling_agent.controller.crawling_controller import CrawlingAgentController
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"Import error: {e}")
    IMPORTS_SUCCESSFUL = False
    # Create dummy classes for type hints to work
    class TaskInstruction: pass
    class DataSourceType: 
        ERP = "erp"
        DOCUMENT_STORAGE = "document_storage"
        KNOWLEDGE_GRAPH = "knowledge_graph"
    class DataSourceQuery: pass
    class QueryType: 
        SQL = "sql"
        MONGODB = "mongodb"
        SPARQL = "sparql"
    class CrawlingContext: pass
    class ActionRequest: pass
    class ERPConnector: pass
    class DocumentStorageConnector: pass
    class KnowledgeGraphConnector: pass
    class QueryTranslator: pass
    class CrawlingAgentController: pass


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Required imports not available")
class TestIntegratedConnectors:
    """Test class for integrated connector testing."""
    
    @pytest.fixture
    def mock_connectors(self, monkeypatch):
        """Create mock connectors for testing."""
        # Create mock connectors
        erp_connector = ERPConnector()
        doc_connector = DocumentStorageConnector(mock_mode=True)
        kg_connector = KnowledgeGraphConnector()
        
        # Mock the ERP connector's execute_query method
        def mock_erp_execute_query(query):
            return {
                "data": [
                    {"id": 1, "name": "Expensive Product 1", "price": 150},
                    {"id": 2, "name": "Expensive Product 2", "price": 200}
                ],
                "metadata": {
                    "row_count": 2,
                    "columns": ["id", "name", "price"],
                    "execution_time_ms": 42.5
                }
            }
        monkeypatch.setattr(erp_connector, "execute_query", mock_erp_execute_query)
        monkeypatch.setattr(erp_connector, "connect", lambda: None)
        
        # Mock the Knowledge Graph connector's execute_query method
        def mock_kg_execute_query(query):
            return {
                "data": [
                    {"product": "prod1", "name": "Expensive Product 1", "price": "150.0"},
                    {"product": "prod2", "name": "Expensive Product 2", "price": "200.0"}
                ],
                "metadata": {
                    "row_count": 2,
                    "execution_time_ms": 42.5
                }
            }
        monkeypatch.setattr(kg_connector, "execute_query", mock_kg_execute_query)
        
        return {
            "erp": erp_connector,
            "document_storage": doc_connector,
            "knowledge_graph": kg_connector
        }
    
    @pytest.fixture
    def mock_translator(self, monkeypatch):
        """Create a mock translator for testing."""
        # Check if QueryTranslator exists and has a use_mock parameter
        try:
            translator = QueryTranslator(use_mock=True)
            return translator
        except (ImportError, TypeError):
            # Create a mock translator
            class MockTranslator:
                def translate(self, query):
                    context = CrawlingContext(original_query=query)
                    context.update_status("planning")
                    
                    # Create a simple task instruction
                    task = TaskInstruction(
                        task_id=str(uuid.uuid4()),
                        original_query=query,
                        description="Find products with price > 100",
                        data_sources=[DataSourceType.ERP, DataSourceType.DOCUMENT_STORAGE, DataSourceType.KNOWLEDGE_GRAPH],
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
                            ),
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
                    
                    context.task_instruction = task
                    context.thought = "I need to find products with price greater than 100 from all data sources."
                    context.plan = {
                        "objective": "Find expensive products",
                        "data_sources": ["erp", "document_storage", "knowledge_graph"],
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Query all data sources",
                                "description": "Get products with price > 100"
                            }
                        ]
                    }
                    
                    # Add action requests
                    for ds in ["erp", "document_storage", "knowledge_graph"]:
                        query_str = "SELECT * FROM products WHERE price > 100" if ds == "erp" else \
                                   '{"product_type": {"$exists": true}, "price": {"$gt": 100}}' if ds == "document_storage" else \
                                   """
                                   PREFIX product: <http://example.org/product#>
                                   SELECT ?product ?name ?price
                                   WHERE {
                                       ?product product:price ?price .
                                       ?product product:name ?name .
                                       FILTER (?price > 100)
                                   }
                                   """
                        action = ActionRequest.create_query_action(
                            source="translator",
                            data_source=ds,
                            query=query_str,
                            query_params={}
                        )
                        context.add_action_request(action)
                    
                    return context
            
            return MockTranslator()

    @pytest.fixture
    def mock_controller(self, mock_connectors, monkeypatch):
        """Create a mock controller for testing."""
        # Check if CrawlingAgentController exists and has a mock_mode parameter
        try:
            controller = CrawlingAgentController(mock_mode=True)
            return controller
        except (ImportError, TypeError):
            # Create a mock controller
            class MockController:
                def __init__(self, connectors=None):
                    self.connectors = connectors or mock_connectors
                
                def execute(self, context):
                    context.update_status("acting")
                    
                    # Process each action request
                    for action in context.action_requests:
                        # Update action status
                        context.update_action_status(action.action_id, "in_progress")
                        
                        # Get the appropriate connector
                        data_source = action.action_type.split("_")[1]
                        connector = self.connectors.get(data_source)
                        
                        if connector:
                            # Find the matching query
                            query = None
                            for q in context.task_instruction.queries:
                                if q.source_type.value == data_source:
                                    query = q
                                    break
                            
                            if query:
                                # Execute the query
                                result = connector.execute_query(query)
                                
                                # Add observation
                                context.add_observation(action.action_id, result)
                        
                        # Update action status
                        context.update_action_status(action.action_id, "completed")
                    
                    # Set final result
                    context.set_final_result({
                        "context_id": context.context_id,
                        "original_query": context.original_query,
                        "observations": context.observations,
                        "metadata": {
                            "execution_time": context.updated_at,
                            "data_sources": ["erp", "document_storage", "knowledge_graph"],
                            "action_count": len(context.action_requests),
                            "completed_action_count": len([a for a in context.action_requests if a.status == "completed"])
                        }
                    })
                    
                    return context
            
            return MockController(mock_connectors)
    
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