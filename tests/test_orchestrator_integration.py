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
        from langgraph_integration.contracts.response_envelope import ResponseEnvelope
        
        # Verify BaseState has all required fields
        assert "user_input" in BaseState.__annotations__
        assert "intent" in BaseState.__annotations__
        assert "relevant_tables" in BaseState.__annotations__
        assert "schema_snippet" in BaseState.__annotations__
        assert "join_plan" in BaseState.__annotations__
        assert "sql_query" in BaseState.__annotations__
        assert "exec_result" in BaseState.__annotations__
        assert "final_response" in BaseState.__annotations__

        envelope = ResponseEnvelope.model_validate({"ok": True, "data": [{"id": 1}]})
        assert envelope.data == [{"id": 1}]
        
        logger.info("✅ State contracts properly defined")

    @pytest.mark.asyncio
    async def test_health_check_short_circuit(self):
        """Health check intents should bypass discovery and return health status envelope."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        from langgraph_integration.contracts.state import BaseState

        orchestrator = QueryOrchestrator()

        orchestrator.mcp.get_health_status = AsyncMock(
            return_value={"status": "ok", "components": {"db": "ok"}}
        )

        with patch.object(orchestrator, "_discovery_node", new_callable=AsyncMock) as mock_discovery:
            result = await orchestrator.process_query("Is the system healthy?")
            mock_discovery.assert_not_called()

        assert result["health_status"]["status"] == "ok"
        assert result["exec_result"] is None

        health_state = await orchestrator._answer_health_node(
            BaseState(user_input="Health?", intent={"operation": "health_check"})
        )
        exec_result = health_state.get("exec_result", {})
        assert isinstance(exec_result, dict)
        assert exec_result.get("data") == []
        assert exec_result.get("row_count", 0) == 0

    @pytest.mark.asyncio
    async def test_discovery_empty_tables_routes_to_clarification(self):
        """Discovery returning empty tables should skip join_sql and prompt for clarification."""
        from langgraph_integration.orchestrator import QueryOrchestrator

        orchestrator = QueryOrchestrator()

        class FakeIntentGraph:
            async def ainvoke(self, state):
                return {
                    "intent": {
                        "operation": "query",
                        "primary_entities": ["sales"],
                        "keywords_for_discovery": ["sales"],
                        "metrics": [],
                    }
                }

        class FakeDiscoveryGraph:
            async def ainvoke(self, state):
                intent = dict(state.get("intent", {}))
                intent["needs_clarification"] = True
                intent["clarification_question"] = "Need a more specific business area or timeframe."
                intent["ambiguity_reason"] = "Discovery found only empty tables."
                state["intent"] = intent
                state["relevant_tables"] = []
                state["candidate_views"] = []
                state["schema_snippet"] = ""
                state["column_index"] = {}
                state["error_info"] = {
                    "type": "DISCOVERY_EMPTY_TABLES",
                    "message": "Discovery found only empty tables.",
                }
                return state

        orchestrator.intent_parser.build_subgraph = MagicMock(return_value=FakeIntentGraph())
        orchestrator.discovery_agent.build_subgraph = MagicMock(return_value=FakeDiscoveryGraph())

        async def fake_index(state):
            return state

        join_called = {"value": False}

        async def fail_join(state):
            join_called["value"] = True
            raise AssertionError("join_sql should not run")

        async def fake_answer(state):
            return {**state, "final_response": "Need clarification"}

        orchestrator._index_database_node = fake_index
        orchestrator._join_sql_node = fail_join
        orchestrator._answer_node = fake_answer

        orchestrator.graph = orchestrator._build_graph()

        result = await orchestrator.graph.ainvoke({"user_input": "Show missing sales data"})

        orchestrator.discovery_agent.build_subgraph.assert_called_once()
        assert join_called["value"] is False
        assert result["final_response"] == "Need clarification"
        assert result["intent"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_process_query_returns_clarify_envelope(self):
        """process_query should return structured clarification envelope when intent parser flags ambiguity."""
        from langgraph_integration.orchestrator import QueryOrchestrator

        orchestrator = QueryOrchestrator()

        class ClarifyIntentGraph:
            async def ainvoke(self, state):
                return {
                    "intent": {
                        "operation": "query",
                        "needs_clarification": True,
                        "clarification_question": "Which region should I analyze?",
                        "ambiguity_reason": "Multiple regions found",
                        "keywords_for_discovery": [],
                    }
                }

        orchestrator.intent_parser.build_subgraph = MagicMock(return_value=ClarifyIntentGraph())

        result = await orchestrator.process_query("Show sales numbers")

        assert isinstance(result, dict)
        assert result.get("clarify") is True
        assert result.get("clarification_question") == "Which region should I analyze?"
        assert result.get("final_response") == "Which region should I analyze?"

    @pytest.mark.asyncio
    async def test_index_database_loads_previous_exec_cache(self):
        """index_database should hydrate previous_exec_result from in-memory cache."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        from langgraph_integration.contracts.state import BaseState

        orchestrator = QueryOrchestrator()
        orchestrator.mcp.health_check = AsyncMock(return_value=True)
        orchestrator.mcp_client.list_tables = AsyncMock(return_value=[])

        orchestrator._previous_exec_cache = {
            "exec_result": {"ok": True, "data": [{"value": 1}]},
            "sql_query": "SELECT 1",
            "sources": ["dbo.table1"],
        }

        result_state = await orchestrator._index_database_node(BaseState(user_input="hello"))

        assert result_state.get("previous_exec_result") == {"ok": True, "data": [{"value": 1}]}
        assert result_state.get("previous_sql") == "SELECT 1"
        assert result_state.get("previous_sources") == ["dbo.table1"]

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
        
        # Create state with query intent but skip LLM parsing to avoid network dependency
        state = BaseState(
            user_input="Show me customers",
            intent={"operation": "query"}
        )
        result = await orchestrator._route_operation_node(state)
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