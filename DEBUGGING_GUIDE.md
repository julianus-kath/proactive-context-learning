# Real-Time Debugging Guide for LangGraph Workflow

This guide shows you how to monitor the agent's execution flow, scout mode operations, tool calls, and SQL generation in real-time.

## Quick Start

### 1. **Start Services with Real-time Logs** 
Run the Mac startup script as normal:
```bash
./start_all_services_mac.sh
```

The script now shows LangGraph startup logs in real-time. You'll see initialization messages like:
```
🚀 Initializing LangGraph workflow...
✅ LangGraph workflow initialized successfully
✅ Debug logger initialized
```

### 2. **Monitor Real-Time Debug Stream** (New!)
In a **separate terminal**, run the debug stream monitor:
```bash
python3 debug_stream.py
```

This shows:
- 🔍 Scout mode table searches
- 🔧 Tool calls (search_tables, describe_table_batch)
- ✅ Tool results
- 📝 Intent parsing decisions
- 🔄 SQL generation
- ⚡ Query execution
- ❌ Errors with full tracebacks

### 3. **Traditional Log Files**
If you prefer, monitor logs the old way:
```bash
# Terminal 1: Web UI logs
tail -f logs/web_ui.log

# Terminal 2: LangGraph logs (with filtering)
tail -f logs/langgraph.log | grep -E "(SCOUT|🔍|🎯|⚡|❌|✅)"
```

---

## What to Look For

### Scout Mode (Table Selection)
When you ask a question, the agent should enter **Scout Mode** to find relevant tables:

**Expected Flow:**
```
🔍 SCOUT MODE: Analyzing user query: "How many customers do we have?"
📊 Extracted keywords: ['customers']
🔎 Searching tables with keyword: 'customers'
✅ Scout mode found 2 matching tables
  ✓ Selected table: public.customers
  ✓ Selected table: public.customer_orders
🎯 Selected 2 relevant tables for query
```

**Red Flag 🚩:** If you see:
```
⚠️  Scout mode search failed: ...
⚠️  Falling back to schema overview
```
Then scout mode isn't working. Check if MCP server is responding to `search_tables`.

---

### Intent Parsing
After scout mode, the agent analyzes what you're asking for:

**Expected Flow:**
```
📝 Intent Analysis Complete:
   Operation: query
   Confidence: 0.95
   Entities: ['customers']
✅ Intent: QUERY
   → Will route to scout mode (select_tables)
   → Then generate SQL using indexed tables
```

**Red Flag 🚩:** If you see:
```
⚠️  Intent: CLARIFY - Missing fields: ['location', 'time period']
   → Will route to clarification node
```
AND THEN you get the generic "I need more information..." response, it means:
1. Intent parser thinks it needs more info
2. But the answer-first defaults aren't being applied

---

### SQL Generation
After selecting tables, SQL should be generated:

**Expected Flow:**
```
📝 Built schema snippet (500 chars) for 2 tables
📌 Schema snippet preview:
   Table: public.customers
     - id (integer)
     - name (varchar)
     - email (varchar)
🔄 SQL generated: SELECT COUNT(*) FROM public.customers
```

**Red Flag 🚩:** If you see:
```
❌ Error generating SQL: ...
```
Check the full error in the logs.

---

### Query Execution
Finally, SQL is executed and results returned:

**Expected Flow:**
```
⚡ Executing query (timeout: 30000ms, max_rows: 1000)
⚡ Query Executed
   Status: ✅ SUCCESS
   Rows returned: 1
   Duration: 125.43ms
```

---

## Common Issues and Fixes

### Issue 1: "I need more information..." Generic Response

**Cause:** Intent parser is routing to `clarify` node, but generating a fallback message.

**Debug Steps:**
1. Look for `Intent Analysis Complete` in logs
2. Check if operation is `clarify` or `query`
3. If it's `clarify`, check the `missing_fields`
4. If missing fields are just ["schema information", "location"], then answer-first should kick in

**Fix:**
In `langgraph_integration/graph_definition.py`, check the `schema_related` set in `_parse_intent_json_response`:
```python
schema_related = {
    "schema information", "schema", "specific schema",
    "location", "specific location", "region",
    "category", "product category", "specific category",
    "tables to query", "table names"
}
```

Add your missing field if it's schema-related.

---

### Issue 2: Scout Mode Not Being Called

