"""
Query validator for MCP server - Phase 2: Safety & Bounded Execution.

This module provides comprehensive SQL query validation, safety checks,
and row cap injection for production-ready database access.

Features:
- SELECT/WITH...SELECT validation (read-only enforcement)
- Single statement validation (no multi-statement attacks)
- Comment stripping (prevent SQL injection via comments)
- Row cap injection (LIMIT for PostgreSQL, TOP for SQL Server)
- Structured error codes for clear error handling
- Dialect-aware SQL manipulation

Structured Error Codes:
- READ_ONLY_VIOLATION: Non-SELECT statement detected
- VALIDATION_FAILED: Query failed validation checks
- TIMEOUT: Query execution exceeded timeout
- ROWCAP_ENFORCED: Row limit was injected or clamped
- INVALID_SYNTAX: SQL syntax error detected
"""

import re
import logging
from typing import Tuple, Optional, Literal
from dataclasses import dataclass
from enum import Enum

from mcp_server.config import config

logger = logging.getLogger(__name__)


class ValidationErrorCode(str, Enum):
    """Structured error codes for query validation."""
    READ_ONLY_VIOLATION = "READ_ONLY_VIOLATION"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    TIMEOUT = "TIMEOUT"
    ROWCAP_ENFORCED = "ROWCAP_ENFORCED"
    INVALID_SYNTAX = "INVALID_SYNTAX"
    MULTI_STATEMENT = "MULTI_STATEMENT"
    EMPTY_QUERY = "EMPTY_QUERY"


@dataclass
class ValidationResult:
    """Result of query validation."""
    valid: bool
    query: Optional[str] = None  # Modified query with caps injected
    error_code: Optional[ValidationErrorCode] = None
    error_message: Optional[str] = None
    row_cap_applied: bool = False
    original_limit: Optional[int] = None


