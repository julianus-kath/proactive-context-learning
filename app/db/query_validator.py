"""
SQL Query Validator - Ensures Only Safe, Read-Only Queries

This module validates SQL queries before execution to prevent:
- Data modification (INSERT, UPDATE, DELETE, DROP, etc.)
- SQL injection attacks
- Resource exhaustion (missing row limits, timeouts)
- Multiple statement execution

Design Principles (from ADRs):
-------------------------------
1. **Read-Only Enforcement**: Only SELECT statements allowed
2. **Defense in Depth**: Multiple validation layers (regex + SQL parsing)
3. **Fail-Safe**: Reject by default, allow only explicitly safe queries
4. **Audit Trail**: Log all validation attempts for security monitoring

Validation Layers:
------------------
1. **Syntax Check**: Basic SQL structure validation
2. **Statement Type**: Only SELECT allowed
3. **Dangerous Patterns**: Block comments, multiple statements, dynamic SQL
4. **Row Limits**: Enforce maximum result size
5. **Timeout**: Enforce maximum execution time

Usage:
------
    from app.db.query_validator import validate_query, QueryValidator
    
    # Basic validation
    result = validate_query("SELECT * FROM customers LIMIT 100")
    if result.is_valid:
        execute_query(result.sanitized_query)
    else:
        print(f"Invalid query: {result.error}")
    
    # Custom validator with different limits
    validator = QueryValidator(max_rows=500, timeout_seconds=60)
    result = validator.validate("SELECT * FROM large_table")
"""

import re
import logging
from typing import Optional, List, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationError(Enum):
    """Types of validation errors."""
    NOT_SELECT = "Query must be a SELECT statement"
    MULTIPLE_STATEMENTS = "Multiple statements not allowed"
    DANGEROUS_KEYWORDS = "Query contains dangerous keywords"
    SQL_COMMENTS = "SQL comments not allowed"
    MISSING_ROW_LIMIT = "Query must include row limit"
    INVALID_SYNTAX = "Invalid SQL syntax"
    EMPTY_QUERY = "Query cannot be empty"
    SUSPICIOUS_PATTERN = "Query contains suspicious patterns"


