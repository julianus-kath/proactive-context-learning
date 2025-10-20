# Comprehensive Debug Logging Guide

## Overview

The system now includes a comprehensive debug logging system that tracks:
- **Tool calls** and their results with timing
- **Scout mode operations** (table discovery, search rankings)
- **Intent parsing** decisions with confidence scores
- **Schema discovery** results
- **SQL generation** with reasoning
- **Query execution** with performance metrics
- **Workflow decisions** and state updates
- **Errors** with detailed context

## Features

### 1. Visual Log Formatting
- **Clear separators** for easy reading
- **Emoji indicators** for log types (🔧 tool calls, ✅ results, 🔍 scout mode, etc.)
- **Nested indentation** for complex operations
- **Structured data** with readable formatting

### 2. Log Types

| Emoji | Type | Description |
|-------|------|-------------|
| 🔧 | TOOL_CALL | Initiating a tool call with arguments |
| ✅ | TOOL_RESULT | Tool execution result (success) |
| 🔍 | SCOUT_MODE | Scout mode table discovery/search |
| 📝 | INTENT_PARSE | Intent parsing results |
| 📊 | SCHEMA_DISCOVERY | Table schema information discovered |
| 🔄 | SQL_GENERATION | SQL query generation |
| ⚡ | QUERY_EXECUTION | Query execution with results |
| ❌ | ERROR | Workflow errors |
| ⚠️ | WARNING | Warning messages |
| ℹ️ | INFO | Informational messages |
| 🎯 | DECISION | Workflow decisions made |
| 💾 | STATE_UPDATE | State changes |
| ⏱️ | TIMING | Performance checkpoints |

### 3. Logging Destinations

Logs are written to:
1. **File**: `logs/langgraph_debug.log` - Comprehensive file log
2. **Console**: STDOUT - Readable terminal output
3. **Buffer**: In-memory buffer - For frontend streaming
4. **API**: HTTP endpoints - For real-time monitoring

## Usage

### Using the Debug Logger in Code

```python
from langgraph_integration.debug_logger import get_debug_logger

# Get the global logger instance
logger = get_debug_logger()

# Log tool calls
logger.tool_call("search_tables", {"keyword": "orders"})
# ... do work ...
logger.tool_result("search_tables", {"tables": ["orders", "order_items"]}, duration_ms=45.2)

# Log scout mode operations
logger.scout_mode_operation(
    "search_tables",
    "keyword='orders'",
    ["orders", "order_items", "order_status"],
    {"matches": 3}
)

# Log intent parsing
logger.intent_parsed(
    "How many orders in September?",
    "query",
    confidence=0.95,
    entities=["orders", "September"],
    missing_fields=None
)

# Log SQL generation
logger.sql_generated(
    "SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9",
    "User asked for count",
    table_context=["orders"]
)

# Log query execution
logger.query_executed(
    "SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9",
    rows_returned=1,
    duration_ms=123.45
)

# Log decisions
logger.decision_made(
    "Route to table selection",
    "Intent is query type, need to select relevant tables",
    options_considered=["clarify", "query", "schema_query"]
)

# Log errors
logger.workflow_error(
    "MCP_CONNECTION_ERROR",
    "Failed to connect to MCP server",
    context={"url": "http://localhost:8000", "timeout": 30}
)

# Log warnings
logger.warning(
    "Slow query detected",
    "Query took 5000ms",
    context={"query": "SELECT * FROM large_table"}
)

# Log info
logger.info(
    "Database indexed",
    "Successfully indexed all tables",
    {"tables": 25, "schemas": 2}
)
```

## API Endpoints for Real-Time Logs

### 1. Get and Clear Logs
```bash
GET http://localhost:8001/debug/logs
```

Returns all buffered logs and clears the buffer:
```json
{
  "logs": [
    {
      "timestamp": "2025-01-15T10:30:45.123456",
      "type": "TOOL_CALL",
      "message": "\n🔧 Tool Call: search_tables\n────────────────────────────────────────────────────────────────\n  tool_id: search_tables_0\n  arguments: {\"keyword\": \"orders\"}\n  timestamp: 2025-01-15T10:30:45.123456\n────────────────────────────────────────────────────────────────\n",
      "session_id": "20250115_103045"
    }
  ],
  "status": "success"
}
```

### 2. Stream Logs (Non-destructive)
```bash
GET http://localhost:8001/debug/logs/stream
```

Returns logs without clearing the buffer (useful for polling).

## Viewing Logs

### Terminal Output
Logs appear in real-time in the terminal where you started the service:
```
────────────────────────────────────────────────────────────────
🔧 Tool Call: search_tables
────────────────────────────────────────────────────────────────
  tool_id: search_tables_0
  arguments:
    keyword: orders
  timestamp: 2025-01-15T10:30:45.123456
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
🔍 Scout Mode: search_tables
────────────────────────────────────────────────────────────────
  operation: search_tables
  query: keyword='orders'
  tables_searched:
    - orders
    - order_items
    - order_status
  result_count: 3
  timestamp: 2025-01-15T10:30:45.200000
  top_results:
    - table_name: orders
      score: 0.95
    - table_name: order_items
      score: 0.87
────────────────────────────────────────────────────────────────
```

### File Logs
Read the comprehensive log file:
```bash
tail -f logs/langgraph_debug.log
```

### Web Frontend (Recommended)
If the frontend is updated to call `/debug/logs/stream`, logs will stream in real-time.

## Monitoring Scout Mode

Scout mode operations are logged with all details:

