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
        
        # Step 2: Basic validation
        validation = self._basic_validation(cleaned_query)
        if not validation.valid:
            return validation
        
        # Step 3: Read-only enforcement
        validation = self._enforce_read_only(cleaned_query)
        if not validation.valid:
            return validation
        
        # Step 4: Inject or clamp row caps
        validation = self._inject_row_cap(cleaned_query, requested_limit)
        
        return validation
    
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
    
    def _inject_postgres_limit(self, query: str, limit: int) -> ValidationResult:
        """
        Inject or clamp LIMIT clause for PostgreSQL.
        
        Args:
            query: SQL query
            limit: Row limit to enforce
        
        Returns:
            ValidationResult with modified query
        """
        # Check if query already has LIMIT
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
            # No TOP - inject one
            # Find SELECT keyword and inject TOP after it
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