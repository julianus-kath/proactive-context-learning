# 🎯 START HERE: Phase 9 Deep Debugging

## The Problem

Your Phase 9 changes broke the workflow. Only `search_tables` is called. Downstream agents don't run. You get bad responses.

## The Solution

Use the new debugging system to see **exactly** what's happening at each step.

## 3-Minute Quick Start

### Step 1: Open 3 Terminal Windows

Just open three terminal tabs/windows. You'll use them simultaneously.

### Step 2: Terminal 1 - Start Services

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code
bash start_all_services_mac.sh
```

**Wait for it to say:**
```
✅ Web UI is ready: http://localhost:3000
✅ LangGraph Studio is ready: http://localhost:2024
✅ LangGraph Service is ready: http://localhost:5001
```

Takes ~30 seconds.

### Step 3: Terminal 2 - Start the Debugger

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code
python debug_stream_v2.py
```

**You should see:**
```
🔬 DEEP WORKFLOW DEBUGGER - Phase 9 Intent Parser Investigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Connecting to: http://localhost:5001

[waiting for logs...]
```

Leave this running. It will update in real-time.

### Step 4: Terminal 3 - Send a Test Query

```bash
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers do we have?"}'
```

**Immediately watch Terminal 2** - you'll see real-time output showing every step.

## What You'll See

### Successful Example

```
═══════════════════════════════════════════════════════════════
📚 AGENT: INDEX_DATABASE #1 | 🚀 ENTRY
═══════════════════════════════════════════════════════════════

🚀 [14:23:45.123] Entering agent index_database with 3 state keys
State keys: user_input, messages, session_id

✅ [14:23:45.234] Exiting after processing
🔄 STATE CHANGES:
  ➕ Added keys: ['catalog', 'mcp_status']

════════════════════════════════════════════════════════════════
🧠 AGENT: PARSE_INTENT #2 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

🧠 [14:23:46.000] Parsing intent with LLM

Intent:
  operation:                 query
  confidence:                0.95
  primary_entities:          ['customers']
  keywords_for_discovery:    ['customers', 'total']  ← GOOD
  metrics:                   ['count']

✅ [14:23:46.200] Exiting after processing
🔄 STATE CHANGES:
  🔄 Modified keys: ['intent']

════════════════════════════════════════════════════════════════
🔍 AGENT: DISCOVERY #3 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

Intent keywords for discovery: ['customers', 'total']  ← GOOD - SAME AS BEFORE

📡 MCP TOOL: search_tables
  Tool: search_tables
  Params:
    query: customers total
    page: 1

📊 MCP RESULT: search_tables
  Tool: search_tables
  status: ✅ OK
  candidates_count: 3  ← GOOD - NOT 943

✅ [14:23:47.000] Exiting after processing
🔄 STATE CHANGES:
  ➕ Added keys: ['relevant_tables', 'schema_snippet', 'candidate_views']

════════════════════════════════════════════════════════════════
🔗 AGENT: JOIN_SQL #4 | 🚀 ENTRY  ← GOOD - CONTINUES
════════════════════════════════════════════════════════════════

[... more agents continue ...]

Response: "We have 12,543 customers."  ← GOOD - NATURAL ANSWER
```

### Broken Example

```
════════════════════════════════════════════════════════════════
🧠 AGENT: PARSE_INTENT #2 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

[parses query...]

✅ [14:23:46.200] Exiting after processing
🔄 STATE CHANGES:
  intent: {}  ← BAD - EMPTY INTENT

════════════════════════════════════════════════════════════════
🔍 AGENT: DISCOVERY #3 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

Intent keywords for discovery: []  ← BAD - EMPTY

📡 MCP TOOL: search_tables
  Tool: search_tables
  Params:
    query: how many customers do we have  ← BAD - ALL WORDS
    page: 1

📊 MCP RESULT: search_tables
  Tool: search_tables
  status: ✅ OK
  candidates_count: 943  ← BAD - TOO MANY

[No downstream agents run]

Response: "Please write SQL manually"  ← BAD
```

## Quick Diagnosis (30 seconds)

Look for these ✅ or ❌:

```
✅ After PARSE_INTENT, is intent populated?
   Look for: keywords_for_discovery: ['...']

✅ In DISCOVERY, does it have the same keywords?
   Should match PARSE_INTENT keywords

✅ Does search_tables return ~3 candidates?
   Should be ~3, NOT 943

✅ After DISCOVERY, does JOIN_SQL appear?
   Should say "🔗 AGENT: JOIN_SQL #4 | 🚀 ENTRY"

✅ Do all 5-6 agents appear in order?
   INDEX → PARSE → DISCOVERY → JOIN → EXEC → ANSWER
```

If all ✅, system works.

