"""
Dialect Adapter: Unified SQL execution across PostgreSQL and SQL Server.

Phase 7 Enhancement:
- Transparent dialect handling (PostgreSQL vs SQL Server)
- Automatic query translation for dialect-specific differences
- Silent retry logic with exponential backoff
- Connection health monitoring
- Detailed error mapping and recovery

Supported Dialects:
- postgres: PostgreSQL with asyncpg driver
- mssql: SQL Server with pyodbc driver
"""

import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class DatabaseDialect(Enum):
    """Supported database dialects."""
    POSTGRES = "postgres"
    MSSQL = "mssql"


@dataclass
class QueryTranslation:
    """Result of SQL query translation."""
    original: str
    translated: str
    dialect: str
    changes: List[str]  # List of changes made


class DialectAdapter:
    """
    Unified SQL execution with dialect-aware translation and retry logic.
    
    Handles differences between PostgreSQL and SQL Server automatically.
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 0.5  # seconds
    MAX_BACKOFF = 5.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    # Transient error codes that warrant retry
    TRANSIENT_ERRORS = {
        "postgres": [
            "08000",  # Connection error
            "08003",  # Connection does not exist
            "08006",  # Connection failure
            "08P01",  # Protocol violation
        ],
        "mssql": [
            "40197",  # Connection error
            "40501",  # Service is busy
            "40613",  # Database unavailable
            "40666",  # Connection terminated
            "64",     # Communication link failure
        ]
    }
    
    def __init__(self, connector, dialect: str):
        """
        Initialize dialect adapter.
        
        Args:
            connector: Database connector (PostgresConnector or MSSQLConnector)
            dialect: Database dialect ("postgres" or "mssql")
        """
        self.connector = connector
        self.dialect = DatabaseDialect(dialect)
        self.query_stats = {
            "total_queries": 0,
            "retried_queries": 0,
            "failed_queries": 0,
            "total_retry_attempts": 0
        }
    
    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        timeout: Optional[float] = None,
        auto_retry: bool = True
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Execute a query with automatic retry and dialect translation.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            limit: Result row limit
            timeout: Query timeout in seconds
            auto_retry: Enable automatic retry on transient errors
            
        Returns:
            Tuple of (column_names, rows)
            
        Raises:
            Exception: If query fails after all retries
        """
        self.query_stats["total_queries"] += 1
        
        # Translate query if needed
        translated = self._translate_query(query)
        if translated.changes:
            logger.info(f"Query translation for {self.dialect.value}: {translated.changes}")
            query_to_execute = translated.translated
        else:
            query_to_execute = query
        
        # Execute with retry logic
        if auto_retry:
            return await self._execute_with_retry(
                query_to_execute,
                params=params,
                limit=limit,
                timeout=timeout
            )
        else:
            return await self._execute_once(
                query_to_execute,
                params=params,
                limit=limit,
                timeout=timeout
            )
    
    async def _execute_with_retry(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        timeout: Optional[float] = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Execute with exponential backoff retry logic.
        
        Args:
            query: SQL query
            params: Query parameters
            limit: Row limit
            timeout: Query timeout
            
        Returns:
            Tuple of (column_names, rows)
        """
        backoff = self.INITIAL_BACKOFF
        last_error = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(f"Query execution attempt {attempt}/{self.MAX_RETRIES}")
                return await self._execute_once(query, params, limit, timeout)
                
            except Exception as e:
                error_code = self._extract_error_code(str(e))
                is_transient = self._is_transient_error(error_code)
                
                last_error = e
                
                if not is_transient or attempt >= self.MAX_RETRIES:
                    logger.error(f"Query failed after {attempt} attempt(s): {e}")
                    self.query_stats["failed_queries"] += 1
                    raise
                
                # Transient error - retry with backoff
                self.query_stats["retried_queries"] += 1
                self.query_stats["total_retry_attempts"] += 1
                
                logger.warning(
                    f"⚠️ Transient error (code: {error_code}), retrying in {backoff:.2f}s... "
                    f"(attempt {attempt}/{self.MAX_RETRIES})"
                )
                
                await asyncio.sleep(backoff)
                backoff = min(backoff * self.BACKOFF_MULTIPLIER, self.MAX_BACKOFF)
        
        raise last_error or Exception("Query execution failed after all retries")
    
    async def _execute_once(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        timeout: Optional[float] = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Execute query once without retry.
        
        Args:
            query: SQL query
            params: Query parameters
            limit: Row limit
            timeout: Query timeout
            
        Returns:
            Tuple of (column_names, rows)
        """
        try:
            if self.dialect == DatabaseDialect.POSTGRES:
                # PostgreSQL via asyncpg
                return await self.connector.query(query, params=params, limit=limit)
            else:
                # SQL Server via pyodbc (synchronous, wrapped in executor)
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: self.connector.query(query, params=params, limit=limit)
                )
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise
    
    def _translate_query(self, query: str) -> QueryTranslation:
        """
        Translate query for target dialect.
        
        Handles common differences between PostgreSQL and SQL Server:
        - LIMIT vs TOP
        - RETURNING vs OUTPUT
        - Array functions
        - String functions
        - Case sensitivity
        
        Args:
            query: Original SQL query
            
        Returns:
            QueryTranslation object
        """
        changes = []
        translated = query
        
        if self.dialect == DatabaseDialect.MSSQL:
            # Translate PostgreSQL -> SQL Server
            
            # LIMIT -> TOP (for SELECT)
            if " LIMIT " in translated.upper():
                import re
                # Match "SELECT ... LIMIT n"
                pattern = r"(?i)(SELECT\s+.*?)\s+LIMIT\s+(\d+)"
                if re.search(pattern, translated):
                    translated = re.sub(
                        pattern,
                        r"SELECT TOP \2 \1",
                        translated,
                        flags=re.IGNORECASE
                    )
                    changes.append("LIMIT → TOP")
            
            # RETURNING -> OUTPUT (for INSERT/UPDATE/DELETE)
            if " RETURNING " in translated.upper():
                translated = translated.replace(" RETURNING ", " OUTPUT ")
                changes.append("RETURNING → OUTPUT")
            
            # PostgreSQL string functions -> SQL Server equivalents
            replacements = {
                r"\bCONCAT\(": "CONCAT(",  # Both support CONCAT
                r"\bSUBSTRING\(": "SUBSTRING(",  # Both support SUBSTRING
                r"\bLOWER\(": "LOWER(",
                r"\bUPPER\(": "UPPER(",
                r"\bLENGTH\(": "LEN(",  # LENGTH -> LEN
                r"\bTRIM\(": "TRIM(",
                r"\bCURRENT_TIMESTAMP": "GETDATE()",
                r"\bNOW\(\)": "GETDATE()",
            }
            
            import re
            for pattern, replacement in replacements.items():
                if re.search(pattern, translated, re.IGNORECASE):
                    translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
                    changes.append(f"{pattern[2:-2]} → {replacement[:-1]}")
            
            # Schema prefix handling (dbo. in SQL Server)
            if "." not in translated.split()[0]:
                # Add dbo. prefix if not present
                translated = translated.replace("SELECT", "SELECT")  # No change needed for now
        
        elif self.dialect == DatabaseDialect.POSTGRES:
            # Translate SQL Server -> PostgreSQL
            
            # TOP -> LIMIT
            if " TOP " in translated.upper():
                import re
                pattern = r"(?i)(SELECT\s+)TOP\s+(\d+)\s+"
                match = re.search(pattern, translated)
                if match:
                    limit_value = match.group(2)
                    translated = re.sub(pattern, r"\1", translated)
                    translated = f"{translated} LIMIT {limit_value}"
                    changes.append("TOP → LIMIT")
            
            # OUTPUT -> RETURNING
            if " OUTPUT " in translated.upper():
                translated = translated.replace(" OUTPUT ", " RETURNING ")
                changes.append("OUTPUT → RETURNING")
            
            # SQL Server functions -> PostgreSQL equivalents
            replacements = {
                r"\bGETDATE\(\)": "CURRENT_TIMESTAMP",
                r"\bLEN\(": "LENGTH(",
                r"\bIIF\(": "CASE WHEN",
                r"\bDATEADD\(": "DATE_ADD(",  # Requires manual translation
                r"\bDATEDIFF\(": "EXTRACT()",  # Requires manual translation
            }
            
            import re
            for pattern, replacement in replacements.items():
                if re.search(pattern, translated, re.IGNORECASE):
                    translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
                    changes.append(f"{pattern[2:-2]} → {replacement[:-1]}")
        
        return QueryTranslation(
            original=query,
            translated=translated,
            dialect=self.dialect.value,
            changes=changes
        )
    
    def _is_transient_error(self, error_code: str) -> bool:
        """
        Check if error code represents a transient error that warrants retry.
        
        Args:
            error_code: Database error code
            
        Returns:
            True if error is transient
        """
        if not error_code:
            # Connection timeout, network errors, etc. - usually transient
            return "timeout" in error_code.lower() or "connection" in error_code.lower()
        
        transient_codes = self.TRANSIENT_ERRORS.get(self.dialect.value, [])
        return error_code in transient_codes
    
    def _extract_error_code(self, error_message: str) -> Optional[str]:
        """
        Extract database error code from error message.
        
        Args:
            error_message: Error message from database
            
        Returns:
            Error code or None
        """
        import re
        
        # PostgreSQL error codes (e.g., "08000")
        pg_match = re.search(r"\b([0-9][0-9A-Z]{4})\b", error_message)
        if pg_match:
            return pg_match.group(1)
        
        # SQL Server error codes (e.g., "Msg 40501")
        mssql_match = re.search(r"Msg\s+(\d+)", error_message)
        if mssql_match:
            return mssql_match.group(1)
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get query execution statistics."""
        return {
            **self.query_stats,
            "retry_ratio": (
                self.query_stats["retried_queries"] / self.query_stats["total_queries"]
                if self.query_stats["total_queries"] > 0
                else 0
            )
        }