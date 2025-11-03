# 🔬 PHASE 9 DEEP DEBUG — Complete Diagnostic Guide

## The Issue (Confirmed)

After introducing the `IntentParserAgent`, only the `search_tables` MCP tool is called. The workflow chain breaks after discovery starts.

**Root Cause Areas to Check:**
1. Intent parser not populating `intent` in state
2. Intent parser returning something unexpected
3. Discovery agent not setting `relevant_tables`
4. Downstream agents not receiving required state keys
5. Async/await issues in intent parser (uses sync `invoke()` in async context)

---

## Quick Diagnosis (2 minutes)

### Step 1: Check Intent Parser Output

Add this logging to `langgraph_integration/agents/intent_parser/agent.py` line 180 (after LLM parsing):

```python
logger.info(f"🔍 RAW RESPONSE TYPE: {type(response)}")
logger.info(f"🔍 RAW RESPONSE CONTENT: {response.content if hasattr(response, 'content') else response}")
logger.info(f"🔍 PARSED INTENT: {parsed}")
logger.info(f"🔍 INTENT KEYS: {list(intent.keys())}")
logger.info(f"🔍 INTENT[keywords_for_discovery]: {intent.get('keywords_for_discovery')}")
```

Run query: `"How many customers?"`

**Look for:**
- Is `keywords_for_discovery` populated? ✅ or ❌
- Is the intent being returned as a dict? ✅ or ❌
- Are there any exceptions? ✅ or ❌

### Step 2: Check Discovery Agent Keywords

Add this logging to `langgraph_integration/agents/discovery/agent.py` line 143 (in _extract_keywords):

```python
logger.info(f"🔍 EXTRACT_KEYWORDS INPUT intent: {intent}")
logger.info(f"🔍 EXTRACT_KEYWORDS OUTPUT keywords: {keywords}")
logger.info(f"🔍 KEYWORDS FROM INTENT: {intent.get('keywords_for_discovery', [])}")
```

Run same query.

**Look for:**
- Are keywords being passed from intent? ✅ or ❌
- Is fallback extraction being used? ✅ or ❌
- Do keywords look correct? ✅ or ❌

### Step 3: Check Discovery Search Results

Add this logging to `langgraph_integration/agents/discovery/agent.py` line 189 (after search loop):

```python
logger.info(f"🔍 SEARCH COMPLETED")
logger.info(f"🔍 CANDIDATES FOUND: {len(unique_candidates)}")
if unique_candidates:
    for c in unique_candidates[:3]:
        logger.info(f"  - {c.get('name', c.get('full_name'))}")
else:
    logger.info(f"🔍 NO CANDIDATES FOUND!")
```

**Look for:**
- Are candidates being found? ✅ or ❌
- Should we see ~3 candidates? ✅ or ❌

### Step 4: Check Discovery Output State

Add this logging to `langgraph_integration/agents/discovery/agent.py` line 494 (in _build_schema_snippet_node):

```python
logger.info(f"🔍 BEFORE SETTING relevant_tables")
logger.info(f"🔍 candidates: {len(candidates)}")
logger.info(f"🔍 Setting relevant_tables to: {relevant_tables}")
logger.info(f"🔍 AFTER: state['relevant_tables'] = {state.get('relevant_tables')}")
```

**Look for:**
- Is `relevant_tables` being set? ✅ or ❌
- Does it contain table names? ✅ or ❌

### Step 5: Check Orchestrator State Flow

Add this logging to `langgraph_integration/orchestrator.py` line 331 (in _discovery_node):

```python
logger.info(f"🔍 DISCOVERY RESULT KEYS: {list(result.keys())}")
logger.info(f"🔍 DISCOVERY result['relevant_tables']: {result.get('relevant_tables')}")
logger.info(f"🔍 BEFORE COPY: state['relevant_tables'] = {state.get('relevant_tables')}")
state["relevant_tables"] = result.get("relevant_tables", [])
logger.info(f"🔍 AFTER COPY: state['relevant_tables'] = {state.get('relevant_tables')}")
```

**Look for:**
- Is result from discovery subgraph empty? ❌
- Is `relevant_tables` in the result? ✅ or ❌
- Is state being updated correctly? ✅ or ❌

### Step 6: Run Full Test with Logging

```bash
# Terminal 1
bash start_all_services_mac.sh

# Terminal 2 - Watch logs
tail -f /tmp/langgraph.log | grep "🔍"

# Terminal 3 - Send query
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers?"}'
```

---

## Deeper Analysis (10 minutes)

### Suspect #1: Intent Parser Async Issue

The intent parser calls `self.llm.invoke()` (synchronous) inside an async function:

**File:** `langgraph_integration/agents/intent_parser/agent.py` line 170

```python
async def _parse_with_llm(self, user_input: str) -> ParsedIntent:
    ...
    response = self.llm.invoke(prompt)  # ← SYNC CALL IN ASYNC FUNCTION
```

**Fix:** Change to use `ainvoke()`:

```python
response = await self.llm.ainvoke(prompt)  # ← ASYNC
```

**To Test:**
1. Make this change
2. Run query
3. Check if intent is now populated

### Suspect #2: Intent Not Being Set in State

If intent parser fails silently, `state["intent"]` might not exist.

