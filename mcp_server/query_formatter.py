"""
Query Result Formatter for Answer-first Presentation - Phase 7: Autonomous Discovery.

This module formats database query results into natural language answers
customized for the user's original intent and query type.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)


class QueryFormatter:
    """
    Formats query results for natural language presentation.
    """
    
    HIDDEN_COLUMNS = {
        'id', 'pk', 'primary_key', 'rowid', 'oid',
        'created_at', 'updated_at', 'modified_date',
        'internal_id', 'system_id'
    }
    
    PRIORITY_COLUMNS = {
        'name', 'title', 'description', 'email', 'phone',
        'amount', 'total', 'price', 'quantity', 'count',
        'date', 'start_date', 'end_date', 'period',
        'status', 'type', 'category', 'region'
    }
    
    def __init__(self, intent: str = "SEARCH", max_rows: int = 100):
        """Initialize formatter."""
        self.intent = intent
        self.max_rows = max_rows
    
    def format_results(self,
                      rows: List[Dict[str, Any]],
                      columns: List[str],
                      execution_time_ms: float,
                      original_query: str) -> Dict[str, Any]:
        """Format query results for presentation."""
        if not rows:
            return {
                "summary": "No results found.",
                "row_count": 0,
                "execution_time_ms": execution_time_ms,
                "data": [],
                "insight": "The query executed successfully but returned no rows."
            }
        
        if self.intent == "AGGREGATE":
            return self._format_aggregate(rows, columns, execution_time_ms)
        elif self.intent == "TREND":
            return self._format_trend(rows, columns, execution_time_ms)
        elif self.intent == "REPORT":
            return self._format_report(rows, columns, execution_time_ms)
        elif self.intent == "JOIN":
            return self._format_join(rows, columns, execution_time_ms)
        elif self.intent == "FILTER":
            return self._format_filter(rows, columns, execution_time_ms)
        else:
            return self._format_search(rows, columns, execution_time_ms)
    
    def _format_aggregate(self, rows, columns, exec_time):
        """Format aggregate results."""
        if len(rows) == 1 and len(columns) == 1:
            value = rows[0][columns[0]]
            return {
                "summary": f"Result: {value}",
                "value": value,
                "row_count": 1,
                "execution_time_ms": exec_time
            }
        return {
            "summary": f"Found {len(rows)} groups",
            "row_count": len(rows),
            "data": rows[:5],
            "columns": columns,
            "execution_time_ms": exec_time
        }
    
    def _format_trend(self, rows, columns, exec_time):
        """Format trend results."""
        return {
            "summary": f"Retrieved {len(rows)} time periods",
            "row_count": len(rows),
            "data": rows[:10],
            "columns": columns,
            "execution_time_ms": exec_time
        }
    
    def _format_report(self, rows, columns, exec_time):
        """Format report results."""
        return {
            "summary": f"Top {min(10, len(rows))} items",
            "row_count": len(rows),
            "data": rows[:10],
            "columns": columns,
            "execution_time_ms": exec_time
        }
    
    def _format_join(self, rows, columns, exec_time):
        """Format join results."""
        return {
            "summary": f"Found {len(rows)} related records",
            "row_count": len(rows),
            "data": rows[:20],
            "columns": columns,
            "execution_time_ms": exec_time
        }
    
    def _format_filter(self, rows, columns, exec_time):
        """Format filter results."""
        return {
            "summary": f"Found {len(rows)} matching records",
            "row_count": len(rows),
            "data": rows[:20],
            "columns": columns,
            "execution_time_ms": exec_time
        }
    
    def _format_search(self, rows, columns, exec_time):
        """Format search results."""
        display_cols = [c for c in columns if c.lower() not in self.HIDDEN_COLUMNS][:10]
        return {
            "summary": f"Found {len(rows)} records",
            "row_count": len(rows),
            "data": rows[:20],
            "columns": display_cols,
            "execution_time_ms": exec_time
        }


def format_results(rows: List[Dict[str, Any]],
                   columns: List[str],
                   execution_time_ms: float,
                   intent: str = "SEARCH",
                   original_query: str = "") -> Dict[str, Any]:
    """Convenience function to format results."""
    formatter = QueryFormatter(intent=intent)
    return formatter.format_results(rows, columns, execution_time_ms, original_query)