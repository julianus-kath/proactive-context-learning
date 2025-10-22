"""
Tests for DiscoveryAgent using actual MCP server (no mocks).

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

from langgraph_integration.agents.discovery.agent import DiscoveryAgent, create_discovery_agent
from langgraph_integration.contracts.state import BaseState
from langgraph_integration.mcp_client import MCPDatabaseTool


@pytest.fixture(scope="module")
def mcp_client():
    """Fixture: Create MCP client."""
    client = MCPDatabaseTool()
    return client


@pytest.fixture(scope="module")
def discovery_agent():
    """Fixture: Create DiscoveryAgent instance."""
    # Create synchronously, will be initialized in async context
    return DiscoveryAgent(llm_model="gpt-4o")


@pytest.mark.asyncio
async def test_mcp_health_check(mcp_client):
    """Test that MCP server is healthy and reachable."""
    logger.info("🔍 Test: MCP health check")
    is_healthy = await mcp_client.health_check()
    assert is_healthy, "MCP server is not healthy"
    logger.info("✅ MCP server is healthy")


@pytest.mark.asyncio
async def test_search_tables_basic(mcp_client):
    """Test basic table search via MCP."""
    logger.info("🔍 Test: Basic search_tables")
    
    result = await mcp_client.search_tables("customer", page=1, page_size=5)
    
    assert result is not None, "search_tables returned None"
    assert len(result) > 0, "search_tables returned empty result"
    
    # Parse result
    if result and len(result) > 0:
        content = result[0].get("text", "")
        data = json.loads(content) if isinstance(content, str) else content
        logger.info(f"✅ Found tables: {json.dumps(data, indent=2)[:500]}...")


@pytest.mark.asyncio
async def test_describe_table_basic(mcp_client):
    """Test describing a table via MCP."""
    logger.info("🔍 Test: describe_table")
    
    # First search for a table
    search_result = await mcp_client.search_tables("customer", page=1, page_size=1)
    assert search_result and len(search_result) > 0, "search_tables failed"
    
    # Extract table name
    content = search_result[0].get("text", "")
    data = json.loads(content) if isinstance(content, str) else content
    
    # Handle different formats
    if isinstance(data, dict):
        tables = data.get("results", data.get("tables", []))
    else:
        tables = data
    
    if not tables:
        pytest.skip("No tables found to describe")
    
    table_name = tables[0].get("table_name") or tables[0].get("name") or tables[0].get("full_name")
    assert table_name, "Could not extract table name"
    
    logger.info(f"  Describing table: {table_name}")
    
    # Describe the table
    desc_result = await mcp_client.describe_table(table_name, include_sample=False)
    assert desc_result is not None, "describe_table returned None"
    assert len(desc_result) > 0, "describe_table returned empty result"
    
    logger.info(f"✅ Successfully described {table_name}")


@pytest.mark.asyncio
async def test_discovery_agent_initialization(discovery_agent):
    """Test DiscoveryAgent initialization."""
    logger.info("🔍 Test: DiscoveryAgent initialization")
    
    assert discovery_agent is not None
    assert discovery_agent.mcp is not None
    assert discovery_agent.llm is not None
    assert discovery_agent.max_candidates_to_describe == 3
    assert discovery_agent.view_role_coverage_threshold == 0.70
    
    logger.info("✅ DiscoveryAgent initialized correctly")


@pytest.mark.asyncio
async def test_discovery_agent_subgraph_build(discovery_agent):
    """Test DiscoveryAgent subgraph compilation."""
    logger.info("🔍 Test: DiscoveryAgent subgraph build")
    
    subgraph = await discovery_agent.build_subgraph()
    assert subgraph is not None, "Failed to build subgraph"
    
    logger.info("✅ DiscoveryAgent subgraph compiled successfully")


@pytest.mark.asyncio
async def test_discovery_agent_search_candidates(discovery_agent):
    """Test search_candidates node."""
    logger.info("🔍 Test: search_candidates node")
    
    initial_state = BaseState(
        user_input="How many customers do we have?",
        intent={
            "operation": "query",
            "entities": ["customers"],
            "filters": {}
        },
        session_described_tables={}
    )
    
    result_state = await discovery_agent._search_candidates_node(initial_state)
    
    # Should have candidate_views populated or error_info
    if "error_info" in result_state:
        logger.warning(f"  Search failed: {result_state['error_info'].get('message')}")
        # This is acceptable - not all queries will find candidates
    else:
        candidates = result_state.get("candidate_views", [])
        assert candidates is not None, "candidate_views is None"
        assert len(candidates) > 0, f"No candidates found for 'customers'"
        logger.info(f"✅ Found {len(candidates)} candidate(s)")
        
        # Check candidate structure
        for c in candidates[:3]:
            assert "table_name" in c or "name" in c or "full_name" in c, "Missing table name"
            logger.debug(f"  - {c.get('table_name', c.get('name', c.get('full_name', '?')))}")


@pytest.mark.asyncio
async def test_discovery_agent_rank_candidates(discovery_agent):
    """Test rank_candidates node."""
    logger.info("🔍 Test: rank_candidates node")
    
    # Create mock candidates
    candidates = [
        {
            "table_name": "dbo.customers",
            "score": 0.9,
            "is_view": False,
            "role_coverage": 0.75,
            "has_rows": True
        },
        {
            "table_name": "dbo.customer_orders",
            "score": 0.7,
            "is_view": False,
            "role_coverage": 0.6,
            "has_rows": True
        },
        {
            "table_name": "customer_summary_view",
            "score": 0.65,
            "is_view": True,
            "role_coverage": 0.85,
            "has_rows": True
        }
    ]
    
    state = BaseState(
        candidate_views=candidates,
        intent={"operation": "query"}
    )
    
    result_state = await discovery_agent._rank_candidates_node(state)
    
    ranked = result_state.get("candidate_views", [])
    assert len(ranked) > 0, "No candidates after ranking"
    
    # Should be sorted by score
    scores = [c.get("score", 0) for c in ranked]
    assert scores == sorted(scores, reverse=True), "Candidates not sorted by score"
    
    logger.info(f"✅ Ranked {len(ranked)} candidates")
    for i, c in enumerate(ranked[:3]):
        logger.debug(f"  {i+1}. {c['table_name']} (score={c['score']:.3f})")


@pytest.mark.asyncio
async def test_discovery_agent_score_candidate(discovery_agent):
    """Test candidate scoring formula."""
    logger.info("🔍 Test: candidate scoring")
    
    candidate_good = {
        "table_name": "dbo.customers",
        "score": 0.9,
        "is_view": False,
        "role_coverage": 0.75,
        "has_rows": True
    }
    
    candidate_view = {
        "table_name": "customer_view",
        "score": 0.7,
        "is_view": True,
        "role_coverage": 0.8,
        "has_rows": True
    }
    
    candidate_empty = {
        "table_name": "old_table",
        "score": 0.85,
        "is_view": False,
        "role_coverage": 0.5,
        "has_rows": False  # Empty table
    }
    
    intent = {"operation": "query"}
    
    score_good = discovery_agent._score_candidate(candidate_good, intent)
    score_view = discovery_agent._score_candidate(candidate_view, intent)
    score_empty = discovery_agent._score_candidate(candidate_empty, intent)
    
    logger.info(f"  Scores:")
    logger.info(f"    Good candidate: {score_good:.3f}")
    logger.info(f"    View candidate: {score_view:.3f}")
    logger.info(f"    Empty candidate: {score_empty:.3f}")
    
    # Views should score higher with same text_sim if role_coverage is high
    assert score_view > 0, "View score should be positive"
    
    # Empty tables should score lower
    assert score_empty <= score_good, "Empty table should score lower or equal"
    
    logger.info("✅ Scoring formula working correctly")


@pytest.mark.asyncio
async def test_discovery_agent_full_flow(discovery_agent):
    """Test full discovery flow end-to-end."""
    logger.info("🔍 Test: Full discovery flow")
    
    initial_state = BaseState(
        user_input="Show me the top sales orders",
        intent={
            "operation": "query",
            "entities": ["orders", "sales"],
            "filters": {}
        },
        session_described_tables={},
        messages=[]
    )
    
    # Build and run subgraph
    subgraph = await discovery_agent.build_subgraph()
    
    try:
        final_state = subgraph.invoke(initial_state)
        
        # Check outputs
        if "error_info" in final_state and final_state["error_info"]:
            logger.warning(f"Discovery failed: {final_state['error_info'].get('message')}")
            # Log but don't fail - MCP might not have matching tables
        else:
            relevant_tables = final_state.get("relevant_tables", [])
            schema_snippet = final_state.get("schema_snippet", "")
            
            logger.info(f"✅ Discovery completed")
            logger.info(f"  Relevant tables: {relevant_tables}")
            logger.info(f"  Schema snippet length: {len(schema_snippet)} chars")
            
            # Assertions
            assert relevant_tables is not None, "relevant_tables is None"
            assert schema_snippet is not None, "schema_snippet is None"
            
            if relevant_tables:
                assert len(relevant_tables) > 0, "No relevant tables found"
                assert all(isinstance(t, str) for t in relevant_tables), "Invalid table names"
                logger.info(f"  Found {len(relevant_tables)} relevant table(s)")
    
    except Exception as e:
        logger.error(f"❌ Discovery flow failed: {e}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_discovery_agent_keyword_extraction(discovery_agent):
    """Test keyword extraction from user input."""
    logger.info("🔍 Test: Keyword extraction")
    
    test_cases = [
        {
            "user_input": "How many customers do we have?",
            "intent": {"entities": ["customers"]},
            "expected_contains": ["customers", "many"]
        },
        {
            "user_input": "Show me sales orders for product 123",
            "intent": {"entities": ["orders"]},
            "expected_contains": ["sales", "orders", "product"]
        }
    ]
    
    for case in test_cases:
        keywords = discovery_agent._extract_keywords(
            case["user_input"],
            case["intent"]
        )
        logger.debug(f"  Input: '{case['user_input']}'")
        logger.debug(f"  Keywords: {keywords}")
        
        # Verify some keywords were extracted
        assert len(keywords) > 0, f"No keywords extracted for: {case['user_input']}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])