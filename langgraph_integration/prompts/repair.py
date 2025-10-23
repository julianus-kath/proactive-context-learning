"""
Repair Prompts - for SQL error recovery and retry.
"""

SQL_REPAIR_PROMPT = """You are a SQL debugging expert for Microsoft SQL Server.

The following query failed. Analyze the error and generate a corrected version.

**Original Query:**
{sql_query}

**Error Message:**
{error_message}

**Schema Context:**
{schema_snippet}

**Join Plan (if available):**
{join_plan}

**CRITICAL MSSQL Syntax Issues to Check (in priority order):**
1. **LIMIT vs TOP (MOST COMMON ERROR):**
   ✗ WRONG: SELECT * FROM dbo.orders LIMIT 100
   ✓ CORRECT: SELECT TOP 100 * FROM dbo.orders
   If the error mentions "LIMIT", replace it with TOP immediately.

2. **Schema prefix missing:**
   ✗ WRONG: SELECT * FROM orders
   ✓ CORRECT: SELECT * FROM dbo.orders

3. **Incorrect date functions:**
   ✗ WRONG: DATE_SUB(GETDATE(), INTERVAL 1 YEAR) [PostgreSQL]
   ✓ CORRECT: DATEADD(year, -1, GETDATE()) [MSSQL]

4. **Backticks instead of brackets:**
   ✗ WRONG: SELECT `order_date` FROM dbo.orders [MySQL style]
   ✓ CORRECT: SELECT [order_date] FROM dbo.orders [MSSQL style]

5. **Missing brackets for spaced identifiers:**
   ✗ WRONG: SELECT order date FROM dbo.orders
   ✓ CORRECT: SELECT [order date] FROM dbo.orders

6. **JOIN condition errors:**
   - Check foreign key relationships in schema
   - Verify column names on both sides of the join

7. **Aggregate without GROUP BY:**
   - If using COUNT, SUM, AVG, MAX, MIN, must have GROUP BY

8. **OFFSET...FETCH syntax (valid but unusual):**
   - MSSQL supports: OFFSET 0 ROWS FETCH NEXT 100 ROWS ONLY
   - But prefer TOP syntax: SELECT TOP 100 instead

**Debugging Steps:**
1. Identify the specific error (syntax, table not found, column not found, etc.)
2. Check the join plan for FK relationships
3. Verify all table/column names against schema_snippet
4. Validate MSSQL syntax

**Generate Corrected SQL:**
- Ensure fully qualified names (dbo.table_name)
- Use MSSQL syntax (TOP, DATEADD, GETDATE())
- Apply same filters as original intent
- Keep row limit and safety constraints

**Output (corrected SQL only, no explanation):**
SELECT ...
"""

REPAIR_WITH_FALLBACK = """You are a SQL recovery expert.

**Failed Query:**
{sql_query}

**Error:**
{error_message}

**Retry Attempt:** {retry_count} of 2

**Strategy:**
If this is attempt 1 of 2:
  - Fix the syntax error and retry
If this is attempt 2 of 2:
  - FALLBACK: Generate a simpler query (e.g., single table, no joins)
  - Or ask user for clarification

**Generate fixed SQL:**
"""

QUERY_SIMPLIFICATION = """You are simplifying an overly complex query.

**Complex Query:**
{sql_query}

**Issue:** Query likely timed out or is too complex.

**Simplification Strategy:**
1. Reduce joins from 3+ to 2 or fewer
2. Remove expensive aggregations (if possible)
3. Add more specific WHERE filters to reduce rows
4. Consider sampling (TOP N rows only)

**Generate simplified version:**
"""