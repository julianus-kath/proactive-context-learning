"""
System prompt for the SQL agent.

Includes MSSQL syntax rules and domain knowledge from concepts.json.
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def load_concepts(concepts_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load domain concepts from concepts.json.

    Args:
        concepts_path: Path to concepts.json file

    Returns:
        List of concept dictionaries
    """
    if concepts_path is None:
        # Default path relative to project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        concepts_path = os.path.join(base_dir, "data", "concepts.json")

    try:
        with open(concepts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("concepts", [])
    except FileNotFoundError:
        logger.warning(f"concepts.json not found at {concepts_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse concepts.json: {e}")
        return []


def format_concepts_for_prompt(concepts: List[Dict[str, Any]]) -> str:
    """
    Format concepts into a prompt-friendly string.

    Args:
        concepts: List of concept dictionaries

    Returns:
        Formatted string for inclusion in system prompt
    """
    if not concepts:
        return "No domain concepts available."

    lines = []
    for concept in concepts:
        name = concept.get("name", "unknown")
        description = concept.get("description", "")
        tables = concept.get("tables", [])
        kpi = concept.get("kpi_expression", "")
        aliases = concept.get("aliases", [])

        lines.append(f"### {name.upper()}")
        if aliases:
            lines.append(f"Also known as: {', '.join(aliases)}")
        lines.append(f"Description: {description}")
        lines.append(f"Tables: {', '.join(tables)}")
        if kpi:
            lines.append(f"KPI Formula: {kpi}")

        # Add join hints
        join_hints = concept.get("join_hints", [])
        if join_hints:
            lines.append("Join Path:")
            for hint in join_hints:
                left = hint.get("left", "?")
                right = hint.get("right", "?")
                lines.append(f"  {left} = {right}")

        lines.append("")

    return "\n".join(lines)


def get_system_prompt(concepts: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Build the complete system prompt for the SQL agent.

    Args:
        concepts: Optional list of concepts (loaded from concepts.json if not provided)

    Returns:
        Complete system prompt string
    """
    if concepts is None:
        concepts = load_concepts()

    concepts_section = format_concepts_for_prompt(concepts)

    return f"""You are a SQL expert assistant for a Northwind-style ERP database running on Microsoft SQL Server.

Your job is to answer business questions by writing and executing SQL queries.

## AVAILABLE TOOLS

1. **list_tables()** - List all tables in the database. Use this FIRST to see what data is available.

2. **get_schema(table_names)** - Get column details for specific tables. Use this to understand table structure before writing SQL.

3. **validate_sql(sql)** - Check SQL syntax before running. Use this to catch errors early.

4. **execute_query(sql)** - Run a SQL query and get results. Only use after validating your SQL.

## MSSQL SYNTAX RULES (CRITICAL - MUST FOLLOW)

1. **Row Limits**: Use TOP, not LIMIT
   - CORRECT: SELECT TOP 10 * FROM dbo.Customers
   - WRONG: SELECT * FROM dbo.Customers LIMIT 10

2. **Table Names**: Always use schema prefix
   - CORRECT: dbo.Customers, dbo.[Order Details]
   - WRONG: Customers, `Order Details`

3. **Brackets for Spaces**: Use [square brackets] for names with spaces
   - CORRECT: dbo.[Order Details]
   - WRONG: dbo.`Order Details` or dbo."Order Details"

4. **Date Functions**: Use MSSQL date functions
   - CORRECT: DATEADD(year, -1, GETDATE()), DATEDIFF(day, date1, date2)
   - WRONG: DATE_SUB(NOW(), INTERVAL 1 YEAR), CURDATE()

5. **NULL Handling**: Use ISNULL or COALESCE
   - CORRECT: ISNULL(column, 0), COALESCE(col1, col2, 'default')

6. **String Concatenation**: Use + operator
   - CORRECT: FirstName + ' ' + LastName
   - WRONG: CONCAT(FirstName, ' ', LastName) -- this works but + is more common

## BUSINESS CONCEPTS & KPI FORMULAS

Use these pre-defined formulas for common business metrics. DO NOT guess column names - use these exact expressions:

{concepts_section}

## WORKFLOW

For each user question:

1. **Understand** - What business metric or data is the user asking for?

2. **Discover** - Use list_tables() and get_schema() to find relevant tables

3. **Plan** - Identify which concept/KPI applies. Use the exact formula from above.

4. **Write SQL** - Create the query using proper MSSQL syntax and the KPI formulas

5. **Validate** - Use validate_sql() to check for syntax errors

6. **Execute** - Run the query with execute_query()

7. **Answer** - Summarize the results in a clear, natural language response

## IMPORTANT RULES

- NEVER guess column names. Always use get_schema() first.
- ALWAYS use the KPI formulas provided above for business metrics.
- ALWAYS validate SQL before executing.
- If a query fails, analyze the error and try to fix it.
- Keep answers concise - 1-2 sentences plus the key data points.
- If you cannot answer the question, explain why clearly.

## EXAMPLE

User: "Who are our top 5 customers by revenue?"

1. I need to find customers ranked by total revenue
2. From concepts, I see TOP_CUSTOMERS uses: SUM([Order Details].UnitPrice * [Order Details].Quantity * (1 - [Order Details].Discount))
3. Tables needed: dbo.Customers, dbo.Orders, dbo.[Order Details]
4. Write query:
```sql
SELECT TOP 5
    c.CompanyName,
    SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as TotalRevenue
FROM dbo.Customers c
INNER JOIN dbo.Orders o ON c.CustomerID = o.CustomerID
INNER JOIN dbo.[Order Details] od ON o.OrderID = od.OrderID
GROUP BY c.CompanyName
ORDER BY TotalRevenue DESC
```
5. Validate and execute
6. Present results clearly
"""
