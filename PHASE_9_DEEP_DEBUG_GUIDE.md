# 🔬 Phase 9 Deep Debugging Guide - Intent Parser Investigation

## Overview

When Phase 9's IntentParserAgent was introduced, it appears the workflow broke in a subtle way. Only `search_tables` MCP tool is being called, and downstream agents aren't executing. This guide shows how to use the **Deep Workflow Debugger** to expose exactly where the problem is.

## The Problem

**Current Symptom:** 
- User asks question
- Only `search_tables` MCP tool is called
- Discovery agent returns results
- ❌ Join SQL agent doesn't run
- ❌ Execution agent doesn't run  
- ❌ Answer agent doesn't run
- User gets confused response instead of answer

**Root Cause:** Likely one of:
1. Intent is not being populated correctly in state
2. Intent is being lost between nodes
3. State is being reset/isolated between graph nodes
4. Intent object structure is wrong
5. Routing is bypassing downstream agents

## New Debugging Tools

### 1. Enhanced Debug Stream (`debug_stream_v2.py`)

A completely redesigned real-time monitor that shows:
- **Agent execution flow** with entry/exit markers
- **State snapshots** before and after each agent
- **Intent field tracking** with detailed changes
- **MCP tool calls** and results
- **Internal reasoning** steps

#### Usage

```bash
# Terminal 1: Start the services
bash start_all_services_mac.sh

# Terminal 2: Start the debugger
python debug_stream_v2.py

# Terminal 3: Send test query
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers do we have?"}'
```

#### What You'll See

```
🔬 DEEP WORKFLOW DEBUGGER - Phase 9 Intent Parser Investigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═════════════════════════════════════════════════════════════════
📚 AGENT: INDEX_DATABASE #1 | 🚀 ENTRY
═════════════════════════════════════════════════════════════════

🚀 [14:23:45.123] Entering agent index_database with 3 state keys
State keys: user_input, messages, session_id

✅ [14:23:45.234] Exiting after processing
🔄 STATE CHANGES:
  ➕ Added keys: catalog, mcp_status
  🔄 Modified keys: none

════════════════════════════════════════════════════════════════
🧠 AGENT: PARSE_INTENT #2 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

🧠 Intent parsed with LLM: ['customers']
  operation:                 query
  confidence:                0.95
  primary_entities:          ['customers']
  keywords_for_discovery:    ['customers', 'total']  ← CRITICAL
  metrics:                   ['count']

✅ [14:23:46.123] Exiting after processing
🔄 STATE CHANGES:
  🔄 Modified keys: ['intent']
  Intent field changes:
    operation: None → query
    confidence: None → 0.95
    keywords_for_discovery: [] → ['customers', 'total']

════════════════════════════════════════════════════════════════
🔍 AGENT: DISCOVERY #3 | 🚀 ENTRY
════════════════════════════════════════════════════════════════

🧠 Intent keywords for discovery: ['customers', 'total']
Current Intent:
  operation:                 query
  confidence:                0.95
  primary_entities:          ['customers']
  keywords_for_discovery:    ['customers', 'total']
  metrics:                   ['count']

📡 MCP TOOL: search_tables
  Tool: search_tables
  Params:
    query: customers total
    page: 1
    page_size: 20

📊 MCP RESULT: search_tables
  Tool: search_tables
  status: ✅ OK
  candidates_count: 3
  top_candidates: [customers, customer_summary, customer_orders]

✅ [14:23:47.234] Exiting after processing
🔄 STATE CHANGES:
  ➕ Added keys: relevant_tables, schema_snippet, candidate_views
```

### 2. Enhanced Server-Side Logging

The `langgraph_integration/debug_logger.py` now includes Phase 9-specific tracking:

```python
logger.agent_entry("discovery", state)
logger.intent_parsed_phase9(intent, parsing_method="LLM")
logger.mcp_tool_invoked("search_tables", params, agent="discovery")
logger.mcp_tool_result("search_tables", result)
logger.agent_exit("discovery", before_state, after_state)
```

## Debugging Workflow

