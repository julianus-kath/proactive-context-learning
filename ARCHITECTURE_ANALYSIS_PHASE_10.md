# ARCHITECTURE ANALYSIS & IMPLEMENTATION PLAN (Phase 10)
**Status**: Complete Deep Dive | Date: 2025-11-07

---

## EXECUTIVE SUMMARY

Your system is **architecturally sound but operationally incomplete**. The agent flow exists, but there are **3 critical gaps**:

1. **No Result Validation Agent** → Empty results pass to Answer without sanity-checking
2. **No Conditional Retry Logic** → When discovery fails (empty results), no recovery path
3. **JSON Parsing Errors in MCP** → Relations tool returns invalid/empty JSON from Windows server
4. **State Handoff Fragility** → Answer agent receives malformed exec_result (sometimes dict, sometimes string)

**After exec_recovery completes, the flow DOES reach Answer**, but Answer has no way to diagnose "this result is wrong." Your concern is valid: we need a **Validation & Diagnostic Agent** to bridge this gap.

---

## PART I: CURRENT ARCHITECTURE (As-Is)

### A. System Topology (From repo.md & Code)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER / UI (macOS)                              │
│                    (Chatbot UI on port 3000)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│                  LangGraph Orchestrator (macOS)                       │
│                    (FastAPI on port 5001)                            │
│                                                                       │
│  ┌─ START ─────────────────────────────────────────────────────────┐ │
│  │                                                                  │ │
│  ├──→ [index_database]      (MCP health check)                    │ │
│  │         ↓                                                       │ │
│  ├──→ [parse_intent]        (Intent Parser Agent subgraph)        │ │
│  │         ↓                                                       │ │
│  ├──→ [route_operation]     (Conditional router)                  │ │
│  │         ↓                                                       │ │
│  │    (SPLITS INTO BRANCHES)                                       │ │
│  │         ├─→ FOR "query":                                        │ │
│  │         │     [discovery] → [join_sql] → [validate_sql]        │ │
│  │         │         ↓            ↓            ↓                   │ │
│  │         │     [exec_recovery] → [answer] → END                 │ │
│  │         │                                                       │ │
│  │         ├─→ FOR "schema_query":                                │ │
│  │         │     [discovery_for_schema] → [answer_schema] → END   │ │
│  │         │                                                       │ │
│  │         ├─→ FOR "health_check":                                │ │
│  │         │     [answer_health] → END                            │ │
│  │         │                                                       │ │
│  │         └─→ FOR errors/clarification:                          │ │
│  │             [answer_error] or [answer] (with clarification)    │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ JSON-RPC (over HTTP)
                             │ MCP_SERVER_URL (Windows VPN)
