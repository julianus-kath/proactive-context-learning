# Diagnostic: Discovery Failure - All 12 Queries (Dec 14 2025)

## What the Latest Run Proved

Your latest evaluation (20251214_165151) shows:
- **0/12 queries succeeded** ✅ Correct! This is honest reporting
- **All queries: `sql_generated=[], tables_used=[], relevant_tables=0`**
- **Clear error messages** instead of silent hallucinations
- **Grounding gate working** - preventing ungrounded answers

## What Changed With The Fixes

| Before | After |
|--------|-------|
| "...suppliers..." response (irrelevant sample data) | "system isn't responding" (honest error) |
| `sql_executed: [""]` (empty string executed) | `sql_executed: []` (hard blocked, no execution) |
| `summary: 12/12 success` (wrong) | `summary: 0/12 completed, 12 failed` (correct) |

**The fixes worked correctly. They exposed the real problem.**

---

## Root Cause Analysis

Your query pipeline never reaches SQL generation because **Discovery returns ZERO candidates** for all 12 queries.

### Query Path Breakdown

```
✅ index_database  → parse_intent  → route_operation  → discovery
❌                    (OK?)          (OK?)              (RETURNS EMPTY!)
                                                        ↓
                                                  (no candidates)
                                                        ↓
                                               join_sql SKIPPED
                                                        ↓
                                              exec_recovery SKIPPED
                                                        ↓
                                        answer (NO SQL → GROUNDING GATE)
                                                        ↓
                                              FAIL (correctly)
```

### Why Discovery Returns Empty (Two Possibilities)

**Possibility 1: `keywords_for_discovery` is EMPTY**
- Intent parser succeeds but extracts zero keywords
- Discovery has nothing to search for → returns zero candidates
- **Log signal**: `keywords_for_discovery: []`

**Possibility 2: Scout/Catalog is NOT INITIALIZED**
- Discovery has keywords but Scout catalog missing
- MCP tool call fails or returns empty
- **Log signal**: `CATALOG_NOT_READY` in error_info OR `DISCOVERY_NO_CANDIDATES` with empty keyword list

**Possibility 3: Scout/Catalog exists but search tool is broken**
- Catalog loads fine, but semantic search returns no results
- **Log signal**: `DISCOVERY_NO_CANDIDATES` with non-empty keyword list

---

## New Diagnostic Capability (Just Added)

Your updated code now includes:

### 1. **Hard Blocking on Catalog** (`_index_database_node`)
```python
# NEW: Two-step check
Step 1: MCP health_check()
Step 2: _get_or_build_catalog()  ← NEW hard block

Result: If catalog can't be loaded/built → entire pipeline blocked
Log: "📚 [INDEX_DATABASE] ❌ HARD BLOCK: CATALOG_NOT_READY"
```

### 2. **Loud Failure on Zero Candidates** (`_discovery_node`)
```python
# NEW: If discovery returns empty tables list
if not relevant_tables and not state.get("error_info"):
    state["error_info"] = {
        "type": "DISCOVERY_NO_CANDIDATES",
        "message": f"Discovery could not find any relevant tables. Keywords: {keywords}",
        "keywords_attempted": keywords,
        "tables_found": 0,
    }

Result: You'll see explicit error_info instead of silent empty list
Log: "🔍 [DISCOVERY] ❌ FAIL LOUD: Discovery could not find any..."
```

### 3. **Catalog Building Strategy** (`_get_or_build_catalog`)
```python
Attempt 1: Load from MCP scout runner
Attempt 2: Load from file (data/catalog/scout_catalog.json)
Attempt 3: Build it via MCP (idempotent)

Result: Will try to auto-build if missing
Log: "📚 [CATALOG] Attempt 1/2/3..."
```

---

## How to Diagnose (Step-by-Step)

### Step 1: Run a Single Query and Check Logs

```bash
# Start LangGraph service
python -m chatbot_ui.langgraph_service &

# In another terminal, run ONE query
curl -X POST http://localhost:5001/process_query \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "How many products do we have?",
    "api_key": "supersecretapikey"
  }'

# Search logs for these signals
grep "📚 \[INDEX_DATABASE\]" langgraph_integration.log  # Catalog load
grep "🧠 \[PARSE_INTENT\]" langgraph_integration.log     # Keywords
grep "🔍 \[DISCOVERY\]" langgraph_integration.log        # Discovery result
```

### Step 2: Check Which Failure Point You Hit

**🔴 If you see:**
```
📚 [INDEX_DATABASE] ❌ HARD BLOCK: CATALOG_NOT_READY
```
→ Scout/Catalog is missing. **See Section "Fixing: Catalog Initialization"** below.

**🔴 If you see:**
```
🧠 [PARSE_INTENT] keywords_for_discovery: []
```
→ Intent parser extracted zero keywords. **See Section "Fixing: Intent Parser"** below.

**🔴 If you see:**
```
🔍 [DISCOVERY] ❌ FAIL LOUD: Discovery could not find any relevant tables
    Keywords attempted: [...]
```
→ Keywords exist, but Scout search found nothing. **See Section "Fixing: Scout Search"** below.

---

## Fixing: Catalog Initialization

If you see `CATALOG_NOT_READY`:

### Check 1: Does the catalog file exist?
```bash
ls -lh data/catalog/scout_catalog.json
```

If it doesn't exist, try building it:
```bash
cd mcp_server
python -c "
from scout_runner import ScoutRunner
from database_adapter import DatabaseAdapter
db = DatabaseAdapter()
scout = ScoutRunner(db)
catalog = scout.build_catalog()
print(f'Built catalog with {len(catalog[\"tables\"])} tables')
"
```

### Check 2: Is MCP's build_catalog() endpoint available?

Look for this in `mcp_server/tools.py`:
```python
async def build_catalog(db_manager):
    # Should exist and build the scout catalog
```

If it's missing, you need to:
1. Add a catalog-building endpoint to MCP
2. Or pre-build the catalog offline and save to `data/catalog/scout_catalog.json`

---

## Fixing: Intent Parser

If you see empty `keywords_for_discovery`:

### Check the current extraction logic (lines ~520-528 of orchestrator.py)
```python
# This is NAIVE extraction - it only looks for exact keyword matches
kws = []
for w in ["customers", "products", "orders", "sales"]:
    if w in t:  # ← This is case-sensitive and word-exact
        kws.append(w)
```

### The Problem
For questions like:
- "When will the product 'Chai' need to be reordered?" 
  - ✅ Has "product" → should extract `["product"]`
  - But if the exact word matching fails → `[]`

- "Which suppliers are at risk?" 
  - ❌ Has no exact matches for `["customers", "products", "orders", "sales"]`
  - Extracts `[]` even though "suppliers" is clearly relevant

### The Solution

Replace the naive regex with actual intent parsing from **IntentParserAgent**:

```python
async def _parse_intent_node(self, state: BaseState) -> BaseState:
    # ... existing code calls intent_parser subgraph ...
    # IntentParserAgent should extract these fields:
    intent["keywords_for_discovery"]     # ← should be populated
    intent["primary_entities"]          # ← suppliers, products, etc.
    intent["operation"]                 # ← query / schema_query / etc.
```

**Check**: Is IntentParserAgent actually being called and returning keywords?

Look for logs around line 650-700:
```
🧠 [PARSE_INTENT] Building IntentParserAgent subgraph...
🧠 [PARSE_INTENT] Keywords extracted: [...]
```

If these aren't present, IntentParserAgent isn't running properly.

---

## Fixing: Scout Search

If you see `DISCOVERY_NO_CANDIDATES` with non-empty keywords:

This means:
- ✅ Keywords extracted properly
- ✅ Catalog loaded
- ❌ Scout semantic search returned zero results

### Debug Steps

1. **Check the MCP search endpoint**
   
   Verify this exists and returns results:
   ```bash
   curl -X POST http://localhost:5000/mcp/search_tables \
     -H "Content-Type: application/json" \
     -d '{
       "search_query": "product",
       "intent_data": {"primary_entities": ["product"]}
     }'
   ```
   
   Expected: `{"tables": [...]}`  (non-empty)

2. **Check TableRanker logic**
   
   In `mcp_server/table_ranker.py`, verify that semantic matching is working:
   ```python
   def rank_tables(self, tables, entities, operations):
       # Should score tables based on name/keyword matches
       # If all tables score 0 → nothing returns
   ```

3. **Check if catalog has the expected tables**
   
   ```bash
   python -c "
   import json
   with open('data/catalog/scout_catalog.json') as f:
       catalog = json.load(f)
   print(f'Tables: {list(catalog[\"tables\"].keys())[:10]}')
   "
   ```

---

## Evaluation Impact (New Criteria)

With the updated evaluation (`artifact_validation_errors` in `eval/run_benchmark.py`), your results will now show:

```json
{
  "Q1": {
    "status": "failed",
    "failure_reasons": [
      "missing_sql",
      "missing_tables"
    ],
    "error_info": {
      "type": "DISCOVERY_NO_CANDIDATES",
      "message": "Discovery could not find any relevant tables..."
    }
  }
}
```

This is **correct and honest reporting**.

---

## Next Priority Actions

### Immediate (30 min)

1. **Run one query and collect logs** (see "How to Diagnose" section)
2. **Identify which failure point** (catalog / keywords / search)
3. **Add that diagnostic to CLAUDE.md** so future runs are faster to debug

### Short-term (1-2 hours)

**If Catalog is missing:**
- Build offline or add MCP endpoint
- Verify in logs: `📚 [CATALOG] ✅ Loaded: X tables`

**If Keywords are empty:**
- Verify IntentParserAgent is running
- Add logging: `logger.info(f"Extracted keywords: {keywords}")`

**If Search returns zero:**
- Test MCP search endpoint manually
- Check TableRanker scoring logic

### Medium-term (depends on above)

Once Discovery returns candidates:
- Run eval again → SQL will be generated
- Move to fixing SQL generation quality
- Then fix execution-level issues

---

## Summary

**What you learned:**
- Your grounding gate + hard blocks are working (preventing hallucinations)
- Discovery returning zero candidates is the real blocker
- Three possible root causes (catalog / keywords / search)

**What to do next:**
- Run one query with new diagnostic logging
- Find which failure point
- Fix that specific issue
- Re-run evaluation

**Expected next outcome:**
Once discovery returns candidates → SQL generation starts → you move to testing quality of SQL.