```
🔍 Scout Mode: search_tables
────────────────────────────────────────────────────────────────
  operation: search_tables
  query: keyword='orders'
  tables_searched:
    - orders
    - order_items
    - order_status
  result_count: 3
  top_results:
    - table_name: orders
      score: 0.95
    - table_name: order_items
      score: 0.87
    - table_name: order_status
      score: 0.73
```

## Monitoring Intent Parsing

Intent parsing shows what was detected and if clarification is needed:

```
📝 Intent Parsed: query
────────────────────────────────────────────────────────────────
  user_query: How many orders did we send out in September?
  intent_type: query
  confidence: 0.95
  extracted_entities:
    - orders
    - September
────────────────────────────────────────────────────────────────
```

## Monitoring SQL Generation

See exactly what SQL was generated and why:

```
🔄 SQL Generated
────────────────────────────────────────────────────────────────
  sql: SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9 AND YEAR(order_date) = 2025
  reason: Intent: query, Entities: orders, September, 2025
  timestamp: 2025-01-15T10:30:46.500000
  tables_used:
    - orders
────────────────────────────────────────────────────────────────
```

## Monitoring Query Execution

Track query performance and results:

```
⚡ Query Executed
────────────────────────────────────────────────────────────────
  sql: SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9...
  status: ✅ SUCCESS
  rows_returned: 1
  duration_ms: 123.45
  timestamp: 2025-01-15T10:30:46.700000
────────────────────────────────────────────────────────────────
```

## Example: Full Query Flow Logs

Here's a complete flow from start to finish:

```
────────────────────────────────────────────────────────────────
🔧 Tool Call: search_tables
────────────────────────────────────────────────────────────────
  tool_id: search_tables_0
  arguments:
    keyword: orders
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
✅ Tool Result: search_tables
────────────────────────────────────────────────────────────────
  tool_name: search_tables
  status: ✅ SUCCESS
  result_preview: Found 3 matching tables
  duration_ms: 45.23
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
🔍 Scout Mode: search_tables
────────────────────────────────────────────────────────────────
  operation: search_tables
  query: keyword='orders'
  tables_searched:
    - orders
    - order_items
    - order_status
  result_count: 3
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
📝 Intent Parsed: query
────────────────────────────────────────────────────────────────
  user_query: How many orders in September?
  intent_type: query
  confidence: 0.95
  extracted_entities:
    - orders
    - September
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
🎯 Decision: Route to table selection
────────────────────────────────────────────────────────────────
  decision: Route to table selection
  reason: Intent is query type, need to select relevant tables
  options_considered:
    - clarify
    - query
    - schema_query
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
🔄 SQL Generated
────────────────────────────────────────────────────────────────
  sql: SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9
  reason: Intent: query, Entities: orders, September
  tables_used:
    - orders
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
⚡ Query Executed
────────────────────────────────────────────────────────────────
  sql: SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9
  status: ✅ SUCCESS
  rows_returned: 1
  duration_ms: 156.78
────────────────────────────────────────────────────────────────
```

## Troubleshooting with Logs

### Issue: MCP Server Connection Error
Look for TOOL_CALL logs with "list_tables", "search_tables", etc., and check for HTTP errors:
```
🔧 Tool Call: search_tables
  arguments: {"keyword": "orders"}

❌ Error
  error_type: HTTP error
  message: Connection refused
```

### Issue: Intent Not Detected
Check INTENT_PARSE logs for low confidence:
```
📝 Intent Parsed: clarify
  confidence: 0.35  ← Low confidence!
  missing_fields: [tables, date_range]
```

### Issue: Wrong SQL Generated
Compare what was in INTENT_PARSE vs what ended up in SQL_GENERATED:
```
📝 Intent Parsed: query
  extracted_entities: [orders, September]

🔄 SQL Generated
  sql: SELECT * FROM customers  ← Wrong table!
```

### Issue: Slow Query
Check QUERY_EXECUTION logs for duration:
```
⚡ Query Executed
  duration_ms: 5000.23  ← Very slow!
```

## Log File Location

- **Main log**: `logs/langgraph_debug.log`
- **Session ID**: Recorded in each log entry (e.g., `20250115_103045`)

## Configuration

To customize logging behavior, modify `debug_logger.py`:

```python
# Change log directory
logger = DebugLogger("langgraph", log_dir="/custom/path/logs")

# Change log level
logger.logger.setLevel(logging.DEBUG)  # More verbose
logger.logger.setLevel(logging.INFO)   # Less verbose
```

## Best Practices

1. **Monitor logs while testing** - Watch terminal output or `/debug/logs/stream`
2. **Clear logs regularly** - Call `/debug/logs` to get and clear buffer
3. **Check timing** - Look for slow operations in duration_ms
4. **Verify decisions** - Confirm intent parsing and routing decisions
5. **Track confidence** - Low confidence scores indicate uncertain detections
6. **Review errors** - Check errors with full context in logs

## Integration with Frontend

Update your frontend to poll `/debug/logs/stream` every 1-2 seconds:

```javascript
async function streamDebugLogs() {
  const response = await fetch('http://localhost:8001/debug/logs/stream');
  const data = await response.json();
  
  data.logs.forEach(log => {
    console.log(`[${log.type}] ${log.message}`);
    // Display in your UI
  });
}

// Poll every 1 second
setInterval(streamDebugLogs, 1000);
```

## Summary

This comprehensive logging system provides:
- ✅ Complete visibility into all operations
- ✅ Easy-to-read formatted output
- ✅ Real-time streaming to frontend
- ✅ Performance metrics
- ✅ Detailed error context
- ✅ Scout mode transparency
- ✅ Intent parsing insights

Use it to debug issues, optimize performance, and understand system behavior!