┌────────────────────────────▼────────────────────────────────────────┐
│              MCP Server (Windows/VPN on port 8000)                    │
│                    (FastAPI + pyodbc)                                │
│                                                                       │
│  Tools Exposed:                                                      │
│  ├─ Discovery: list_tables, search_tables, describe_table,          │
│  │             list_views, search_views, describe_view,             │
│  │             list_view_dependencies, list_relations              │
│  ├─ Execution: query_bounded (safe, read-only, row-capped)         │
│  └─ Catalog: Scout catalog (built at startup, TTL refresh)         │
│                                                                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ ODBC
┌────────────────────────────▼────────────────────────────────────────┐
│              MSSQL ERP Database (Client VPN)                          │
│         (Only real production source of truth)                       │
└────────────────────────────────────────────────────────────────────┘
```

### B. Agent Composition (5 Main Agents as Subgraphs)

Each agent is a **self-contained subgraph** with async nodes:

| Agent | Responsibility | Input | Output | Issues |
|-------|-----------------|-------|--------|--------|
| **IntentParser** | Parse user query → structured intent | `user_input`, `messages` | `intent` (ParsedIntent) | ✅ Working; clean semantic parsing |
| **Discovery** | Find relevant tables/views via Scout | `intent.keywords_for_discovery` | `relevant_tables`, `candidate_views`, `schema_snippet`, `column_index` | ⚠️ Returns wrong tables when keywords empty; no fallback retry |
| **JoinPlanAndSQL** | Plan joins & generate MSSQL | `relevant_tables`, `schema_snippet` | `join_plan`, `sql_query` | ⚠️ JSON parsing error on `list_relations` (empty response from Windows MCP) |
| **ExecAndRecovery** | Execute query safely + repair on error | `sql_query`, `retry_count` | `exec_result`, `error_info` | ⚠️ Returns zero-result silently; no validation pass/fail signal |
| **Answer** | Format result as natural language | `exec_result`, `error_info`, `intent` | `final_response` | ✅ Mostly working; handles clarification & zero-result cases |

### C. MCP Server Architecture (Windows/VPN Side)

**Current Structure:**
```
mcp_server/
├─ server.py              (FastAPI entry point, routes JSON-RPC requests)
├─ tools.py               (Tool implementations: list_tables, search_tables, etc.)
├─ catalog.py             (Scout catalog manager)
├─ db_mssql.py            (MSSQL connection via pyodbc)
├─ scout_mode.py          (Semantic ranking & caching)
├─ health.py              (Health endpoint, catalog status)
├─ models.py              (Pydantic schemas for responses)
├─ discovery_tools.py     (Wrapper around catalog for discovery)
├─ database_adapter.py    (Abstract DB interface)
└─ bounded_query.py       (Safe query execution: TOP, timeout, redaction)
```

**Key Points:**
- **Scout Catalog** is built at startup (or on-demand TTL) and cached in memory
- **All discovery is catalog-backed** (no live information_schema queries)
- **Ranking is hybrid**: text similarity (0.45) + role coverage (0.25) + subject match (0.15) + has_rows (0.10) + is_view_bonus (0.05)
- **list_relations** returns FK relationships for join planning
- **query_bounded** enforces: TOP 1000, 30s timeout, SELECT-only, column redaction

---

## PART II: CRITICAL ISSUES & ROOT CAUSES

### ISSUE 1: Empty Results Not Validated Before Answer

**Symptom:**
```
✅ Tool Result: query
Status: SUCCESS ← query_bounded says OK=true
Result: 0 rows  ← But result is empty!
...
Answer: "Your query executed successfully but returned no data"
```

**Root Cause:**
- ExecAndRecoveryAgent only checks if query executed without error (`ok=true`)
- Does NOT check if **result makes sense** given the intent
- When exec_result has `row_count=0`, it's treated as success, not as a diagnostic signal

**Architecture Problem:**
There is NO intermediate validation gate. The flow is:
```
discovery → join_sql → validate_sql → exec_recovery → [DIRECTLY TO ANSWER]
                                                              ↑
                                          (NO SANITY-CHECK HERE)
```

**Why It Matters:**
User asked "How many customers?" → Discovery found "customers" table → Generated `SELECT COUNT(*) FROM customers` → Ran successfully → Got 0 rows → Answered "no data found"

But this could mean:
1. ✅ Correct table, correct query, genuinely no data (rare)
2. ❌ Wrong table discovered (table is named differently)
3. ❌ Wrong schema / missing table in ERP
4. ❌ Time filter is too restrictive

Currently, all 4 cases are indistinguishable from Answer's perspective.

---

### ISSUE 2: list_relations Returns Invalid JSON

**Symptom from your logs:**
```
2025-11-07 22:06:52,112 - langgraph - INFO - 
✅ Tool Result: list_relations
...
Failed to parse relations result: Expecting value: line 1 column 1 (char 0)
```

**Root Cause:**
- `list_relations` is called on 3 candidate tables
- MCP server (Windows) returns empty/malformed JSON response
- Join planning code attempts `json.loads()` on empty string `""`
- Silently falls back: "No FK relationships found"

**What's happening in code** (langgraph_integration/agents/join_sql/agent.py:1272):
```python
try:
    relations = json.loads(response_text)
