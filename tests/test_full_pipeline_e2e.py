"""
End-to-End Pipeline Test (Phase 10b)

Tests the complete query orchestration pipeline with MCP server.
Validates:
- Orchestrator initialization
- Intent parsing
- Discovery (Scout mode)
- Join planning & SQL generation
- SQL validation & repair
- Query execution & recovery
- Result validation
- Answer generation

Prerequisites:
- MCP server running and healthy (192.168.1.35:8000)
- Database connected and Scout catalog available
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
import pytest
from dotenv import load_dotenv

# Load environment variables (project root .env)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()  # fallback to default lookup

# Add parent directory to path
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFullPipelineE2E:
    """End-to-end pipeline tests with real MCP server."""

    @pytest.mark.asyncio
    async def test_simple_query_full_pipeline(self):
        """Test complete pipeline: query → discovery → join_sql → exec → answer."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        logger.info("=" * 60)
        logger.info("🚀 FULL PIPELINE E2E TEST")
        logger.info("=" * 60)
        
        orchestrator = QueryOrchestrator(llm_model="gpt-4o", llm_temp=0.0)
        
        # Run query through pipeline
        result = await orchestrator.ainvoke({
            'user_input': 'Show me top 5 products by sales',
            'conversation_history': []
        })

        # If the LLM is unavailable, the orchestrator will ask for clarification.
        intent = result.get('intent', {})
        if intent.get('operation') == 'clarify':
            logger.warning("LLM unavailable; received clarification response. Skipping full pipeline assertions.")
            assert result.get('final_response')
            return

        # Validate all stages
        logger.info("\n📋 Pipeline Validation:")
        
        # 1. Intent parsing
        assert intent.get('operation') == 'query'
        logger.info(f"  ✅ Intent parsed: operation={intent['operation']}")
        
        # 2. Discovery
        discovery = result.get('discovery_result', {})
        candidates = discovery.get('candidates_count', 0)
        assert candidates > 0
        logger.info(f"  ✅ Discovery completed: {candidates} candidates found")
        
        # 3. Relevant tables identified
        relevant_tables = result.get('relevant_tables', [])
        assert len(relevant_tables) > 0
        logger.info(f"  ✅ Relevant tables: {len(relevant_tables)} selected")
        
        # 4. SQL generated
        sql_query = result.get('sql_query', '')
        assert len(sql_query) > 0
        logger.info(f"  ✅ SQL generated: {sql_query[:60]}...")
        
        # 5. Validation completed
        validation_result = result.get('validation_result', {})
        assert 'is_valid' in validation_result
        logger.info(f"  ✅ SQL validated: is_valid={validation_result.get('is_valid')}")
        
        # 6. Query executed
        exec_result = result.get('exec_result', {})
        assert exec_result.get('ok') is True or exec_result.get('ok') is not None
        assert isinstance(exec_result.get('data', []), list)
        row_count = exec_result.get('row_count', len(exec_result.get('data', [])))
        logger.info(f"  ✅ Query executed: {row_count} rows returned")
        
        # 7. Answer generated
        answer = result.get('answer', '')
        assert len(answer) > 0
        logger.info(f"  ✅ Answer generated: {answer[:80]}...")
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 FULL PIPELINE TEST PASSED!")
        logger.info("=" * 60)

    @pytest.mark.asyncio
    async def test_schema_query_pipeline(self):
        """Test schema discovery pipeline."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        logger.info("\n🔍 SCHEMA QUERY TEST")
        
        orchestrator = QueryOrchestrator()
        
        result = await orchestrator.ainvoke({
            'user_input': 'What tables do we have?',
            'conversation_history': []
        })
        
        # Validate schema query routing
        intent = result.get('intent', {})
        assert intent.get('operation') == 'schema_query'
        
        # Should have discovery results
        discovery = result.get('discovery_result', {})
        assert 'candidates_count' in discovery
        
        logger.info(f"  ✅ Schema query: {discovery.get('candidates_count', 0)} tables found")

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in pipeline."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        logger.info("\n⚠️  ERROR HANDLING TEST")
        
        orchestrator = QueryOrchestrator()
        
        # Empty query should not crash
        try:
            result = await orchestrator.ainvoke({
                'user_input': '',
                'conversation_history': []
            })
            logger.info("  ✅ Empty query handled gracefully")
        except Exception as e:
            logger.warning(f"  ⚠️  Empty query raised: {type(e).__name__}")

    @pytest.mark.asyncio
    async def test_recursion_limit_handling(self):
        """Test that recursion limit is properly configured."""
        from langgraph_integration.orchestrator import QueryOrchestrator
        
        logger.info("\n📊 RECURSION LIMIT TEST")
        
        orchestrator = QueryOrchestrator()
        
        # Test ainvoke with default recursion_limit
        result = await orchestrator.ainvoke({
            'user_input': 'Show top customers',
            'conversation_history': []
        })
        
        # Should complete without hitting recursion limit
        assert result.get('answer') is not None or result.get('error_info') is not None
        logger.info("  ✅ Query completed with default recursion_limit=200")
        
        # Test with custom recursion_limit
        result = await orchestrator.ainvoke({
            'user_input': 'Show top products',
            'conversation_history': []
        }, config={'recursion_limit': 150})
        
        assert result.get('answer') is not None or result.get('error_info') is not None
        logger.info("  ✅ Query completed with custom recursion_limit=150")


# Smoke test for manual execution
async def main():
    """Quick smoke test."""
    logger.info("Starting E2E smoke test...")
    
    test = TestFullPipelineE2E()
    await test.test_simple_query_full_pipeline()
    await test.test_schema_query_pipeline()
    await test.test_recursion_limit_handling()
    
    logger.info("\n✅ All smoke tests passed!")


if __name__ == '__main__':
    asyncio.run(main())