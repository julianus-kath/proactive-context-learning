# Quick Start: Comprehensive Logging System

## TL;DR - Get Logs Running in 30 Seconds

### 1. Start your application
```bash
python chatbot_ui/langgraph_service.py
```

### 2. Watch logs appear in terminal
You'll see real-time output like:
```
────────────────────────────────────────────────────────────────
🔧 Tool Call: search_tables
────────────────────────────────────────────────────────────────
  arguments: {"keyword": "orders"}
  timestamp: 2025-01-15T10:30:45.123456
────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────
✅ Tool Result: search_tables
────────────────────────────────────────────────────────────────
  duration_ms: 45.23
────────────────────────────────────────────────────────────────
```

### 3. (Optional) View logs via API
In another terminal:
```bash
curl http://localhost:8001/debug/logs/stream | python -m json.tool
```

Done! That's all you need to see comprehensive logs.

---

## What You'll See

### Tool Calls
Every MCP tool call is logged with arguments and timing
```
🔧 search_tables → arguments
✅ Result (45.23ms)
```

### Scout Mode
When the system searches for tables:
```
🔍 Scout Mode: search_tables
  query: keyword='orders'
  matches: 3 tables found
  top_results: [orders, order_items, order_status]
```

### Intent Parsing
When the system understands your query:
```
📝 Intent Parsed: query
  user_query: How many orders in September?
  confidence: 0.95
  entities: [orders, September]
```

### SQL Generation
When SQL is created:
```
🔄 SQL Generated
  sql: SELECT COUNT(*) FROM orders WHERE MONTH(order_date) = 9
  reason: User asked for count
  tables_used: [orders]
```

### Query Execution
When queries run:
```
⚡ Query Executed
  status: ✅ SUCCESS
  rows_returned: 1
  duration_ms: 156.78
```

### Errors
When something fails (with full context):
```
❌ Error: MCP connection timeout
  error: Connection refused
  context: url=http://localhost:8000, timeout=30
```

---

## Common Views

### View in Terminal (Best for Real-Time)
```bash
# Terminal 1: Start service
python chatbot_ui/langgraph_service.py

# Terminal 2: Watch logs
tail -f logs/langgraph_debug.log
```

### View via API (Best for Automation)
```bash
# Get and clear logs
curl http://localhost:8001/debug/logs

# Stream logs (doesn't clear)
curl http://localhost:8001/debug/logs/stream
```

### View in File
```bash
# Read from start
cat logs/langgraph_debug.log

# Follow file
tail -f logs/langgraph_debug.log

# Search for errors
grep "❌" logs/langgraph_debug.log

# Search for scout mode
grep "🔍" logs/langgraph_debug.log
```

---

## Test the Logging System

Verify everything works:
```bash
python tests/test_debug_logging.py
```

You'll see 15 different log examples and confirmation that the system works.

---

## Integrating with Frontend

Poll logs in your frontend (JavaScript):
```javascript
async function getDebugLogs() {
  const response = await fetch('http://localhost:8001/debug/logs/stream');
  const data = await response.json();
  
  data.logs.forEach(log => {
    console.log(`[${log.type}] ${log.message}`);
    // Display in UI
  });
}

// Poll every 1 second
setInterval(getDebugLogs, 1000);
```

---

## Troubleshooting Your Issues

### Issue: "Timeout Error" in logs
Look for:
```
🔧 Tool Call: [tool_name]
❌ Tool Result
  error: TimeoutError
```
**Fix**: Check MCP server is running

### Issue: "JSON Parsing Error"
Look for:
```
❌ Error
  error: Failed to parse JSON response
```
**Fix**: Check MCP server returns valid JSON

### Issue: "0 tables across 0 schemas"
This appears in `_index_database`. Look for scout mode results:
```
🔍 Scout Mode: list_tables
  result_count: 0  ← Problem!
```
**Fix**: Check database connection and schema

### Issue: Wrong intent detected
Look for low confidence:
```
📝 Intent Parsed: clarify
  confidence: 0.35  ← Too low!
  missing_fields: [tables, date_range]
```
**Fix**: Ask more specific questions

---

## Log Levels

| Emoji | Meaning | Color |
|-------|---------|-------|
| 🔧 | Starting operation | Blue |
| ✅ | Success | Green |
| ❌ | Error | Red |
| ⚠️ | Warning | Yellow |
| 🔍 | Discovery/Search | Cyan |
| 📝 | Decision/Analysis | Purple |
| 📊 | Data/Schema | Orange |
| ⏱️ | Performance | Gray |

---

## Performance Metrics

Look for timing info in logs:
```
Duration_ms: 45.23     ← Fast
Duration_ms: 5000.00   ← Slow (warning!)
```

Most operations should complete in <1000ms.

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/debug/logs` | GET | Get logs and **clear buffer** |
| `/debug/logs/stream` | GET | Get logs **without clearing** |
| `/health` | GET | Check service health |

---

## File Locations

| File | Purpose |
|------|---------|
| `logs/langgraph_debug.log` | Main debug log file |
| `langgraph_integration/debug_logger.py` | Logging system code |
| `langgraph_integration/DEBUG_LOGGING_GUIDE.md` | Full documentation |
| `tests/test_debug_logging.py` | Test script |

---

## Next Steps

1. ✅ **Run your app**
   ```bash
   python chatbot_ui/langgraph_service.py
   ```

2. ✅ **Watch logs in terminal**
   - See real-time operations
   - Notice tool calls and results
   - Watch for errors

3. ✅ **Test scout mode**
   - Query the system
   - Check scout mode logs to see table searches

4. ✅ **Monitor performance**
   - Look for duration_ms values
   - Identify slow operations

5. ✅ **(Optional) Integrate with frontend**
   - Poll `/debug/logs/stream`
   - Display in UI panel

---

## Quick Tips

- 💡 **Always watch terminal** for immediate feedback
- 💡 **Check `/debug/logs` endpoint** during development
- 💡 **Search logs for emojis** to find specific issues
- 💡 **Look for confidence scores** to find uncertain detections
- 💡 **Compare scout mode results** with actual schema
- 💡 **Track timing** for performance optimization

---

## That's It!

You now have comprehensive visibility into:
- ✅ All tool calls and results
- ✅ Scout mode table searches
- ✅ Intent parsing decisions
- ✅ SQL generation and execution
- ✅ Performance metrics
- ✅ Errors with full context

Happy debugging! 🎯