except json.JSONDecodeError as e:
    logger.warning(f"Failed to parse relations result: {e}")
    # Fall back to direct SELECT (no joins)
```

**Architecture Problem:**
- MCP tool response typing is weak (returns string, not structured dict)
- No validation of response shape before parsing
- Join planning silently degrades to single-table query

---

### ISSUE 3: sql_validator Agent Exists But Is Never Used

**From orchestrator.py (line 116):**
```python
self.sql_validator_agent = None
logger.info("✅ SQLValidatorAgent registered (AST validation, auto-repair)")
```

**And at line 173:**
```python
graph.add_node("validate_sql", self._validate_sql_node)
```

**But when I search for `_validate_sql_node`:**
```python
async def _validate_sql_node(self, state: BaseState) -> BaseState:
    # THIS METHOD DOESN'T EXIST IN THE MAIN ORCHESTRATOR
    # The node is added but never implemented!
```

**Result:** Node runs but does nothing → State passes through unchanged.

---

### ISSUE 4: Recovery Agent Infrastructure Incomplete

Your question: *"where are recovery/validation agents instantiated?"*

**Answer:** They're NOT fully wired.

**What exists:**
- `sql_validator` agent class (lazy init at line 116: `self.sql_validator_agent = None`)
- `_validate_sql_node` is registered (line 173) but not implemented
- `_exec_recovery_node` handles query errors (retry logic), but only for syntax/timeout errors

**What's missing:**
- **Result Validation Agent**: should check `exec_result` for sanity (row count makes sense? columns expected? no NULLs where shouldn't be?)
- **Discovery Recovery Agent**: should retry discovery with different keywords if result seems wrong
- **Diagnostic Agent**: should analyze failure modes and suggest next steps

---

### ISSUE 5: State Passing Inconsistency

**In _answer_node (line 1095):**
```python
exec_result = state.get("exec_result", {}) or {}
```

This defensively creates an empty dict, but earlier exec_recovery might have set:
```python
state["exec_result"] = exec_result  # Could be dict, could be None, could be error object
```

**Risk:** Type confusion downstream if exec_result structure varies.

---

## PART III: ARCHITECTURAL DECISIONS TO QUESTION

### Decision 1: "Relations parsing failures are OK, just skip joins"
**Critique:**
- ❌ **Symptom masking**: If MCP returns empty JSON 3 times, we silently fall back
- ❌ **No diagnostics**: User never learns the Windows server is broken
- ✅ **Resilience**: Falls back gracefully, but...
- **Fix**: Log severity should escalate; MCP health should be checked

### Decision 2: "Discovery returns top N candidates; if empty, that's discovery's job"
**Critique:**
- ❌ **No feedback loop**: If discovery returns 0 tables, join_sql gets empty list → generates broken SQL
- ❌ **Delayed failure**: Errors appear at execution time, not discovery time
- ✅ **Matches repo.md**: Views-first fallback to joins is correct strategy
- **Fix**: Add discovery validation: if `len(relevant_tables) == 0`, trigger re-discovery or escalation

### Decision 3: "Execute first, handle errors second"
**Critique:**
- ✅ **Fast path**: Catches genuine syntax errors
- ✅ **Self-healing**: Can retry with repair attempts
- ❌ **Semantic errors invisible**: Query that returns 0 rows is not flagged as error
- **Fix**: Add post-execution validation: check row count against intent expectations

### Decision 4: "Answer agent formats any result, even empty ones"
**Critique:**
- ✅ **Graceful degradation**: Better than crash
- ❌ **No diagnosis**: User gets message but no insight into why
- ❌ **No recovery**: No path to suggest "try broader time range" or "try alternative table"
- **Fix**: Add diagnostic layer before answer: assess result validity, suggest alternatives

---

## PART IV: PROPOSED ARCHITECTURE FIX (Phase 10)

### New Agent: Result Validator & Diagnostic

**Purpose:** Inserted between `exec_recovery` and `answer`, this agent:

1. **Validates result makes sense**
   - Does row_count match intent? (COUNT query should have 1 row; DETAIL query should have N)
   - Are expected columns present?
   - Is NULLability reasonable?

2. **Diagnoses issues**
   - If 0 rows: Is this schema/table issue or data issue?
   - If schema mismatch: Which agent failed? (discovery? join_sql?)
   - Suggest next action: retry discovery, broaden filter, check time window

3. **Routes appropriately**
   - ✅ Valid result → pass to Answer (format & return)
   - ⚠️ Suspicious result → pass to Answer with warning flag
   - ❌ Invalid result → route to recovery: either re-discovery or error message

**Graph Topology (Updated):**
```
discovery → join_sql → validate_sql → exec_recovery → [NEW] result_validator → answer → END
                                                              ↑                ↓
                                                              └────← [recovery paths]
