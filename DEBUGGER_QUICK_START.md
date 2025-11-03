# 🔬 LangGraph Debugger - Quick Start Guide

## What's New

When you run `./start_all_services_mac.sh`, you'll now see a **prominent highlighted message** telling you how to watch real-time agent reasoning!

## Two Ways to Use the Debugger

### Option 1: Manual (Default) - Shows Instructions

When services start, you'll see:

```
╔═══════════════════════════════════════════════════════════════╗
║  🔬 WATCH REAL-TIME AGENT REASONING (Recommended!)          ║
╚═══════════════════════════════════════════════════════════════╝
Open a NEW TERMINAL and run:

    tail -f logs/langgraph_debugger.log

This shows:
  ✓ Agent entries/exits with state snapshots
  ✓ Intent parsing (keywords, confidence, operation)
  ✓ Discovery results (tables found)
  ✓ SQL generation and execution
  ✓ Routing decisions and error propagation

💡 This is the best way to debug 'missing info' responses!
```

**Then you manually open a new terminal** and run:
```bash
tail -f logs/langgraph_debugger.log
```

---

### Option 2: Auto-Open (Optional) - Opens Automatically

**To enable auto-open:**

1. Edit `start_all_services_mac.sh`
2. Find this line (around line 211):
   ```bash
   AUTO_OPEN_DEBUGGER="${AUTO_OPEN_DEBUGGER:-0}"
   ```
3. Change it to:
   ```bash
   AUTO_OPEN_DEBUGGER="${AUTO_OPEN_DEBUGGER:-1}"
   ```

**OR** set it as an environment variable before running:
```bash
export AUTO_OPEN_DEBUGGER=1
./start_all_services_mac.sh
```

When enabled, the startup script will **automatically open a new Terminal window** with the debugger output running!

---

## What You'll See in the Debugger

### Example Output for "How many customers do we have?"

```
════════════════════════════════════════════════════
📚 INDEX_DATABASE - ENTRY
════════════════════════════════════════════════════
Input State:
  user_input: "How many customers do we have?"
  messages: [1 message]
  session_id: "abc123"

════════════════════════════════════════════════════
📚 INDEX_DATABASE - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  [No state changes]
✅ MCP healthy, catalog ready

════════════════════════════════════════════════════
🧠 PARSE_INTENT - ENTRY
════════════════════════════════════════════════════
Input State:
  user_input: "How many customers do we have?"
  messages: [1 message]

════════════════════════════════════════════════════
🧠 PARSE_INTENT - EXIT
════════════════════════════════════════════════════

Intent Details:
  operation:              query
  confidence:             0.95
  keywords_for_discovery:  ['customers', 'customer'] ✅
  primary_entities:       ['customers']
  metrics:                 ['count']

🔄 State Changes:
  ➕ Added: intent

════════════════════════════════════════════════════
🚦 ROUTE_OPERATION - ENTRY
════════════════════════════════════════════════════

🚦 Routing Decision: QUERY PIPELINE

════════════════════════════════════════════════════
🔍 DISCOVERY - ENTRY
════════════════════════════════════════════════════
Input State:
  intent:
    operation: query
    keywords_for_discovery: ['customers', 'customer']

📡 MCP Tool Call:
  Tool: search_tables
  Arguments:
    query: "customers customer"
    page: 1
    page_size: 10

📊 MCP Tool Result: ✅ Success
  Tool: search_tables
  Duration: 45.78ms
  Status: ok
  Rows: 10 candidates

════════════════════════════════════════════════════
🔍 DISCOVERY - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: relevant_tables, schema_snippet, column_index
  relevant_tables: ['dbo.KHKArtikelKunden']

════════════════════════════════════════════════════
🔗 JOIN_SQL - ENTRY
════════════════════════════════════════════════════
Input State:
  relevant_tables: ['dbo.KHKArtikelKunden']
  intent:
    metrics: ['count']

════════════════════════════════════════════════════
🔗 JOIN_SQL - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: sql_query, join_plan
  sql_query: "SELECT COUNT(*) AS total_count FROM dbo.KHKArtikelKunden"

════════════════════════════════════════════════════
⚡ EXEC_RECOVERY - ENTRY
════════════════════════════════════════════════════
Input State:
  sql_query: "SELECT COUNT(*) AS total_count FROM dbo.KHKArtikelKunden"

📡 MCP Tool Call:
  Tool: query
  Arguments:
    sql: "SELECT COUNT(*) AS total_count FROM dbo.KHKArtikelKunden"

📊 MCP Tool Result: ✅ Success
  Tool: query
  Duration: 28.49ms
  Status: ok
  Rows: 1

════════════════════════════════════════════════════
⚡ EXEC_RECOVERY - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: exec_result
  🔄 Modified: error_info (cleared), intent.operation (set to "query")
  exec_result.ok: true
  exec_result.row_count: 1

════════════════════════════════════════════════════
✨ ANSWER - ENTRY
════════════════════════════════════════════════════
Input State:
  exec_result:
    ok: true
    row_count: 1
    rows: [{"total_count": 577}]

════════════════════════════════════════════════════
✨ ANSWER - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: final_response
  final_response: "There are 577 customers."
```