class QueryValidator:
    """
    SQL query validator with safety checks and row cap injection.
    
    This validator ensures all queries are:
    1. Read-only (SELECT or WITH...SELECT only)
    2. Single statement (no semicolons except in strings)
    3. Free of dangerous patterns
    4. Bounded by row limits
    """
    
    # Dangerous SQL keywords that indicate write operations
    WRITE_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
        'EXEC', 'EXECUTE', 'CALL', 'DECLARE', 'SET'
    }
    
    # Allowed statement types (read-only)
    ALLOWED_STATEMENTS = {'SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'EXPLAIN'}
    
    def __init__(self, dialect: Literal["postgres", "mssql"] = "postgres", max_rows: int = 1000):
        """
        Initialize query validator.
        
        Args:
            dialect: Database dialect (postgres or mssql)
            max_rows: Maximum rows to return (default: 1000)
        """
        self.dialect = dialect
        self.max_rows = max_rows
        logger.info(f"QueryValidator initialized: dialect={dialect}, max_rows={max_rows}")
    
    def validate_and_cap(self, query: str, requested_limit: Optional[int] = None) -> ValidationResult:
        """
        Validate query and inject row caps.
        
        This is the main entry point for query validation. It performs:
        1. Basic validation (empty, comments, multi-statement)
        2. Read-only enforcement (SELECT/WITH only)
        3. Row cap injection or clamping
        
        Args:
            query: SQL query to validate
            requested_limit: Optional limit requested by caller
        
        Returns:
            ValidationResult with validated query or error details
        """
        # Step 1: Strip comments and whitespace
        cleaned_query = self._strip_comments(query)

        # Step 1b: Normalize obviously invalid aggregate forms such as COUNT(DISTINCT *)
        # to a portable equivalent COUNT(*). This prevents dialect-specific syntax
        # errors in Postgres while preserving the intent of "row counting" queries.
        fixed_query = self._sanitize_distinct_star(cleaned_query)
        
        # Step 2: Basic validation
        validation = self._basic_validation(fixed_query)
        if not validation.valid:
            return validation
        
        # Step 3: Read-only enforcement
        validation = self._enforce_read_only(fixed_query)
        if not validation.valid:
            return validation
        
        # Step 4: Inject or clamp row caps
        validation = self._inject_row_cap(fixed_query, requested_limit)
        
        return validation

    def _sanitize_distinct_star(self, query: str) -> str:
        """
        Replace invalid COUNT(DISTINCT *) constructs with COUNT(*).

        Some upstream components (or LLM outputs) may generate COUNT(DISTINCT *)
        which is not valid SQL in Postgres or SQL Server. In practice these
        queries are used for simple cardinality checks, so COUNT(*) is a safe,
        portable fallback.
        """
        if not query or "distinct" not in query.lower():
            return query

        pattern = re.compile(r"COUNT\s*\(\s*DISTINCT\s+\*\s*\)", flags=re.IGNORECASE)
        if not pattern.search(query):
            return query

        logger.warning("Normalizing invalid COUNT(DISTINCT *) to COUNT(*) for safer execution")
        return pattern.sub("COUNT(*)", query)
    
    def _strip_comments(self, query: str) -> str:
        """
        Strip SQL comments from query.
        
        Removes:
        - Single-line comments (-- comment)
        - Multi-line comments (/* comment */)
        
        Args:
            query: SQL query with potential comments
        
        Returns:
            Query with comments removed
        """
        # Remove single-line comments (-- comment)
        query = re.sub(r'--[^\n]*', '', query)
        
        # Remove multi-line comments (/* comment */)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        return query.strip()
    
    def _basic_validation(self, query: str) -> ValidationResult:
        """
        Perform basic query validation.
        
        Checks:
        - Query is not empty
        - Query is a single statement (no semicolons except in strings)
        
        Args:
            query: Cleaned SQL query
        
        Returns:
            ValidationResult indicating success or failure
        """
        # Check for empty query
        if not query or not query.strip():
            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.EMPTY_QUERY,
                error_message="Query cannot be empty"
            )
        
        # Check for multiple statements (semicolons outside of strings)
        # This is a simplified check - a full parser would be more robust
        if self._has_multiple_statements(query):
            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.MULTI_STATEMENT,
                error_message="Multiple statements not allowed. Only single SELECT queries are permitted."
            )
        
        return ValidationResult(valid=True, query=query)
    
    def _has_multiple_statements(self, query: str) -> bool:
        """
        Check if query contains multiple statements.
        
        This is a simplified check that looks for semicolons outside of strings.
        A production system would use a proper SQL parser.
        
        Args:
            query: SQL query to check
        
        Returns:
            True if multiple statements detected
        """
        # Remove string literals to avoid false positives
        # This regex removes single-quoted strings
        query_no_strings = re.sub(r"'[^']*'", '', query)
        
        # Check for semicolons (statement separators)
        # Allow trailing semicolon but not internal ones
        semicolons = [i for i, c in enumerate(query_no_strings) if c == ';']
        
        if not semicolons:
            return False
        
        # Allow single trailing semicolon
        if len(semicolons) == 1 and semicolons[0] == len(query_no_strings.strip()) - 1:
            return False
        
        return True
    
    def _enforce_read_only(self, query: str) -> ValidationResult:
        """
        Enforce read-only query execution.
        
        Only SELECT and WITH...SELECT statements are allowed.
        All write operations (INSERT, UPDATE, DELETE, etc.) are rejected.
        
        Args:
            query: SQL query to validate
        
        Returns:
            ValidationResult indicating success or failure
        """
        # Get first keyword (statement type)
        first_keyword = self._get_first_keyword(query)
        
        if not first_keyword:
            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.INVALID_SYNTAX,
                error_message="Could not determine query type"
            )
        
        # Check if it's an allowed statement type
        if first_keyword not in self.ALLOWED_STATEMENTS:
            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.READ_ONLY_VIOLATION,
                error_message=f"Only SELECT queries are allowed. Found: {first_keyword}"
            )
        
        # Check for dangerous keywords anywhere in the query
        query_upper = query.upper()
        for keyword in self.WRITE_KEYWORDS:
            # Use word boundaries to avoid false positives (e.g., "INSERTED_AT" column)
            if re.search(rf'\b{keyword}\b', query_upper):
                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.READ_ONLY_VIOLATION,
                    error_message=f"Write operation not allowed: {keyword}"
                )
        
        return ValidationResult(valid=True, query=query)
    
    def _get_first_keyword(self, query: str) -> Optional[str]:
        """
        Extract the first SQL keyword from query.
        
        Args:
            query: SQL query
        
        Returns:
            First keyword in uppercase, or None if not found
        """
        # Match first word (alphanumeric)
        match = re.match(r'\s*(\w+)', query, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None
    
    def _inject_row_cap(self, query: str, requested_limit: Optional[int] = None) -> ValidationResult:
        """
        Inject or clamp row limits in query.
        
        Behavior:
        - If query has no LIMIT/TOP: inject max_rows
        - If query has LIMIT/TOP > max_rows: clamp to max_rows
        - If query has LIMIT/TOP <= max_rows: keep as-is
        - If requested_limit provided: use min(requested_limit, max_rows)
        
        Args:
            query: SQL query to modify
            requested_limit: Optional limit requested by caller
        
        Returns:
            ValidationResult with modified query and metadata
        """
        # Aggregate safety: do not cap pure aggregate-only queries
        try:
            if self._is_pure_aggregate_select(query):
                logger.info("Skipping row cap for pure aggregate query")
                return ValidationResult(valid=True, query=query, row_cap_applied=False)
        except Exception:
            # On parser errors, fall back to standard behavior
            pass
        # Determine effective limit
        effective_limit = self.max_rows
        if requested_limit is not None:
            effective_limit = min(requested_limit, self.max_rows)
        
        if self.dialect == "postgres":
            return self._inject_postgres_limit(query, effective_limit)
        elif self.dialect == "mssql":
            return self._inject_mssql_top(query, effective_limit)
        else:
            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.VALIDATION_FAILED,
                error_message=f"Unsupported dialect: {self.dialect}"
            )

    def _is_pure_aggregate_select(self, query: str) -> bool:
        """
        Heuristically detect if the SELECT is aggregate-only (no non-aggregated columns, no GROUP BY).
        Safe to skip row caps in this case.
        """
        q = query.strip()
        # Quick checks
        if not re.match(r"^\s*SELECT\b", q, re.IGNORECASE):
            return False
        # If GROUP BY is present, it's not pure aggregate-only (risk of truncation changing counts)
        if re.search(r"\bGROUP\s+BY\b", q, re.IGNORECASE):
            return False
        # Extract SELECT list up to FROM (best-effort, not full parser)
        upper = q.upper()
        if " FROM " not in upper:
            return False
        select_part = q[0: upper.index(" FROM ")]
        # Remove SELECT and DISTINCT
        select_list = re.sub(r"^\s*SELECT\s+", "", select_part, flags=re.IGNORECASE)
        select_list = re.sub(r"^\s*DISTINCT\s+", "", select_list, flags=re.IGNORECASE)
        # Remove whitespace
        select_list_stripped = select_list.strip()
        # Common aggregate-only patterns
        agg_funcs = ["COUNT(", "SUM(", "MIN(", "MAX(", "AVG("]
        # If select list contains only aggregates (possibly with aliases and commas)
        # Tokenize by commas at top level (best-effort)
        parts = [p.strip() for p in select_list_stripped.split(',') if p.strip()]
        if not parts:
            return False
        for part in parts:
            # Allow optional CAST/CONVERT wrappers around aggregates
            part_upper = part.upper()
            # Strip aliases using AS or space alias
            part_upper = re.sub(r"\s+AS\s+\w+$", "", part_upper)
            part_upper = re.sub(r"\s+\w+$", "", part_upper)
            # Accept forms like COUNT(*), COUNT(1), SUM(col), AVG(CAST(col AS ...))
            is_agg = any(func in part_upper for func in agg_funcs)
            if not is_agg:
                return False
        return True
    
    def _inject_postgres_limit(self, query: str, limit: int) -> ValidationResult:
        """
        Inject or clamp LIMIT clause for PostgreSQL.
        
        Args:
            query: SQL query
            limit: Row limit to enforce
        
        Returns:
            ValidationResult with modified query
        """
        # Normalize occasional SQL Server–style syntax that may appear when
        # upstream agents generate MSSQL-flavoured SQL (TOP / [dbo].[table]):
        #
        # 1) Strip SELECT TOP n and treat it as a user-specified limit
        # 2) Convert [schema].[name] brackets to Postgres-style quotes
        top_match = re.search(r'\bSELECT\s+TOP\s+(\d+)\s+', query, re.IGNORECASE)
        if top_match:
            try:
                top_limit = int(top_match.group(1))
                if top_limit < limit:
                    limit = top_limit
            except Exception:
                top_limit = None  # best-effort; fall back to existing limit
            # Remove the TOP clause from the SELECT
            query = re.sub(
                r'\bSELECT\s+TOP\s+\d+\s+',
                'SELECT ',
                query,
                flags=re.IGNORECASE,
            )
            logger.info(
                "Normalized SQL Server TOP clause for Postgres (TOP %s)",
                top_match.group(1),
            )

        if "[" in query or "]" in query:
            # Convert SQL Server bracket identifiers to unquoted Postgres identifiers.
            # Example: public.[order_details] -> public.order_details
            query = re.sub(r'\[([^\]]+)\]', r'\1', query)
            logger.info("Normalized SQL Server bracket identifiers to Postgres style")

        # Map common MSSQL schema prefixes to the configured Postgres schema
        # After bracket normalization, patterns like dbo.order_details are easy to match.
        default_schema = getattr(config, "postgres_schema", "public")
        query = re.sub(
            r'\bdbo\.',
            f'{default_schema}.',
            query,
            flags=re.IGNORECASE,
        )

        # Check if query already has LIMIT (after any normalization)
        limit_match = re.search(r'\bLIMIT\s+(\d+)', query, re.IGNORECASE)
        
        if limit_match:
            # Query has existing LIMIT
            existing_limit = int(limit_match.group(1))
            
            if existing_limit > limit:
                # Clamp to max limit
                modified_query = re.sub(
                    r'\bLIMIT\s+\d+',
                    f'LIMIT {limit}',
                    query,
                    flags=re.IGNORECASE
                )
                logger.info(f"Clamped LIMIT from {existing_limit} to {limit}")
                return ValidationResult(
                    valid=True,
                    query=modified_query,
                    row_cap_applied=True,
                    original_limit=existing_limit
                )
            else:
                # Keep existing limit
                return ValidationResult(
                    valid=True,
                    query=query,
                    row_cap_applied=False,
                    original_limit=existing_limit
                )
        else:
            # No LIMIT - inject one
            # Handle queries with/without semicolon
            query_stripped = query.rstrip().rstrip(';')
            modified_query = f"{query_stripped} LIMIT {limit}"
            
            logger.info(f"Injected LIMIT {limit}")
            return ValidationResult(
                valid=True,
                query=modified_query,
                row_cap_applied=True,
                original_limit=None
            )
    
    def _inject_mssql_top(self, query: str, limit: int) -> ValidationResult:
        """
        Inject or clamp TOP clause for SQL Server.
        
        Important: In SQL Server, TOP must come after DISTINCT if DISTINCT is present.
        Valid: SELECT DISTINCT TOP n ... (not SELECT TOP n DISTINCT ...)
        
        This method validates that the query has proper structure (columns and FROM clause)
        before injecting TOP to avoid creating malformed SQL.
        
        Args:
            query: SQL query
            limit: Row limit to enforce
        
        Returns:
            ValidationResult with modified query
        """
        # Check if query already has TOP
        top_match = re.search(r'\bSELECT\s+TOP\s+(\d+)', query, re.IGNORECASE)
        
        if top_match:
            # Query has existing TOP
            existing_limit = int(top_match.group(1))
            
            if existing_limit > limit:
                # Clamp to max limit
                modified_query = re.sub(
                    r'\bSELECT\s+TOP\s+\d+',
                    f'SELECT TOP {limit}',
                    query,
                    flags=re.IGNORECASE
                )
                logger.info(f"Clamped TOP from {existing_limit} to {limit}")
                return ValidationResult(
                    valid=True,
                    query=modified_query,
                    row_cap_applied=True,
                    original_limit=existing_limit
                )
            else:
                # Keep existing TOP
                return ValidationResult(
                    valid=True,
                    query=query,
                    row_cap_applied=False,
                    original_limit=existing_limit
                )
        else:
            # No TOP - inject one, but first validate query structure
            # Check if query has enough structure to be valid after TOP injection
            if not self._is_valid_select_structure(query):
                logger.warning(f"Skipping TOP injection for incomplete query: {query[:50]}...")
                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_SYNTAX,
                    error_message="Query structure is incomplete or invalid for TOP injection"
                )
            
            # Check if query has SELECT DISTINCT (TOP must come after DISTINCT in SQL Server)
            distinct_match = re.search(r'\bSELECT\s+DISTINCT\b', query, re.IGNORECASE)
            
            if distinct_match:
                # SELECT DISTINCT exists - inject TOP after DISTINCT
                modified_query = re.sub(
                    r'\bSELECT\s+DISTINCT\b',
                    f'SELECT DISTINCT TOP {limit}',
                    query,
                    count=1,
                    flags=re.IGNORECASE
                )
                logger.info(f"Injected TOP {limit} after DISTINCT")
            else:
                # No DISTINCT - inject TOP directly after SELECT
                modified_query = re.sub(
                    r'\bSELECT\b',
                    f'SELECT TOP {limit}',
                    query,
                    count=1,
                    flags=re.IGNORECASE
                )
                logger.info(f"Injected TOP {limit}")
            
            return ValidationResult(
                valid=True,
                query=modified_query,
                row_cap_applied=True,
                original_limit=None
            )
    
    def _is_valid_select_structure(self, query: str) -> bool:
        """
        Check if a SELECT query has valid structure for TOP injection.
        
        A valid query should have:
        1. At least one column (not just "SELECT")
        2. Can include asterisk, column names, expressions, or functions
        
        Args:
            query: SQL query to validate
        
        Returns:
            True if query structure is valid for TOP injection
        """
        query_stripped = query.strip()
        
        # Check if query is just "SELECT" or "SELECT DISTINCT"
        select_only_pattern = r'^\s*SELECT\s*$'
        select_distinct_only_pattern = r'^\s*SELECT\s+DISTINCT\s*$'
        
        if re.match(select_only_pattern, query_stripped, re.IGNORECASE):
            logger.error(f"🚨 INCOMPLETE QUERY DETECTED: Query contains only 'SELECT' keyword")
            logger.error(f"📝 This indicates a problem in the SQL generation process")
            logger.error(f"🔍 Check agent workflow for incomplete SQL generation")
            return False
        
        if re.match(select_distinct_only_pattern, query_stripped, re.IGNORECASE):
            logger.error(f"🚨 INCOMPLETE QUERY DETECTED: Query contains only 'SELECT DISTINCT' keywords")
            logger.error(f"📝 This indicates a problem in the SQL generation process")
            logger.error(f"🔍 Check agent workflow for incomplete SQL generation")
            return False
        
        # Check if query has valid content after SELECT [DISTINCT]
        # Look for common patterns that indicate a valid query structure:
        
        # 1. SELECT followed by asterisk (SELECT *)
        if re.search(r'\bSELECT\s+\*', query, re.IGNORECASE):
            return True
            
        # 2. SELECT DISTINCT followed by asterisk or columns
        if re.search(r'\bSELECT\s+DISTINCT\s+(\*|\w+)', query, re.IGNORECASE):
            return True
        
        # 3. SELECT followed by word characters (column names, functions)
        if re.search(r'\bSELECT\s+\w+', query, re.IGNORECASE):
            return True
            
        # 4. SELECT followed by numbers (SELECT 1, SELECT 123, etc.)
        if re.search(r'\bSELECT\s+\d+', query, re.IGNORECASE):
            return True
            
        # 5. SELECT followed by expressions with parentheses (functions, etc.)
        if re.search(r'\bSELECT\s+\w+\s*\(', query, re.IGNORECASE):
            return True
        
        # If we can't determine structure, log what we found for debugging
        logger.warning(f"🔍 QUERY STRUCTURE UNKNOWN: Cannot determine if query is valid for TOP injection")
        logger.warning(f"📝 Query: {query[:100]}...")
        logger.warning(f"🔍 This may indicate an unusual but valid query pattern")
        
        # Err on the side of caution
        return False


def validate_query(query: str, dialect: str = "postgres", max_rows: int = 1000, 
                   requested_limit: Optional[int] = None) -> ValidationResult:
    """
    Convenience function for query validation.
    
    Args:
        query: SQL query to validate
        dialect: Database dialect (postgres or mssql)
        max_rows: Maximum rows to return
        requested_limit: Optional limit requested by caller
    
    Returns:
        ValidationResult with validated query or error details
    """
    validator = QueryValidator(dialect=dialect, max_rows=max_rows)
    return validator.validate_and_cap(query, requested_limit)