```

**Result Validator Node Logic:**
```python
async def _result_validator_node(self, state: BaseState) -> BaseState:
    """
    Validate exec_result sanity BEFORE answer formatting.
    
    Outputs:
    - result_validation: {valid: bool, severity: "ok"|"warning"|"error", 
                         diagnosis: str, suggestions: List[str]}
    - May route to recovery or directly to answer
    """
    intent = state.get("intent", {})
    exec_result = state.get("exec_result", {})
    join_plan = state.get("join_plan", {})
    sql_query = state.get("sql_query", "")
    
    # Check 1: Does result structure match expectation?
    if intent.get("operation") == "query":
        metrics = intent.get("metrics", [])
        is_count = "count" in [m.lower() for m in metrics]
        row_count = exec_result.get("row_count", 0)
        
        # COUNT queries should return 1 row
        if is_count and row_count != 1:
            return _route_to_discovery_recovery(state)
        
        # If zero rows but expected data
        if row_count == 0 and not is_count:
            analysis = _diagnose_zero_rows(state)
            if analysis["is_schema_issue"]:
                return _route_to_discovery_recovery(state)
            else:
                # Likely genuine empty result; pass with warning
                state["result_validation"] = {
                    "valid": True, "severity": "warning",
                    "diagnosis": "Empty result, likely no matching data",
                    "suggestions": [...]
                }
    
    # Check 2: Column presence
    if not _columns_match(exec_result, join_plan):
        return _route_to_join_sql_recovery(state)
    
    # All checks passed
    state["result_validation"] = {"valid": True, "severity": "ok"}
    return state
```

---

## PART V: IMPLEMENTATION PLAN (Detailed)

### Phase 10a: Add Result Validator Agent (1-2 hours)

**Files to create:**
```
langgraph_integration/agents/result_validator/
├─ agent.py          (ResultValidatorAgent class + subgraph)
├─ __init__.py
```

**Files to modify:**
```
langgraph_integration/orchestrator.py        (add validator node, wire graph)
langgraph_integration/contracts/state.py     (add result_validation output field)
```

**Key responsibilities:**
1. **Validate row count** against intent (COUNT vs DETAIL query)
2. **Diagnose zero-row cases** (schema issue? data issue? filter too strict?)
3. **Check columns match** join_plan expectations
4. **Suggest next action** (retry discovery, broaden filter, etc.)
5. **Route to appropriate recovery**

---

### Phase 10b: Fix sql_validator Node (30 minutes)

**Currently:** Node exists but does nothing (line 173 adds it, but `_validate_sql_node` not implemented)

**To do:**
1. Implement `_validate_sql_node` to actually validate generated SQL:
   - AST parsing to check syntax
   - Column validation (use column_index from discovery)
   - FK validation (use join_plan)
   - Repair if needed (call sql_validator_agent)

2. Update orchestrator graph edge: `validate_sql → exec_recovery` (already correct)

---

### Phase 10c: Fix list_relations JSON Parsing (30 minutes)

**Currently:** Silent failure on empty JSON response from MCP

**To do:**
1. **Strengthen response validation** in MCP client:
   ```python
   response = await mcp.call_tool("list_relations", {"table": fqtn})
   if not response or response.get("error"):
       log_escalation("MCP list_relations failed")
       mark_discovery_as_incomplete()
   ```

2. **Update join_sql agent** to handle failures better:
   - Log when fallback to single-table happens
   - Flag in join_plan: `"fk_resolution": "failed"` (not `None`)

---

### Phase 10d: Implement Recovery Routing (1 hour)

**Add conditional routing in orchestrator:**
```python
# After result_validator, decide where to go
def route_after_validation(state: BaseState) -> str:
    validation = state.get("result_validation", {})
    
    if validation.get("should_retry_discovery"):
        return "discovery"  # Loop back with enhanced keywords
    elif validation.get("should_retry_join_sql"):
        return "join_sql"   # Re-plan joins
    else:
        return "answer"     # Proceed to answer formatting