## How to Interpret the Output

### ✅ Good Signs (Healthy Flow)
- Each agent shows **ENTRY** → **EXIT**
- **State Changes** show data flowing (e.g., `intent` added, `relevant_tables` added, `sql_query` added)
- `keywords_for_discovery` is **NOT empty** ✅
- `relevant_tables` is **NOT empty** ✅
- `exec_result.ok = true` ✅
- `error_info` is **cleared** after successful execution

### ❌ Bad Signs (Where to Look for Problems)

| Symptom | What It Means | Where to Look |
|---------|---------------|---------------|
| `keywords_for_discovery: []` ❌ | Intent parsing failed | `PARSE_INTENT` agent - check LLM response |
| `relevant_tables: []` ❌ | Discovery found nothing | `DISCOVERY` agent - check MCP `search_tables` result |
| `sql_query: ""` ❌ | SQL generation failed | `JOIN_SQL` agent - check if tables were passed in |
| `exec_result.ok: false` ❌ | Query execution failed | `EXEC_RECOVERY` agent - check SQL syntax error |
| `error_info` NOT cleared | Error propagating to answer | `EXEC_RECOVERY` exit - should clear `error_info` on success |
| Agent sequence stops early | Pipeline broke | Last agent that ran - check its EXIT state |

## Debugging Workflow

1. **Ask a question** in the Web UI
2. **Watch the debugger** output to see agent flow
3. **Find the first failure point**:
   - Look for the last agent that shows ENTRY/EXIT
   - If an agent shows ENTRY but not EXIT, it crashed
   - If an agent shows EXIT but next agent doesn't start, routing failed
4. **Check the state** at the failure point:
   - What keys are present?
   - What keys are missing?
   - Is `error_info` set?
5. **Fix the problem** based on what's missing

## Common Issues and Solutions

### Issue: "Missing info" response

**Debug steps:**
1. Check if `EXEC_RECOVERY` shows `exec_result.ok: true`
2. If YES, check if `error_info` was cleared in EXEC_RECOVERY EXIT
3. If NO, `ANSWER` will default to "missing info" path

**Solution:** Ensure `error_info = None` after successful execution (already fixed in orchestrator).

---

### Issue: Discovery searches all 943 tables

**Debug steps:**
1. Check `PARSE_INTENT` EXIT
2. Look for `keywords_for_discovery: []` (empty = bad)

**Solution:** IntentParserAgent needs to extract better keywords. Check LLM prompt in `agents/intent_parser/agent.py`.

---

### Issue: No tables found in discovery

**Debug steps:**
1. Check `DISCOVERY` EXIT
2. Look for `relevant_tables: []`
3. Check MCP tool call for `search_tables` - what was the query?

**Solution:** Keywords may be too generic or MCP ranking is off. Check MCP server logs.

---

## Tips

- **Keep the debugger open** while testing - it's the fastest way to see what's happening
- **Look for state deltas** - they show what each agent actually did
- **Check intent parsing first** - if intent is wrong, everything downstream fails
- **Compare MCP logs and LangGraph debugger** - MCP shows what tools were called, debugger shows why they were called

---

## Need Help?

If you're still stuck:
1. Copy the relevant debugger output (from the failing agent's ENTRY to its EXIT)
2. Share it with the error message from the Web UI
3. This will show exactly where the pipeline is breaking

---

**Status**: ✅ Debugger is running and integrated into startup script!

