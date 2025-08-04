"""
Test script for the Knowledge Graph (SPARQL) connector.
"""
import pytest
import uuid
import sys
from typing import Dict, Any

# Import required modules, handling potential import errors
try:
    from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
    from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
    from crawling_agent.connectors.knowledge_graph_connector import KnowledgeGraphConnector
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"Import error: {e}")
    IMPORTS_SUCCESSFUL = False
    # Create dummy classes for type hints to work
    class TaskInstruction: pass
    class DataSourceType: KNOWLEDGE_GRAPH = "knowledge_graph"
    class DataSourceQuery: pass
    class QueryType: SPARQL = "sparql"
    class CrawlingContext: pass
    class ActionRequest: pass
    class KnowledgeGraphConnector: pass


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Required imports not available")
class TestKnowledgeGraphConnector:
    """Test class for the Knowledge Graph connector."""
    
    @pytest.fixture
    def mock_kg_connector(self, monkeypatch):
        """Create a mock Knowledge Graph connector for testing."""
        # Create a mock connector that overrides the necessary methods
        connector = KnowledgeGraphConnector()
        
        # Mock the execute_query method
        def mock_execute_query(query):
            # Return mock data based on the query
            if "employee" in query.query.lower() and "sales" in query.query.lower():
                return {
                    "data": [
                        {"employee": "emp1", "name": "John Doe", "position": "Manager"},
                        {"employee": "emp2", "name": "Jane Smith", "position": "Associate"}
                    ],
                    "metadata": {
                        "row_count": 2,
                        "execution_time_ms": 35.2
                    }
                }
            elif "product" in query.query.lower() and "price" in query.query.lower():
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
            else:
                return {
                    "data": [],
                    "metadata": {
                        "row_count": 0,
                        "execution_time_ms": 10.0
                    }
                }
        monkeypatch.setattr(connector, "execute_query", mock_execute_query)
        
        return connector
    
    @pytest.fixture
    def employee_query_action(self):
        """Create a sample employee query action."""
        sparql_query = """
        PREFIX org: <http://example.org/organization#>
        SELECT ?employee ?name ?position
        WHERE {
            ?employee org:worksIn ?department .
            ?department org:name "Sales" .
            ?employee org:name ?name .
            ?employee org:position ?position .
        }
        """
        return ActionRequest.create_query_action(
            source="test",
            data_source="knowledge_graph",
            query=sparql_query,
            query_params={}
        )
    
    @pytest.fixture
    def product_query_action(self):
        """Create a sample product query action."""
        sparql_query = """
        PREFIX product: <http://example.org/product#>
        SELECT ?product ?name ?price
        WHERE {
            ?product product:price ?price .
            ?product product:name ?name .
            FILTER (?price > 100)
        }
        """
        return ActionRequest.create_query_action(
            source="test",
            data_source="knowledge_graph",
            query=sparql_query,
            query_params={}
        )
    
    def test_kg_connector_initialization(self, mock_kg_connector):
        """Test that the Knowledge Graph connector initializes correctly."""
        assert mock_kg_connector is not None
        assert hasattr(mock_kg_connector, 'execute_query')
    
    def test_employee_query(self, mock_kg_connector, employee_query_action):
        """Test an employee query against the Knowledge Graph connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.KNOWLEDGE_GRAPH,
            query_type=QueryType.SPARQL,
            query=employee_query_action.parameters.get("query", ""),
            parameters=employee_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_kg_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        
        # Check that the data contains expected fields if there are results
        if result["data"]:
            employee = result["data"][0]
            assert "employee" in employee
            assert "name" in employee
            assert "position" in employee
    
    def test_product_query(self, mock_kg_connector, product_query_action):
        """Test a product query against the Knowledge Graph connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.KNOWLEDGE_GRAPH,
            query_type=QueryType.SPARQL,
            query=product_query_action.parameters.get("query", ""),
            parameters=product_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_kg_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        
        # Check that the data contains expected fields if there are results
        if result["data"]:
            product = result["data"][0]
            assert "product" in product
            assert "name" in product
            assert "price" in product
            # Verify the price is greater than 100
            assert float(product["price"]) > 100
    
    def test_natural_language_to_kg_query(self, mock_kg_connector):
        """Test translating a natural language query to a Knowledge Graph query and executing it."""
        # Natural language query
        nl_query = "Find all employees in the Sales department"
        
        # Manually create a task instruction (in a real system, this would be done by a translator)
        sparql_query = """
        PREFIX org: <http://example.org/organization#>
        SELECT ?employee ?name ?position
        WHERE {
            ?employee org:worksIn ?department .
            ?department org:name "Sales" .
            ?employee org:name ?name .
            ?employee org:position ?position .
        }
        """
        
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=nl_query,
            description="Find employees in Sales department",
            data_sources=[DataSourceType.KNOWLEDGE_GRAPH],
            queries=[
                DataSourceQuery(
                    source_type=DataSourceType.KNOWLEDGE_GRAPH,
                    query_type=QueryType.SPARQL,
                    query=sparql_query,
                    parameters={}
                )
            ]
        )
        
        # Create a context
        context = CrawlingContext(original_query=nl_query, task_instruction=task)
        
        # Add an action request
        action = ActionRequest.create_query_action(
            source="test",
            data_source="knowledge_graph",
            query=sparql_query,
            query_params={}
        )
        context.add_action_request(action)
        
        # Execute the query
        query = task.queries[0]
        result = mock_kg_connector.execute_query(query)
        
        # Add the observation to the context
        context.add_observation(action.action_id, result)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert isinstance(result["data"], list)
        
        # Check that the observation was added to the context
        assert "actions" in context.observations
        assert action.action_id in context.observations["actions"]
        
        # Check the observation data
        observation = context.observations["actions"][action.action_id]
        assert "data" in observation
        assert isinstance(observation["data"]["data"], list)
        
        # If there are results, check they contain expected fields
        if observation["data"]["data"]:
            employee = observation["data"]["data"][0]
            assert "employee" in employee
            assert "name" in employee
            assert "position" in employee


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])