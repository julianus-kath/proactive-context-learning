# 🚨 Phase 9 Debug Quick Reference Card

## TL;DR - Run This Now

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
```

## What Should You See?

### ✅ HEALTHY FLOW

```
🚀 PARSE_INTENT enters
  keywords_for_discovery: ['customers']          ← Good
  
✅ PARSE_INTENT exits with intent populated      ← Good

🚀 DISCOVERY enters
  State keys include: intent                      ← Good
  keywords_for_discovery: ['customers']          ← Good (SAME as parse_intent)
  
📡 MCP TOOL: search_tables called 1 time         ← Good (NOT 5+ times)
  Params: {"query": "customers", ...}
  
  Result: 3 candidates                           ← Good (NOT 943)
    - customers_table
    - customer_summary_view
    - customer_orders
    
✅ DISCOVERY exits
  Added: relevant_tables, schema_snippet         ← Good

🚀 JOIN_SQL enters                               ← Good (Agent chain continues)
🚀 EXEC_RECOVERY enters                          ← Good
🚀 ANSWER enters                                 ← Good

Final response: "We have 12,543 customers."      ← Good
```

### ❌ BROKEN FLOW #1: Intent Not Populated

```
🚀 PARSE_INTENT enters
  (processes query)
  
✅ PARSE_INTENT exits
  intent: {}                                     ← BAD! Empty intent
  
🚀 DISCOVERY enters
  State keys: user_input, messages             ← BAD! No intent!
  keywords_for_discovery: []                   ← BAD! Empty keywords

📡 MCP TOOL: search_tables called 5+ times      ← BAD! Re-extracting words
  "how", "many", "customers", "do", "we"
  
Result: 943 candidates                          ← BAD! Too many
```

**Root Cause:** IntentParserAgent failing
**Fix:** Check agent.py parse() method - add logging

### ❌ BROKEN FLOW #2: State Isolation

```
✅ PARSE_INTENT exits
  intent: {"operation": "query", "confidence": 0.95, ...}  ← Good
  
🚀 DISCOVERY enters
  intent: {}                                     ← BAD! Intent lost!
  
OR
  
  intent: {"operation": "unknown", ...}        ← BAD! Different intent!
```

**Root Cause:** State not being returned/merged properly
**Fix:** Verify each node returns modified state

### ❌ BROKEN FLOW #3: Workflow Stops Early

```
✅ DISCOVERY exits
  Added: relevant_tables, schema_snippet        ← Good exit
  
❌ No JOIN_SQL entry                             ← Bad! Should continue

Final response: "Please write the SQL yourself" ← Bad! Fallback
```

**Root Cause:** Graph routing broken or node execution failed
**Fix:** Check route_operation node routing logic

## Quick Diagnosis Checklist

```
□ Is intent field populated after PARSE_INTENT?
  
□ Do keywords_for_discovery have 2-5 words?
  (NOT: "how", "many", "do", "we" - function words)
  
□ Is intent the SAME in DISCOVERY as it was in PARSE_INTENT?
  (Look for keywords_for_discovery field)
  
□ Is search_tables called exactly 1 time?
  (Not 0 times, not 5+ times)
  
□ Does search_tables return ~3 candidates?
  (Not 943, not 0)
  
□ Does workflow continue after DISCOVERY?
  (JOIN_SQL node should execute)
  
□ Does workflow continue through JOIN_SQL → EXEC → ANSWER?
  (All 5 nodes should appear: INDEX, PARSE, DISCOVERY, JOIN, EXEC, ANSWER)
  
□ Is final response natural language?
  (Not asking user to write SQL)
```

## Critical Fields to Watch

### In PARSE_INTENT Output

```json
{
  "operation": "query",              // Should be "query" or "schema_query"
  "confidence": 0.85,                // Should be > 0.5
  "keywords_for_discovery": ["customers", "total"],  // Should be 2-5 words
  "primary_entities": ["customers"], // Should be 1-3 nouns
  "metrics": ["count"],              // Should match what user asked
  "filters": [],                     // Can be empty
  "time_window": null                // Usually null for simple queries
}
```

### In DISCOVERY State After Entry

Should have EXACTLY the same `intent` as PARSE_INTENT output.

If different:
- State isolation issue
- Node not preserving state
- Intent being overwritten

### In MCP Tool Calls

```
search_tables called with:
  query: "customers total"           // Should be keywords joined
  page: 1
  page_size: 20
  
Result has:
  candidates_count: 3                // Should be small (3-10)
  top_candidates: [...]              // Should show actual table names
```

## Emergency Actions

### To see full state at each agent:

Add to orchestrator._parse_intent_node:
```python
import json
print(f"STATE AT PARSE_INTENT ENTRY: {json.dumps(state, indent=2, default=str)}")
```

### To see what discovery does:

Add to discovery._search_candidates_node:
```python
print(f"DISCOVERY RECEIVED INTENT: {state.get('intent')}")
print(f"DISCOVERY KEYWORDS: {intent.get('keywords_for_discovery')}")
```

### To verify MCP calls:

Check mcp_client.py:
```python
logger.info(f"MCP CALL: {tool_name} with params: {params}")
```

## Where's the Bug? Decision Tree

```
Does intent exist after parse_intent?
├─ NO  → IntentParserAgent broken
│       Check: langgraph_integration/agents/intent_parser/agent.py
│
└─ YES → Does intent reach discovery?
         ├─ NO  → State loss between nodes
         │       Check: orchestrator graph edges
         │       Check: _parse_intent_node returns state
         │
         └─ YES → Does discovery use it?
                  ├─ NO  → Discovery re-extracting keywords
                  │       Check: discovery._extract_keywords()
                  │
                  └─ YES → Does workflow continue?
                           ├─ NO  → Graph routing broken
                           │       Check: route_operation node
                           │
                           └─ YES → All working! Check downstream
```

## How to Report Issues

Include:

1. **Full debug output** (from terminal 2) - at least 50 lines
2. **The query you sent** (what you asked)
3. **What you expected** (natural language answer)
4. **What you got** (error message or weird response)
5. **Highlighted failures** (mark the ❌ points in output)

Example:
```
Query: "How many customers do we have?"

Expected: "We have 12,543 customers."

Got: "Please write the SQL yourself"

FAILURE POINT:
❌ PARSE_INTENT exits with empty intent
   intent: {}
   
❌ DISCOVERY enters with no intent
   Cannot extract keywords, using fallback
```

---

## Files Changed for Phase 9 Debugging

- ✅ `debug_stream_v2.py` - NEW: Deep workflow debugger
- ✅ `langgraph_integration/debug_logger.py` - ENHANCED: Phase 9 tracking methods
- ✅ `PHASE_9_DEEP_DEBUG_GUIDE.md` - NEW: Comprehensive guide
- ✅ `PHASE_9_DEBUG_QUICK_REFERENCE.md` - NEW: This file

## Next Steps

1. **Run the debugger** with a test query
2. **Find the failure point** using this reference
3. **Collect the debug output**
4. **Report which step breaks** (intent parsing, discovery, join sql, execution, answer)
5. **We'll fix from there**

---

**Status:** Ready for deep investigation 🔬