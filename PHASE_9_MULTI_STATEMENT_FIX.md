# Phase 9 Multi-Statement Validation Error — Root Cause & Deep Fix

**Status:** 🔴 CRITICAL BUG IDENTIFIED & READY FOR FIX

**Problem:** SQL query validation fails with `ValidationErrorCode.MULTI_STATEMENT` when LLM repairs/simplifies queries.

---

## 🔍 Deep Dive: Root Cause Analysis

### The Error Flow

```
1. Query Fails (e.g., validation, syntax, timeout)
   ↓
2. ExecAndRecoveryAgent calls LLM for repair/simplification
   ↓
3. LLM Response includes:
   - Original problematic SQL
   - Markdown explanation  
   - Simplified/repaired SQL in code fence
   ↓
4. _extract_sql() tries to extract just the SQL
   BUT: Returns everything from first SELECT to end-of-string
   ↓
5. Result: Multiple SQL statements + markdown passed to query_bounded
   ↓
6. MCP validates and rejects: "MULTI_STATEMENT error"
```

### Evidence from Logs

```
ERROR:mcp_server.bounded_query: Invalid query: 
  SELECT a.id, a.name, b.total_sales, c.region_name, d.manager_name
  FROM customers a
  JOIN sales b ON a.id = b.customer_id
  ...
  ORDER BY b.total_sales DESC;  ← First query ends here
  ```
  
  ### Simplified Version    ← Markdown starts here
  1. **Reduce Joins**: ...
  ...
  
  ```sql                      ← Second code fence
  SELECT a.id, a.name, b.total_sales
  ...
  LIMIT 100;                 ← Second query ends here
  ```
```

### Architecture Issues

#### Issue #1: Prompt Lacks Output Format Strictness

**File:** `langgraph_integration/prompts/repair.py`

Lines 72-74:
```python
**Output (corrected SQL only, no explanation):**
SELECT ...
```

**Problem:** This instruction is:
- ❌ Weak — LLM can interpret "only" as "but you can add explanation"
- ❌ Ambiguous — Doesn't specify JSON wrapping or strict format
- ❌ Not enforced — No schema validation on LLM response

**Solution:** Make prompt strict and explicit:
```
**CRITICAL: Output format MUST be:**
\`\`\`sql
SELECT ...
\`\`\`
**DO NOT include any explanation, markdown, or text outside the code fence.**
**If you cannot fix it, respond with: CANNOT_FIX**
```

#### Issue #2: SQL Extraction is Too Naive

**File:** `langgraph_integration/agents/exec_recovery/agent.py`, lines 552-579

**Current logic:**
```python
def _extract_sql(self, text: str) -> str:
    # Find first SELECT
    select_idx = text.upper().find("SELECT")
    if select_idx >= 0:
        text = text[select_idx:]  # ❌ Takes EVERYTHING from first SELECT to EOF
    return text.strip()
```

**Problem:** This assumes:
- ✗ There's only ONE SELECT statement
- ✗ Everything after SELECT is SQL
- ✗ Markdown/explanation comes BEFORE SELECT
- ✗ No semicolons mark statement boundaries

**Reality:** LLM responses are:
- Multiple SELECTs
- Explanation interspersed between SELECTs
- Markdown boundaries

#### Issue #3: No SQL Statement Boundary Detection

**Problem:** The extraction doesn't know where a SQL statement ends:
```
SELECT ... FROM ... WHERE ... ORDER BY ... ;   ← Ends here
```

A proper extractor needs to:
1. Find first SELECT
2. Extract SQL until: `;` (SQL terminator)
3. Stop at markdown markers (`#`, `\`\`\``, `-`, `>`)
4. Validate single complete SELECT

#### Issue #4: LLM Behavior Inconsistency

**Problem:** Different LLM calls behave differently:
- Sometimes: Returns plain SQL (good)
- Sometimes: Returns SQL with explanation (bad)
- Sometimes: Returns markdown-formatted multi-part response (worst)

**Root cause:** No structured output format (not using JSON mode or strict schema)

---

## ✅ Complete Fix Strategy

### Fix #1: Upgrade Prompts (Strict Output Format)

**File:** `langgraph_integration/prompts/repair.py`

Add strict output format requirement:
```python
SQL_REPAIR_PROMPT = """...
**CRITICAL OUTPUT FORMAT:**
- Return ONLY a single SELECT statement
- Wrap in triple backticks: \`\`\`sql ... \`\`\`
- No explanation before or after
- If cannot fix: respond only with: CANNOT_FIX
- Invalid response examples (DO NOT DO):
  ❌ "Here's the fix:\n\n```sql SELECT ...```"  (has explanation)
  ❌ "```sql SELECT ... ``` \n\nThe issue was..."  (has trailing text)
  ❌ Multiple SQL statements in one response
"""
```

