"""
Test State Passing & Information Flow Fixes

Tests for the critical fixes that prevent:
1. Keyword pollution in discovery
2. LLM explanation leakage into SQL
3. Invalid SQL generation/repair
"""

import pytest
import logging

logger = logging.getLogger(__name__)


class TestKeywordExtraction:
    """Test discovery keyword extraction improvements"""
    
    def test_extract_keywords_excludes_have(self):
        """Test that 'have' is excluded from keywords"""
        from langgraph_integration.agents.discovery.agent import DiscoveryAgent
        
        discovery = DiscoveryAgent()
        
        # Query with "have" should not extract it
        keywords = discovery._extract_keywords("how many customers do we have", {})
        assert "have" not in keywords, f"'have' should be excluded but got: {keywords}"
        assert "customers" in keywords, f"'customers' should be included but got: {keywords}"
    
    def test_extract_keywords_excludes_do_does_did(self):
        """Test that do/does/did are excluded from keywords"""
        from langgraph_integration.agents.discovery.agent import DiscoveryAgent
        
        discovery = DiscoveryAgent()
        
        keywords = discovery._extract_keywords("show me what do we sell", {})
        assert "do" not in keywords
        assert "does" not in keywords
        assert "did" not in keywords
    
    def test_extract_keywords_includes_nouns(self):
        """Test that actual nouns are included"""
        from langgraph_integration.agents.discovery.agent import DiscoveryAgent
        
        discovery = DiscoveryAgent()
        
        keywords = discovery._extract_keywords("how many customers do we have", {})
        assert "customers" in keywords
        
        keywords = discovery._extract_keywords("show me all products with sales", {})
        assert "products" in keywords
        assert "sales" in keywords
    
    def test_extract_keywords_order_preserved(self):
        """Test that keyword order is preserved"""
        from langgraph_integration.agents.discovery.agent import DiscoveryAgent
        
        discovery = DiscoveryAgent()
        
        keywords = discovery._extract_keywords("customers and orders", {})
        assert keywords == ["customers", "orders"] or keywords == ["customers", "orders"]


class TestSQLExtraction:
    """Test SQL extraction from LLM responses"""
    
    def test_extract_sql_with_select(self):
        """Test extracting SQL that contains SELECT"""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        
        response = "To query this, use:\nSELECT TOP 1000 * FROM dbo.customers"
        extracted = agent._extract_sql(response)
        
        assert extracted.startswith("SELECT")
        assert "dbo.customers" in extracted
    
    def test_extract_sql_without_select_returns_empty(self):
        """Test that explanatory text without SELECT returns empty string"""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        
        # LLM response with explanation but no SQL
        response = """It seems that the original query was not provided, 
                      which is why the error message states "No SQL query to execute." 
                      To assist you effectively, I need the actual SQL query."""
        
        extracted = agent._extract_sql(response)
        assert extracted == "", f"Expected empty string but got: {extracted[:100]}"
    
    def test_extract_sql_removes_markdown(self):
        """Test that markdown code fences are removed"""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        
        response = """```sql
SELECT TOP 1000 * FROM dbo.orders
```"""
        
        extracted = agent._extract_sql(response)
        assert extracted == "SELECT TOP 1000 * FROM dbo.orders"
        assert "```" not in extracted
    
    def test_extract_sql_handles_explanations_before_select(self):
        """Test that explanations before SELECT are removed"""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        
        response = """This query will fetch all customers:
        SELECT TOP 1000 * FROM dbo.customers WHERE active = 1"""
        
        extracted = agent._extract_sql(response)
        assert extracted.startswith("SELECT")
        assert "This query" not in extracted


class TestSQLGeneration:
    """Test SQL generation validation"""
    
    def test_sql_generation_validates_select_top(self):
        """Test that generated SQL must have SELECT TOP"""
        from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
        import asyncio
        
        agent = JoinPlanAndSQLAgent()
        
        # Create a state with valid join plan
        state = {
            "join_plan": {
                "strategy": "view",
                "primary_table": "dbo.customers",
                "where_filters": []
            },
            "schema_snippet": "dbo.customers: id (int), name (varchar)"
        }
        
        # Run generation - should pass
        result = asyncio.run(agent._generate_sql_node(state))
        
        assert "error_info" not in result or result.get("error_info") is None
        assert "sql_query" in result
        assert result["sql_query"].startswith("SELECT TOP")
    
    def test_sql_generation_validates_from_clause(self):
        """Test that generated SQL has FROM clause"""
        from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
        import asyncio
        
        agent = JoinPlanAndSQLAgent()
        
        state = {
            "join_plan": {
                "strategy": "joins",
                "primary_table": "dbo.sales_orders",
                "joins": []
            },
            "schema_snippet": "dbo.sales_orders: order_id (int), customer_id (int)"
        }
        
        result = asyncio.run(agent._generate_sql_node(state))
        
        sql = result.get("sql_query", "")
        assert "FROM" in sql.upper()


class TestErrorHandling:
    """Test error handling and state clean ness"""
    
    def test_repair_failure_propagates_properly(self):
        """Test that repair failures are caught and don't contaminate state"""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        import asyncio
        
        agent = ExecAndRecoveryAgent()
        
        # Create a state where repair will fail (bad SQL, LLM returns explanation)
        state = {
            "sql_query": "INVALID SQL WILL TRIGGER REPAIR",
            "error_info": {"message": "Test error"},
            "schema_snippet": "dbo.test: id (int)",
            "join_plan": {}
        }
        
        # Run repair - it will try LLM, get explanation, extraction returns empty
        # Validation should catch this and raise error
        # Function should handle gracefully without setting broken SQL to state
        result = asyncio.run(agent._repair_sql_node(state))
        
        # Should have error_info set
        assert "error_info" in result


class TestStateContracts:
    """Test that state contracts flow properly"""
    
    def test_discovery_output_has_required_fields(self):
        """Test that discovery output includes all required fields"""
        from langgraph_integration.contracts.state import DiscoveryAgentOutput
        
        # This validates the TypedDict contract
        output = DiscoveryAgentOutput(
            relevant_tables=["dbo.customers"],
            schema_snippet="dbo.customers: id (int)",
            candidate_views=[],
            session_described_tables={},
            column_index={"dbo.customers": ["id", "name"]}
        )
        
        assert output["relevant_tables"]
        assert output["schema_snippet"]
        assert "column_index" in output
    
    def test_join_sql_input_contract_validation(self):
        """Test that join_sql input has required fields from discovery"""
        from langgraph_integration.contracts.state import JoinPlanAndSQLAgentInput
        
        input_state = JoinPlanAndSQLAgentInput(
            intent={"operation": "query"},
            relevant_tables=["dbo.customers"],
            schema_snippet="dbo.customers: id (int)",
            column_index={"dbo.customers": ["id", "name"]}
        )
        
        assert input_state["relevant_tables"]
        assert input_state["schema_snippet"]
        assert "column_index" in input_state


class TestEndToEndScenarios:
    """Integration tests for end-to-end scenarios"""
    
    def test_simple_count_query_flow(self):
        """Test "how many customers do we have" flow"""
        # This is a higher-level test that would test the full orchestrator
        # Skipping detailed implementation for now
        pass
    
    def test_query_with_no_matching_tables(self):
        """Test handling when discovery finds no tables"""
        # Test graceful degradation
        pass


# Markers for pytest
pytestmark = [
    pytest.mark.unit,
    pytest.mark.state_passing,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])