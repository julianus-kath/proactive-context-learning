# 🚀 START HERE - Real-Time Debugging for LangGraph

## Your Problem
You couldn't see what the agent was doing. You kept getting generic "I need more information" responses without understanding why.

## The Solution
A real-time debugging system that shows **every step** the agent takes. **Setup takes 90 seconds.**

---

## IMMEDIATE ACTION (Right Now!)

### Step 1: Fix Your .env File
First, fix the URL issue we identified earlier:
```bash
# Open .env and change:
# FROM: MCP_SERVER_URL=http://192.168.1.358000
# TO:   MCP_SERVER_URL=http://192.168.1.35:8000
```

### Step 2: Open 3 Terminal Windows

**Terminal 1 - Start Services:**
```bash
./start_all_services_mac.sh
```

Wait for:
```
✅ All Mac services started successfully!
  🌐 Web UI:           http://localhost:3000
  🤖 LangGraph:        http://localhost:5001
```

**Terminal 2 - Monitor Execution (NEW!) ⭐**
```bash
python3 debug_stream.py
```

Wait for:
```
🔍 LangGraph Real-time Debug Stream Monitor
Connecting to http://localhost:5001...
```

**Terminal 3 - Ask Questions:**
```bash
# Option A: Open web UI
open http://localhost:3000

# Option B: Use curl
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How many customers do we have?"}], "api_key": "supersecretapikey"}'
```

### Step 3: Watch Terminal 2

When you ask a question, Terminal 2 shows **everything**:

```
[10:30:45.123] 🔍 SCOUT MODE: Analyzing user query
[10:30:45.234] 📊 Extracted keywords
[10:30:45.345] ✅ Scout mode found 2 matching tables
[10:30:45.456] 📝 Intent Analysis: operation=query, confidence=0.95
[10:30:45.567] 🔄 SQL generated: SELECT COUNT(*) FROM customers
[10:30:45.678] ⚡ Query Executed: ✅ SUCCESS (1 rows, 15.23ms)
```

---

## What Changed (For Your Understanding)

### Bug Fixes
✅ Fixed `'NoneType' object has no attribute 'get'` error in clarify node  
✅ Added null-safety checks and better error logging

### New Visibility  
✅ **Scout Mode:** See tables being searched and selected  
✅ **Intent:** See why routing decision was made  
✅ **SQL:** See generated queries and table context  
✅ **Execution:** See results and performance metrics  
✅ **Startup:** See catalog indexing progress  

### New Tools
✅ `debug_stream.py` - Real-time log monitor (run in Terminal 2)  
✅ Enhanced startup script - Shows logs as services start  

---

## Common Debugging Scenarios

### Scenario 1: You Get Generic Response
**Terminal 2 will show:**
```
⚠️  Intent: CLARIFY - Missing fields: ['location']
   → Will route to clarification node
```

**This means:** Intent parser thinks it needs more info  
**Solution:** Read DEBUGGING_GUIDE.md section on answer-first defaults

### Scenario 2: Scout Mode Isn't Being Called
**Terminal 2 will show:**
```
✅ Intent: QUERY
   → Direct SQL provided: SELECT ...
   → Will route to execute_direct
```

**This means:** SQL was provided directly (OK for simple queries)

### Scenario 3: Scout Mode Search Failed
**Terminal 2 will show:**
```
⚠️  Scout mode search failed: Connection refused
```

**This means:** Windows MCP server is down  
**Fix:** On Windows machine, run: `start_mcp_server_windows.bat`

---

## Documentation (In Order of Importance)

1. **README_DEBUG_SYSTEM.md** ← Start here for quick reference
2. **QUICK_DEBUG_START.md** ← Detailed troubleshooting checklist
3. **DEBUGGING_GUIDE.md** ← Complete reference (600+ lines)
4. **DEBUG_IMPLEMENTATION_SUMMARY.md** ← Technical details

---

## Expected Workflow After Setup

```
You (Terminal 3):
"How many customers do we have?"
         ↓
LangGraph (Terminal 1 background):
Runs the query processing
         ↓
Debug Stream (Terminal 2):
Shows EVERY STEP in real-time with colors:
  🔍 SCOUT MODE: Found tables
  📝 INTENT: Decision made
  🔄 SQL: Generated query
  ⚡ EXECUTE: Got results
         ↓
UI (Terminal 3):
Displays final answer
```

---

## Quick Commands

```bash
# See if everything's working
curl http://localhost:5001/health

# Make a test API call
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test"}],
    "api_key": "supersecretapikey"
  }'

# Check logs the old way if needed
tail -f logs/langgraph.log
```

---

## Troubleshooting First Steps

**Problem:** debug_stream.py won't connect
```
❌ Cannot connect to service (attempt 1/5)...
```
**Fix:** Make sure Terminal 1 services are running. Wait 5-10 seconds for LangGraph startup.

**Problem:** No logs appearing in Terminal 2 even after asking question
**Fix:** Check Terminal 1 has both services running (Web UI + LangGraph)

**Problem:** MCP server connection error
```
❌ Cannot connect to MCP server at http://192.168.1.35:8000
```
**Fix:** Check .env file has correct IP:port. On Windows, run MCP batch file.

---

## Files You Don't Need to Touch

- ✅ `langgraph_integration/graph_definition.py` - Already updated
- ✅ `start_all_services_mac.sh` - Already updated
- ✅ All the `.md` documentation files - Just reference them

---

## What NOT to Do

❌ Don't modify debug_stream.py unless you want to customize colors  
❌ Don't disable the startup script's log streaming  
❌ Don't ignore warnings about MCP server - fix it first  

---

## Success Indicators

✅ Terminal 1: Services start with real-time logs  
✅ Terminal 2: Shows "Connecting..." then waits for queries  
✅ Terminal 3: You can ask questions and get answers  
✅ Terminal 2: Shows 🔍 🔄 ⚡ emojis when you ask questions  
✅ You understand **why** the agent made each decision  

---

## Next 5 Minutes

1. **[1 min]** Fix .env file (IP:port)
2. **[1 min]** Start Terminal 1: `./start_all_services_mac.sh`
3. **[1 min]** Start Terminal 2: `python3 debug_stream.py`
4. **[1 min]** Ask question in Terminal 3
5. **[1 min]** Watch Terminal 2 for complete execution flow

---

## That's It!

Now you have:
- ✅ Real-time visibility into scout mode
- ✅ Clear routing decision explanations
- ✅ Tool call tracking
- ✅ SQL generation visibility
- ✅ Query execution metrics
- ✅ Easy troubleshooting

**Your next command:**
```bash
./start_all_services_mac.sh
```

Then in a new terminal:
```bash
python3 debug_stream.py
```

Then ask a question and **watch the magic happen**. 🎯

---

**Need help?** Read README_DEBUG_SYSTEM.md or DEBUGGING_GUIDE.md

**Ready?** Start with Terminal 1 above! 🚀