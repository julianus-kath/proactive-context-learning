"""
Join & SQL Agent Prompts - for join planning and MSSQL generation.
"""

JOIN_PLANNER_PROMPT = """You are a database architect designing a join plan for a SQL Server query.

**Goal:** Build a join strategy using ≤3 tables that answers the user's query.

**Available Tables:**
{schema_snippet}

**Foreign Key Relationships (from list_relations):**
{fk_hints}

**User Query:**
{user_input}

**Decision Process:**
1. Identify the FACT table (main entity: sales orders, invoices, customers, etc.)
2. Identify DIMENSION tables (date, product, customer, location, etc.)
3. Plan joins via FK relationships ONLY (no guessing column names)
4. Keep total hop count ≤ 3 (fact → dim1 → dim2)
5. Include WHERE filters from the query intent

**Output (JSON):**
{{
  "strategy": "view" | "joins",
  "primary_table": "dbo.sales_orders",
  "joins": [
    {{
      "table": "dbo.customers",
      "on": "sales_orders.customer_id = customers.id",
      "type": "INNER"
    }}
  ],
  "where_filters": [
    {{"column": "order_date", "operator": ">=", "value": "2024-01-01"}}
  ],
  "select_columns": ["customer_name", "SUM(order_total)"],
  "groupby_columns": ["customer_name"],
  "limit": 1000,
  "reason": "Fact table + 1 dimension; filters via FK"
}}
"""

SQL_GENERATOR_PROMPT_MSSQL = """You are a SQL expert for Microsoft SQL Server (MSSQL).

Generate a production-ready SELECT query based on the join plan.

**CRITICAL MSSQL RULES:**
- Use TOP {row_limit} instead of LIMIT
- Use DATEADD(year, -1, GETDATE()) for date math (NOT DATE_SUB)
- Always use fully-qualified table names: [dbo].[table_name] or dbo.table_name
- Use ISNULL or COALESCE for NULL handling
- Always use square brackets for identifiers if they contain spaces: [Order Date]
- Never use backticks (MySQL only)
- Date literals: CAST('2024-01-01' AS DATE) or CONVERT(DATE, '2024-01-01', 120)
- GETDATE() for current timestamp

**Join Plan:**
{join_plan}

**Generate the SQL:**
- Ensure it compiles without errors
- Include proper NULL handling
- Use meaningful column aliases
- Format for readability

**Output (SQL only, no explanation):**
SELECT ...
FROM ...
WHERE ...
"""

SQL_GENERATOR_WITH_VALIDATION = """You are generating a SELECT query for Microsoft SQL Server.

**Schema:**
{schema_snippet}

**User Query:**
{user_input}

**Requirements:**
{requirements}

**Constraints:**
- READ-ONLY: SELECT only
- ROW LIMIT: TOP {row_limit}
- TIMEOUT: {query_timeout_seconds} seconds max
- MSSQL Dialect: TOP, DATEADD, GETDATE(), fully-qualified names
- Safety: Redact sensitive columns (password, email, ssn)

**Generate valid MSSQL:**
"""

VIEWS_PREFERENCE = """
**IMPORTANT:** If a single view covers the query intent with role_coverage >= 0.70:
1. Prefer the view over joins
2. The query becomes: SELECT * FROM [schema].[view_name] WHERE <filters>
3. Only fall back to joins if no suitable view exists

Example:
- User: "Show me total sales by product category"
- View: vw_sales_by_category (role_coverage=0.80, covers amount + category)
→ Use view instead of joining sales_orders + order_items + products + product_categories
"""