# SQL Generation Column Validation Fix

**Issue**: The LLM-based SQL generator was producing queries with non-existent column names (e.g., `ORDER BY [Name]` when `Name` column doesn't exist in `dbo.KHKAdressen`).

**Root Cause**: The LLM was being too creative - it was adding `ORDER BY` clauses with guessed column names instead of strictly using only columns from the provided schema snippet.

---

## Solution: Two-Layer Validation

### Layer 1: Stricter LLM Prompt (Preventive)

**File**: `langgraph_integration/prompts/__init__.py` (SQL_GENERATOR_PROMPT)

**Changes**:
- Added explicit warning: "You MUST use ONLY columns that appear in the schema below"
- Added concrete error examples: "ORDER BY [Name] when Name is not in schema ← Column doesn't exist - ERROR"
- Rule 6 now says: "ONLY use ORDER BY with columns that are explicitly listed in the schema"
- Rule 7 says: "Validate every column/table name exists in the schema BEFORE using it"
- Fallback instruction: "If you're unsure about a column name, use SELECT * instead"

**Impact**: The LLM now has very clear instructions not to hallucinate column names. Most times, this will prevent the issue at generation time.

### Layer 2: Post-Validation (Defensive)

**File**: `langgraph_integration/graph_definition.py`

**New Methods**:

#### `_validate_sql_columns(sql_query: str, schema_snippet: str) -> Dict[str, Any]`
- Extracts all column names from generated SQL using regex
- Extracts all columns from schema snippet (looks for `- ColumnName: Type` pattern)
- Compares the two sets to find invalid columns
- Returns: `{"valid": bool, "message": str, "invalid_columns": List[str]}`

**Example Output**:
```python
{
    "valid": False,
    "message": "SQL uses columns not in schema: {'Name', 'Amount'}",
    "invalid_columns": ['Name', 'Amount']
}
```

#### `_extract_primary_table(sql_query: str) -> Optional[str]`
- Parses SQL to extract the primary table name
- Handles patterns: `FROM dbo.table`, `FROM [schema].[table]`, etc.
- Returns: Fully qualified table name like `dbo.KHKAdressen`

**Example Output**: `"dbo.KHKAdressen"`

### Validation Flow (in `_generate_sql`)

```
1. LLM generates SQL with improved prompt
2. Extract SQL from response
3. Validate SQL columns against schema
4. If valid: Use generated SQL
5. If invalid: 
   - Log validation error with invalid columns
   - Fall back to simple: SELECT TOP 100 * FROM {extracted_table}
   - Log fallback SQL
```

---

## Changes Made

### 1. `langgraph_integration/prompts/__init__.py`

**Before**:
```python
6. Use ORDER BY for consistent, meaningful results
7. Validate all tables/columns exist in schema (if not, the query will fail)
```

**After**:
```python
⚠️ CRITICAL CONSTRAINT: You MUST use ONLY columns that appear in the schema below.
DO NOT guess or hallucinate column names. If a column is not listed, do NOT use it.

❌ WRONG - HALLUCINATING COLUMNS:
  - ORDER BY [Name] when Name is not in schema  ← Column doesn't exist - ERROR
  - WHERE [Amount] > 100 when Amount isn't listed ← Failure - don't guess

6. ⚠️ CRITICAL: ONLY use ORDER BY with columns that are explicitly listed in the schema above
7. ⚠️ CRITICAL: Validate every column/table name exists in the schema BEFORE using it
8. If you're unsure about a column name, use SELECT * instead of ordering by a guessed column

If a column you need is not in the schema, return: SELECT TOP {limit} * FROM {table}
Do NOT attempt to guess column names. The schema provided is definitive.
```

### 2. `langgraph_integration/graph_definition.py` - `_generate_sql()` method

**Added validation after SQL generation**:
```python
# VALIDATION: Check if SQL uses columns that exist in schema
schema_snippet = state.get("schema_snippet", "")
column_validation = self._validate_sql_columns(sql_query, schema_snippet)

if not column_validation["valid"]:
    # LLM generated SQL with non-existent columns
    logger.warning(f"⚠️ SQL validation failed: {column_validation['message']}")
    logger.warning(f"   Invalid columns: {column_validation['invalid_columns']}")
    logger.warning(f"   Falling back to simple SELECT *")
    
    # Fallback: Extract table and generate simple SELECT without ORDER BY
    table_match = self._extract_primary_table(sql_query)
    if table_match:
        sql_query = f"SELECT TOP 100 * FROM {table_match}"
        logger.info(f"✅ Fallback SQL: {sql_query}")
```

### 3. Added Two New Methods to `DatabaseWorkflow` class

- `_validate_sql_columns()` - Validates column names
- `_extract_primary_table()` - Extracts table name from SQL

---

## Testing the Fix

### Before (Broken):
```
User Query: "list any 5 customers"
Generated SQL: SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [Name]
Error: Ungültiger Spaltenname 'Name' (Invalid column name 'Name')
```

### After (Fixed):
```
User Query: "list any 5 customers"
Generated SQL (attempt): SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [Name]
Validation: ❌ Invalid columns found: ['Name']
Fallback SQL: SELECT TOP 100 * FROM dbo.KHKAdressen
Result: ✅ Query executes successfully
```

---

## Key Improvements

1. **Two-layer defense**: LLM prompt + runtime validation
2. **Clear logging**: Easy to debug when validation fails
3. **Graceful degradation**: Falls back to safe `SELECT *` instead of failing
4. **Table extraction**: Handles various SQL formatting styles
5. **No impact on valid queries**: Valid SQL passes validation unchanged

---

## Troubleshooting

### If validation still fails:

1. Check logs for "SQL validation failed" messages
2. Look at "Invalid columns" list to see what LLM hallucinated
3. Check schema_snippet being provided - ensure it has all expected columns
4. Verify `build_schema_snippet()` is formatting columns correctly as `- ColumnName: Type`

### If table extraction fails:

1. Check the regex pattern in `_extract_primary_table()`
2. Log the raw SQL to see what format it's in
3. Manually verify the table name matches `FROM` clause in SQL

---

## Future Improvements

1. **Use structured output**: Require LLM to return column names in strict JSON format
2. **Schema enrichment**: Include sample data in schema snippet to help LLM understand column meanings
3. **Phase 1 Scout Mode integration**: Use role_hints from column_enricher.py for semantic guidance
4. **Semantic validation**: Check that column types match how they're used (e.g., ORDER BY on numeric/string, not JSON)

---

## Architecture Alignment

✅ **Proxy-only separation**: No changes to proxy or database access layer
✅ **Database abstraction**: Validation works regardless of backend
✅ **Read-only operations**: Only SELECT queries affected
✅ **JSON as single format**: No changes to data format
✅ **Security maintained**: No sensitive data exposed in validation logs