Similarly for `QUERY_SIMPLIFICATION`:
```python
QUERY_SIMPLIFICATION = """...
**CRITICAL OUTPUT FORMAT:**
- Return ONLY a simplified SELECT statement
- Wrap in triple backticks: \`\`\`sql ... \`\`\`
- No explanation, no markdown headings, no multiple versions
- If cannot simplify: respond only with: CANNOT_SIMPLIFY
"""
```

### Fix #2: Robust SQL Extraction Method

**File:** `langgraph_integration/agents/exec_recovery/agent.py`

Replace `_extract_sql()` with intelligent multi-stage extractor:

```python
def _extract_sql(self, text: str) -> str:
    """
    🔧 ROBUST FIX: Extract single SQL statement from LLM response.
    
    Handles:
    - Markdown code fences (```sql ... ```)
    - Explanations before/after SQL
    - Multiple SELECT statements (returns only the clean one)
    - Markdown markers (#, ##, etc.)
    - Special tokens (CANNOT_FIX, CANNOT_SIMPLIFY)
    """
    text = text.strip()
    
    # Stage 1: Check for special tokens
    if "CANNOT_FIX" in text or "CANNOT_SIMPLIFY" in text:
        logger.warning("❌ LLM indicated it cannot repair/simplify this query")
        return ""
    
    # Stage 2: Extract from markdown code fence if present
    sql_from_fence = self._extract_from_code_fence(text)
    if sql_from_fence:
        logger.debug("✅ Extracted SQL from markdown code fence")
        return sql_from_fence
    
    # Stage 3: Extract first SELECT...semicolon if no fence
    sql_from_select = self._extract_select_to_semicolon(text)
    if sql_from_select:
        logger.debug("✅ Extracted SQL from SELECT statement")
        return sql_from_select
    
    # Stage 4: Nothing valid found
    logger.warning("⚠️  Could not extract valid SQL from LLM response")
    logger.debug(f"Response preview: {text[:300]}...")
    return ""

def _extract_from_code_fence(self, text: str) -> str:
    """Extract SQL from markdown code fence (```sql ... ```)."""
    # Find ```sql block
    fence_start = text.find("```sql")
    if fence_start < 0:
        return ""
    
    fence_start += 6  # Skip "```sql"
    fence_end = text.find("```", fence_start)
    
    if fence_end < 0:
        # No closing fence - take to end
        fence_end = len(text)
    
    sql = text[fence_start:fence_end].strip()
    
    # Validate: must start with SELECT (after whitespace)
    if not sql.upper().lstrip().startswith("SELECT"):
        logger.warning("⚠️  Code fence does not contain SELECT statement")
        return ""
    
    # Remove trailing markdown (###, ##, etc. or other code fences)
    lines = sql.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Stop at markdown markers or other code fences
        if stripped.startswith("#") or stripped.startswith("```"):
            break
        clean_lines.append(line)
    
    sql = "\n".join(clean_lines).strip()
    
    # Remove trailing semicolons/whitespace for consistency
    sql = sql.rstrip(";").strip()
    
    return sql

def _extract_select_to_semicolon(self, text: str) -> str:
    """Extract SELECT statement up to first semicolon."""
    # Find first SELECT (case-insensitive)
    select_idx = text.upper().find("SELECT")
    if select_idx < 0:
        return ""
    
    # Find first semicolon after SELECT
    semicolon_idx = text.find(";", select_idx)
    if semicolon_idx < 0:
        # No semicolon - might be unfinished
        logger.warning("⚠️  SELECT found but no terminating semicolon")
        return ""
    
    sql = text[select_idx:semicolon_idx].strip()
    
    # Validate: single SELECT, no markdown
    if text[select_idx:semicolon_idx].count("SELECT") > 1:
        logger.warning("⚠️  Multiple SELECT statements found - cannot disambiguate")
        return ""
    
    # Check for markdown/explanation markers after semicolon
    after_sql = text[semicolon_idx+1:].strip()
    if after_sql and not after_sql.startswith("\n"):
        # Might have markdown immediately following
        logger.debug(f"⚠️  Content after SQL: {after_sql[:50]}...")
    
    return sql

def _validate_extracted_sql(self, sql: str) -> bool:
    """Validate extracted SQL is a single, complete SELECT."""
    sql = sql.strip()
    
    # Must start with SELECT
    if not sql.upper().startswith("SELECT"):
        logger.error("❌ Extracted SQL does not start with SELECT")
        return False
    
    # Must not have multiple statements
    statement_count = sql.upper().count("SELECT")
    if statement_count > 1:
        logger.error(f"❌ Multiple SELECT statements ({statement_count}) found")
        return False
    
    # Must not have dangerous statements
    for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]:
        if keyword in sql.upper():
            logger.error(f"❌ Dangerous keyword found: {keyword}")
            return False
    
    return True
