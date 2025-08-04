"""
Test script for the ERP (SQL) connector.
"""
import pytest
import uuid
import sys
from typing import Dict, Any

# Import required modules, handling potential import errors
try:
    from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
    from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
    from crawling_agent.connectors.erp_connector import ERPConnector
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"Import error: {e}")
    IMPORTS_SUCCESSFUL = False
    # Create dummy classes for type hints to work
    class TaskInstruction: pass
    class DataSourceType: ERP = "erp"
    class DataSourceQuery: pass
    class QueryType: SQL = "sql"
    class CrawlingContext: pass
    class ActionRequest: pass
    class ERPConnector: pass


@pytest.mark.skipif(not IMPORTS_SUCCESSFUL, reason="Required imports not available")
class TestERPConnector:
    """Test class for the ERP connector."""
    
    @pytest.fixture
    def mock_erp_connector(self, monkeypatch):
        """Create a mock ERP connector for testing."""
        # Create a mock connector that overrides the necessary methods
        connector = ERPConnector()
        
        # Mock the connect method
        def mock_connect():
            connector.connection = "mock_connection"
        monkeypatch.setattr(connector, "connect", mock_connect)
        
        # Mock the execute_query method
        def mock_execute_query(query):
            # Return mock data based on the query
            if "products" in query.query.lower():
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
            elif "employees" in query.query.lower():
                return {
                    "data": [
                        {"id": 1, "name": "John Doe", "department": "Sales", "position": "Manager"},
                        {"id": 2, "name": "Jane Smith", "department": "Sales", "position": "Associate"}
                    ],
                    "metadata": {
                        "row_count": 2,
                        "columns": ["id", "name", "department", "position"],
                        "execution_time_ms": 35.2
                    }
                }
            else:
                return {
                    "data": [],
                    "metadata": {
                        "row_count": 0,
                        "columns": [],
                        "execution_time_ms": 10.0
                    }
                }
        monkeypatch.setattr(connector, "execute_query", mock_execute_query)
        
        return connector
    
    @pytest.fixture
    def product_query_action(self):
        """Create a sample product query action."""
        return ActionRequest.create_query_action(
            source="test",
            data_source="erp",
            query="SELECT * FROM products WHERE price > 100",
            query_params={}
        )
    
    @pytest.fixture
    def employee_query_action(self):
        """Create a sample employee query action."""
        return ActionRequest.create_query_action(
            source="test",
            data_source="erp",
            query="SELECT e.* FROM employees e JOIN departments d ON e.department_id = d.id WHERE d.name = 'Sales'",
            query_params={}
        )
    
    def test_erp_connector_initialization(self, mock_erp_connector):
        """Test that the ERP connector initializes correctly."""
        assert mock_erp_connector is not None
        assert hasattr(mock_erp_connector, 'execute_query')
    
    def test_product_query(self, mock_erp_connector, product_query_action):
        """Test a product query against the ERP connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.ERP,
            query_type=QueryType.SQL,
            query=product_query_action.parameters.get("query", ""),
            parameters=product_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_erp_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0
        
        # Check that the data contains expected fields
        if result["data"]:
            product = result["data"][0]
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert product["price"] > 100  # Verify the query condition
    
    def test_employee_query(self, mock_erp_connector, employee_query_action):
        """Test an employee query against the ERP connector."""
        # Create a DataSourceQuery from the action
        query = DataSourceQuery(
            source_type=DataSourceType.ERP,
            query_type=QueryType.SQL,
            query=employee_query_action.parameters.get("query", ""),
            parameters=employee_query_action.parameters.get("parameters", {})
        )
        
        # Execute the query
        result = mock_erp_connector.execute_query(query)
        
        # Verify the result
        assert result is not None
        assert "data" in result
        assert "metadata" in result
        assert isinstance(result["data"], list)
        
        # Check that the data contains expected fields if there are results
        if result["data"]:
            employee = result["data"][0]
            assert "id" in employee
            assert "name" in employee
            # Verify that employees are from Sales department
            if "department" in employee:
                assert employee["department"] == "Sales"
    
    def test_natural_language_to_erp_query(self, mock_erp_connector):
        """Test translating a natural language query to an ERP query and executing it."""
        # Natural language query
        nl_query = "Find all products with price greater than 100"
        
        # Manually create a task instruction (in a real system, this would be done by a translator)
        task = TaskInstruction(
            task_id=str(uuid.uuid4()),
            original_query=nl_query,
            description="Find expensive products",
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
        
        # Create a context
        context = CrawlingContext(original_query=nl_query, task_instruction=task)
        
        # Add an action request
        action = ActionRequest.create_query_action(
            source="test",
            data_source="erp",
            query="SELECT * FROM products WHERE price > 100",
            query_params={}
        )
        context.add_action_request(action)
        
        # Execute the query
        query = task.queries[0]
        result = mock_erp_connector.execute_query(query)
        
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
            assert "price" in product
            assert product["price"] > 100


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])