```

**Update graph:**
```python
graph.add_conditional_edges(
    "result_validator",
    route_after_validation,
    {
        "discovery": "discovery",
        "join_sql": "join_sql",
        "answer": "answer"
    }
)
```

---

### Phase 10e: Add Observability (30 minutes)

**Add to debug_logger:**
```python
def result_validation(validation_result, exec_result):
    logger.info(f"🔍 RESULT VALIDATION")
    logger.info(f"   Valid: {validation_result['valid']}")
    logger.info(f"   Severity: {validation_result['severity']}")
    logger.info(f"   Diagnosis: {validation_result['diagnosis']}")
    logger.info(f"   Row count: {exec_result.get('row_count')}")
```

---

## PART VI: ISSUES TO FIX IN PARALLEL

### 1. **State Type Safety** (MEDIUM)
**Issue:** `exec_result` can be dict, None, or error object. Inconsistent.

**Fix:**
```python
# In contracts/state.py, update type hint
exec_result: Optional[Dict[str, Any]]  # ALWAYS dict or None, never string

# In exec_recovery agent
if not exec_result:
    state["exec_result"] = {
        "ok": False,
        "error": "Query execution returned no result",
        "row_count": 0
    }
```

### 2. **MCP Response Typing** (MEDIUM)
**Issue:** Tools return JSON strings that must be parsed client-side; no shape validation.

**Fix:** Define Pydantic models in mcp_server/models.py:
```python
class ListRelationsResponse(BaseModel):
    fk_relationships: List[Dict[str, str]]
    
# In tools.py
def list_relations(...) -> ListRelationsResponse:
    # ...
    return ListRelationsResponse(fk_relationships=[...])
```

### 3. **Discovery Fallback Heuristic** (LOW)
**Issue:** If keywords_for_discovery is empty, discovery uses fallback extraction → 943 tables.

**Fix:** Make keyword fallback smarter:
```python
if not keywords:
    # Instead of ALL tables, extract from user_input directly
    fallback_keywords = extract_nouns(user_input)
    # Then search with fallback
