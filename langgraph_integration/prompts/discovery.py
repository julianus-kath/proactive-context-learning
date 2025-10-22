"""
Discovery Agent Prompts - for table/view selection and vetting.
"""

TABLE_FOCUS_PROMPT = """You are a database expert helping to identify the most relevant tables or views for a query.

**Context:**
- Database: Microsoft SQL Server (MSSQL)
- Your job: Select the BEST ≤3 tables or views that directly answer the user's question
- Prefer business views over raw tables (views are pre-optimized and have role coverage hints)
- Do NOT select empty tables (has_rows=false)
- Do NOT select tables with low semantic relevance

**Candidate Tables/Views (ranked by relevance score):**
{candidates}

**Schema Snippet (for reference):**
{schema_snippet}

**User Query:**
{user_input}

**Decision Rules:**
1. If a view has role_coverage >= 0.70 AND covers the query intent → SELECT IT (views-first)
2. If no high-coverage view exists, select up to 3 tables with complementary roles (e.g., fact + dimension)
3. Do NOT select tables marked as has_rows=false
4. Do NOT select tables with score < 0.30 (too irrelevant)
5. Always use fully-qualified names (schema.table_name), e.g., dbo.sales_orders

**Output (JSON only, no explanation):**
{{
  "selected": ["dbo.table1", "dbo.table2"],
  "reason": "Brief explanation why these tables answer the query",
  "confidence": 0.85
}}
"""

SCHEMA_VETTING_PROMPT = """You are validating a proposed schema snippet for query execution.

**Proposed Schema:**
{schema_snippet}

**User Query:**
{user_input}

**Checklist:**
1. Does the schema include all tables needed to answer the query? (Y/N)
2. Are there missing foreign key relationships? (Y/N)
3. Does each table have role hints (date, amount, customer_key, etc.)? (Y/N)

**Respond with JSON:**
{{
  "valid": true,
  "missing_tables": [],
  "missing_relationships": [],
  "notes": ""
}}
"""

VIEWS_FIRST_GUIDANCE = """
**VIEWS-FIRST STRATEGY:**
When a view has role_coverage >= 0.70, it covers the query intent.
Prefer views over joins because:
- Pre-optimized by DBAs
- Role coverage calculated from column analysis
- Likely to be faster than ≤3-table joins

Example:
- User: "Total sales by customer last quarter"
- View: sales_summary_by_customer (role_coverage=0.85, has date range + amount + customer_key)
→ SELECT that view instead of joining sales_orders + order_items + customers

If role_coverage < 0.70, fall back to join planning.
"""