### Step 1: Start Everything with Logging

```bash
# Terminal 1
bash start_all_services_mac.sh

# Check that services are running
curl http://localhost:5001/health
```

### Step 2: Monitor the Debugger

```bash
# Terminal 2
python debug_stream_v2.py
```

### Step 3: Send a Test Query

```bash
# Terminal 3
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{
    "user_input": "How many customers do we have?"
  }'
```

### Step 4: Analyze the Debug Output

Look for these **critical questions**:

#### Q1: Is Intent Parsed Correctly?
```
🧠 AGENT: PARSE_INTENT exits with:
  keywords_for_discovery: ['customers', ...]    ← Should NOT be empty
  operation: query                               ← Should be 'query'
  confidence: 0.95                               ← Should be > 0.7
```

If keywords are empty or wrong, **IntentParserAgent is broken**.

#### Q2: Is Intent Passed to Discovery?
```
🔍 AGENT: DISCOVERY enters with:
  intent_keywords: ['customers', ...]            ← Should match PARSE_INTENT output
```

If intent is missing or different, **state isolation issue**.

#### Q3: Is Discovery Called Only Once?
```
📡 MCP TOOL: search_tables (called 1 time)
  Params:
    query: customers [total, ...]
```

If called multiple times, **discovery is re-extracting keywords**.

#### Q4: Does Workflow Continue After Discovery?
```
✅ AGENT: DISCOVERY exits
  ➕ Added keys: relevant_tables, schema_snippet
  
🔗 AGENT: JOIN_SQL enters                       ← Should appear next
```

If JOIN_SQL doesn't appear, **graph routing is broken**.

#### Q5: What's the State at Each Step?
```
State keys: user_input, intent, relevant_tables, ...
```

Count should grow:
- After INDEX_DATABASE: +catalog, +mcp_status
- After PARSE_INTENT: +intent
- After DISCOVERY: +relevant_tables, +schema_snippet, +column_index
- After JOIN_SQL: +query_blueprint, +generated_sql
- After EXEC: +query_result, +result_rows
- After ANSWER: +final_response

If any step is missing, workflow is broken there.

## Common Issues & Fixes

### Issue 1: Intent Not Populated
**Symptom:** PARSE_INTENT exits but `intent` field is still empty

**Root Cause:** IntentParserAgent.parse() failing silently

**Debug:**
```python
# In langgraph_integration/agents/intent_parser/agent.py
# Add logging:
async def parse(self, user_input: str) -> ParsedIntent:
    logger.info(f"🧠 Parsing: {user_input}")
    try:
        intent = await self._parse_with_llm(user_input)
        logger.info(f"✅ Parsed: {intent}")
        return intent
    except Exception as e:
        logger.error(f"❌ Parse failed: {e}")
        return self._empty_intent(user_input)
```

### Issue 2: State Isolation Between Nodes
**Symptom:** State changes in one node don't appear in the next

**Root Cause:** Nodes not returning modified state

**Check:**
```python
# Each node MUST return state:
async def _parse_intent_node(self, state: BaseState) -> BaseState:
    # ... do stuff ...
    state["intent"] = intent  # ← MUST update state
    return state              # ← MUST return state
```

### Issue 3: Intent Lost After Routing
**Symptom:** PARSE_INTENT has intent, but DISCOVERY doesn't

**Root Cause:** route_operation node not preserving state

**Check:**
```python
async def _route_operation_node(self, state: BaseState) -> BaseState:
    # This MUST NOT modify state
    return state  # ← Return unchanged
```

### Issue 4: Discovery Called Multiple Times
**Symptom:** Multiple MCP search_tables calls

**Root Cause:** Discovery re-extracting keywords from user_input

**Debug:** Check discovery agent logs for `_extract_keywords` being called per-word

**Fix:** Verify discovery uses only `intent["keywords_for_discovery"]`:
```python
def _extract_keywords(self, user_input: str, intent: Dict[str, Any]) -> List[str]:
    keywords = intent.get("keywords_for_discovery", [])
    if not keywords:
        logger.warning(f"⚠️  No keywords in intent!")
        return self._fallback_keyword_extraction(user_input)
    return keywords
```