```

### 4. **Answer Agent Clarity** (LOW)
**Issue:** Answer agent is doing too much (clarification + count extraction + schema response).

**Fix:** Split into focused nodes:
- `answer_data_result` (format data)
- `answer_clarification` (ask user)
- `answer_schema` (explain schema)
- `answer_error` (explain error)

---

## PART VII: SUCCESS METRICS (Phase 10)

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Zero-result handling** | Silent fallback | Diagnosed + suggested | Count "retries" in logs |
| **Recovery routing** | None | 60% success on retry | Test suite: "empty result → retry discovery" |
| **MCP JSON failures** | Silently ignored | Logged + escalated | Error count & severity |
| **State type safety** | Mixed types | Always valid | Type checker passes |
| **Query success rate** | ~72% (Phase 8) | →85% | End-to-end test on 20 queries |

---

## PART VIII: RISK ANALYSIS

### Risk 1: Infinite Loops
**If result_validator routes back to discovery, could loop forever.**

**Mitigation:**
- Track retry count per phase (max 2 discovery retries, max 2 join retries)
- If max exceeded, escalate to answer with error

### Risk 2: Over-Validation Latency
**Adding another agent adds ~200-300ms per query.**

**Mitigation:**
- Result validator is lightweight (no LLM calls initially)
- Cache validation results if query structure repeats

### Risk 3: Diagnostic False Positives
**"This result is wrong" might misfire on edge cases (e.g., 0 customers is valid).**

**Mitigation:**
- Use conservative thresholds (only flag if VERY suspicious)
- Always allow user to accept/reject suggested retry

---

## PART IX: IMPLEMENTATION SEQUENCE (Recommended)

**Week 1 (Phase 10a-10c):**
1. Day 1-2: Create ResultValidatorAgent (skeleton + basic validation)
2. Day 2-3: Implement _validate_sql_node (AST parsing, column validation)
3. Day 3-4: Fix list_relations JSON parsing + MCP response typing
4. Day 4-5: Integrate into orchestrator, wire graph, test basic flow

**Week 2 (Phase 10d-10e):**
1. Day 1-2: Implement recovery routing (conditional edges)
2. Day 2-3: Add observability (debug logs, metrics)
3. Day 3-4: Test end-to-end (manual + smoke tests)
4. Day 4-5: Polish, document, prepare for user study

---

## PART X: WHAT TO DO NOW (Next 30 Minutes)

### ✅ Immediate Actions:

1. **Accept this architecture review** (you're reading it now ✓)

2. **Confirm your priorities:**
   - Do you want to tackle result validation (most impactful)?
   - Or fix MCP JSON parsing issues first (quick win)?
   - Or improve sql_validator (lower priority)?

3. **Prep work:**
   - Review langgraph_integration/agents/exec_recovery/agent.py (understand retry logic)
   - Review langgraph_integration/agents/answer/agent.py (understand answer formatting)
   - Decide: Should result_validator be LLM-based or rule-based initially?

4. **Next: We'll create Phase 10a (ResultValidatorAgent) together.**

---

## APPENDIX A: File Dependency Graph

```
orchestrator.py (main orchestrator)
├─ imports: IntentParserAgent, DiscoveryAgent, JoinPlanAndSQLAgent,
│          ExecAndRecoveryAgent, AnswerAgent, InterpretationAgent
├─ builds graph with 10+ nodes & conditional edges
└─ MISSING: ResultValidatorAgent class & node

agents/result_validator/ (NEEDS TO BE CREATED)
├─ agent.py (new class ResultValidatorAgent)
└─ __init__.py (export)

contracts/state.py (state schema)
├─ BaseState (union of all fields)
├─ NEEDS TO ADD: result_validation field
└─ Type hints for all intermediate values

mcp_server/tools.py (MCP tool implementations)
├─ _search_tables_from_catalog()
├─ list_relations() [PROBLEMATIC: returns empty JSON]
├─ list_views()
└─ query_bounded()

agents/join_sql/agent.py (join planning)
├─ Calls list_relations() [NEEDS ERROR HANDLING]
├─ Attempts JSON parsing [FAILS SILENTLY]
└─ Falls back to single-table

debug_logger.py (observability)
├─ agent_entry(), agent_exit()
├─ NEEDS TO ADD: result_validation logging
└─ tool_result()
```

---

## APPENDIX B: Example Trace (Current vs. After Fix)

### CURRENT (Your Logs):
```
🚀 AGENT ENTRY: discovery
✅ Tool Result: search_tables (1 candidate)
✅ Tool Result: describe_table (3 calls)
ℹ️  ✅ AGENT EXIT: discovery
   Added: relevant_tables, schema_snippet, candidate_views

