# Scout Mode Root Cause Analysis: "No Data" Bug Investigation

**Date:** 2025  
**Status:** FINDINGS DOCUMENTED

---

## Executive Summary

The "no data" issue is **NOT a field name problem** (Phase 10b fixes are correct). The root cause is:

**Scout Mode semantic discovery is not being used to validate SQL generation.**

When the user asks "How many customers do we have?", the system:
1. ✅ Discovery Agent SHOULD find "KHKAdressen" via Scout (fuzzy matching, intent boosting)
2. ✅ Passes "KHKAdressen" to JoinPlanAndSQLAgent as `relevant_tables`
3. ❌ **BUT** JoinPlanAndSQLAgent's LLM generates SQL referencing "dbo.Customer" (hallucinated, doesn't exist)
4. ❌ No validation that "dbo.Customer" actually exists in the catalog before execution
5. ❌ Query fails silently, returns "no data" message

---

## Architecture Gap Analysis

### Scout Mode (Should Be Working)

✅ **Implemented (ADR-0014, ADR-0020):**
- `mcp_server/scout_runner.py` - Semantic search engine with intent-aware boosting
- Line 334-489: `ScoutRunner.search()` includes sophisticated ranking for "customer" queries
- Line 427-430: **Explicit boost for customer count queries:**
  ```python
  if "count" in intent_operations and any(e in ["kunde", "kunden", "customer", "customers"] for e in intent_entities):
      if any(tok in name_lower for tok in ["khkadressen", "adressen", "adresse", "kunde", "kunden", "customer"]):
          score = min(1.0, score + 0.6)
          reasons.append("Customer master boost")
  ```

✅ **MCP Search Tools Use Scout (tools.py line 1196-1232):**
- Line 1205-1206: Tries `ScoutRunner.search()` first
- Line 1210-1214: Passes `intent_data` for semantic ranking
- Should return `KHKAdressen` with high score for "customer" queries

### Discovery Agent (Should Be Returning Correct Tables)

✅ **Implementation (langgraph_integration/agents/discovery/agent.py):**
- Line 181: Calls `await self.mcp.search_tables(query_str, page=1, page_size=10, intent_data=intent)`
- Should receive Scout-ranked results including KHKAdressen
- Stores in state: `relevant_tables: ["KHKAdressen", ...]`

### Join SQL Agent (THE GAP - NOT VALIDATING)

❌ **Problem (langgraph_integration/agents/join_sql/agent.py line 213-290):**

The `_build_join_plan_node()` receives `relevant_tables` from discovery, then:

1. Line 226-232: Logs the tables received from discovery ✓
2. Line 250-270: Classifies tables by simple name heuristics (checking for "khkadressen", "adressen", etc.) ✓
3. **BUT THEN**: Line 213+ passes this information to the LLM via prompts

The problem: **The LLM in `_generate_sql_node()` is given this schema info but is FREE TO IGNORE IT.**

The prompt at `langgraph_integration/prompts/join_sql.py` says:
- Line 5-56: "Build join strategy using ≤3 tables"
- But gives the LLM a `schema_snippet` that MAY NOT match what was actually discovered

**Missing: A validation step that:**
1. Takes the generated SQL table names
2. Checks if they exist in the catalog
3. Falls back to discovered tables if SQL references non-existent tables

---

## Evidence Trail

### What Should Happen (Discovery Works)

Scout search for "How many customers do we have?" with intent `{entities: ["customer"], metrics: ["count"]}`:

```
ScoutRunner.search() scoring for KHKAdressen:
- "customer" in "khkadressen" → fuzzy match score ~0.7
- intent_operations contains "count" ✓
- intent_entities contains "customer" ✓
- BOOST: +0.6 → final score ~1.0
- REASON: "Customer master boost"

Result: KHKAdressen returned as #1 with score 1.0
```

### What's Actually Happening (LLM Hallucination)

1. Discovery Agent receives: `relevant_tables: ["dbo.KHKAdressen"]` from MCP
2. JoinPlanAndSQLAgent builds plan with this table
3. But the LLM prompt includes generic schema snippet
4. LLM generates: `SELECT COUNT(*) FROM dbo.Customer` ← **Hallucinated - not from discovery**
5. No validation checks if "dbo.Customer" actually exists
6. Query fails: "Ungültiger Objektname 'dbo.Customer'" (German: "Invalid object name")
7. Empty result → "no data" message