## Detailed Log Format

Each debug entry includes:

```json
{
  "type": "AGENT_ENTRY|AGENT_EXIT|MCP_CALL|MCP_RESULT|INTENT_CHECK",
  "node": "parse_intent",
  "timestamp": "2025-01-15T14:23:45.123Z",
  "message": "Agent parse_intent entering with 3 state keys",
  "data": {
    "state_keys": ["user_input", "messages", "session_id"],
    "intent": {
      "operation": "query",
      "confidence": 0.95,
      "keywords_for_discovery": ["customers", "total"],
      "primary_entities": ["customers"],
      "metrics": ["count"],
      ...
    },
    "state": { ... full state snapshot ... }
  }
}
```

## Enabling Deep Debugging in Code

To add deep debugging to any agent:

```python
from langgraph_integration.debug_logger import get_debug_logger

logger = get_debug_logger()

async def _parse_intent_node(self, state: BaseState) -> BaseState:
    # Log entry
    logger.agent_entry("parse_intent", state)
    before_state = dict(state)
    
    try:
        # Do work
        intent = await self.intent_parser.parse(user_input)
        
        # Log the parsed intent
        logger.intent_parsed_phase9(intent, parsing_method="LLM")
        
        state["intent"] = intent
        
        # Log exit
        logger.agent_exit("parse_intent", before_state, state)
        return state
    except Exception as e:
        logger.workflow_error("INTENT_PARSE_ERROR", str(e), {"user_input": user_input})
        raise
```

## Next Steps After Debugging

1. **Collect the debug output** when reproducing the issue
2. **Identify the first point of failure** (where state stops flowing)
3. **Add logging** at that point
4. **Check state structure** - print complete state at entry/exit
5. **Verify intent fields** - all required fields populated?
6. **Test with simplified query** - "How many customers?" (not complex)
7. **Compare with working Phase 8** - look at git history for pre-Phase9 code

## Emergency Diagnostic Script

If you need to quickly diagnose, run:

```bash
python -c "
from langgraph_integration.orchestrator import create_query_orchestrator
import asyncio

async def test():
    orch = create_query_orchestrator()
    
    state = {
        'user_input': 'How many customers?',
        'messages': [],
        'session_id': 'test123'
    }
    
    print('\\n🧪 Testing orchestrator...')
    print(f'Initial state keys: {list(state.keys())}')
    
    # Run full flow
    result = await orch.graph.ainvoke(state)
    
    print(f'\\nFinal state keys: {list(result.keys())}')
    print(f'\\nIntent field: {result.get(\"intent\")}')
    print(f'\\nRelevant tables: {result.get(\"relevant_tables\")}')
    print(f'\\nGenerated SQL: {result.get(\"generated_sql\")}')
    print(f'\\nFinal response: {result.get(\"final_response\")}')

asyncio.run(test())
"
```

## Key Metrics to Track

### Healthy Flow
- ✅ Intent populated after parse_intent
- ✅ Discovery returns 2-5 candidates (not 943)
- ✅ Join SQL agent creates blueprint
- ✅ SQL execution returns rows
- ✅ Answer agent formats response
- ✅ User gets natural language answer

### Broken Flow  
- ❌ Intent empty after parse_intent
- ❌ Discovery returns all 943 candidates
- ❌ Join SQL agent doesn't execute
- ❌ Execution agent doesn't execute
- ❌ User gets error or asks for SQL

## Questions to Answer

Before you ask for help, have these answers:

1. **At what agent does the flow stop?** (discovery, join_sql, exec, answer)
2. **Is the intent populated?** (check intent field in debug output)
3. **What are the keywords_for_discovery?** (should be 2-5 clean words)
4. **How many MCP search_tables calls happen?** (should be 1)
5. **What state keys are present at each step?** (should grow)
6. **Is the intent preserved across nodes?** (should see same intent in next node)

---

**Next:** Run debug_stream_v2.py, send a test query, and collect the output. Then we can analyze what's breaking.