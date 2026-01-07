"""
SQL validation tool for MSSQL syntax checking.
"""

import re
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Common MSSQL syntax patterns
MSSQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
    "ON", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS", "NULL",
    "ORDER", "BY", "ASC", "DESC", "GROUP", "HAVING", "TOP", "DISTINCT",
    "AS", "WITH", "CASE", "WHEN", "THEN", "ELSE", "END", "UNION", "ALL",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "ISNULL",
    "DATEADD", "DATEDIFF", "GETDATE", "YEAR", "MONTH", "DAY",
    "CAST", "CONVERT", "OVER", "PARTITION", "ROW_NUMBER", "RANK",
}


@tool
def validate_sql(sql: str) -> str:
    """
    Validate SQL syntax for MSSQL compatibility.

    Checks for common syntax errors and MSSQL-specific requirements.
    Use this tool BEFORE executing a query to catch errors early.

    Args:
        sql: The SQL query to validate

    Returns:
        Validation result: either "Valid" or a description of the issues found.
    """
    issues = []
    sql_upper = sql.upper()
    sql_stripped = sql.strip()

    # Check 1: Must be a SELECT statement
    if not sql_upper.strip().startswith("SELECT") and not sql_upper.strip().startswith("WITH"):
        issues.append("Query must be a SELECT statement (or WITH ... SELECT). INSERT/UPDATE/DELETE are not allowed.")

    # Check 2: Check for MySQL LIMIT syntax (should use TOP instead)
    if re.search(r'\bLIMIT\s+\d+', sql_upper):
        issues.append("MSSQL uses TOP instead of LIMIT. Change 'SELECT ... LIMIT N' to 'SELECT TOP N ...'")

    # Check 3: Check for MySQL backticks (MSSQL uses square brackets)
    if '`' in sql:
        issues.append("MSSQL uses [square brackets] for identifiers, not `backticks`")

    # Check 4: Check for unqualified table names (should have schema prefix)
    # This is a soft warning
    from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)\s', sql_upper)
    if from_match:
        table_name = from_match.group(1)
        if '.' not in table_name and table_name not in MSSQL_KEYWORDS:
            issues.append(f"Consider using schema prefix: 'dbo.{table_name}' instead of just '{table_name}'")

    # Check 5: Check for MySQL date functions
    mysql_date_funcs = ["DATE_SUB", "DATE_ADD", "NOW()", "CURDATE()"]
    for func in mysql_date_funcs:
        if func in sql_upper:
            issues.append(f"'{func}' is MySQL syntax. Use MSSQL equivalents: DATEADD, DATEDIFF, GETDATE()")

    # Check 6: Check for balanced parentheses
    open_parens = sql.count('(')
    close_parens = sql.count(')')
    if open_parens != close_parens:
        issues.append(f"Unbalanced parentheses: {open_parens} opening vs {close_parens} closing")

    # Check 7: Check for balanced brackets
    open_brackets = sql.count('[')
    close_brackets = sql.count(']')
    if open_brackets != close_brackets:
        issues.append(f"Unbalanced brackets: {open_brackets} opening vs {close_brackets} closing")

    # Check 8: Check for semicolon (single statement only)
    if sql_stripped.count(';') > 1:
        issues.append("Multiple statements detected. Only single SELECT statements are allowed.")

    # Check 9: Check for dangerous operations
    dangerous_patterns = [
        (r'\bDROP\s+', "DROP statements are not allowed"),
        (r'\bTRUNCATE\s+', "TRUNCATE statements are not allowed"),
        (r'\bDELETE\s+FROM', "DELETE statements are not allowed"),
        (r'\bINSERT\s+INTO', "INSERT statements are not allowed"),
        (r'\bUPDATE\s+\w+\s+SET', "UPDATE statements are not allowed"),
        (r'\bEXEC\s+', "EXEC/EXECUTE statements are not allowed"),
        (r'\bEXECUTE\s+', "EXEC/EXECUTE statements are not allowed"),
    ]
    for pattern, message in dangerous_patterns:
        if re.search(pattern, sql_upper):
            issues.append(message)

    # Return result
    if not issues:
        return "Valid MSSQL syntax. The query looks correct and safe to execute."
    else:
        return "Validation issues found:\n" + "\n".join(f"  - {issue}" for issue in issues)