---

## Why Scout Isn't Being Validated

### Theory 1: Scout Not Ready Yet
- `scout_runner.start()` (server.py line 129) is **non-blocking**
- Background build might not complete before first query
- System falls back to old `DiscoveryTools.search_tables()`
- **But**: Old discovery also has same problem - it would suggest KHKAdressen, but LLM still hallucinates

### Theory 2: Schema Snippet Not Being Used
- The `schema_snippet` passed to LLM might be incomplete or wrong
- LLM doesn't have the discovered table in its context
- Falls back to knowledge of generic "Customer" table from training data

### Theory 3: No Validation Gate
- **MOST LIKELY**: SQL generation has NO gate that says "validate all table names exist in catalog"
- LLM is free to hallucinate
- No safety check before execution

---

## The Fix (Three-Part Strategy)

### Part 1: Ensure Scout Is Used
```python
# In tools.py _search_tables() - line 1206
if scout_runner and scout_runner.is_ready():
    # Use Scout search
else:
    # INSTEAD OF: Fall back to old discovery
    # DO: Return error saying "Scout catalog loading, try again in X seconds"
    # This forces front-end to wait for Scout to be ready
```

### Part 2: Validate SQL Before Execution
```python
# In join_sql_agent.py _generate_sql_node()
# After SQL is generated:
generated_tables = extract_table_names_from_sql(sql)
discovered_tables = set(relevant_tables)

for table in generated_tables:
    if table.lower() not in {t.lower() for t in discovered_tables}:
        logger.error(f"SQL references unknown table {table}")
        # Regenerate SQL using ONLY discovered tables
```

### Part 3: Pass Discovery Results to LLM
```python
# In join_sql agent prompts - join_sql.py
# CHANGE: Pass discovered tables explicitly
"MUST USE ONLY THESE DISCOVERED TABLES:\n" + "\n".join(relevant_tables)
"Do NOT use any other tables."
```

---

## Verification Test

### What We Need to Check

1. **Is Scout returning KHKAdressen for "customer" queries?**
   ```python
   # In scout_runner.py line 334
   results = scout_runner.search("customer", intent_data={"entities": ["customer"], "metrics": ["count"]})
   assert results[0]["name"] == "KHKAdressen"
   ```

2. **Is Discovery Agent passing it forward?**
   ```python
   # Check discovery agent output state
   assert "KHKAdressen" in state["relevant_tables"]
   ```

3. **Does Join SQL Agent keep it or hallucinate?**
   ```python
   # Check join_plan
   assert "KHKAdressen" in join_plan["primary_table"]  # or in joins list
   assert "dbo.Customer" not in generated_sql
   ```

---

## Files to Review/Modify

| File | Issue | Priority |
|------|-------|----------|
| `mcp_server/scout_runner.py` | ✅ Looks good - semantic search is correct | Check |
| `mcp_server/tools.py:1196` | ❌ Falls back to old discovery if Scout not ready | FIX |
| `langgraph_integration/agents/join_sql/agent.py` | ❌ No validation of SQL table names | FIX |
| `langgraph_integration/prompts/join_sql.py` | ⚠️ Needs explicit constraint on table names | UPDATE |
| `langgraph_integration/agents/exec_recovery/agent.py` | ✅ Phase 10b fixes verified | OK |
| `langgraph_integration/orchestrator.py` | ✅ Correctly reads "data" field | OK |

---

## Recommendation

**Priority 1: Add SQL Validation Gate**
- Before any SQL execution, validate all table names exist in discovered tables
- This prevents hallucination immediately
- ~20 lines of code

**Priority 2: Tighten LLM Prompt**
- Explicitly list discovered tables in the prompt
- Add "MUST NOT use any other tables" constraint
- Update prompts/join_sql.py

**Priority 3: Scout Ready Check**
- When Scout isn't ready, don't fall back - make client wait
- Or async wait for Scout to be ready
- Better UX than random failures

---

## Next Steps

1. Run DEBUG_NO_DATA.py to confirm SQL generation is the issue
2. Add table validation to join_sql agent
3. Test with "How many customers do we have?" query
4. Verify ScoutRunner.search() returns KHKAdressen
5. Check if LLM respects discovered table constraints