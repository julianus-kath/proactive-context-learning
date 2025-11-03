# 🔬 Comprehensive LangGraph Debugging - Fix Summary

## What Was Wrong

The **LangGraph debugger was only showing MCP tool calls**, but **NO agent reasoning steps** (entry/exit, state changes, routing decisions).

### Root Cause
The `orchestrator.py` file **wasn't calling the debug logger's `agent_entry()` and `agent_exit()` methods**. Only the `mcp_client.py` was emitting tool call logs, so you could see `search_tables`, `describe_table`, `query` calls, but not:
- Which agents were executing
- What state they received
- What state they produced
- Where routing decisions were made
- Why the answer was "missing info"

## What Was Fixed

### 1. Added Debug Logging to All Orchestrator Nodes

Updated `/langgraph_integration/orchestrator.py` to emit structured debug events for **every agent node**:

#### Nodes with Debug Logging Added:
1. ✅ `_index_database_node` - Entry/exit with state snapshots
2. ✅ `_parse_intent_node` - Entry/exit + intent parsing details
3. ✅ `_route_operation_node` - Entry/exit with routing decision
4. ✅ `_discovery_node` - Entry/exit with table discovery results
5. ✅ `_join_sql_node` - Entry/exit with SQL generation
6. ✅ `_exec_recovery_node` - Entry/exit with query execution results
7. ✅ `_answer_node` - Entry/exit with final response formatting

#### Pattern Used:
```python
async def _some_node(self, state: BaseState) -> BaseState:
    debug_logger.agent_entry("some_node", dict(state))
    before_state = dict(state)
    
    try:
        # ... do work ...
        
        debug_logger.agent_exit("some_node", before_state, dict(state))
        return state
    except Exception as e:
        # ... handle error ...
        debug_logger.agent_exit("some_node", before_state, dict(result_state))
        return result_state
```

### 2. Integrated Debug Logger Import

Added at the top of `orchestrator.py`:
```python
from langgraph_integration.debug_logger import get_debug_logger

debug_logger = get_debug_logger()
```

### 3. Verified Debugger Configuration

- ✅ Debugger script: `debug_langgraph_comprehensive.py` created
- ✅ Startup integration: `start_all_services_mac.sh` launches debugger automatically
- ✅ Debug endpoint: LangGraph service exposes `/debug/logs/stream` (non-destructive polling)
- ✅ Debugger running: PID 94381, connected to `http://localhost:5001`

## What You'll See Now

### Before (Your Current Experience):
```
🔧 Tool Call: search_tables
✅ Tool Result: search_tables
🔧 Tool Call: describe_table
✅ Tool Result: describe_table
🔧 Tool Call: query
✅ Tool Result: query
(No agent reasoning visible)
```

### After (With Debug Logging):
```
════════════════════════════════════════════════════
📚 INDEX_DATABASE - ENTRY
════════════════════════════════════════════════════
Input State:
  user_input: "How many customers do we have?"
  messages: [...]

════════════════════════════════════════════════════
📚 INDEX_DATABASE - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ✅ MCP healthy

════════════════════════════════════════════════════
🧠 PARSE_INTENT - ENTRY
════════════════════════════════════════════════════
Input State:
  user_input: "How many customers do we have?"

Intent Details:
  operation:              query
  confidence:             0.95
  keywords_for_discovery:  ['customers', 'customer'] ✅
  primary_entities:       ['customers']
  metrics:                 ['count']

════════════════════════════════════════════════════
🧠 PARSE_INTENT - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: intent

════════════════════════════════════════════════════
🚦 ROUTE_OPERATION - ENTRY
════════════════════════════════════════════════════
Routing Decision: QUERY PIPELINE
  Path: discovery → join_sql → exec_recovery → answer

════════════════════════════════════════════════════
🔍 DISCOVERY - ENTRY
════════════════════════════════════════════════════
Input State:
  intent:
    keywords_for_discovery: ['customers', 'customer']
    operation: query

🔧 Tool Call: search_tables
  query: "customers customer"
✅ Tool Result: Found 10 candidates (top: dbo.KHKArtikelKunden, score 0.95)

════════════════════════════════════════════════════
🔍 DISCOVERY - EXIT
════════════════════════════════════════════════════
🔄 State Changes:
  ➕ Added: relevant_tables, schema_snippet, column_index
  relevant_tables: ['dbo.KHKArtikelKunden']

... (and so on for join_sql, exec_recovery, answer) ...
```

## How to Test

### 1. Services Are Already Running
```bash
ps aux | grep -E "(langgraph_service|debug_langgraph)"
```