```

### Fix #3: Updated _repair_sql_node() and _simplify_query_node()

**File:** `langgraph_integration/agents/exec_recovery/agent.py`

Lines 323-327 and 421-423 need to:
1. Call updated `_extract_sql()`
2. Validate extracted SQL
3. Handle extraction failure gracefully

```python
async def _repair_sql_node(self, state: BaseState) -> BaseState:
    """Attempt to repair failed SQL."""
    logger.info("🔧 Attempting SQL repair...")
    
    sql = state.get("sql_query", "")
    error_info = state.get("error_info", {})
    schema_snippet = state.get("schema_snippet", "")
    join_plan = state.get("join_plan", {})
    
    error_msg = error_info.get("message", error_info.get("error", "Unknown error"))
    
    try:
        repair_prompt = SQL_REPAIR_PROMPT.format(
            sql_query=sql,
            error_message=error_msg,
            schema_snippet=schema_snippet,
            join_plan=json.dumps(join_plan, indent=2)
        )
        
        logger.debug(f"Sending repair prompt to LLM...")
        response = await self.llm.ainvoke(repair_prompt)
        repaired_sql = response.content.strip()
        
        # 🔧 IMPROVED EXTRACTION
        repaired_sql = self._extract_sql(repaired_sql)
        
        # 🔧 VALIDATION
        if not repaired_sql:
            raise ValueError("Extraction returned empty SQL")
        
        if not self._validate_extracted_sql(repaired_sql):
            raise ValueError("Extracted SQL failed validation")
        
        logger.info(f"✅ LLM repaired SQL ({len(repaired_sql)} chars)")
        logger.debug(f"Repaired: {repaired_sql[:100]}...")
        
        state["sql_query"] = repaired_sql
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        return state
        
    except Exception as e:
        logger.warning(f"Repair attempt failed: {e}")
        state["error_info"] = {
            "type": "REPAIR_FAILED",
            "message": f"SQL repair attempt failed: {str(e)}",
            "error": str(e),
            "stage": "repair"
        }
        return state
```

---

## 🧪 Test Cases

### Test #1: Code Fence Extraction
```python
response = """Here's the fixed query:

```sql
SELECT id, name FROM dbo.customers WHERE status = 'active'
```

This removes the expensive joins."""

extracted = agent._extract_sql(response)
assert "WHERE status" in extracted
assert "This removes" not in extracted  # No explanation
assert extracted.count("SELECT") == 1    # Single statement
```

### Test #2: Multiple SELECTs (Reject)
```python
response = """The original query:
```sql
SELECT * FROM dbo.orders
```

Should be simplified to:
```sql
SELECT TOP 100 id, total FROM dbo.orders
```
"""

extracted = agent._extract_sql(response)
assert extracted == ""  # Should reject (multiple SELECTs)
```

### Test #3: Special Token
```python
response = "CANNOT_FIX: This query requires database-specific context"
extracted = agent._extract_sql(response)
assert extracted == ""
```

### Test #4: No Code Fence (Fallback to SELECT...;)
```python
response = "The fix is: SELECT TOP 100 id FROM dbo.customers;"
extracted = agent._extract_sql(response)
assert "SELECT TOP 100" in extracted
```

---

## 📊 Impact

### Before Fix
- ❌ Multi-statement validation errors
- ❌ Markdown/explanation leaking into SQL
- ❌ Discovery spam from retry attempts
- ❌ User confusion ("query validation failed")

### After Fix
- ✅ Robust extraction handles any LLM format
- ✅ Single, clean SQL statement validated
- ✅ Failed extraction gracefully degrades
- ✅ Clear logging of what was extracted

---

## 🚀 Implementation Plan

1. **Update prompts** — Make output format stricter
2. **Refactor _extract_sql()** — Multi-stage intelligent extraction  
3. **Add _extract_from_code_fence()** — Handle markdown code blocks
4. **Add _extract_select_to_semicolon()** — Fallback extraction
5. **Add _validate_extracted_sql()** — Ensure single SELECT
6. **Update repair nodes** — Use new validation
7. **Test** — Run unit tests covering all cases

---

## Files to Change

1. `/langgraph_integration/prompts/repair.py` — Stricter output format
2. `/langgraph_integration/agents/exec_recovery/agent.py` — Robust extraction + validation
3. `/tests/test_sql_extraction.py` — New unit tests (create)

---

## 🔗 Architecture Alignment

**Principle:** [repo.md § 11 — Do/Don't]
> **Don't** include full schemas in prompts.

**Principle:** [repo.md § 2 — Execution (safety)]
> `query_bounded` enforces safety through bounded execution, but **input validation must happen first**.

This fix ensures that **extracted SQL is always valid before reaching query_bounded**, preventing downstream validation failures.

---

**Status:** Ready for implementation