"""
SQL Normalizer - Ensures SQL dialect consistency.

Primary focus is MSSQL (TOP syntax), but this module is now
dialect-aware and can operate in PostgreSQL mode as well.

Dialect selection is controlled via the DB_DIALECT environment
variable:
    - "mssql"   → MSSQL-focused normalization & validation
    - "postgres" → Pass-through for LIMIT, with generic safety checks
"""

import os
import re
import logging

logger = logging.getLogger(__name__)


def _current_dialect() -> str:
    """
    Return the active database dialect.
    
    Defaults to "mssql" for backwards compatibility if unset or unknown.
    """
    dialect = os.getenv("DB_DIALECT", "mssql")
    if not isinstance(dialect, str):
        return "mssql"
    dialect = dialect.strip().lower()
    if dialect in {"mssql", "sqlserver"}:
        return "mssql"
    if dialect in {"postgres", "postgresql"}:
        return "postgres"
    # Fallback: keep legacy MSSQL behaviour
    logger.warning(f"Unknown DB_DIALECT '{dialect}', defaulting to MSSQL normalizer")
    return "mssql"


def normalize_sql_to_mssql(sql: str) -> tuple[str, list[str]]:
    """
    Convert any PostgreSQL LIMIT syntax to MSSQL TOP syntax.
    
    Safety layer for edge cases where LLM generates incorrect dialect.
    This is the second-pass safety mechanism after prompt guidance.
    
    Args:
        sql: The SQL query potentially containing LIMIT syntax
    
    Returns:
        Tuple of (normalized_sql, warnings_list)
        
    Examples:
        >>> normalize_sql_to_mssql("SELECT * FROM users LIMIT 10")
        ("SELECT TOP 10 * FROM users", True)
        
        >>> normalize_sql_to_mssql("SELECT * FROM users LIMIT 10 OFFSET 5")
        ("SELECT TOP 10 * FROM users", True)  # Note: OFFSET dropped (MSSQL uses different syntax)
        
        >>> normalize_sql_to_mssql("SELECT TOP 10 * FROM users")
        ("SELECT TOP 10 * FROM users", False)
    """
    if not sql or not isinstance(sql, str):
        return sql, []
    
    warnings: list[str] = []
    
    # Pattern: "LIMIT N [OFFSET M]" (PostgreSQL syntax)
    # Matches: LIMIT 10, LIMIT 10 OFFSET 5, etc.
    pattern = r'\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?\b'
    
    def replace_limit(match):
        limit_count = match.group(1)
        offset_count = match.group(2)
        
        if offset_count:
            # LIMIT N OFFSET M case
            message = (
                f"SQL dialect fix: LIMIT {limit_count} OFFSET {offset_count} → TOP {limit_count}. "
                "Note: OFFSET syntax differs in MSSQL (use ROW_NUMBER for pagination)."
            )
            logger.warning(message)
            warnings.append(message)
            return f'TOP {limit_count}'
        else:
            # Simple LIMIT N case
            message = f"SQL dialect fix: LIMIT {limit_count} → TOP {limit_count}"
            logger.info(message)
            warnings.append(message)
            return f'TOP {limit_count}'
    
    # Find if there's a match
    if not re.search(pattern, sql, flags=re.IGNORECASE):
        return sql, []
    
    # Apply the substitution
    normalized = re.sub(pattern, replace_limit, sql, flags=re.IGNORECASE)
    return normalized, warnings


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
    
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    if sql_upper.startswith("WITH"):
        select_idx = sql_upper.find("SELECT")
        if select_idx == -1:
            return False, "CTE query missing SELECT statement"
        effective_upper = sql_upper[select_idx:]
    elif sql_upper.startswith("SELECT"):
        effective_upper = sql_upper
    else:
        return False, "Query must start with SELECT"

    # Should have FROM clause (allowing newline/spacing variations)
    if not re.search(r'\bFROM\b', effective_upper):
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
    
    # For MSSQL-specific validation, return None-style reason on success
    return True, None


def _validate_common_select_safety(sql: str) -> tuple[bool, str]:
    """
    Dialect-agnostic safety checks for SELECT-style queries.
    
    This is used for PostgreSQL mode where LIMIT is allowed but we still
    want to prevent obvious mistakes and dangerous statements.
    """
    if not sql or not isinstance(sql, str):
        return False, "Empty or non-string SQL"

    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    if sql_upper.startswith("WITH"):
        select_idx = sql_upper.find("SELECT")
        if select_idx == -1:
            return False, "CTE query missing SELECT statement"
        effective_upper = sql_upper[select_idx:]
    elif sql_upper.startswith("SELECT"):
        effective_upper = sql_upper
    else:
        return False, "Query must start with SELECT or WITH"

    if not re.search(r'\bFROM\b', effective_upper):
        return False, "Query must have FROM clause"

    forbidden = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE "]
    for stmt in forbidden:
        if sql_upper.startswith(stmt):
            return False, f"DML statements like {stmt} are not allowed"

    if sql.count("'") % 2 != 0:
        return False, "Unbalanced single quotes"

    if sql.count('"') % 2 != 0:
        return False, "Unbalanced double quotes"

    open_parens = sql.count("(")
    close_parens = sql.count(")")
    if open_parens != close_parens:
        return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"

    return True, None


def _prepare_sql_mssql(sql: str) -> tuple[str, list[str]]:
    """
    MSSQL-specific normalization and validation pipeline.
    """
    if not sql:
        raise ValueError("Empty SQL query")

    warnings: list[str] = []

    # Step 1: Normalize LIMIT → TOP
    normalized_sql, norm_warnings = normalize_sql_to_mssql(sql)
    warnings.extend(norm_warnings)

    # Strip trailing semicolon for cleaner execution
    normalized_sql = normalized_sql.strip().rstrip(";")

    # Step 2: Validate MSSQL syntax
    is_valid, reason = validate_mssql_syntax(normalized_sql)
    if not is_valid:
        raise ValueError(f"SQL validation failed: {reason}")

    return normalized_sql, warnings


def prepare_sql_for_execution(sql: str) -> tuple[str, list[str]]:
    """
    Prepare SQL for execution for MSSQL targets.
    
    This is the legacy, MSSQL-focused pipeline used by tests and
    by components that are always expected to generate MSSQL SQL.
    
    Args:
        sql: The SQL query to prepare
    
    Returns:
        Tuple of (cleaned_sql, warnings_list)
    
    Raises:
        ValueError: If SQL fails validation
    """
    return _prepare_sql_mssql(sql)


def _prepare_sql_postgres(sql: str) -> tuple[str, list[str]]:
    """
    PostgreSQL-safe preparation: keep LIMIT clauses, apply generic safety checks.
    """
    if not sql:
        raise ValueError("Empty SQL query")

    warnings: list[str] = []

    # No LIMIT→TOP conversion in Postgres mode – pass through as-is
    normalized_sql = sql.strip().rstrip(";")

    is_valid, reason = _validate_common_select_safety(normalized_sql)
    if not is_valid:
        raise ValueError(f"SQL validation failed: {reason}")

    return normalized_sql, warnings


def prepare_sql_for_execution_dialect_aware(sql: str) -> tuple[str, list[str]]:
    """
    Dialect-aware preparation helper used by the execution agent.
    
    - If DB_DIALECT=postgres → keep LIMIT and apply generic safety checks.
    - Otherwise (default)    → use MSSQL pipeline (LIMIT→TOP).
    """
    dialect = _current_dialect()
    if dialect == "postgres":
        return _prepare_sql_postgres(sql)
    return _prepare_sql_mssql(sql)
