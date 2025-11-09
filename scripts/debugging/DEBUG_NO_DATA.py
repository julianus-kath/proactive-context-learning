#!/usr/bin/env python3
"""
Comprehensive diagnostic to trace "no data" issue through entire pipeline.

This script tests:
1. MCP connectivity
2. Query execution
3. Data parsing
4. State flow through orchestrator
"""

import asyncio
import json
import logging
from typing import Any, Dict

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

async def test_mcp_connection():
    """Test that MCP server is reachable and responds."""
    print("\n" + "="*80)
    print("STEP 1: Testing MCP Server Connection")
    print("="*80)
    
    try:
        from langgraph_integration.mcp_client import get_shared_mcp_tool
        
        mcp = get_shared_mcp_tool()
        logger.info("✅ MCP tool created")
        
        # Try a simple discovery call
        logger.info("📡 Attempting list_tables call...")
        result = await mcp.list_tables(page=0, page_size=5)
        logger.info(f"✅ MCP responded with {len(result) if result else 0} content items")
        
        if result:
            logger.info(f"   Result is type: {type(result)}")
            if isinstance(result, dict):
                logger.info(f"   Result keys: {list(result.keys())}")
            elif isinstance(result, list) and len(result) > 0:
                logger.info(f"   First item type: {type(result[0])}")
                if isinstance(result[0], dict) and "text" in result[0]:
                    text = result[0]["text"][:200]
                    logger.info(f"   Response preview: {text}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ MCP connection failed: {e}", exc_info=True)
        return False


async def test_count_query():
    """Test executing a COUNT query through the full pipeline."""
    print("\n" + "="*80)
    print("STEP 2: Testing COUNT Query Execution")
    print("="*80)
    
    try:
        from langgraph_integration.mcp_client import get_shared_mcp_tool
        
        mcp = get_shared_mcp_tool()
        
        # Try a simple COUNT query  
        sql = "SELECT COUNT(*) AS customer_count FROM [dbo].[Customer]"
        logger.info(f"📊 Executing query: {sql}")
        
        # Call query_bounded directly (which should detect COUNT and use legacy 'query')
        result = await mcp.query_bounded(sql)
        
        logger.info(f"✅ Query returned {type(result)}")
        
        if result:
            if isinstance(result, list):
                logger.info(f"   Result is a list with {len(result)} items")
                if len(result) > 0:
                    logger.info(f"   First item type: {type(result[0])}")
                    if isinstance(result[0], dict):
                        keys = list(result[0].keys())
                        logger.info(f"   Keys in first item: {keys}")
                        
                        if "text" in result[0]:
                            text = result[0]["text"]
                            logger.info(f"   Text length: {len(text)}")
                            logger.info(f"   Text preview:\n{text[:500]}")
                            
                            # Try to extract JSON
                            if "Full response (JSON):" in text:
                                logger.info("   ✅ Found 'Full response (JSON):' marker")
                                json_part = text.split("Full response (JSON):", 1)[-1].strip()
                                try:
                                    # Try to find the JSON block
                                    brace_idx = json_part.find('{')
                                    if brace_idx >= 0:
                                        json_text = json_part[brace_idx:]
                                        data = json.loads(json_text[:500])  # Quick test parse
                                        logger.info(f"   ✅ JSON is parseable")
                                except Exception as e:
                                    logger.error(f"   ❌ JSON parsing failed: {e}")
                            else:
                                logger.warning("   ⚠️  No 'Full response (JSON):' marker found")
            elif isinstance(result, dict):
                logger.info(f"   Result is a dict with keys: {list(result.keys())}")
                if "text" in result:
                    logger.info(f"   Has 'text' field with {len(result['text'])} chars")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Query execution failed: {e}", exc_info=True)
        return None


async def test_query_parsing(result: Any):
    """Test that query result parsing works correctly."""
    print("\n" + "="*80)
    print("STEP 3: Testing Query Result Parsing")
    print("="*80)
    
    try:
        from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
        
        agent = ExecAndRecoveryAgent()
        
        if not result:
            logger.error("❌ No result to parse")
            return None
        
        logger.info(f"📝 Parsing result (length: {len(result)})")
        parsed = agent._parse_query_result(result)
        
        logger.info(f"✅ Parsing complete")
        logger.info(f"   parsed['ok']: {parsed.get('ok')}")
        logger.info(f"   parsed['row_count']: {parsed.get('row_count')}")
        logger.info(f"   parsed['data'] length: {len(parsed.get('data', []))}")
        logger.info(f"   parsed keys: {list(parsed.keys())}")
        
        if parsed.get('data'):
            logger.info(f"   First data row: {parsed['data'][0]}")
        else:
            logger.warning("   ⚠️  'data' is empty!")
            if parsed.get('error'):
                logger.warning(f"   Error: {parsed['error']}")
        
        return parsed
        
    except Exception as e:
        logger.error(f"❌ Parsing failed: {e}", exc_info=True)
        return None


async def test_orchestrator_format(parsed_result: Dict[str, Any]):
    """Test that orchestrator can format results correctly."""
    print("\n" + "="*80)
    print("STEP 4: Testing Orchestrator Result Formatting")
    print("="*80)
    
    try:
        # Simulate what orchestrator does
        if not parsed_result:
            logger.error("❌ No parsed result to format")
            return
        
        # This is line 1633 in orchestrator.py
        data = parsed_result.get("../../data", [])
        row_count = parsed_result.get("row_count", 0)
        execution_time = parsed_result.get("execution_time_ms", 0)
        
        logger.info(f"📋 Orchestrator reads from exec_result:")
        logger.info(f"   data: {data}")
        logger.info(f"   row_count: {row_count}")
        logger.info(f"   execution_time_ms: {execution_time}")
        
        # This is the check that triggers "no data" (line 1645)
        if not data:
            logger.error("❌ DATA IS EMPTY - This triggers 'no data' message!")
            return
        
        logger.info(f"✅ Data is present ({len(data)} rows)")
        
        # Format as orchestrator would (line 1655 for COUNT)
        if data and len(data) > 0:
            count_value = list(data[0].values())[0]
            logger.info(f"✅ Formatted answer: 'There are {count_value} customers in the database.'")
        
    except Exception as e:
        logger.error(f"❌ Formatting failed: {e}", exc_info=True)


async def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "  NO DATA DIAGNOSTIC - Full Pipeline Trace".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    # Test 1: MCP connectivity
    if not await test_mcp_connection():
        logger.error("💥 MCP connection failed - cannot proceed")
        return
    
    # Test 2: Query execution
    query_result = await test_count_query()
    if not query_result:
        logger.error("💥 Query execution failed - cannot proceed")
        return
    
    # Test 3: Result parsing
    parsed_result = await test_query_parsing(query_result)
    if not parsed_result:
        logger.error("💥 Result parsing failed - cannot proceed")
        return
    
    # Test 4: Orchestrator formatting
    await test_orchestrator_format(parsed_result)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
If all steps succeeded (✅):
  → "no data" message is NOT coming from data parsing
  → Issue may be in intent parsing or SQL generation
  → Check if SQL query is actually being generated correctly
  
If step 3 or 4 shows ❌ with empty data:
  → MCP is not returning data properly
  → OR parsing is not extracting it correctly
  → Check MCP server logs on Windows machine
  
If step 1 or 2 fails:
  → MCP server is unreachable or erroring
  → Check: is Windows MCP server running?
  → Check: is MCP_SERVER_URL set correctly?
  → Check firewall/VPN connectivity
""")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)