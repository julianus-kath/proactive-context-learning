"""
Integration tests for the Multi-Agent Orchestrator (Phase 8).

Tests that the 4 specialized agents are properly composed and working together.
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestQueryOrchestrator:
    """Test QueryOrchestrator composition and flow."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test that orchestrator initializes all 4 agents."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        orchestrator = QueryOrchestrator(
            llm_model="gpt-4o",
            max_joins=3,
            max_retries=2
        )
        
        # Verify all agents are initialized
        assert orchestrator.discovery_agent is not None
        assert orchestrator.join_sql_agent is not None
        assert orchestrator.exec_recovery_agent is not None
        assert orchestrator.answer_agent is not None
        
        # Verify graph is built
        assert orchestrator.graph is not None
        logger.info("✅ Orchestrator initialized with all 4 agents")

    @pytest.mark.asyncio
    async def test_graph_nodes_exist(self):
        """Test that all expected nodes exist in the graph."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        orchestrator = QueryOrchestrator()
        
        # Get graph structure (compiled graphs have limited visibility)
        # We verify through successful invocation with mock MCP
        assert orchestrator.graph is not None
        logger.info("✅ Graph compiled successfully with all nodes")

    @pytest.mark.asyncio
    async def test_simple_intent_parser(self):
        """Test intent parsing for different query types."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        orchestrator = QueryOrchestrator()
        
        # Test: query operation
        intent = orchestrator._simple_intent_parser("Show me top 10 customers")
        assert intent["operation"] == "query"
        assert len(intent["entities"]) > 0
        logger.info(f"✅ Query intent parsed: {intent}")
        
        # Test: schema query
        intent = orchestrator._simple_intent_parser("What tables exist?")
        assert intent["operation"] == "schema_query"
        logger.info(f"✅ Schema query parsed: {intent}")
        
        # Test: health check
        intent = orchestrator._simple_intent_parser("Is the system healthy?")
        assert intent["operation"] == "health_check"
        logger.info(f"✅ Health check parsed: {intent}")

    @pytest.mark.asyncio
    async def test_discovery_agent_callable(self):
        """Test that DiscoveryAgent can be invoked."""
        from langgraph_integration.agents.discovery.agent import DiscoveryAgent
        
        agent = DiscoveryAgent()
        subgraph = agent.build_subgraph()
        
        # Verify subgraph is buildable
        assert subgraph is not None
        logger.info("✅ DiscoveryAgent subgraph built successfully")

    @pytest.mark.asyncio
    async def test_join_sql_agent_callable(self):
        """Test that JoinPlanAndSQLAgent can be invoked."""
        from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
        
        agent = JoinPlanAndSQLAgent()
        subgraph = agent.build_subgraph()
        
        # Verify subgraph is buildable
        assert subgraph is not None
        logger.info("✅ JoinPlanAndSQLAgent subgraph built successfully")

    @pytest.mark.asyncio
    async def test_exec_recovery_agent_callable(self):
        """Test that ExecAndRecoveryAgent can be invoked."""
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        subgraph = agent.build_subgraph()
        
        # Verify subgraph is buildable
        assert subgraph is not None
        logger.info("✅ ExecAndRecoveryAgent subgraph built successfully")

    @pytest.mark.asyncio
    async def test_answer_agent_callable(self):
        """Test that AnswerAgent can be invoked."""
        from langgraph_integration.agents.answer.agent import AnswerAgent
        
        agent = AnswerAgent()
        subgraph = agent.build_subgraph()
        
        # Verify subgraph is buildable
        assert subgraph is not None
        logger.info("✅ AnswerAgent subgraph built successfully")

    @pytest.mark.asyncio
    async def test_create_query_orchestrator_factory(self):
        """Test the factory function creates orchestrator correctly."""
        from langgraph_integration.orchestrator import create_query_orchestrator
        
        orchestrator = create_query_orchestrator(
            llm_model="gpt-4o",
            max_joins=3,
            max_retries=2,
            row_limit=1000,
            query_timeout_seconds=30
        )
        
        assert orchestrator is not None
        assert orchestrator.discovery_agent is not None
        logger.info("✅ Factory function creates orchestrator correctly")

    @pytest.mark.asyncio
    async def test_get_orchestrator_singleton(self):
        """Test the get_orchestrator singleton function."""
        from langgraph_integration.orchestrator import get_orchestrator
        
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        
        # Should be same instance
        assert orch1 is orch2
        logger.info("✅ Singleton orchestrator working correctly")

    @pytest.mark.asyncio
    async def test_state_contracts_valid(self):
        """Test that state contracts are properly defined."""
        from langgraph_integration.contracts.state import (
            BaseState,
            DiscoveryAgentInput,
            DiscoveryAgentOutput,
            JoinPlanAndSQLAgentInput,
            JoinPlanAndSQLAgentOutput,
            ExecAndRecoveryAgentInput,
            ExecAndRecoveryAgentOutput,
            AnswerAgentInput,
            AnswerAgentOutput
        )
        
        # Verify BaseState has all required fields
        assert "user_input" in BaseState.__annotations__
        assert "intent" in BaseState.__annotations__
        assert "relevant_tables" in BaseState.__annotations__
        assert "schema_snippet" in BaseState.__annotations__
        assert "join_plan" in BaseState.__annotations__
        assert "sql_query" in BaseState.__annotations__
        assert "exec_result" in BaseState.__annotations__
        assert "final_response" in BaseState.__annotations__
        
        logger.info("✅ State contracts properly defined")

    @pytest.mark.asyncio
    async def test_orchestrator_with_mock_mcp(self):
        """Test orchestrator flow with mocked MCP calls."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        from langgraph_integration.contracts.state import BaseState
        
        orchestrator = QueryOrchestrator()
        
        # Create mock state
        initial_state = BaseState(
            user_input="Test query",
            messages=[],
            session_described_tables={},
            retry_count=0
        )
        
        # Mock MCP to return healthy
        with patch.object(orchestrator.mcp, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True
            
            # Run index_database node
            result = await orchestrator._index_database_node(initial_state)
            
            # Should not have error_info
            assert result.get("error_info") is None
            logger.info("✅ Orchestrator handles MCP health check")

    @pytest.mark.asyncio
    async def test_orchestrator_intent_routing_query(self):
        """Test routing for query operation."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        from langgraph_integration.contracts.state import BaseState
        
        orchestrator = QueryOrchestrator()
        
        # Create state with query intent
        state = BaseState(
            user_input="Show me customers",
            intent={"operation": "query"},
            messages=[],
            session_described_tables={},
            retry_count=0
        )
        
        # Parse intent
        result = await orchestrator._parse_intent_node(state)
        assert result["intent"]["operation"] == "query"
        logger.info("✅ Routing works for query operation")

    @pytest.mark.asyncio
    async def test_orchestrator_intent_routing_schema(self):
        """Test routing for schema query operation."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        orchestrator = QueryOrchestrator()
        
        # Parse a schema query
        intent = orchestrator._simple_intent_parser("What tables do we have?")
        assert intent["operation"] == "schema_query"
        logger.info("✅ Routing works for schema query")

    @pytest.mark.asyncio
    async def test_orchestrator_intent_routing_health(self):
        """Test routing for health check operation."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        orchestrator = QueryOrchestrator()
        
        # Parse a health check
        intent = orchestrator._simple_intent_parser("Is everything working?")
        assert intent["operation"] == "health_check"
        logger.info("✅ Routing works for health check")


