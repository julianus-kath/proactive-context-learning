"""
Phase 6: Observability & Guardrails - Structured logging and metrics.

This module provides:
- JSON structured logging for all MCP tool calls
- Performance metrics tracking
- Error tracking and categorization
- PII-free logging (no sensitive data)

Architecture alignment:
- Security & privacy: No PII, no sensitive data in logs
- JSON as single data format: All logs are JSON
- Modular design: Clean separation of concerns
"""

import time
import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Error categories for structured logging."""
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    DATABASE = "database"
    TIMEOUT = "timeout"
    CATALOG = "catalog"
    UNKNOWN = "unknown"


@dataclass
class ToolCallMetrics:
    """Metrics for a single tool call."""
    tool_name: str
    duration_ms: float
    success: bool
    cached: bool = False
    cache_hit: bool = False
    row_count: Optional[int] = None
    truncated: bool = False
    error_code: Optional[str] = None
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    db_query_executed: bool = False
    db_query_duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


class StructuredLogger:
    """
    Structured logger for MCP tool calls.
    
    Logs all tool calls with:
    - Tool name
    - Duration (ms)
    - Cache hit/miss
    - Row count (if applicable)
    - Truncated flag (if applicable)
    - Error code and category (if failed)
    - No PII or sensitive data
    """
    
    def __init__(self):
        """Initialize structured logger."""
        self._metrics_history: list[ToolCallMetrics] = []
        self._max_history = 1000  # Keep last 1000 calls
    
    @contextmanager
    def log_tool_call(self, tool_name: str, arguments: Dict[str, Any]):
        """
        Context manager for logging tool calls.
        
        Usage:
            with structured_logger.log_tool_call("list_tables", args) as metrics:
                result = execute_tool(...)
                metrics.row_count = len(result)
                metrics.cached = True
        """
        start_time = time.time()
        metrics = ToolCallMetrics(
            tool_name=tool_name,
            duration_ms=0.0,
            success=True
        )
        
        try:
            yield metrics
            
        except Exception as e:
            metrics.success = False
            metrics.error_message = str(e)
            metrics.error_category = self._categorize_error(e)
            metrics.error_code = getattr(e, 'code', None) or type(e).__name__
            raise
            
        finally:
            # Calculate duration
            duration = (time.time() - start_time) * 1000
            metrics.duration_ms = round(duration, 2)
            
            # Log as JSON
            self._log_metrics(metrics, arguments)
            
            # Store in history
            self._store_metrics(metrics)
    
    def _categorize_error(self, error: Exception) -> str:
        """Categorize error for structured logging."""
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        if "rate limit" in error_msg or "429" in error_msg:
            return ErrorCategory.RATE_LIMIT
        elif "timeout" in error_msg or "timed out" in error_msg:
            return ErrorCategory.TIMEOUT
        elif "validation" in error_msg or "invalid" in error_msg:
            return ErrorCategory.VALIDATION
        elif "catalog" in error_msg or "not initialized" in error_msg:
            return ErrorCategory.CATALOG
        elif "database" in error_msg or "connection" in error_msg:
            return ErrorCategory.DATABASE
        else:
            return ErrorCategory.UNKNOWN
    
    def _log_metrics(self, metrics: ToolCallMetrics, arguments: Dict[str, Any]):
        """Log metrics as structured JSON."""
        log_data = {
            "event": "mcp_tool_call",
            "tool_name": metrics.tool_name,
            "duration_ms": metrics.duration_ms,
            "success": metrics.success,
            "cached": metrics.cached,
            "timestamp": time.time()
        }
        
        # Add optional fields
        if metrics.cache_hit:
            log_data["cache_hit"] = True
        if metrics.row_count is not None:
            log_data["row_count"] = metrics.row_count
        if metrics.truncated:
            log_data["truncated"] = True
        if metrics.db_query_executed:
            log_data["db_query_executed"] = True
        if metrics.db_query_duration_ms is not None:
            log_data["db_query_duration_ms"] = metrics.db_query_duration_ms
        
        # Add error details if failed
        if not metrics.success:
            log_data["error_code"] = metrics.error_code
            log_data["error_category"] = metrics.error_category
            log_data["error_message"] = metrics.error_message
        
        # Redact sensitive arguments (keep only non-sensitive metadata)
        safe_args = self._redact_arguments(arguments)
        if safe_args:
            log_data["arguments"] = safe_args
        
        # Log as JSON
        if metrics.success:
            logger.info(json.dumps(log_data))
        else:
            logger.error(json.dumps(log_data))
    
    def _redact_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive arguments, keep only safe metadata.
        
        Safe to log:
        - page, page_size, limit
        - table_name (if not sensitive)
        - query length (not content)
        - schema name
        
        Never log:
        - SQL query content (may contain sensitive filters)
        - API keys
        - Passwords
        - User data
        """
        safe_args = {}
        
        # Safe numeric parameters
        for key in ["page", "page_size", "limit"]:
            if key in arguments:
                safe_args[key] = arguments[key]
        
        # Safe string parameters (non-sensitive)
        for key in ["schema", "pattern"]:
            if key in arguments:
                safe_args[key] = arguments[key]
        
        # Table name (usually safe, but truncate if too long)
        if "table_name" in arguments:
            table_name = arguments["table_name"]
            if len(table_name) < 100:  # Reasonable table name length
                safe_args["table_name"] = table_name
        
        # Query keyword (for search_tables)
        if "query" in arguments:
            query = arguments["query"]
            if len(query) < 50:  # Short search keywords are safe
                safe_args["search_query"] = query
        
        # SQL query - only log length, not content
        if "sql" in arguments:
            safe_args["sql_length"] = len(arguments["sql"])
        
        return safe_args
    
    def _store_metrics(self, metrics: ToolCallMetrics):
        """Store metrics in history (circular buffer)."""
        self._metrics_history.append(metrics)
        
        # Keep only last N calls
        if len(self._metrics_history) > self._max_history:
            self._metrics_history = self._metrics_history[-self._max_history:]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of recent metrics.
        
        Returns:
            Dictionary with aggregated metrics:
            - total_calls
            - success_rate
            - avg_duration_ms
            - cache_hit_rate
            - error_breakdown
            - tool_breakdown
        """
        if not self._metrics_history:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "cache_hit_rate": 0.0
            }
        
        total_calls = len(self._metrics_history)
        successful_calls = sum(1 for m in self._metrics_history if m.success)
        cached_calls = sum(1 for m in self._metrics_history if m.cache_hit)
        total_duration = sum(m.duration_ms for m in self._metrics_history)
        
        # Error breakdown
        error_breakdown = {}
        for m in self._metrics_history:
            if not m.success and m.error_category:
                error_breakdown[m.error_category] = error_breakdown.get(m.error_category, 0) + 1
        
        # Tool breakdown
        tool_breakdown = {}
        for m in self._metrics_history:
            tool_breakdown[m.tool_name] = tool_breakdown.get(m.tool_name, 0) + 1
        
        return {
            "total_calls": total_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0.0,
            "avg_duration_ms": round(total_duration / total_calls, 2) if total_calls > 0 else 0.0,
            "cache_hit_rate": cached_calls / total_calls if total_calls > 0 else 0.0,
            "error_breakdown": error_breakdown,
            "tool_breakdown": tool_breakdown,
            "history_size": total_calls
        }
    
    def clear_history(self):
        """Clear metrics history."""
        self._metrics_history.clear()


# Global structured logger instance
structured_logger = StructuredLogger()


def log_tool_call(tool_name: str, arguments: Dict[str, Any]):
    """
    Convenience function for logging tool calls.
    
    Usage:
        with log_tool_call("list_tables", args) as metrics:
            result = execute_tool(...)
            metrics.row_count = len(result)
    """
    return structured_logger.log_tool_call(tool_name, arguments)


def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of recent metrics."""
    return structured_logger.get_metrics_summary()