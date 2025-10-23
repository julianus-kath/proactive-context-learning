"""
SQL Normalizer - Ensures SQL dialect consistency (MSSQL focus).

This module provides safety layers to catch and fix SQL syntax issues
before execution. Primary use: convert PostgreSQL LIMIT syntax to MSSQL TOP syntax.
"""

import re
import logging

logger = logging.getLogger(__name__)


def normalize_sql_to_mssql(sql: str) -> tuple[str, bool]:
    """
    Convert any PostgreSQL LIMIT syntax to MSSQL TOP syntax.
    
    Safety layer for edge cases where LLM generates incorrect dialect.
    This is the second-pass safety mechanism after prompt guidance.
    
    Args:
        sql: The SQL query potentially containing LIMIT syntax
    
    Returns:
        Tuple of (normalized_sql, was_modified)
        
    Examples:
        >>> normalize_sql_to_mssql("SELECT * FROM users LIMIT 10")
        ("SELECT TOP 10 * FROM users", True)
        
        >>> normalize_sql_to_mssql("SELECT * FROM users LIMIT 10 OFFSET 5")
        ("SELECT TOP 10 * FROM users", True)  # Note: OFFSET dropped (MSSQL uses different syntax)
        
        >>> normalize_sql_to_mssql("SELECT TOP 10 * FROM users")
        ("SELECT TOP 10 * FROM users", False)
    """
    if not sql or not isinstance(sql, str):
        return sql, False
    
    # Pattern: "LIMIT N [OFFSET M]" (PostgreSQL syntax)
    # Matches: LIMIT 10, LIMIT 10 OFFSET 5, etc.
    pattern = r'\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?\b'
    
    def replace_limit(match):
        limit_count = match.group(1)
        offset_count = match.group(2)
        
        if offset_count:
            # LIMIT N OFFSET M case
            logger.warning(
                f"SQL dialect fix: LIMIT {limit_count} OFFSET {offset_count} → TOP {limit_count}. "
                "Note: OFFSET syntax differs in MSSQL (use ROW_NUMBER for pagination)."
            )
            return f'TOP {limit_count}'
        else:
            # Simple LIMIT N case
            logger.info(f"SQL dialect fix: LIMIT {limit_count} → TOP {limit_count}")
            return f'TOP {limit_count}'
    
    # Find if there's a match
    if not re.search(pattern, sql, flags=re.IGNORECASE):
        return sql, False
    
    # Apply the substitution
    normalized = re.sub(pattern, replace_limit, sql, flags=re.IGNORECASE)
    return normalized, True


def validate_mssql_syntax(sql: str) -> tuple[bool, str]:
    """
    Basic validation of MSSQL syntax.
    
    Args:
        sql: The SQL query to validate
    
    Returns:
        Tuple of (is_valid, reason)
    """
    if not sql or not isinstance(sql, str):
        return False, "Empty or non-string SQL"
    
    sql_upper = sql.upper().strip()
    
    # Must start with SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Query must start with SELECT"
    
    # Should have FROM clause
    if " FROM " not in sql_upper:
        return False, "Query must have FROM clause"
    
    # Reject DML statements (just in case)
    forbidden = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE "]
    for stmt in forbidden:
        if sql_upper.startswith(stmt):
            return False, f"DML statements like {stmt} are not allowed"
    
    # Check for balanced quotes and parentheses (basic check)
    if sql.count("'") % 2 != 0:
        return False, "Unbalanced single quotes"
    
    if sql.count('"') % 2 != 0:
        return False, "Unbalanced double quotes"
    
    open_parens = sql.count("(")
    close_parens = sql.count(")")
    if open_parens != close_parens:
        return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"
    
    # No LIMIT remaining (after normalization)
    if re.search(r'\bLIMIT\b', sql, flags=re.IGNORECASE):
        return False, "Query contains LIMIT (should be TOP for MSSQL)"
    
    return True, "Valid MSSQL syntax"


def prepare_sql_for_execution(sql: str) -> tuple[str, list[str]]:
    """
    Prepare SQL for execution: normalize dialect and validate.
    
    Args:
        sql: The SQL query to prepare
    
    Returns:
        Tuple of (cleaned_sql, warnings_list)
    
    Raises:
        ValueError: If SQL fails validation
    """
    if not sql:
        raise ValueError("Empty SQL query")
    
    warnings = []
    
    # Step 1: Normalize LIMIT → TOP
    normalized_sql, was_modified = normalize_sql_to_mssql(sql)
    if was_modified:
        warnings.append("Converted LIMIT syntax to TOP (dialect fix)")
    
    # Step 2: Validate MSSQL syntax
    is_valid, reason = validate_mssql_syntax(normalized_sql)
    if not is_valid:
        raise ValueError(f"SQL validation failed: {reason}")
    
    return normalized_sql, warnings