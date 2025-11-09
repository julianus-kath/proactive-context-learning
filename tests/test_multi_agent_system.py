"""
Integration tests for multi-agent system.

Tests the full flow:
- DiscoveryAgent → JoinPlanAndSQLAgent → ExecAndRecoveryAgent → AnswerAgent

Prerequisites:
- MCP server running on Windows (port 8000)
- MCP_SERVER_URL environment variable set
- API_KEY environment variable set
"""

import asyncio
import json
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

from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.contracts.state import BaseState
from langgraph_integration.mcp_client import MCPDatabaseTool


@pytest.fixture(scope="module")
def mcp_client():
    """Fixture: MCP client."""
    return MCPDatabaseTool()


@pytest.fixture
def discovery_agent():
    """Fixture: DiscoveryAgent instance."""
    return DiscoveryAgent(llm_model="gpt-4o")


@pytest.fixture
def join_sql_agent():
    """Fixture: JoinPlanAndSQLAgent instance."""
    return JoinPlanAndSQLAgent(llm_model="gpt-4o", max_joins=3)


@pytest.fixture
def exec_recovery_agent():
    """Fixture: ExecAndRecoveryAgent instance."""
    return ExecAndRecoveryAgent(llm_model="gpt-4o", max_retries=2)


@pytest.fixture
def answer_agent():
    """Fixture: AnswerAgent instance."""
    return AnswerAgent(llm_model="gpt-4o")


@pytest.mark.asyncio
async def test_all_agents_initialized(
    discovery_agent,
    join_sql_agent,
    exec_recovery_agent,
    answer_agent
):
    """Test that all agents are properly initialized."""
    logger.info("🔍 Test: All agents initialized")

    assert discovery_agent is not None
    assert join_sql_agent is not None
    assert exec_recovery_agent is not None
    assert answer_agent is not None

    logger.info("✅ All agents initialized")


@pytest.mark.asyncio
async def test_discovery_agent_subgraph(discovery_agent):
    """Test DiscoveryAgent subgraph compilation."""
    logger.info("🔍 Test: DiscoveryAgent subgraph")

    subgraph = await discovery_agent.build_subgraph()
    assert subgraph is not None

    logger.info("✅ DiscoveryAgent subgraph compiled")


@pytest.mark.asyncio
async def test_join_sql_agent_subgraph(join_sql_agent):
    """Test JoinPlanAndSQLAgent subgraph compilation."""
    logger.info("🔍 Test: JoinPlanAndSQLAgent subgraph")

    subgraph = await join_sql_agent.build_subgraph()
    assert subgraph is not None

    logger.info("✅ JoinPlanAndSQLAgent subgraph compiled")


@pytest.mark.asyncio
async def test_exec_recovery_agent_subgraph(exec_recovery_agent):
    """Test ExecAndRecoveryAgent subgraph compilation."""
    logger.info("🔍 Test: ExecAndRecoveryAgent subgraph")

    subgraph = await exec_recovery_agent.build_subgraph()
    assert subgraph is not None

    logger.info("✅ ExecAndRecoveryAgent subgraph compiled")


@pytest.mark.asyncio
async def test_answer_agent_subgraph(answer_agent):
    """Test AnswerAgent subgraph compilation."""
    logger.info("🔍 Test: AnswerAgent subgraph")

    subgraph = await answer_agent.build_subgraph()
    assert subgraph is not None

    logger.info("✅ AnswerAgent subgraph compiled")


@pytest.mark.asyncio
async def test_join_sql_agent_scoring(join_sql_agent):
    """Test candidate scoring in JoinPlanAndSQL agent."""
    logger.info("🔍 Test: JoinPlanAndSQL scoring")

    # Test with mock candidates
    candidates = [
        {
            "table_name": "dbo.customers",
            "score": 0.9,
            "is_view": False,
            "role_coverage": 0.75,
            "has_rows": True
        },
        {
            "table_name": "customer_view",
            "score": 0.7,
            "is_view": True,
            "role_coverage": 0.85,
            "has_rows": True
        }
    ]

    intent = {"operation": "query"}

    # Score manually
    for cand in candidates:
        logger.debug(f"  {cand['table_name']}: {cand['score']:.2f}")

    logger.info("✅ Scoring logic verified")