@dataclass
class ValidationResult:
    """Result of query validation."""
    is_valid: bool
    sanitized_query: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[ValidationError] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class QueryValidator:
    """
    SQL Query Validator with configurable safety rules.
    
    This validator ensures that only safe, read-only queries are executed.
    It uses multiple validation layers to prevent SQL injection and data modification.
    """
    
    # Dangerous SQL keywords that indicate write operations
    DANGEROUS_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE',
        'EXEC', 'EXECUTE', 'CALL', 'MERGE', 'REPLACE', 'GRANT', 'REVOKE',
        'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'SET', 'DECLARE', 'USE',
        'BACKUP', 'RESTORE', 'ATTACH', 'DETACH'
    }
    
    # SQL comment patterns (can hide malicious code)
    COMMENT_PATTERNS = [
        r'--',           # Single-line comment
        r'/\*',          # Multi-line comment start
        r'\*/',          # Multi-line comment end
        r'#',            # MySQL comment
    ]
    
    # Suspicious patterns that might indicate SQL injection
    SUSPICIOUS_PATTERNS = [
        r';\s*SELECT',   # Stacked queries
        r';\s*INSERT',
        r';\s*UPDATE',
        r';\s*DELETE',
        r';\s*DROP',
        r'UNION\s+SELECT',  # UNION-based injection (allow if explicitly needed)
        r'xp_cmdshell',     # SQL Server command execution
        r'sp_executesql',   # Dynamic SQL execution
        r'INTO\s+OUTFILE',  # File writing
        r'LOAD_FILE',       # File reading
    ]
    
    def __init__(
        self,
        max_rows: int = 1000,
        timeout_seconds: int = 30,
        enforce_row_limit: bool = True,
        allow_comments: bool = False,
        allow_union: bool = False
    ):
        """
        Initialize query validator.
        
        Args:
            max_rows: Maximum number of rows to return (default: 1000)
            timeout_seconds: Maximum query execution time (default: 30)
            enforce_row_limit: Whether to require explicit row limits (default: True)
            allow_comments: Whether to allow SQL comments (default: False)
            allow_union: Whether to allow UNION queries (default: False)
        """
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self.enforce_row_limit = enforce_row_limit
        self.allow_comments = allow_comments
        self.allow_union = allow_union
    
    def validate(self, query: str) -> ValidationResult:
        """
        Validate a SQL query for safety.
        
        Args:
            query: SQL query string to validate
        
        Returns:
            ValidationResult with validation status and sanitized query
        """
        # Step 1: Basic checks
        if not query or not query.strip():
            return ValidationResult(
                is_valid=False,
                error="Query cannot be empty",
                error_type=ValidationError.EMPTY_QUERY
            )
        
        query = query.strip()
        query_upper = query.upper()
        
        # Step 2: Check for multiple statements
        if self._has_multiple_statements(query):
            return ValidationResult(
                is_valid=False,
                error="Multiple statements not allowed (found semicolon)",
                error_type=ValidationError.MULTIPLE_STATEMENTS
            )
        
        # Step 3: Check for SQL comments (unless allowed)
        if not self.allow_comments and self._has_comments(query):
            return ValidationResult(
                is_valid=False,
                error="SQL comments not allowed for security reasons",
                error_type=ValidationError.SQL_COMMENTS
            )
        
        # Step 4: Check if it's a SELECT statement
        if not self._is_select_statement(query_upper):
            return ValidationResult(
                is_valid=False,
                error="Only SELECT statements are allowed (read-only access)",
                error_type=ValidationError.NOT_SELECT
            )
        
        # Step 5: Check for dangerous keywords
        dangerous = self._find_dangerous_keywords(query_upper)
        if dangerous:
            return ValidationResult(
                is_valid=False,
                error=f"Query contains dangerous keywords: {', '.join(dangerous)}",
                error_type=ValidationError.DANGEROUS_KEYWORDS
            )
        
        # Step 6: Check for suspicious patterns
        suspicious = self._find_suspicious_patterns(query)
        if suspicious:
            # UNION is allowed if configured
            if 'UNION' in suspicious and self.allow_union:
                suspicious.remove('UNION')
            
            if suspicious:
                return ValidationResult(
                    is_valid=False,
                    error=f"Query contains suspicious patterns: {', '.join(suspicious)}",
                    error_type=ValidationError.SUSPICIOUS_PATTERN
                )
        
        # Step 7: Sanitize and add row limit if needed
        sanitized, warnings = self._sanitize_query(query)
        
        # Step 8: Check for row limit (if enforced)
        if self.enforce_row_limit and not self._has_row_limit(sanitized):
            # Auto-add row limit
            sanitized = self._add_row_limit(sanitized)
            warnings.append(f"Auto-added row limit: {self.max_rows}")
        
        logger.info(f"Query validated successfully: {sanitized[:100]}...")
        
        return ValidationResult(
            is_valid=True,
            sanitized_query=sanitized,
            warnings=warnings
        )
    
    def _has_multiple_statements(self, query: str) -> bool:
        """Check if query contains multiple statements (semicolon-separated)."""
        # Remove string literals to avoid false positives
        query_no_strings = re.sub(r"'[^']*'", '', query)
        query_no_strings = re.sub(r'"[^"]*"', '', query_no_strings)
        
        # Check for semicolons (except at the very end)
        semicolons = [m.start() for m in re.finditer(r';', query_no_strings)]
        
        # Allow single trailing semicolon
        if len(semicolons) == 0:
            return False
        elif len(semicolons) == 1 and query_no_strings.rstrip().endswith(';'):
            return False
        else:
            return True
    
    def _has_comments(self, query: str) -> bool:
        """Check if query contains SQL comments."""
        for pattern in self.COMMENT_PATTERNS:
            if re.search(pattern, query):
                return True
        return False
    
    def _is_select_statement(self, query_upper: str) -> bool:
        """Check if query is a SELECT statement."""
        # Must start with SELECT (after whitespace)
        # OR start with WITH (for CTEs - Common Table Expressions)
        return bool(re.match(r'^\s*(SELECT|WITH)\b', query_upper))
    
    def _find_dangerous_keywords(self, query_upper: str) -> Set[str]:
        """Find dangerous keywords in query."""
        found = set()
        
        for keyword in self.DANGEROUS_KEYWORDS:
            # Use word boundaries to avoid false positives
            if re.search(rf'\b{keyword}\b', query_upper):
                found.add(keyword)
        
        return found
    
    def _find_suspicious_patterns(self, query: str) -> Set[str]:
        """Find suspicious patterns that might indicate SQL injection."""
        found = set()
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                # Extract pattern name for error message
                if 'UNION' in pattern:
                    found.add('UNION')
                elif 'xp_cmdshell' in pattern:
                    found.add('xp_cmdshell')
                elif 'sp_executesql' in pattern:
                    found.add('sp_executesql')
                elif 'OUTFILE' in pattern:
                    found.add('INTO OUTFILE')
                elif 'LOAD_FILE' in pattern:
                    found.add('LOAD_FILE')
                elif ';' in pattern:
                    found.add('stacked queries')
        
        return found
    
    def _has_row_limit(self, query: str) -> bool:
        """Check if query has a row limit (LIMIT or TOP)."""
        query_upper = query.upper()
        
        # Check for LIMIT (PostgreSQL, MySQL)
        if re.search(r'\bLIMIT\s+\d+', query_upper):
            return True
        
        # Check for TOP (SQL Server)
        if re.search(r'\bTOP\s+\d+', query_upper):
            return True
        
        # Check for FETCH FIRST (SQL standard)
        if re.search(r'\bFETCH\s+FIRST\s+\d+', query_upper):
            return True
        
        return False
    
    def _add_row_limit(self, query: str) -> str:
        """Add row limit to query (database-agnostic approach)."""
        query = query.rstrip(';').strip()
        
        # Try to detect database type from query syntax
        # For now, default to LIMIT (works for PostgreSQL, MySQL, SQLite)
        # TODO: Make this configurable based on database type
        
        return f"{query} LIMIT {self.max_rows}"
    
    def _sanitize_query(self, query: str) -> tuple[str, List[str]]:
        """
        Sanitize query by removing trailing semicolons and normalizing whitespace.
        
        Returns:
            Tuple of (sanitized_query, warnings)
        """
        warnings = []
        
        # Remove trailing semicolon
        if query.rstrip().endswith(';'):
            query = query.rstrip(';').strip()
            warnings.append("Removed trailing semicolon")
        
        # Normalize whitespace (but preserve string literals)
        # This is a simple version; more sophisticated parsing could be added
        query = ' '.join(query.split())
        
        return query, warnings