**File:** `langgraph_integration/orchestrator.py` line 296

```python
state["intent"] = intent
return state
```

**Check:** Add logging BEFORE this:

```python
logger.info(f"🔍 ABOUT TO SET INTENT")
logger.info(f"🔍 INTENT TYPE: {type(intent)}")
logger.info(f"🔍 INTENT CONTENT: {intent}")
state["intent"] = intent
logger.info(f"🔍 INTENT NOW IN STATE: {state.get('intent')}")
return state
```

### Suspect #3: Discovery Subgraph Not Returning Full State

The discovery subgraph might not be passing all keys through.

**File:** `langgraph_integration/orchestrator.py` line 328

```python
result = await discovery_graph.ainvoke(state)
```

**Check:** What keys are in result?

```python
logger.info(f"🔍 DISCOVERY RESULT KEYS: {list(result.keys())}")
logger.info(f"🔍 ALL STATE KEYS: {list(state.keys())}")
logger.info(f"🔍 RESULT: {json.dumps({k: str(result[k])[:100] for k in result.keys()}, indent=2)}")
```

### Suspect #4: Downstream Agent (join_sql) Checking Prerequisites

**File:** `langgraph_integration/agents/join_sql/agent.py` line 216

```python
if not relevant_tables:
    error = {
        "type": "NO_TABLES",
        "message": "No relevant tables available for join planning..."
    }
    return {**state, "error_info": error}
```

If `relevant_tables` is empty, join_sql fails!

**Check:** Add logging to orchestrator after discovery:

```python
logger.info(f"🔍 AFTER DISCOVERY:")
logger.info(f"🔍 state['relevant_tables']: {state.get('relevant_tables')}")
logger.info(f"🔍 state['candidate_views']: {len(state.get('candidate_views', []))} items")
logger.info(f"🔍 state['schema_snippet']: {len(state.get('schema_snippet', ''))} chars")
logger.info(f"🔍 state['error_info']: {state.get('error_info')}")
```

---

## Critical Suspect: Async/Await in Intent Parser

I found this in `langgraph_integration/agents/intent_parser/agent.py`:

```python
response = self.llm.invoke(prompt)  # ← NOT AWAITED, BLOCKS EVENT LOOP
```

This should be:

```python
response = await self.llm.ainvoke(prompt)  # ← ASYNC
```

**Why this matters:**
- Calling sync `invoke()` in async function blocks the event loop
- LangGraph's async machinery can get confused
- Downstream nodes may not get scheduled properly

**To Fix:**
1. Change line 170 to use `ainvoke()`
2. Make sure you import ainvoke if needed
3. Test with same query

---

## The Expected vs Actual Flow

### Expected Flow (What Should Happen)
```
User Query: "How many customers?"
  ↓
index_database → ✅ runs
  ↓
parse_intent → ✅ runs, sets intent with keywords: ["customers"]
  ↓
route_operation → ✅ routes to "discovery"
  ↓
discovery → ✅ runs subgraph
  ├─ search_candidates → ✅ calls search_tables("customers")
  ├─ rank_candidates → ✅ ranks 10 results
  ├─ filter_to_limit → ✅ keeps top 3
  ├─ describe_selected → ✅ describes them
  ├─ build_schema_snippet → ✅ sets relevant_tables
  └─ fetch_column_index → ✅ fetches columns
  ↓
join_sql → ✅ runs (receives relevant_tables)
  ├─ check_view_coverage → ✅ checks views
  ├─ fetch_relations → ✅ gets FKs
  ├─ build_join_plan → ✅ plans query
  ├─ generate_sql → ✅ generates SQL
  └─ validate_sql → ✅ validates
  ↓
exec_recovery → ✅ runs (executes SQL)
  ↓
answer → ✅ formats result
  ↓
User gets: "We have 12,543 customers."
```

### Actual Flow (What's Happening)
```
User Query: "How many customers?"
  ↓
index_database → ✅ runs
  ↓
parse_intent → ❓ unknown status
  ↓
route_operation → ❓ might route incorrectly
  ↓
discovery → ✅ runs
  ├─ search_candidates → ✅ calls search_tables
  └─ ❌ STOPS HERE (or errors)
  ↓
join_sql → ❌ DOESN'T RUN (or receives bad state)
  ↓
User gets: "Please write SQL manually" (error fallback)
```

---

## Execution Steps

1. **Add all logging from sections above**
2. **Restart services:** `bash start_all_services_mac.sh`
3. **Send test query** with debug output enabled
4. **Examine logs for:** ❌ signs above
5. **Isolate first failure point**
6. **Report back with:**
   - Query you sent
   - Which step fails first (❌)
   - Full log output for that step
   - State before/after each node

---

## If You're Still Stuck

Collect this information:

```bash
# 1. Full debug output (save to file)
python debug_stream_v2.py > /tmp/debug_output.txt 2>&1 &

# 2. Send query
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers?"}'

# 3. Wait 5 seconds
sleep 5

# 4. Stop debug script and check output
pkill -f debug_stream_v2.py

# 5. Show first 200 lines
head -200 /tmp/debug_output.txt
```

Then share:
- The debug output
- Any error messages
- Which steps show ✅ and which show ❌