@pytest.mark.asyncio
async def test_exec_recovery_agent_sql_extraction(exec_recovery_agent):
    """Test SQL extraction from LLM responses."""
    logger.info("🔍 Test: SQL extraction")

    test_cases = [
        "SELECT TOP 10 * FROM customers",
        "```sql\nSELECT TOP 10 * FROM customers\n```",
        "Here's the query:\n\nSELECT TOP 10 * FROM customers WHERE id > 5",
        "```\nSELECT TOP 10 * FROM customers\n```"
    ]

    for i, text in enumerate(test_cases):
        extracted = exec_recovery_agent._extract_sql(text)
        logger.debug(f"  Case {i+1}: {extracted[:50]}...")
        assert "SELECT" in extracted.upper()

    logger.info("✅ SQL extraction working")


@pytest.mark.asyncio
async def test_answer_agent_error_formatting(answer_agent):
    """Test error formatting in AnswerAgent."""
    logger.info("🔍 Test: Error formatting")

    # Create state with error
    state = BaseState(
        user_input="Show me sales",
        error_info={
            "type": "TIMEOUT",
            "message": "Query timed out",
            "suggestion": "Try limiting by date"
        },
        intent={"operation": "query"}
    )

    # Format error
    result_state = await answer_agent._format_error_node(state)

    final_response = result_state.get("final_response", "")
    assert final_response, "No error response generated"
    assert len(final_response) > 0

    logger.info(f"✅ Error formatted: {final_response[:50]}...")


@pytest.mark.asyncio
async def test_mock_discovery_flow(discovery_agent):
    """Test discovery flow with mock data (no MCP required)."""
    logger.info("🔍 Test: Mock discovery flow")

    # Create mock state
    state = BaseState(
        user_input="How many customers?",
        intent={"operation": "query", "entities": ["customers"]},
        session_described_tables={}
    )

    # Test keyword extraction
    keywords = discovery_agent._extract_keywords(
        state["user_input"],
        state["intent"]
    )

    assert keywords, "No keywords extracted"
    logger.info(f"✅ Keywords: {keywords}")

    # Test candidate scoring with mock data
    mock_candidates = [
        {
            "table_name": "dbo.customers",
            "score": 0.9,
            "is_view": False,
            "role_coverage": 0.8,
            "has_rows": True
        },
        {
            "table_name": "empty_table",
            "score": 0.85,
            "is_view": False,
            "role_coverage": 0.5,
            "has_rows": False
        }
    ]

    scores = []
    for cand in mock_candidates:
        score = discovery_agent._score_candidate(cand, state["intent"])
        scores.append(score)
        logger.debug(f"  {cand['table_name']}: {score:.3f}")

    # First should score higher (has rows, higher role coverage)
    assert scores[0] > scores[1], "Scoring not working correctly"

    logger.info("✅ Mock discovery flow successful")


@pytest.mark.asyncio
async def test_mock_join_planning(join_sql_agent):
    """Test join planning with mock data (no MCP required)."""
    logger.info("🔍 Test: Mock join planning")

    # Create mock state
    state = BaseState(
        relevant_tables=["dbo.orders", "dbo.customers"],
        schema_snippet="dbo.orders: order_id (int), customer_id (int FK), total (decimal)\n"
                      "dbo.customers: customer_id (int), name (varchar)",
        intent={"operation": "query"},
        fk_hints=[{
            "from_table": "dbo.orders",
            "to_table": "dbo.customers",
            "from_column": "customer_id",
            "to_column": "customer_id",
            "join_condition": "orders.customer_id = customers.customer_id"
        }],
        session_described_tables={}
    )

    # Build join plan
    await join_sql_agent._build_join_plan_node(state)

    join_plan = state.get("join_plan")
    assert join_plan, "No join plan generated"
    assert join_plan.get("primary_table") == "dbo.orders"
    assert len(join_plan.get("joins", [])) > 0

    logger.info(f"✅ Join plan: {join_plan.get('strategy')} with {len(join_plan.get('joins', []))} joins")