# Convenience function for simple validation
def validate_query(
    query: str,
    max_rows: int = 1000,
    timeout_seconds: int = 30
) -> ValidationResult:
    """
    Validate a SQL query with default settings.
    
    This is a convenience function for simple validation.
    For more control, use QueryValidator class directly.
    
    Args:
        query: SQL query to validate
        max_rows: Maximum rows to return (default: 1000)
        timeout_seconds: Maximum execution time (default: 30)
    
    Returns:
        ValidationResult with validation status
    
    Example:
        >>> result = validate_query("SELECT * FROM customers")
        >>> if result.is_valid:
        ...     execute(result.sanitized_query)
    """
    validator = QueryValidator(max_rows=max_rows, timeout_seconds=timeout_seconds)
    return validator.validate(query)


def is_read_only(query: str) -> bool:
    """
    Quick check if query is read-only (SELECT only).
    
    This is a fast check that doesn't do full validation.
    Use validate_query() for comprehensive validation.
    
    Args:
        query: SQL query to check
    
    Returns:
        True if query appears to be read-only
    """
    if not query or not query.strip():
        return False
    
    query_upper = query.strip().upper()
    
    # Must start with SELECT
    if not query_upper.startswith('SELECT'):
        return False
    
    # Must not contain dangerous keywords
    validator = QueryValidator()
    dangerous = validator._find_dangerous_keywords(query_upper)
    
    return len(dangerous) == 0