**Debug:**
1. Check if intent operation is `query` (not something else)
2. Look for `🔍 SCOUT MODE:` message
3. If missing, check if SQL was provided directly (execute_direct path)

**Expected log:**
```
✅ Intent: QUERY
   → Will route to scout mode (select_tables)
   → Then generate SQL using indexed tables
🔍 SCOUT MODE: Analyzing user query: ...
```

**If you see:**
```
✅ Intent: QUERY
   → Direct SQL provided: SELECT * FROM ...
   → Will route to execute_direct (skip table selection)
```

Then the intent parser already had SQL and skipped scout mode (this is OK for simple queries).

---

### Issue 3: MCP Server Not Responding

**Debug:**
1. Check if scout mode search failed
2. Look for `Cannot connect to MCP server` in logs
3. Verify Windows MCP is running

**Expected MCP response:**
```
🔧 Tool Call: search_tables_mcp
   arguments: {"query": "customers"}
✅ Tool Result: search_tables_mcp
   Status: ✅ SUCCESS
   Result: {"ok": true, "data": {"results": [...]}}
```

**If you see:**
```
❌ Error: Cannot connect to MCP server at http://192.168.1.35:8000
```

Then:
1. Verify Windows machine is on and connected
2. Check the MCP startup script was run: `start_mcp_server_windows.bat`
3. Verify firewall allows port 8000

---

### Issue 4: Index Database Failed on Startup

**Cause:** The database catalog couldn't be loaded when LangGraph started.

**Debug:**
1. Look for indexing error at startup:
```
❌ Database indexing FAILED: Connection refused
```

2. This sets `catalog_failed` flag
3. When clarify is needed, you get: "I couldn't load the data catalog right now..."

**Fix:**
1. Ensure PostgreSQL is running
2. Check `.env` has correct `POSTGRES_*` variables
3. Restart LangGraph service

---

## Real-Time Monitoring Checklist

When testing a new query, watch for:

✅ **Scout Mode Section:**
- [ ] Keywords extracted correctly
- [ ] Table search returns results
- [ ] 1-3 tables selected
- [ ] Schema descriptions fetched

✅ **Intent Section:**
- [ ] Operation is `query` (not `clarify`)
- [ ] Confidence > 0.8
- [ ] Correct entities extracted

✅ **SQL Generation Section:**
- [ ] Schema snippet shown
- [ ] SQL query generated
- [ ] Uses correct tables from scout mode

✅ **Execution Section:**
- [ ] Query runs successfully
- [ ] Rows returned > 0
- [ ] Duration < 5000ms

---

## Advanced: API-Based Debug Streaming

You can also poll the debug API directly:

```bash
# Get buffered logs and clear buffer
curl http://localhost:5001/debug/logs \
  -H "X-API-Key: supersecretapikey"

# Get logs without clearing (for streaming)
curl http://localhost:5001/debug/logs/stream \
  -H "X-API-Key: supersecretapikey"
```

Both return JSON:
```json
{
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:45.123",
      "type": "SCOUT_MODE",
      "message": "Scout Mode: search_tables",
      "session_id": "20240115_103045"
    }
  ],
  "status": "success"
}
```

---

## Files Modified

This debugging setup uses:
- `langgraph_integration/graph_definition.py` - Added comprehensive logging to all nodes
- `langgraph_integration/debug_logger.py` - Existing debug logger (unchanged)
- `chatbot_ui/langgraph_service.py` - Added streaming endpoints (unchanged in core)
- `start_all_services_mac.sh` - Enhanced with real-time log streaming
- `debug_stream.py` - **NEW** Real-time monitor script

---

## Tips

1. **Color-coded output** helps identify different event types instantly
2. **Emoji prefixes** (🔍, 🔄, ⚡) make scanning logs easier
3. **Two-terminal setup** recommended:
   - Terminal 1: Service startup + background running
   - Terminal 2: Debug stream monitoring
4. **Pipe through grep** for focused debugging:
   ```bash
   tail -f logs/langgraph.log | grep -E "SCOUT|SQL|ERROR"
   ```

---

## Questions?

If you're still seeing generic responses or scout mode isn't triggering:
1. Run `debug_stream.py` while asking the question
2. Capture the full log output (copy-paste from debug stream)
3. Share the logs showing the issue - the detailed output will help identify the problem

Good luck! 🚀