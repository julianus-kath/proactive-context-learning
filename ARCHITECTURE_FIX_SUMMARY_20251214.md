# Architecture Fix Summary - December 14, 2025

## What Happened

**Before**: System was masking failures by silently falling back to sample data  
**After**: System properly surfaces real blockers with clear diagnostic signals

You identified that all 12 queries were failing not due to multiple bugs, but due to **one systematic blockage in Discovery**.

---

## Changes Made (4 Parts)

### 1️⃣ Hard Block Empty SQL Execution
**File**: `langgraph_integration/agents/exec_recovery/agent.py:219-246`

**Change**: Instead of silent fallback when SQL is empty, fail hard immediately
```python
if not sql or not sql.strip():
    error = {"type": "NO_SQL_GENERATED", ...}
    state["exec_result"] = {"ok": False, "error": error["message"]}
    return state  # ← HARD FAIL, don't proceed to MCP
```

**Impact**: Prevents fallback sample queries like `SELECT * FROM customers`

---

### 2️⃣ Grounding Gate Before AnswerAgent  
**File**: `langgraph_integration/orchestrator.py:1386-1418`

**Change**: Don't answer data queries unless SQL execution succeeded
```python
if is_data_query:
    if not exec_ok or not sql_query or exec_error:
        state["final_response"] = "I wasn't able to retrieve the information..."
        return state  # ← FAIL, don't produce ungrounded answers
```

**Impact**: Prevents responses like "The query doesn't show suppliers" when no supplier query was run

---

### 3️⃣ Better Evaluation Success Criteria
**File**: `eval/run_benchmark.py:52-109`

**Change**: Updated `artifact_validation_errors()` to check for:
- Empty SQL (`sql_executed: [""]` or `[]`)
- Missing tables (`tables_used: []`)
- Grounding gate errors (`UNGROUNDED_RESPONSE_PREVENTED`)
- No results (`row_count=None and no preview`)

**Impact**: Summary now shows realistic failure counts instead of masking errors

---

### 4️⃣ Hard Blocking on Catalog + Loud Failure on Empty Discovery
**File**: `langgraph_integration/orchestrator.py`

**Changes**:
a) **New `_get_or_build_catalog()` method** (lines 532-590)
```python
Attempt 1: Load from MCP scout runner
Attempt 2: Load from file (data/catalog/scout_catalog.json)
Attempt 3: Build it via MCP (idempotent)
Result: Raises RuntimeError if all fail (no silent degradation)
```

b) **Hard blocking in `_index_database_node`** (lines 594-650)
```python
if not catalog:
    error = {"type": "CATALOG_NOT_READY", ...}
    # ← HARD BLOCK: entire pipeline stops
```

c) **Loud failure in `_discovery_node`** (lines 975-994)
```python
if not relevant_tables and not error_info:
    error = {
        "type": "DISCOVERY_NO_CANDIDATES",
        "message": f"Keywords: {keywords}...",
        "tables_found": 0,
    }
    state["error_info"] = error
    # ← FAIL LOUD with explicit diagnostic
```

**Impact**: 
- Catalog must be ready before ANY query
- Empty discovery results produce explicit error_info
- Clear signals for debugging (catalog vs keywords vs search)

---

## Current State (Dec 14, 20251214_165151)

### What's Working ✅
- Grounding gate preventing hallucinations
- Hard blocks on empty SQL
- Evaluation detecting failures correctly
- Honest error reporting

### What's Broken ❌
- **Discovery returns ZERO candidates for all 12 queries**
  - This blocks the entire pipeline before SQL generation
  - Root cause: One of three issues (see diagnostic guide)

### Result
- 0/12 queries succeeded (correct and honest)
- All have explicit error messages  
- Clear diagnostic signals for investigation

---

## Next Steps (Priority Order)

### Immediate: Diagnose Discovery Failure