🚀 AGENT ENTRY: join_sql
✅ Tool Result: list_relations (3 calls)
   Failed to parse relations result (3 times)
   No FK relationships found
ℹ️  ✅ AGENT EXIT: join_sql
   Added: join_plan (strategy=single), sql_query

🚀 AGENT ENTRY: exec_recovery
✅ Tool Result: query
   ok=true, row_count=0, rows=[]
ℹ️  ✅ AGENT EXIT: exec_recovery
   Added: exec_result, retry_count=0

[NO LOGGING AFTER THIS - ANSWER NODE IS SILENT]

UI Output: "Your query executed successfully but returned no data"
```

### AFTER FIX (Phase 10):
```
🚀 AGENT ENTRY: discovery
✅ Tool Result: search_tables (1 candidate)
✅ Tool Result: describe_table (3 calls)
ℹ️  ✅ AGENT EXIT: discovery
   Added: relevant_tables, schema_snippet, candidate_views

🚀 AGENT ENTRY: join_sql
✅ Tool Result: list_relations (3 calls)
   ⚠️  MCP Tool failed to parse (empty JSON)
   Falling back to single-table strategy [LOGGED]
ℹ️  ✅ AGENT EXIT: join_sql
   Added: join_plan (strategy=single, fk_resolution=failed), sql_query

🚀 AGENT ENTRY: validate_sql
✅ AST validation: SQL syntax OK
✅ Column validation: columns exist in schema_snippet
ℹ️  ✅ AGENT EXIT: validate_sql
   Added: sql_validated=true

🚀 AGENT ENTRY: exec_recovery
✅ Tool Result: query
   ok=true, row_count=0, rows=[]
ℹ️  ✅ AGENT EXIT: exec_recovery
   Added: exec_result, retry_count=0

🚀 AGENT ENTRY: result_validator [NEW]
🔍 VALIDATION: COUNT query returned 0 rows
   ⚠️  Diagnosis: Possible schema issue (table might be empty or misnamed)
   Suggestions: 
      1. Retry discovery with broader keywords ("count", "total")
      2. Check if table is in ERP (time window may exclude all rows)
🎯 DECISION: Route back to DISCOVERY with enhanced keywords
ℹ️  ✅ AGENT EXIT: result_validator
   Action: retry_discovery=true, route_next=discovery

[LOOP BACK TO DISCOVERY WITH ENHANCED KEYWORDS]

🚀 AGENT ENTRY: discovery [RETRY 1]
📝 Enhanced keywords: ["customer", "count", "total"]
✅ Tool Result: search_tables (5 candidates - better!)
✅ Tool Result: describe_table (calls for top 3)
ℹ️  ✅ AGENT EXIT: discovery
   Retry found better candidates

[CONTINUE THROUGH PIPELINE WITH NEW CANDIDATES]

🚀 AGENT ENTRY: answer
✅ Format result with diagnostic note
Final Response: "Found X customers. Note: Initial query returned no data; 
                 re-searched with enhanced keywords and found matches."
```

---

## APPENDIX C: Questions for You

1. **Should result_validator be rule-based or LLM-powered initially?**
   - Rule-based: Fast, deterministic, easier to debug
   - LLM-based: Smarter, but adds latency & cost

2. **Should recovery routing be exhaustive or conservative?**
   - Exhaustive: Try rediscovery, rejoin, retry 2-3 times before giving up
   - Conservative: Only retry once, escalate to user quickly

3. **For the user study (UTAUT2), should we log every diagnostic decision?**
   - Yes: Lets us analyze which recovery paths actually helped
   - No: Cleaner logs, but less data for research

4. **Should Answer agent still format zero-results, or should validator prevent that?**
   - Formatter style (current): Answer says "no data, possible reasons are..."
   - Preventer style: Validator never passes zero-results to answer; escalates first

---

**END OF ANALYSIS**

Next Step: **Review this document with your team, then we build Phase 10a together.**