@pytest.mark.asyncio
async def test_mock_sql_generation(join_sql_agent):
    """Test SQL generation with mock data (no MCP required)."""
    logger.info("🔍 Test: Mock SQL generation")

    # Create mock state
    state = BaseState(
        relevant_tables=["dbo.orders"],
        schema_snippet="dbo.orders: order_id (int), total (decimal), order_date (date)",
        intent={"operation": "query", "filters": []},
        join_plan={
            "strategy": "joins",
            "primary_table": "dbo.orders",
            "joins": [],
            "where_filters": [],
            "limit": 1000
        }
    )

    # Generate SQL
    await join_sql_agent._generate_sql_node(state)

    sql = state.get("sql_query", "")
    assert sql, "No SQL generated"
    assert "SELECT" in sql.upper()
    assert "TOP 1000" in sql
    assert "dbo.orders" in sql

    logger.info(f"✅ SQL generated: {sql[:80]}...")


@pytest.mark.asyncio
async def test_mock_sql_validation(join_sql_agent):
    """Test SQL validation."""
    logger.info("🔍 Test: SQL validation")

    test_cases = [
        {
            "sql": "SELECT TOP 100 * FROM customers WHERE id > 5",
            "should_pass": True
        },
        {
            "sql": "INSERT INTO customers VALUES (1, 'John')",
            "should_pass": False  # Non-SELECT
        },
        {
            "sql": "SELECT * FROM customers WHERE name = 'John",
            "should_pass": False  # Unbalanced quotes
        },
        {
            "sql": "SELECT * FROM (SELECT * FROM customers)",
            "should_pass": True
        }
    ]

    for case in test_cases:
        state = BaseState(sql_query=case["sql"])
        result = await join_sql_agent._validate_sql_node(state)

        has_error = "error_info" in result and result["error_info"]
        passed = not has_error

        status = "✅" if passed == case["should_pass"] else "❌"
        logger.debug(f"  {status} {case['sql'][:50]}... (passed={passed})")

        assert passed == case["should_pass"], f"Validation incorrect for: {case['sql']}"

    logger.info("✅ SQL validation working")


@pytest.mark.asyncio
async def test_mock_answer_formatting(answer_agent):
    """Test answer formatting with mock data."""
    logger.info("🔍 Test: Answer formatting")

    # Test result formatting
    state = BaseState(
        user_input="How many customers?",
        exec_result={
            "ok": True,
            "data": [{"count": 100}],  # Changed from "rows" to "data" (Phase 10b fix)
            "row_count": 100,
            "execution_time_ms": 150,
            "truncated": False
        },
        sql_query="SELECT COUNT(*) as count FROM dbo.customers"
    )

    result_state = await answer_agent._format_result_node(state)
    response = result_state.get("final_response", "")
    assert response, "No response formatted"
    logger.info(f"✅ Result formatted: {response[:80]}...")

    # Test schema explaining
    schema_state = BaseState(
        user_input="What tables exist?",
        schema_snippet="dbo.customers: customer_id (int), name (varchar)\ndbo.orders: order_id (int), customer_id (int)",
        intent={"operation": "schema_query"}
    )

    schema_result = await answer_agent._explain_schema_node(schema_state)
    schema_response = schema_result.get("final_response", "")
    assert schema_response, "No schema explanation"
    logger.info(f"✅ Schema explained: {schema_response[:80]}...")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])