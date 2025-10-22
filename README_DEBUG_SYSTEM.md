# Real-Time Debugging - Quick Start (TL;DR)

## What's New
You complained you couldn't see what's happening. Now you can. ✅

## Setup (3 terminals, 2 minutes)

### Terminal 1: Start Services
```bash
./start_all_services_mac.sh
```
Wait for:
```
✅ All Mac services started successfully!
```

### Terminal 2: Watch Everything ⭐ NEW
```bash
python3 debug_stream.py
```

### Terminal 3: Ask Questions
Open http://localhost:3000 or use curl:
```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Show me all customers"}], "api_key": "supersecretapikey"}'
```

---

## What You'll See in Terminal 2

**The good flow (scout mode working):**
```
🔍 SCOUT MODE: Analyzing user query: Show me all customers
📊 Extracted keywords: ['customers']
✅ Scout mode found 2 matching tables
  ✓ Selected table: public.customers
🎯 Selected 2 relevant tables
📝 Intent Analysis Complete: Operation: query
✅ Intent: QUERY → Will route to scout mode
🔄 SQL generated: SELECT * FROM public.customers
⚡ Query Executed: ✅ SUCCESS (42 rows)
```

**The problem (generic response):**
```
⚠️  Intent: CLARIFY - Missing fields: ['location']
   → Will route to clarification node
```
Then you get: "I need more information..."

---

## What's Fixed

1. **Error:** `'NoneType' object has no attribute 'get'` ✅ Fixed
2. **Problem:** No visibility into scout mode ✅ Fixed  
3. **Problem:** Can't see routing decisions ✅ Fixed
4. **Problem:** Slow log updates ✅ Fixed (now real-time)
5. **Problem:** Can't tell if tables are being indexed ✅ Fixed (shows at startup)

---

## Common Issues

### Issue: Generic "I need more information" response
**Check in Terminal 2:**
- If you see `🔍 SCOUT MODE:` → Scout is working, check intent decision
- If you don't see scout mode → Intent parser went to "clarify" directly
- If you see `⚠️ Scout mode search failed` → MCP server is down

**Fix:** Usually means answer-first defaults need tuning. See DEBUGGING_GUIDE.md.

### Issue: Scout mode not showing up
**Check in Terminal 2:**
```
✅ Intent: QUERY
   → Direct SQL provided: SELECT ...
   → Will route to execute_direct
```
This means intent parser provided SQL directly (skipping scout mode). This is OK for simple queries.

### Issue: Scout mode search failed
```
⚠️ Scout mode search failed: Connection refused
```
**Fix:** Windows MCP server isn't running. Run: `start_mcp_server_windows.bat`

---

## Files Changed

- ✏️ `langgraph_integration/graph_definition.py` - Added logging everywhere
- ✏️ `start_all_services_mac.sh` - Real-time startup logs
- ✨ `debug_stream.py` - **NEW** Real-time monitor
- 📖 `DEBUGGING_GUIDE.md` - Full documentation
- 📖 `QUICK_DEBUG_START.md` - Detailed guide

---

## Key Logging Locations

All logs go through the debug logger, visible in Terminal 2:

1. **Startup:** Index database, load catalog
2. **Scout Mode:** Search tables, select top 3, fetch schemas
3. **Intent:** Parse user intent, decide routing
4. **SQL:** Generate SQL query
5. **Execute:** Run query, get results
6. **Errors:** Any failures at any step

---

## Advanced: Traditional Log Files

If you don't want to use Terminal 2:

```bash
# Stream logs old-school
tail -f logs/langgraph.log

# Filter for important stuff
tail -f logs/langgraph.log | grep -E "(SCOUT|Intent|SQL|Error|QUERY_EXECUTE)"
```

---

## One-Liner Tests

```bash
# Test 1: Do you see startup logs in Terminal 1?
./start_all_services_mac.sh | head -30

# Test 2: Is debug_stream.py working?
python3 debug_stream.py &
# Wait 3 seconds, should say "Connecting..."
kill %1

# Test 3: Is agent responding?
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "hello"}], "api_key": "supersecretapikey"}'
```

---

## Still Confused?

1. **Read:** QUICK_DEBUG_START.md (180 lines, more detailed)
2. **Read:** DEBUGGING_GUIDE.md (full troubleshooting guide)
3. **Run:** `python3 debug_stream.py` and ask a question
4. **Watch:** Terminal 2 shows you exactly what's happening

The log output IS the documentation at this point. 🎯

---

## TL;DR of TL;DR

**Before:** Can't see what's happening → generic response  
**After:** Run `debug_stream.py` in Terminal 2 → see everything happening in real-time ✅

Start here:
```bash
# Terminal 1
./start_all_services_mac.sh

# Terminal 2
python3 debug_stream.py
```

Then ask your question. Watch Terminal 2. Done! 🚀