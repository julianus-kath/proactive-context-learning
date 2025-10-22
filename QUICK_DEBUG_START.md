# Quick Debug Start - Real-Time Visibility into Scout Mode

## The Problem You Had
✗ Generic response: "I need more information..."  
✗ No visibility into what's happening  
✗ Couldn't see if scout mode was being used  
✗ Slow log updates  

## The Solution (3 Terminal Setup)

### Terminal 1: Start Services
```bash
./start_all_services_mac.sh
```

You'll now see **real-time startup logs** instead of delayed output. Look for:
```
🚀 Initializing LangGraph workflow...
📚 Starting database catalog indexing...
✅ Database catalog indexed successfully
   Total tables: 42
   Schemas found: 3 (public, audit, system)
✅ LangGraph workflow initialized successfully
```

### Terminal 2: Monitor Real-Time Debug Stream ⭐ NEW
```bash
python3 debug_stream.py
```

This shows **every step** the agent takes. When you ask a question, you'll see:

```
[10:30:45.123] 🔍 SCOUT MODE: Analyzing user query: How many customers do we have?
[10:30:45.234] 📊 Extracted keywords: ['customers']
[10:30:45.345] 🔎 Searching tables with keyword: 'customers'
[10:30:45.456] ✅ Scout mode found 2 matching tables
[10:30:45.567]   ✓ Selected table: public.customers
[10:30:45.678]   ✓ Selected table: public.customer_orders
[10:30:45.789] 🎯 Selected 2 relevant tables for query
[10:30:45.890] 📋 Fetching fresh schemas for 2 new tables
[10:30:46.001] ✅ Successfully described 2 tables
[10:30:46.112] 📝 Built schema snippet (512 chars) for 2 tables
[10:30:46.223] 📝 Intent Analysis Complete:
[10:30:46.334]    Operation: query
[10:30:46.445]    Confidence: 0.95
[10:30:46.556]    Entities: ['customers']
[10:30:46.667] ✅ Intent: QUERY
[10:30:46.778]    → Will route to scout mode (select_tables)
[10:30:46.889] 🔄 SQL generated: SELECT COUNT(*) FROM public.customers
[10:30:46.990] ⚡ Executing query (timeout: 30000ms, max_rows: 1000)
[10:30:47.101] ⚡ Query Executed
[10:30:47.212]    Status: ✅ SUCCESS
[10:30:47.323]    Rows returned: 1
[10:30:47.434]    Duration: 12.43ms
```

### Terminal 3: Ask Questions
```bash
# Use the web UI or make API calls
# Whatever you ask will show up in Terminal 2 immediately
```

---

## Key Changes Made

### 1. ✅ Fixed NoneType Error in _clarify
- Added defensive checks for None intent_analysis
- Added logging to show what's happening

### 2. 🔍 Enhanced Scout Mode Logging
- Shows extracted keywords
- Shows table search results
- Shows which tables were selected
- Shows cache hits vs. fresh fetches
- Shows schema snippet building

### 3. 📝 Enhanced Intent Parsing Logging  
- Shows routing decision (query vs clarify vs schema_query)
- Shows if SQL was provided directly
- Shows missing fields that triggered clarification
- Shows defaults that were applied

### 4. 🔄 Enhanced SQL Generation Logging
- Shows schema snippet preview
- Shows tables used
- Shows reason for SQL (which intent/entities)

### 5. ⚡ Enhanced Query Execution
- Shows execution status
- Shows rows returned
- Shows duration
- Shows any errors with full context

### 6. 📚 Enhanced Startup Logging
- Shows catalog indexing progress
- Shows total tables and schemas
- Shows if catalog indexing failed

---

## What to Watch For (Troubleshooting)

### ✅ Normal: Scout Mode Working
```
🔍 SCOUT MODE: Analyzing user query
✅ Scout mode found X matching tables
🎯 Selected X relevant tables
```

### ✗ Problem: Scout Mode Skipped
```
✅ Intent: QUERY
   → Direct SQL provided: SELECT * FROM ...
   → Will route to execute_direct (skip table selection)
```
**Why:** Intent parser provided SQL directly (can be OK for simple queries)

### ✗ Problem: Scout Mode Failed
```
⚠️  Scout mode search failed: Connection refused
⚠️  Falling back to schema overview
```
**Why:** MCP server not responding. Check Windows MCP is running.

### ✗ Problem: Generic Response Triggered
```
📝 Intent Analysis Complete:
   Operation: clarify
⚠️  Intent: CLARIFY - Missing fields: ['location']
   → Will route to clarification node
```
**Why:** Too many missing fields. Check if defaults should apply.

---

## Files Created/Modified

### New Files
- `debug_stream.py` - Real-time debug monitor (run in Terminal 2)
- `DEBUGGING_GUIDE.md` - Comprehensive debugging documentation
- `QUICK_DEBUG_START.md` - This file

### Modified Files
- `langgraph_integration/graph_definition.py` - Added comprehensive logging to all nodes
- `start_all_services_mac.sh` - Added real-time log streaming during startup

---

## API-Based Monitoring (Alternative)

If you prefer not to run `debug_stream.py`, you can poll the API:

```bash
# Get logs (clears buffer)
curl http://localhost:5001/debug/logs -H "X-API-Key: supersecretapikey"

# Stream logs (doesn't clear buffer)
curl http://localhost:5001/debug/logs/stream -H "X-API-Key: supersecretapikey"

# Returns JSON with all buffered logs
{
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:45.123",
      "type": "SCOUT_MODE",
      "message": "Scout Mode: search_tables",
      "session_id": "..."
    }
  ],
  "status": "success"
}
```

---

## Quick Commands

```bash
# Run everything (all 3 terminals)

# Terminal 1
./start_all_services_mac.sh

# Terminal 2 (once services are running)
python3 debug_stream.py

# Terminal 3 (make requests)
# Use web UI at http://localhost:3000
# OR make curl requests:
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "How many customers do we have?"}],
    "api_key": "supersecretapikey"
  }'
```

---

## Next Steps

1. **Start the services** with the enhanced startup script
2. **Run debug_stream.py** to see real-time execution
3. **Ask a question** through the web UI or API
4. **Watch the debug stream** to see scout mode, table selection, and SQL generation
5. **Check DEBUGGING_GUIDE.md** if something unexpected happens

You should now see **complete visibility** into what's happening at each step! 🎉