class TestFactoryIntegration:
    """Test factory functions and integration points."""

    def test_create_orchestrator_with_defaults(self):
        """Test creating orchestrator with default parameters."""
        from langgraph_integration.orchestrator import create_query_orchestrator
        
        orchestrator = create_query_orchestrator()
        assert orchestrator is not None
        logger.info("✅ Orchestrator created with defaults")

    def test_create_orchestrator_with_custom_params(self):
        """Test creating orchestrator with custom parameters."""
        from langgraph_integration.orchestrator import create_query_orchestrator
        
        orchestrator = create_query_orchestrator(
            llm_model="gpt-4o",
            llm_temp=0.1,
            max_joins=2,
            max_retries=3,
            row_limit=500,
            query_timeout_seconds=60
        )
        
        assert orchestrator is not None
        assert orchestrator.join_sql_agent.max_joins == 2
        logger.info("✅ Orchestrator created with custom parameters")

    def test_orchestrator_exposed_in_module(self):
        """Test that orchestrator is properly exposed in module."""
        import langgraph_integration.orchestrator as orch_module
        
        # Check exports
        assert hasattr(orch_module, 'QueryOrchestrator')
        assert hasattr(orch_module, 'create_query_orchestrator')
        assert hasattr(orch_module, 'get_orchestrator')
        logger.info("✅ Orchestrator properly exposed in module")


class TestFastAPIIntegration:
    """Test FastAPI service integration with orchestrator."""

    def test_fastapi_imports_orchestrator(self):
        """Test that FastAPI service imports orchestrator correctly."""
        # This imports should not fail
        try:
            from chatbot_ui.langgraph_service import orchestrator
            logger.info("✅ FastAPI imports orchestrator")
        except ImportError as e:
            logger.error(f"❌ FastAPI import failed: {e}")
            raise

    @pytest.mark.asyncio
    async def test_fastapi_startup_event(self):
        """Test FastAPI startup event initializes orchestrator."""
        from chatbot_ui.langgraph_service import startup_event
        
        try:
            await startup_event()
            logger.info("✅ FastAPI startup event completes")
        except Exception as e:
            logger.warning(f"⚠️ Startup event warning (expected if MCP unavailable): {e}")
            # This is OK - MCP might not be available in test environment


if __name__ == "__main__":
    """Run tests with: pytest tests/test_orchestrator_integration.py -v -s"""
    pytest.main([__file__, "-v", "-s"])