If any ❌, you found the problem. Read the relevant section below.

## Problem Finder Guide

### Problem #1: Intent is Empty After Parsing

```
✅ PARSE_INTENT exits
  intent: {}  ← BAD
```

**Read:** `PHASE_9_DEBUG_QUICK_REFERENCE.md` → "BROKEN FLOW #1: Intent Not Populated"

**Check:** `langgraph_integration/agents/intent_parser/agent.py` - is parse() working?

**Fix:** Add logging to IntentParserAgent

### Problem #2: Intent Lost Between Nodes

```
✅ PARSE_INTENT exits
  intent: {'operation': 'query', ...}  ← Good
  
🔍 DISCOVERY enters
  intent: {}  ← Bad - Different!
```

**Read:** `PHASE_9_DEBUG_QUICK_REFERENCE.md` → "BROKEN FLOW #2: State Isolation"

**Check:** `langgraph_integration/orchestrator.py` - does each node return state?

**Fix:** Verify nodes return modified state

### Problem #3: Too Many Search Calls or Wrong Keywords

```
📡 MCP TOOL: search_tables (called 5 times)
  "how", "many", "customers", "do", "we"  ← Wrong keywords
```

**Read:** `PHASE_9_DEBUG_QUICK_REFERENCE.md` → "Problem #3"

**Check:** `langgraph_integration/agents/discovery/agent.py` - _extract_keywords()

**Fix:** Make sure it uses intent["keywords_for_discovery"] not re-extracting

### Problem #4: Workflow Stops After Discovery

```
✅ DISCOVERY exits
  Added: relevant_tables, schema_snippet
  
❌ No JOIN_SQL entry
```

**Read:** `PHASE_9_DEBUG_QUICK_REFERENCE.md` → "BROKEN FLOW #3: Workflow Stops Early"

**Check:** `langgraph_integration/orchestrator.py` - graph.add_edge("discovery", "join_sql")

**Fix:** Verify graph routing

## Files for Reading

**If you have 2 minutes:**
- Read this file (you're reading it now)

**If you have 5 minutes:**
- Read `PHASE_9_DEBUG_QUICK_REFERENCE.md`

**If you have 15 minutes:**
- Read `PHASE_9_DEEP_DEBUG_GUIDE.md`

**If you need to add logging:**
- Check `PHASE_9_DEEP_DEBUG_GUIDE.md` → "Detailed Log Format" section

## Common Queries to Test

Try different queries to isolate the issue:

```bash
# Simple count
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "Count customers"}'

# Entity question
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "customers"}'

# Schema question
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "What tables do we have?"}'
```

Each should show different intent parsing results.

## Saving Debug Output

To save output for analysis:

```bash
# Terminal 2
python debug_stream_v2.py > debug_output.txt 2>&1
```

Then:
```bash
# Terminal 3
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers?"}'

sleep 2
# Stop Terminal 2 (Ctrl+C)

# Now you have complete output in debug_output.txt
```

## Next Steps After Finding the Problem

1. **Identify** which step breaks (use the diagnostic guide above)
2. **Document** what you see (save debug output)
3. **Isolate** the code causing it
4. **Add logging** to understand why
5. **Fix** the issue
6. **Verify** with debugger again
7. **Test** different queries

## If It All Works

If you see all ✅ marks and natural language responses, then:

1. Phase 9 integration is actually working
2. The issue is elsewhere
3. Check if maybe it's a network/MCP connectivity problem
4. Or check if it's specific to certain queries

## Getting Help

When you ask for help, provide:

1. **The debug output** (at least first 100 lines)
2. **What query you sent**
3. **What response you got**
4. **Which step you identified as broken** (using the checklist)
5. **Any error messages** from the debug output

Example:
```
Query: "How many customers?"

Debug output shows:
- ✅ INDEX_DATABASE works
- ✅ PARSE_INTENT creates intent with keywords: ['customers']
- ❌ DISCOVERY doesn't receive intent
  (State isolation issue)
- ❌ JOIN_SQL never runs
- ❌ EXEC_RECOVERY never runs
- ❌ ANSWER never runs

Final response: "Please write SQL manually"

ROOT CAUSE: Intent lost between PARSE_INTENT and DISCOVERY
```

This is much better than "it doesn't work" 😊

---

## TL;DR Ultra Quick Version

```bash
# Terminal 1
bash start_all_services_mac.sh

# Terminal 2
python debug_stream_v2.py

# Terminal 3
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers?"}'

# Watch Terminal 2 for real-time output
# Find the first ❌
# Use problem finder guide above
# Done!
```

---

**Status:** ✅ Ready to investigate

**Time to first insights:** 5 minutes

**Time to root cause:** 15 minutes

**Good luck! 🔬**