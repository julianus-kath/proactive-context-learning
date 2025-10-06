"""
Bounded query execution module - Phase 2: Production-ready query execution.

This module provides the query_bounded tool that combines:
- Query validation (SELECT-only, single statement)
- Row cap injection (LIMIT/TOP)
- Timeout enforcement
- Column redaction
- Structured error responses
- Execution metadata

Response Envelope:
{
    "ok": true/false,
    "rows": [...],
    "columns": [...],
    "row_count": N,
    "execution_time_ms": N,
    "truncated": true/false,
    "redacted_columns": [...],
    "error_code": "...",
    "error_message": "..."
}
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from query_validator import QueryValidator, ValidationResult, ValidationErrorCode
from column_redactor import ColumnRedactor, RedactionConfig

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Structured response envelope for bounded queries."""
    ok: bool
    rows: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False
    redacted_columns: Optional[List[str]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Remove None values for cleaner response
        return {k: v for k, v in result.items() if v is not None}


class BoundedQueryExecutor:
    """
    Bounded query executor with comprehensive safety controls.
    
    This executor ensures all queries are:
    1. Validated (SELECT-only, single statement)
    2. Bounded (row limits enforced)
    3. Timed (execution time tracked)
    4. Safe (sensitive data redacted)
    5. Monitored (structured errors and metadata)
    """
    
    def __init__(self, 
                 dialect: str = "postgres",
                 max_rows: int = 1000,
                 query_timeout: int = 30,
                 enable_redaction: bool = True,
                 redaction_patterns: Optional[List[str]] = None):
        """
        Initialize bounded query executor.
        
        Args:
            dialect: Database dialect (postgres or mssql)
            max_rows: Maximum rows to return
            query_timeout: Query timeout in seconds
            enable_redaction: Whether to enable column redaction
            redaction_patterns: Custom redaction patterns (uses defaults if None)
        """
        self.dialect = dialect
        self.max_rows = max_rows
        self.query_timeout = query_timeout
        
        # Initialize validator
        self.validator = QueryValidator(dialect=dialect, max_rows=max_rows)
        
        # Initialize redactor
        redaction_config = RedactionConfig(
            patterns=redaction_patterns,
            enabled=enable_redaction
        )
        self.redactor = ColumnRedactor(config=redaction_config)
        
        logger.info(f"BoundedQueryExecutor initialized: dialect={dialect}, "
                   f"max_rows={max_rows}, timeout={query_timeout}s, "
                   f"redaction={enable_redaction}")
    
    async def execute_bounded(self,
                            query: str,
                            db_adapter,
                            requested_limit: Optional[int] = None,
                            params: Optional[Dict[str, Any]] = None) -> QueryResponse:
        """
        Execute a bounded query with full safety controls.
        
        This is the main entry point for safe query execution.
        
        Args:
            query: SQL query to execute
            db_adapter: Database adapter instance
            requested_limit: Optional row limit requested by caller
            params: Optional query parameters
        
        Returns:
            QueryResponse with results or error details
        """
        start_time = time.time()
        
        try:
            # Step 1: Validate and inject row caps
            validation = self.validator.validate_and_cap(query, requested_limit)
            
            if not validation.valid:
                return QueryResponse(
                    ok=False,
                    error_code=validation.error_code.value if validation.error_code else "VALIDATION_FAILED",
                    error_message=validation.error_message,
                    execution_time_ms=self._elapsed_ms(start_time)
                )
            
            # Step 2: Execute query with timeout
            try:
                rows = await self._execute_with_timeout(
                    db_adapter,
                    validation.query,
                    params
                )
            except TimeoutError:
                return QueryResponse(
                    ok=False,
                    error_code=ValidationErrorCode.TIMEOUT.value,
                    error_message=f"Query execution exceeded timeout of {self.query_timeout}s",
                    execution_time_ms=self._elapsed_ms(start_time)
                )
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                return QueryResponse(
                    ok=False,
                    error_code="EXECUTION_FAILED",
                    error_message=str(e),
                    execution_time_ms=self._elapsed_ms(start_time)
                )
            
            # Step 3: Extract columns
            columns = list(rows[0].keys()) if rows else []
            
            # Step 4: Redact sensitive columns
            redacted_rows, redacted_columns = self.redactor.redact_rows(rows, columns)
            
            # Step 5: Build response
            execution_time = self._elapsed_ms(start_time)
            
            return QueryResponse(
                ok=True,
                rows=redacted_rows,
                columns=columns,
                row_count=len(redacted_rows),
                execution_time_ms=execution_time,
                truncated=validation.row_cap_applied,
                redacted_columns=list(redacted_columns) if redacted_columns else None,
                metadata={
                    "original_limit": validation.original_limit,
                    "applied_limit": self.max_rows if validation.row_cap_applied else None,
                    "dialect": self.dialect
                }
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in bounded query execution: {e}")
            return QueryResponse(
                ok=False,
                error_code="INTERNAL_ERROR",
                error_message=f"Internal error: {str(e)}",
                execution_time_ms=self._elapsed_ms(start_time)
            )
    
    async def _execute_with_timeout(self,
                                   db_adapter,
                                   query: str,
                                   params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute query with timeout enforcement.
        
        Note: Timeout is enforced at the driver level via connector configuration.
        This method provides a wrapper for future async timeout support.
        
        Args:
            db_adapter: Database adapter instance
            query: SQL query to execute
            params: Optional query parameters
        
        Returns:
            List of row dictionaries
        
        Raises:
            TimeoutError: If query exceeds timeout
            Exception: If query execution fails
        """
        # The actual timeout is enforced by the database connector
        # (configured in db_postgres.py and db_mssql.py)
        # This wrapper allows for future async timeout support
        
        try:
            rows = await db_adapter.fetch(query, params=params)
            return rows
        except Exception as e:
            # Check if it's a timeout error
            error_str = str(e).lower()
            if 'timeout' in error_str or 'timed out' in error_str:
                raise TimeoutError(f"Query execution timed out: {e}")
            raise
    
    def _elapsed_ms(self, start_time: float) -> float:
        """
        Calculate elapsed time in milliseconds.
        
        Args:
            start_time: Start time from time.time()
        
        Returns:
            Elapsed time in milliseconds
        """
        return round((time.time() - start_time) * 1000, 2)


async def execute_bounded_query(query: str,
                               db_adapter,
                               dialect: str = "postgres",
                               max_rows: int = 1000,
                               query_timeout: int = 30,
                               requested_limit: Optional[int] = None,
                               params: Optional[Dict[str, Any]] = None,
                               enable_redaction: bool = True) -> QueryResponse:
    """
    Convenience function for bounded query execution.
    
    Args:
        query: SQL query to execute
        db_adapter: Database adapter instance
        dialect: Database dialect (postgres or mssql)
        max_rows: Maximum rows to return
        query_timeout: Query timeout in seconds
        requested_limit: Optional row limit requested by caller
        params: Optional query parameters
        enable_redaction: Whether to enable column redaction
    
    Returns:
        QueryResponse with results or error details
    """
    executor = BoundedQueryExecutor(
        dialect=dialect,
        max_rows=max_rows,
        query_timeout=query_timeout,
        enable_redaction=enable_redaction
    )
    
    return await executor.execute_bounded(
        query=query,
        db_adapter=db_adapter,
        requested_limit=requested_limit,
        params=params
    )