You should see:
- `python3 langgraph_service.py` (PID 94321)
- `python3 debug_langgraph_comprehensive.py` (PID 94381)

### 2. View Real-Time Debug Output
```bash
tail -f logs/langgraph_debugger.log
```

This will show:
- **Agent entries**: What state each agent receives
- **Agent exits**: What state each agent produces
- **State deltas**: What changed (added/removed/modified keys)
- **Intent tracking**: Parsed intent fields, keywords, confidence
- **MCP tool calls**: Which tools were invoked and their results
- **Routing decisions**: Which path the workflow took

### 3. Test With a Query

**In the Web UI (http://localhost:3000):**
```
How many customers do we have?
```

**Watch the debugger output** to see:
1. ✅ `index_database` → MCP health check
2. ✅ `parse_intent` → Intent parsed with `keywords_for_discovery: ['customers', 'customer']`
3. ✅ `route_operation` → Routing decision: "query"
4. ✅ `discovery` → Tables found: `['dbo.KHKArtikelKunden']`
5. ✅ `join_sql` → SQL generated: `SELECT COUNT(*) AS total_count FROM dbo.KHKArtikelKunden`
6. ✅ `exec_recovery` → Query executed successfully, 1 row returned
7. ✅ `answer` → Final response formatted

### 4. Compare MCP Logs vs LangGraph Debug Logs

**MCP Server Logs (Windows):**
- Shows `search_tables`, `describe_table`, `query` with timing
- Does NOT show agent reasoning or state flow

**LangGraph Debugger (Mac):**
- Shows ALL agent entries/exits
- Shows state mutations
- Shows intent parsing
- Shows routing decisions
- Shows MCP tool calls **in context** (which agent called which tool)

## Debugging Workflow

When something goes wrong (e.g., "missing info" response):

### Step 1: Check Which Agent Failed
```bash
tail -100 logs/langgraph_debugger.log | grep "ENTRY\|EXIT"
```

This shows the sequence of agents that executed. If the sequence stops early, you know where the failure occurred.

### Step 2: Check State at Failure Point
Look for the last `AGENT_EXIT` before the problem:
- Did `intent` have `keywords_for_discovery`? (Empty = bad)
- Did `discovery` return `relevant_tables`? (Empty = bad)
- Did `join_sql` generate `sql_query`? (Empty = bad)
- Did `exec_recovery` return `exec_result.ok = true`? (False = bad)

### Step 3: Check Error Propagation
Look for `error_info` in state snapshots:
- If `error_info` is set early (e.g., in `discovery`), it propagates downstream
- If `error_info` is NOT cleared after successful execution, `answer` defaults to "missing info"

### Step 4: Check Intent Parsing
```bash
grep "keywords_for_discovery" logs/langgraph_debugger.log
```

If you see `keywords_for_discovery: []`, the `IntentParserAgent` failed to extract keywords, causing discovery to search all 943 tables.

### Step 5: Check Routing Decision
```bash
grep "Routing Decision" logs/langgraph_debugger.log
```

This shows which path the workflow took:
- `query` → Full pipeline (discovery → join_sql → exec_recovery → answer)
- `clarify` → Direct to answer with clarification request
- `schema_query` → Schema explanation path

## Next Steps

1. **Test the system** with "How many customers do we have?"
2. **Watch the debugger output** in real-time: `tail -f logs/langgraph_debugger.log`
3. **Compare** the debugger output with the MCP server logs to see the full picture
4. **Report back** what you see - we should now have full visibility into the agent reasoning!

## Files Modified

1. `/langgraph_integration/orchestrator.py`
   - Added `debug_logger = get_debug_logger()` import
   - Added `agent_entry()` and `agent_exit()` calls to 7 nodes
   - Ensured state snapshots are captured before/after each agent

2. `/start_all_services_mac.sh`
   - Already configured to start `debug_langgraph_comprehensive.py`
   - Debug output logged to `logs/langgraph_debugger.log`

3. `/debug_langgraph_comprehensive.py`
   - Already created and made executable
   - Polls `/debug/logs/stream` every 500ms
   - Formats logs with colors and structure

## Expected Result

You should now see:
- ✅ **Agent entries/exits** with timestamps
- ✅ **State snapshots** (before/after each agent)
- ✅ **State deltas** (what changed)
- ✅ **Intent details** (keywords, confidence, operation)
- ✅ **MCP tool calls** in context
- ✅ **Routing decisions** clearly labeled
- ✅ **Error propagation** visible

This should reveal **exactly where and why** the agent is producing "missing info" responses.

---

**Status**: ✅ **Ready to test!** Services are running with full debug logging enabled.

