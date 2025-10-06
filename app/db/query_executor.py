"""
SQL Query Executor - Safe Query Execution with Timeout & Result Formatting

This module executes validated SQL queries with:
- Timeout enforcement
- Result size limiting
- Structured error handling
- Result formatting for LLM consumption

Design Principles (from ADRs):
-------------------------------
1. **Separation of Concerns**: Validation happens before execution
2. **Timeout Enforcement**: Prevent long-running queries
3. **Result Formatting**: Structure results for LLM consumption
4. **Error Handling**: Graceful degradation with informative errors

Usage:
------
    from app.db.query_executor import QueryExecutor, execute_safe_query
    
    # Basic execution
    result = execute_safe_query(db_client, "SELECT * FROM customers LIMIT 10")
    if result.success:
        print(f"Rows: {result.row_count}")
        print(result.formatted_result)
    else:
        print(f"Error: {result.error}")
    
    # Custom executor with different settings
    executor = QueryExecutor(max_rows=500, timeout_seconds=60)
    result = executor.execute(db_client, "SELECT * FROM large_table")
"""

import logging
import time
from typing import Optional, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from app.db.query_validator import QueryValidator, ValidationResult

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Query execution status."""
    SUCCESS = "success"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"


@dataclass
class QueryResult:
    """Result of query execution."""
    success: bool
    status: ExecutionStatus
    columns: Optional[List[str]] = None
    rows: Optional[List[List[Any]]] = None
    row_count: int = 0
    execution_time_ms: float = 0.0
    formatted_result: Optional[str] = None
    error: Optional[str] = None
    validation_warnings: List[str] = None
    
    def __post_init__(self):
        if self.validation_warnings is None:
            self.validation_warnings = []


class QueryExecutor:
    """
    SQL Query Executor with safety checks and result formatting.
    
    This executor validates queries before execution and formats results
    for LLM consumption. It enforces timeouts and row limits.
    """
    
    def __init__(
        self,
        max_rows: int = 1000,
        timeout_seconds: int = 30,
        enforce_row_limit: bool = True,
        format_results: bool = True
    ):
        """
        Initialize query executor.
        
        Args:
            max_rows: Maximum number of rows to return (default: 1000)
            timeout_seconds: Maximum query execution time (default: 30)
            enforce_row_limit: Whether to enforce row limits (default: True)
            format_results: Whether to format results as text (default: True)
        """
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self.enforce_row_limit = enforce_row_limit
        self.format_results = format_results
        
        # Initialize validator with same settings
        self.validator = QueryValidator(
            max_rows=max_rows,
            timeout_seconds=timeout_seconds,
            enforce_row_limit=enforce_row_limit
        )
    
    def execute(
        self,
        db_client,
        query: str,
        params: Optional[dict] = None,
        conn: Optional[str] = None
    ) -> QueryResult:
        """
        Execute a SQL query safely with validation and timeout.
        
        Args:
            db_client: DatabaseClient instance to execute query
            query: SQL query to execute
            params: Query parameters (optional)
            conn: Connection name for proxy mode (optional)
        
        Returns:
            QueryResult with execution status and results
        """
        start_time = time.time()
        
        # Step 1: Validate query
        validation = self.validator.validate(query)
        
        if not validation.is_valid:
            logger.warning(f"Query validation failed: {validation.error}")
            return QueryResult(
                success=False,
                status=ExecutionStatus.VALIDATION_FAILED,
                error=validation.error,
                execution_time_ms=0.0
            )
        
        # Use sanitized query
        sanitized_query = validation.sanitized_query
        logger.info(f"Executing validated query: {sanitized_query[:100]}...")
        
        # Step 2: Execute query with timeout
        try:
            columns, rows = db_client.query(
                sanitized_query,
                params=params,
                conn=conn,
                limit=self.max_rows,
                timeout_s=self.timeout_seconds
            )
            
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Step 3: Check if results are empty
            if not rows:
                logger.info("Query executed successfully but returned no rows")
                return QueryResult(
                    success=True,
                    status=ExecutionStatus.EMPTY_RESULT,
                    columns=columns,
                    rows=[],
                    row_count=0,
                    execution_time_ms=execution_time,
                    formatted_result="Query executed successfully but returned no rows.",
                    validation_warnings=validation.warnings
                )
            
            # Step 4: Format results
            formatted = None
            if self.format_results:
                formatted = self._format_results(columns, rows)
            
            logger.info(f"Query executed successfully: {len(rows)} rows in {execution_time:.2f}ms")
            
            return QueryResult(
                success=True,
                status=ExecutionStatus.SUCCESS,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time,
                formatted_result=formatted,
                validation_warnings=validation.warnings
            )
            
        except TimeoutError as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query timeout after {execution_time:.2f}ms: {e}")
            return QueryResult(
                success=False,
                status=ExecutionStatus.TIMEOUT,
                error=f"Query timeout after {self.timeout_seconds}s",
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query execution failed after {execution_time:.2f}ms: {e}")
            return QueryResult(
                success=False,
                status=ExecutionStatus.EXECUTION_FAILED,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def _format_results(self, columns: List[str], rows: List[List[Any]]) -> str:
        """
        Format query results as human-readable text for LLM consumption.
        
        Args:
            columns: List of column names
            rows: List of rows (each row is a list of values)
        
        Returns:
            Formatted string representation of results
        """
        if not rows:
            return "No results found."
        
        # Build header
        lines = []
        lines.append(f"Query returned {len(rows)} row(s):")
        lines.append("")
        
        # Calculate column widths for alignment
        col_widths = [len(col) for col in columns]
        for row in rows[:100]:  # Only check first 100 rows for width
            for i, val in enumerate(row):
                val_str = str(val) if val is not None else "NULL"
                col_widths[i] = max(col_widths[i], len(val_str))
        
        # Limit column width to 50 characters
        col_widths = [min(w, 50) for w in col_widths]
        
        # Build header row
        header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(columns))
        lines.append(header)
        lines.append("-" * len(header))
        
        # Build data rows (limit to first 100 for display)
        display_rows = rows[:100]
        for row in display_rows:
            row_str = " | ".join(
                str(val).ljust(col_widths[i])[:col_widths[i]] if val is not None else "NULL".ljust(col_widths[i])
                for i, val in enumerate(row)
            )
            lines.append(row_str)
        
        # Add truncation notice if needed
        if len(rows) > 100:
            lines.append("")
            lines.append(f"... and {len(rows) - 100} more row(s)")
        
        return "\n".join(lines)


# Convenience function for simple execution
def execute_safe_query(
    db_client,
    query: str,
    params: Optional[dict] = None,
    conn: Optional[str] = None,
    max_rows: int = 1000,
    timeout_seconds: int = 30
) -> QueryResult:
    """
    Execute a SQL query safely with default settings.
    
    This is a convenience function for simple query execution.
    For more control, use QueryExecutor class directly.
    
    Args:
        db_client: DatabaseClient instance
        query: SQL query to execute
        params: Query parameters (optional)
        conn: Connection name for proxy mode (optional)
        max_rows: Maximum rows to return (default: 1000)
        timeout_seconds: Maximum execution time (default: 30)
    
    Returns:
        QueryResult with execution status and results
    
    Example:
        >>> from app.db.client import DatabaseClient
        >>> client = DatabaseClient()
        >>> result = execute_safe_query(client, "SELECT * FROM customers LIMIT 10")
        >>> if result.success:
        ...     print(result.formatted_result)
    """
    executor = QueryExecutor(
        max_rows=max_rows,
        timeout_seconds=timeout_seconds
    )
    return executor.execute(db_client, query, params, conn)