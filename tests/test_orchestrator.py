"""
Tests for QueryOrchestrator (multi-agent composition).

Tests the full orchestrator workflow without requiring MCP server.
"""

import asyncio
import logging
import os
import pytest
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add langgraph_integration to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from langgraph_integration.orchestrator import QueryOrchestrator, create_orchestrator
from langgraph_integration.contracts.state import BaseState


@pytest.fixture
def orchestrator():
    """Fixture: QueryOrchestrator instance."""
    return QueryOrchestrator(llm_model="gpt-4o")


@pytest.mark.asyncio
async def test_orchestrator_initialization(orchestrator):
    """Test orchestrator initialization."""
    logger.info("🔍 Test: Orchestrator initialization")

    assert orchestrator is not None
    assert orchestrator.discovery_agent is not None
    assert orchestrator.join_sql_agent is not None
    assert orchestrator.exec_recovery_agent is not None
    assert orchestrator.answer_agent is not None
    assert orchestrator.llm is not None
    assert orchestrator.mcp is not None

    logger.info("✅ Orchestrator initialized correctly")


@pytest.mark.asyncio
async def test_orchestrator_graph_build(orchestrator):
    """Test orchestrator graph compilation."""
    logger.info("🔍 Test: Orchestrator graph build")

    graph = orchestrator.build_graph()
    assert graph is not None

    logger.info("✅ Orchestrator graph compiled successfully")


def test_orchestrator_has_timeout_attr(self):
    from langgraph_integration.orchestrator import QueryOrchestrator

    orch = QueryOrchestrator(query_timeout_seconds=42)
    assert hasattr(orch, "query_timeout_seconds")
    assert orch.query_timeout_seconds == 42


@pytest.mark.asyncio
async def test_simple_intent_parser(orchestrator):
    """Test simple intent parser."""
    logger.info("🔍 Test: Simple intent parser")

    test_cases = [
        {
            "input": "What tables are in the database?",
            "expected_operation": "schema_query"
        },
        {
            "input": "Is the system healthy?",
            "expected_operation": "health_check"
        },
        {
            "input": "Show me sales data",
            "expected_operation": "query"
        },
        {
            "input": "How many customers do we have?",
            "expected_operation": "query"
        }
    ]

    for case in test_cases:
        intent = orchestrator._simple_intent_parser(case["input"])
        assert intent["operation"] == case["expected_operation"], \
            f"Expected {case['expected_operation']}, got {intent['operation']} for: {case['input']}"
        logger.debug(f"  ✅ {case['input'][:50]}... → {intent['operation']}")

    logger.info("✅ Intent parser working correctly")


@pytest.mark.asyncio
async def test_orchestrator_mock_schema_query(orchestrator):
    """Test orchestrator with mock schema query."""
    logger.info("🔍 Test: Mock schema query workflow")

    # Create initial state
    state = BaseState(
        user_input="What tables exist?",
        messages=[],
        session_described_tables={},
        retry_count=0
    )

    # Index database node
    indexed_state = await orchestrator._index_database_node(state)
    assert not indexed_state.get("error_info"), "Index database failed"

    # Parse intent node
    parsed_state = await orchestrator._parse_intent_node(indexed_state)
    intent = parsed_state.get("intent", {})
    assert intent.get("operation") == "schema_query", "Intent not recognized as schema_query"

    logger.info(f"✅ Schema query identified: {intent}")


@pytest.mark.asyncio
async def test_orchestrator_mock_health_check(orchestrator):
    """Test orchestrator with mock health check."""
    logger.info("🔍 Test: Mock health check workflow")

    # Create initial state
    state = BaseState(
        user_input="Is the system working?",
        messages=[],
        session_described_tables={},
        retry_count=0
    )

    # Index database node
    indexed_state = await orchestrator._index_database_node(state)

    # Parse intent node
    parsed_state = await orchestrator._parse_intent_node(indexed_state)
    intent = parsed_state.get("intent", {})
    assert intent.get("operation") == "health_check", "Intent not recognized as health_check"

    logger.info(f"✅ Health check identified: {intent}")


@pytest.mark.asyncio
async def test_orchestrator_mock_query_flow(orchestrator):
    """Test orchestrator with mock query flow."""
    logger.info("🔍 Test: Mock query flow")

    # Create initial state
    state = BaseState(
        user_input="Show me top customers",
        messages=[],
        session_described_tables={},
        retry_count=0
    )

    # Index database
    indexed_state = await orchestrator._index_database_node(state)
    assert not indexed_state.get("error_info")

    # Parse intent
    parsed_state = await orchestrator._parse_intent_node(indexed_state)
    intent = parsed_state.get("intent", {})
    assert intent.get("operation") == "query"

    logger.info(f"✅ Query flow initiated: {intent}")


@pytest.mark.asyncio
async def test_orchestrator_error_handling(orchestrator):
    """Test orchestrator error handling."""
    logger.info("🔍 Test: Error handling")

    # Test with empty input
    state = BaseState(
        user_input="",
        messages=[],
        session_described_tables={},
        retry_count=0
    )

    parsed_state = await orchestrator._parse_intent_node(state)
    assert parsed_state.get("error_info"), "Should have error_info for empty input"

    logger.info("✅ Error handling working")


@pytest.mark.asyncio
async def test_orchestrator_state_flow(orchestrator):
    """Test state flow through orchestrator nodes."""
    logger.info("🔍 Test: State flow through nodes")

    # Create initial state
    initial_state = BaseState(
        user_input="How many customers?",
        messages=[],
        session_described_tables={},
        retry_count=0
    )

    # Flow through nodes
    state = initial_state.copy()

    # Index
    state = await orchestrator._index_database_node(state)
    logger.debug("  After index_database")

    # Parse intent
    state = await orchestrator._parse_intent_node(state)
    logger.debug(f"  After parse_intent: operation={state.get('intent', {}).get('operation')}")

    # Check that state has required fields
    assert state.get("user_input")
    assert state.get("intent")

    logger.info("✅ State flow working correctly")


@pytest.mark.asyncio
async def test_factory_function():
    """Test factory function for orchestrator creation."""
    logger.info("🔍 Test: Factory function")

    orchestrator = await create_orchestrator(
        llm_model="gpt-4o",
        max_joins=3,
        max_retries=2
    )

    assert orchestrator is not None
    assert orchestrator.join_sql_agent.max_joins == 3
    assert orchestrator.exec_recovery_agent.max_retries == 2

    logger.info("✅ Factory function working")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])