# Syntax Error Repair & Retry Routing Fix

**Date:** 2025-01-01  
**Issue:** Syntax errors (especially around numeric values like "100") were propagating to the user instead of triggering the repair agent.  
**Root Cause:** Error types from execution didn't match routing conditions in graph_definition.py  
**Status:** ✅ FIXED

---

## Problem Summary

When the LLM generates a query with syntax errors (e.g., numeric values incorrectly quoted), the MCP server returns:
```
ERROR: Falsche Syntax in der Nähe von "100". [Incorrect syntax near "100"]
```

Previously, this error would:
- Be tagged as `error_type: "QUERY_ERROR"` in exec_recovery
- NOT match the routing condition (which only checked for `"query_execution_error"`)
- Skip the repair agent entirely
- Propagate directly to the user

**Expected behavior:** Syntax errors should automatically trigger the repair agent to fix and retry.

---

## Root Causes & Fixes

### 1. **Error Type Mismatch in Routing** ✅ FIXED
**File:** `langgraph_integration/graph_definition.py` (lines 1444-1470)

**Problem:**
```python
# OLD CODE - only 2 specific error types triggered retry
if (error_type in ["query_execution_error", "direct_query_execution_error"] and 
    retry_count < max_retries):
    return "retry"
```

**Actual error types generated:**
- `"QUERY_ERROR"` (from MCP failures, includes syntax errors)
- `"EXECUTION_ERROR"` (runtime issues)
- `"TIMEOUT"` (query timeout)
- `"SQL_VALIDATION_ERROR"` (pre-execution validation)

**Fix Applied:**
```python
# NEW CODE - all database errors trigger retry
retryable_errors = {
    "QUERY_ERROR",              # Syntax errors, DB errors from MCP
    "EXECUTION_ERROR",          # Runtime failures
    "query_execution_error",    # Legacy routing
    "direct_query_execution_error"  # Legacy routing
}

if error_type in retryable_errors and retry_count < max_retries:
    logger.info(f"🔄 Routing {error_type} to retry (attempt {retry_count + 1}/{max_retries})")
    return "retry"
```

### 2. **Numeric Value Quoting in SQL Generation** ✅ FIXED
**File:** `langgraph_integration/agents/join_sql/agent.py` (lines 290-313, 320-353)

**Problem:**
```python
# OLD CODE - ALL values quoted, even numbers
where_conditions.append(f"{col} {op} '{val}'")
# Generated: WHERE quantity = '100'  ❌ WRONG for numeric columns
```

**Fix Applied:**
```python
# NEW CODE - detect if value is numeric, quote only strings
val_str = str(val).strip()
try:
    float(val_str)  # Check if numeric
    condition = f"{col} {op} {val_str}"  # No quotes
except ValueError:
    condition = f"{col} {op} '{val_str}'"  # Quotes for strings
where_conditions.append(condition)
```

**Result:**
- `WHERE quantity = 100` ✓ CORRECT (numeric, no quotes)
- `WHERE status = 'active'` ✓ CORRECT (string, quotes)

### 3. **Enhanced Repair Prompt for MSSQL** ✅ IMPROVED
**File:** `langgraph_integration/prompts/repair.py` (lines 27-31)

Added explicit guidance for numeric value quoting as issue #2:
```
2. **Numeric value quoting errors (if error near numbers like "100"):**
   ✗ WRONG: WHERE quantity = '100'  [numeric in quotes]
   ✓ CORRECT: WHERE quantity = 100  [unquoted numeric]
```

This helps the LLM repair agent recognize and fix this specific error pattern.

---

## Flow Diagram (After Fix)

```
User Query
    ↓
Plan Query → Generate SQL → Execute
    ↓                          ↓
Check Result ← ← ← ← ← ← ← ← ↓
    ↓
[ERROR DETECTED]
    ↓
Is QUERY_ERROR? YES → Repair Agent (LLM fixes syntax)
    ↓                        ↓
    NO                  Retry Execution
    ↓                        ↓
Return to User         SUCCESS? YES → Format & Return ✓
(after max_retries)         ↓
                           NO
                           ↓
                    Try Simplification
                           ↓
                    Final Retry
                           ↓
                    SUCCESS? NO → Return Error to User
```

---

## Testing This Fix

### Test Case 1: Numeric Quoting Error
**Input:** "How many customers have status 100?"
```sql
-- BEFORE FIX: WHERE status = '100'  ❌
-- AFTER FIX: WHERE status = 100    ✓
```

**Expected Behavior:**
1. First attempt generates WHERE status = '100'
2. MCP returns syntax error: "Incorrect syntax near '100'"
3. Error type = "QUERY_ERROR" ✓ (now routed to retry)
4. Repair agent fixes to WHERE status = 100
5. Query succeeds ✓

### Test Case 2: LIMIT vs TOP Error
**Input:** "Select top 100 customers"
```sql
-- BEFORE FIX: LIMIT 100  ❌ 
-- AFTER FIX: TOP 100     ✓
```

**Expected Behavior:**
1. If generated with LIMIT 100
2. MCP returns error about LIMIT
3. Repair agent sees error, checks repair prompt
4. Recognizes this as common LIMIT vs TOP issue
5. Generates correct TOP syntax ✓

### Verification Script
```bash
# Check that routing logs appear:
# Looking for: "🔄 Routing QUERY_ERROR to retry"
# Before: Error goes directly to "❌ Error {error_type} not retryable"
```

---

## Related Files

- **graph_definition.py:** Main workflow routing logic
- **join_sql/agent.py:** SQL generation (now with smart value quoting)
- **exec_recovery/agent.py:** Query execution and repair attempts
- **prompts/repair.py:** LLM repair instructions (now with numeric quoting guidance)

---

## Summary of Changes

| Component | Change | Impact |
|-----------|--------|--------|
| Routing Logic | Expanded retryable errors from 2 to 4 types | Syntax errors now trigger repair ✓ |
| SQL Generation | Smart numeric/string value quoting | Eliminates syntax errors from WHERE clauses ✓ |
| Repair Prompt | Added numeric quoting guidance | LLM better understands this error type ✓ |

---

## Future Improvements

1. **Parameterized Queries:** Use SQL parameters instead of string concatenation for better safety
2. **Type Inference:** Infer column types from schema to guide value quoting automatically
3. **Syntax Validation:** Pre-validate SQL before execution to catch errors early
4. **Error Categorization:** Distinguish between retryable (syntax) and user-error (clarification) cases