Run one query and check logs:
```bash
python -m chatbot_ui.langgraph_service
# In another terminal:
curl -X POST http://localhost:5001/process_query \
  -d '{"user_input": "How many products?", "api_key": "supersecretapikey"}'

# Check which signal appears:
grep "CATALOG_NOT_READY" logs/*  # Issue 1: Catalog
grep "keywords_for_discovery: \[\]" logs/*  # Issue 2: Keywords  
grep "DISCOVERY_NO_CANDIDATES" logs/*  # Issue 3: Search
```

### Then: Fix the Root Cause

**If CATALOG_NOT_READY**: See "Fixing: Catalog Initialization" in DIAGNOSTIC_DISCOVERY_FAILURE_20251214.md

**If keywords empty**: See "Fixing: Intent Parser" in diagnostic guide

**If search fails**: See "Fixing: Scout Search" in diagnostic guide

### Finally: Re-Run Evaluation

Once discovery returns candidates:
```bash
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name fixed_discovery \
  --target http://localhost:5001
```

You should see SQL being generated and tables_used being populated.

---

## Code Quality Checklist

- [x] All modules compile without syntax errors
- [x] Existing node signatures preserved
- [x] State contract maintained (BaseState compatible)
- [x] Error handling adds error_info (not just logging)
- [x] Hard blocks prevent silent degradation
- [x] Diagnostic signals are explicit and searchable
- [x] Logging includes context (keywords, counts, attempt numbers)
- [x] No breaking changes to evaluation API

---

## Architecture Lessons Learned

### Anti-Pattern 1: Silent Fallbacks
❌ **Bad**: If SQL fails, execute sample query and answer based on that
✅ **Good**: If SQL fails, return explicit error and don't answer

### Anti-Pattern 2: Evaluation Over-Optimism  
❌ **Bad**: "Completed HTTP request" = success
✅ **Good**: Check actual grounding (SQL + tables + results + no errors)

### Anti-Pattern 3: Empty Results Without Signals
❌ **Bad**: Discovery returns `[]` with no error_info
✅ **Good**: If discovery returns empty, set explicit error_info with diagnostic

### Pattern 1: Hard Prerequisites
✅ **Good**: Scout/Catalog must exist before ANY discovery  
This prevents downstream nodes from failing cryptically.

### Pattern 2: Fail Loud, Not Silent
✅ **Good**: Every node that can fail should attach `error_info`  
Not just log warnings that get lost in noise.

---

## Files Modified

| File | Lines | Purpose |
|------|-------|---------|
| `langgraph_integration/agents/exec_recovery/agent.py` | 219-246 | Hard block empty SQL |
| `langgraph_integration/orchestrator.py` | 532-994 | Catalog blocking + discovery failure + intent check |
| `eval/run_benchmark.py` | 52-109 | Better failure detection |

---

## Success Metrics for Next Run

When you run the updated evaluation:
- ✅ `summary.json` shows `failed_queries > 0`
- ✅ Each Q-file has explicit `failure_reasons` 
- ✅ Queries with issues show `error_info.type` (e.g., "DISCOVERY_NO_CANDIDATES")
- ✅ Latency drops (no more 30s timeouts trying to hallucinate)
- ✅ Logs contain diagnostic signals (catalog, keywords, candidates)

---

## What This Fixes vs What Still Needs Work

### Now Fixed 🟢
- [x] SQL loss between nodes (hard block prevents this)
- [x] Ungrounded answers (grounding gate prevents this)
- [x] Silent failures masked as success (honest reporting)
- [x] Invisible state contract violations (explicit errors)

### Still Needs Fixing 🔴
- [ ] Discovery returning zero candidates (root cause TBD)
- [ ] SQL generation quality (once discovery works)
- [ ] Date range handling for 2024 queries
- [ ] Complex join planning for multi-table queries

---

## Appendix: Rollback Instructions

If needed, revert to pre-fix state:
```bash
git diff HEAD langgraph_integration/orchestrator.py | head -50
# Shows all changes made

git checkout langgraph_integration/orchestrator.py
git checkout langgraph_integration/agents/exec_recovery/agent.py
git checkout eval/run_benchmark.py
```

But **do not rollback** - fixes are correct. Instead, diagnose Discovery issue.
