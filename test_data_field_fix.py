#!/usr/bin/env python3
"""
Quick test to verify the "rows" → "data" field name fix.
Tests that data flows end-to-end through the pipeline.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from langgraph_integration.orchestrator import QueryOrchestrator
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

logger = logging.getLogger(__name__)


async def test_data_field_fix():
    """Test that execution results flow through correctly."""
    logger.info("🧪 Testing data field fix...")
    
    try:
        orch = QueryOrchestrator(llm_model="gpt-4o")
        
        # Simple count query
        test_query = "How many customers do we have?"
        
        logger.info(f"📝 Running query: {test_query}")
        result = await orch.ainvoke({
            'user_input': test_query,
            'conversation_history': []
        })
        
        # Check result structure
        logger.info("=" * 60)
        logger.info("RESULT STRUCTURE:")
        logger.info("=" * 60)
        
        if "exec_result" in result and result["exec_result"]:
            exec_result = result["exec_result"]
            logger.info(f"✅ exec_result exists")
            logger.info(f"   - Keys: {list(exec_result.keys())}")
            logger.info(f"   - ok: {exec_result.get('ok')}")
            logger.info(f"   - row_count: {exec_result.get('row_count')}")
            logger.info(f"   - data length: {len(exec_result.get('data', []))}")
            
            if exec_result.get("data"):
                logger.info(f"   - First row: {exec_result['data'][0] if exec_result['data'] else 'N/A'}")
        else:
            logger.warning("❌ No exec_result in result")
        
        logger.info(f"\n📊 Final Answer: {result.get('final_answer', 'N/A')}")
        
        # Validation
        if result.get("exec_result") and result["exec_result"].get("data"):
            logger.info("\n✅ SUCCESS: Data field is populated and flowing through!")
            return True
        elif "no data" in result.get("final_answer", "").lower():
            logger.error("\n❌ FAILED: Still getting 'no data' message")
            logger.error(f"   Full answer: {result.get('final_answer')}")
            return False
        else:
            logger.warning("\n⚠️  Unclear result state")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_data_field_fix())
    sys.exit(0 if success else 1)