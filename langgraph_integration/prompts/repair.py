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

**Common MSSQL Issues to Check:**
1. Table/view name typos or missing schema prefix (dbo., webshop., etc.)
2. Column name mismatch (check alias usage, case sensitivity)
3. Incorrect date functions (DATEADD instead of DATE_SUB, GETDATE() instead of NOW())
4. Missing brackets around identifiers with spaces: [Order Date]
5. INNER vs LEFT JOIN causing NULL filtering
6. Aggregate function without GROUP BY
7. HAVING clause used before WHERE
8. TOP syntax error (TOP N, not LIMIT N)
9. JOIN condition using wrong column names (check foreign keys)
10. Missing quotes around string literals

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