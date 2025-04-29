"""
Test script for the Document Storage (MongoDB) connector.
"""
import pytest
import uuid
from typing import Dict, Any

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
from crawling_agent.connectors.document_storage_connector import DocumentStorageConnector


class TestDocumentStorageConnector:
    """Test class for the Document Storage connector."""
    
    @pytest.fixture
    def mock_doc_connector(self):
        """Create a mock Document Storage connector for testing."""
        return DocumentStorageConnector(mock_mode=True)
    
    @pytest.fixture
    def product_query_action(self):
        """Create a sample product query action."""
        return ActionRequest.create_query_action(
            source="test",
            data_source="document_storage",
            query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
            query_params={}
        )
    
    @pytest.fixture
    def order_query_action(self):
        """Create a sample order query action."""
        return ActionRequest.create_query_action(
            source="test",
            data_source="document_storage",
            query='{"customer_name": "ABC Corp", "order_date": {"$gte": {"$date": "2023-05-01T00:00:00Z"}}}',
            query_params={}
        )
    
    def test_doc_connector_initialization(self, mock_doc_connector):
        """Test that the Document Storage connector initializes correctly."""
        assert mock_doc_connector is not None
        assert hasattr(mock_doc_connector, 'execute_query')
    
    def test_product_query(self, mock_doc_connector, product_query_action):
        """Test a product query against the Document Storage connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.DOCUMENT_STORAGE,
            query_type=QueryType.MONGODB,
            query=product_query_action.parameters.get("query", ""),
            parameters=product_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_doc_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        
        # Check that the data contains expected fields if there are results
        if result["data"]:
            product = result["data"][0]
            assert "product_type" in product
            assert "price" in product
            assert product["price"] > 100  # Verify the query condition
    
    def test_order_query(self, mock_doc_connector, order_query_action):
        """Test an order query against the Document Storage connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.DOCUMENT_STORAGE,
            query_type=QueryType.MONGODB,
            query=order_query_action.parameters.get("query", ""),
            parameters=order_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_doc_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        
        # Check that the data contains expected fields if there are results
        if result["data"]:
            order = result["data"][0]
            assert "customer_name" in order
            assert order["customer_name"] == "ABC Corp"
            assert "order_date" in order
    
    def test_natural_language_to_doc_query(self, mock_doc_connector):
        """Test translating a natural language query to a Document Storage query and executing it."""
        # Natural language query
        nl_query = "Find all product documents with price greater than 100"
        
        # Manually create a task instruction (in a real system, this would be done by a translator)
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=nl_query,
            description="Find expensive product documents",
            data_sources=[DataSourceType.DOCUMENT_STORAGE],
            queries=[
                DataSourceQuery(
                    source_type=DataSourceType.DOCUMENT_STORAGE,
                    query_type=QueryType.MONGODB,
                    query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
                    parameters={}
                )
            ]
        )
        
        # Create a context
        context = CrawlingContext(original_query=nl_query, task_instruction=task)
        
        # Add an action request
        action = ActionRequest.create_query_action(
            source="test",
            data_source="document_storage",
            query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
            query_params={}
        )
        context.add_action_request(action)
        
        # Execute the query
        query = task.queries[0]
        result = mock_doc_connector.execute_query(query)
        
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
        
        # If there are results, check they match the query criteria
        if observation["data"]["data"]:
            product = observation["data"]["data"][0]
            assert "product_type" in product
            assert "price" in product
            assert product["price"] > 100


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])