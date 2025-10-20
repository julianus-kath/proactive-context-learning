"""
Test script to verify comprehensive debug logging system is working correctly.
Run this to see the full logging output.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from langgraph_integration.debug_logger import get_debug_logger, DebugLogger


async def test_logging():
    """Test all logging functionality."""
    
    print("\n" + "="*80)
    print("COMPREHENSIVE DEBUG LOGGING SYSTEM TEST")
    print("="*80 + "\n")
    
    # Get logger instance
    logger = get_debug_logger("test_debug")
    
    # Test 1: Tool Calls
    print("\n📋 TEST 1: Tool Calls and Results")
    print("-" * 80)
    logger.tool_call("search_tables", {"keyword": "orders", "page": 1})
    await asyncio.sleep(0.5)  # Simulate work
    logger.tool_result(
        "search_tables",
        {"tables": ["orders", "order_items", "order_details"]},
        duration_ms=245.67
    )
    
    # Test 2: Scout Mode Operations
    print("\n📋 TEST 2: Scout Mode Operations")
    print("-" * 80)
    logger.scout_mode_operation(
        "search_tables",
        "keyword='orders'",
        ["orders", "order_items", "order_details"],
        {"matches": 3, "top_score": 0.98}
    )
    
    # Test 3: Intent Parsing
    print("\n📋 TEST 3: Intent Parsing")
    print("-" * 80)
    logger.intent_parsed(
        "How many orders were sent in September compared to August?",
        "query",
        0.92,
        entities=["orders", "September", "August", "comparison"],
        missing_fields=None
    )
    
    # Test 4: Schema Discovery
    print("\n📋 TEST 4: Schema Discovery")
    print("-" * 80)
    logger.schema_discovered(
        "orders",
        columns=[
            {"name": "order_id", "type": "INT", "nullable": False},
            {"name": "customer_id", "type": "INT", "nullable": False},
            {"name": "order_date", "type": "DATE", "nullable": False},
            {"name": "total_amount", "type": "DECIMAL(10,2)", "nullable": True},
            {"name": "status", "type": "VARCHAR(50)", "nullable": False},
        ],
        row_count=15234,
        relationships=[
            {"foreign_key": "customer_id", "references": "customers.customer_id"}
        ]
    )
    
    # Test 5: SQL Generation
    print("\n📋 TEST 5: SQL Generation")
    print("-" * 80)
    logger.sql_generated(
        "SELECT COUNT(*) as september_count, MONTH(order_date) as month FROM orders WHERE YEAR(order_date) = 2025 AND MONTH(order_date) IN (8, 9) GROUP BY MONTH(order_date)",
        "User asked for comparison between August and September orders",
        table_context=["orders"]
    )
    
    # Test 6: Query Execution
    print("\n📋 TEST 6: Query Execution")
    print("-" * 80)
    logger.query_executed(
        "SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9",
        rows_returned=1,
        duration_ms=234.56
    )
    
    # Test 7: Query Error
    print("\n📋 TEST 7: Query Error")
    print("-" * 80)
    logger.query_executed(
        "SELECT * FROM invalid_table",
        rows_returned=0,
        duration_ms=45.12,
        error="Table 'invalid_table' not found"
    )
    
    # Test 8: Decisions
    print("\n📋 TEST 8: Workflow Decisions")
    print("-" * 80)
    logger.decision_made(
        "Route to table selection",
        "Intent type is 'query' - system needs to determine relevant tables",
        options_considered=["clarify", "schema_query", "direct_execution", "table_selection"]
    )
    
    # Test 9: State Updates
    print("\n📋 TEST 9: State Updates")
    print("-" * 80)
    logger.state_updated(
        "intent_analysis",
        old_value=None,
        new_value={"operation": "query", "confidence": 0.92}
    )
    
    # Test 10: Performance Timing
    print("\n📋 TEST 10: Timing Checkpoints")
    print("-" * 80)
    logger.timing_checkpoint("database_index", 125.34)
    logger.timing_checkpoint("intent_parsing", 456.78)
    logger.timing_checkpoint("table_selection", 234.12)
    logger.timing_checkpoint("sql_generation", 345.67)
    logger.timing_checkpoint("query_execution", 1234.56)
    
    # Test 11: Warnings
    print("\n📋 TEST 11: Warnings")
    print("-" * 80)
    logger.warning(
        "Slow query detected",
        "Query took longer than 5 seconds to execute",
        context={
            "query": "SELECT * FROM large_table",
            "duration_ms": 5123.45,
            "threshold_ms": 5000
        }
    )
    
    # Test 12: Info Messages
    print("\n📋 TEST 12: Informational Messages")
    print("-" * 80)
    logger.info(
        "System initialized",
        "All components ready for operation",
        {
            "database_tables": 25,
            "schemas": 2,
            "mcp_server": "healthy"
        }
    )
    
    # Test 13: Errors
    print("\n📋 TEST 13: Workflow Errors")
    print("-" * 80)
    logger.workflow_error(
        "mcp_connection_error",
        "Failed to connect to MCP server after 3 retries",
        context={
            "url": "http://localhost:8000",
            "timeout": 30,
            "last_error": "Connection refused"
        }
    )
    
    # Test 14: Tool Error
    print("\n📋 TEST 14: Tool Error")
    print("-" * 80)
    logger.tool_call("describe_table", {"table_name": "orders"})
    await asyncio.sleep(0.3)
    logger.tool_result(
        "describe_table",
        None,
        duration_ms=123.45,
        error="HTTP Error 500: Internal Server Error"
    )
    
    # Test 15: Intent Clarification
    print("\n📋 TEST 15: Intent Requiring Clarification")
    print("-" * 80)
    logger.intent_parsed(
        "Show me the data",
        "clarify",
        0.45,
        entities=None,
        missing_fields=["tables_to_query", "specific_columns", "filter_criteria"]
    )
    
    # Show buffer statistics
    print("\n" + "="*80)
    print("BUFFER STATISTICS")
    print("="*80)
    buffered = logger.get_buffered_logs_no_clear()
    print(f"Total log entries in buffer: {len(buffered)}")
    print(f"Log types: {set(log['type'] for log in buffered)}")
    
    # Clear buffer
    logger.get_buffered_logs()
    print(f"Buffer after clear: {len(logger.get_buffered_logs_no_clear())} entries")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*80)
    print("\nCheck the following for output:")
    print("  1. Terminal: You should see all log messages above")
    print("  2. File: logs/test_debug_debug.log")
    print("  3. Buffer: Use /debug/logs API endpoint")
    print("\nThe logging system is working correctly!")


def main():
    """Run the test."""
    print("\n🚀 Starting Comprehensive Debug Logging Test...\n")
    
    try:
        asyncio.run(test_logging())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()