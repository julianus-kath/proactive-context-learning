"""
Comprehensive Debug Logging System
Provides detailed, readable logging for tool calls, scout mode, and workflow decisions.
"""

import os
import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum
from functools import wraps
from collections import defaultdict
import threading

# Thread-safe log collection for frontend streaming
_logs_buffer: List[Dict[str, Any]] = []
_logs_lock = threading.Lock()


def _sanitize_for_serialization(
    value: Any,
    *,
    max_depth: int = 5,
    max_list_length: int = 20,
    max_dict_items: int = 50,
    _visited: Optional[set] = None
) -> Any:
    """
    Convert arbitrary Python objects into JSON-serializable structures.

    Limits recursion depth and collection sizes to keep logs manageable.
    """
    if max_depth <= 0:
        return repr(value)

    if _visited is None:
        _visited = set()

    # Primitive types pass through
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    obj_id = id(value)
    if obj_id in _visited:
        return "<recursive>"
    _visited.add(obj_id)

    # Datetime-like objects
    if isinstance(value, datetime):
        return value.isoformat()

    # Path, Enum, etc.
    if isinstance(value, (Path, Enum)):
        return str(value)

    # Dictionaries
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for idx, (key, val) in enumerate(value.items()):
            if idx >= max_dict_items:
                sanitized["__truncated__"] = f"{len(value) - max_dict_items} more items"
                break
            sanitized[str(key)] = _sanitize_for_serialization(
                val,
                max_depth=max_depth - 1,
                max_list_length=max_list_length,
                max_dict_items=max_dict_items,
                _visited=_visited,
            )
        return sanitized

    # Iterables
    if isinstance(value, (list, tuple, set)):
        iterable = list(value)
        sanitized_list = [
            _sanitize_for_serialization(
                item,
                max_depth=max_depth - 1,
                max_list_length=max_list_length,
                max_dict_items=max_dict_items,
                _visited=_visited,
            )
            for item in iterable[:max_list_length]
        ]
        if len(iterable) > max_list_length:
            sanitized_list.append(f"... {len(iterable) - max_list_length} more items")
        return sanitized_list

    # Objects with dict() or __dict__
    for attr in ("dict", "__dict__"):
        if hasattr(value, attr):
            try:
                obj_dict = getattr(value, attr)
                if callable(obj_dict):
                    obj_dict = obj_dict()
                return _sanitize_for_serialization(
                    obj_dict,
                    max_depth=max_depth - 1,
                    max_list_length=max_list_length,
                    max_dict_items=max_dict_items,
                    _visited=_visited,
                )
            except Exception:
                continue

    # Fallback to repr
    return repr(value)


class LogLevel(Enum):
    """Log level categories for better organization."""
    TOOL_CALL = "🔧"
    TOOL_RESULT = "✅"
    SCOUT_MODE = "🔍"
    INTENT_PARSE = "📝"
    SCHEMA_DISCOVERY = "📊"
    SQL_GENERATION = "🔄"
    QUERY_EXECUTION = "⚡"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    DECISION = "🎯"
    STATE_UPDATE = "💾"
    TIMING = "⏱️"


class DebugLogger:
    """
    Comprehensive debug logger for LangGraph workflow.
    
    Features:
    - Structured logging with clear visual separators
    - Tool call tracking with arguments and results
    - Scout mode operation logging
    - Performance timing
    - JSON-formatted output for parsing
    - Thread-safe buffer for frontend streaming
    """
    
    def __init__(self, name: str = "langgraph", log_dir: str = None):
        """
        Initialize the debug logger.
        
        Args:
            name: Logger name
            log_dir: Directory for log files (default: ./logs)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Create logs directory if needed
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up file handler with comprehensive formatting
        log_file = self.log_dir / f"{name}_debug.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Set up console handler for terminal output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._jsonl_lock = threading.Lock()
        self._event_counter = 0
        self._agent_timings = defaultdict(list)
        self.session_jsonl_dir = self.log_dir / "sessions"
        self.session_jsonl_dir.mkdir(parents=True, exist_ok=True)
        self.session_jsonl_path = self.session_jsonl_dir / f"{self.session_id}.jsonl"
        self.call_stack = []  # Track nested operations
        self.current_node = None  # Track current LangGraph node context
        
    def _log_entry(
        self,
        level: LogLevel,
        title: str,
        data: Dict[str, Any] = None,
        nested: bool = False
    ) -> str:
        """
        Create a formatted log entry.
        
        Args:
            level: Log level category
            title: Title of the log entry
            data: Additional data to log
            nested: Whether this is a nested operation
            
        Returns:
            Formatted log message
        """
        indent = "  " * len(self.call_stack) if nested else ""
        separator = "─" * 60
        
        message_lines = [
            f"\n{indent}{level.value} {title}",
            f"{indent}{separator}"
        ]
        
        if data:
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2, default=str)
                    message_lines.append(f"{indent}  {key}:")
                    for line in value_str.split('\n'):
                        message_lines.append(f"{indent}    {line}")
                else:
                    message_lines.append(f"{indent}  {key}: {value}")
        
        message_lines.append(f"{indent}{separator}")
        return "\n".join(message_lines)
    
    def _write_jsonl(self, entry: Dict[str, Any]) -> None:
        """Persist structured log entry to session JSONL file."""
        try:
            sanitized_entry = _sanitize_for_serialization(entry)
            with self._jsonl_lock:
                with self.session_jsonl_path.open("a", encoding="utf-8") as f:
                    json.dump(sanitized_entry, f, ensure_ascii=False)
                    f.write("\n")
        except Exception as exc:
            self.logger.debug(f"Failed to write JSONL log entry: {exc}")
    
    def tool_call(self, tool_name: str, arguments: Dict[str, Any], tool_id: str = None):
        """
        Log a tool call initiation.
        
        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments
            tool_id: Optional unique identifier for this call
        """
        call_id = tool_id or f"{tool_name}_{len(self.call_stack)}"
        self.call_stack.append(call_id)
        
        message = self._log_entry(
            LogLevel.TOOL_CALL,
            f"Tool Call: {tool_name}",
            {
                "tool_id": call_id,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat()
            },
            nested=True
        )
        
        self.logger.debug(message)
        self._add_to_buffer(
            message,
            "TOOL_CALL",
            {
                "event": "tool_call",
                "tool_name": tool_name,
                "tool_id": call_id,
                "arguments": arguments,
            }
        )
    
    def tool_result(self, tool_name: str, result: Any, duration_ms: float = None, error: str = None):
        """
        Log tool execution result.
        
        Args:
            tool_name: Name of the tool
            result: Tool result/response
            duration_ms: Execution time in milliseconds
            error: Error message if execution failed
        """
        if self.call_stack:
            self.call_stack.pop()
        
        status = "✅ SUCCESS" if not error else "❌ FAILED"
        
        data = {
            "tool_name": tool_name,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        if duration_ms is not None:
            data["duration_ms"] = round(duration_ms, 2)
        
        if error:
            data["error"] = error
            message = self._log_entry(
                LogLevel.ERROR,
                f"Tool Result: {tool_name}",
                data,
                nested=True
            )
            self.logger.error(message)
        else:
            # Truncate large results for readability
            if isinstance(result, (dict, list)):
                result_display = result if len(str(result)) < 500 else f"{str(result)[:500]}... [truncated]"
            else:
                result_display = result if len(str(result)) < 500 else f"{str(result)[:500]}... [truncated]"
            
            data["result_preview"] = result_display
            message = self._log_entry(
                LogLevel.TOOL_RESULT,
                f"Tool Result: {tool_name}",
                data,
                nested=True
            )
            self.logger.info(message)
        
        structured_payload = {
            "event": "tool_result",
            "tool_name": tool_name,
            "status": status,
            "duration_ms": data.get("duration_ms"),
            "error": error,
            "result_preview": data.get("result_preview"),
        }
        self._add_to_buffer(message, "TOOL_RESULT", structured_payload)
    
    def tool_error(self, tool_name: str, error: str, context: Optional[Dict[str, Any]] = None):
        """
        Log tool errors explicitly (used by MCP client fallbacks).
        """
        data = {
            "tool_name": tool_name,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        if context:
            data["context"] = context
        
        message = self._log_entry(
            LogLevel.ERROR,
            f"Tool Error: {tool_name}",
            data,
            nested=False
        )
        self.logger.error(message)
        structured_payload = {"event": "tool_error", **data}
        self._add_to_buffer(message, "TOOL_ERROR", structured_payload)
    
    def scout_mode_operation(self, operation: str, query: str, tables_searched: List[str], results: Dict[str, Any]):
        """
        Log scout mode table search operation.
        
        Args:
            operation: Scout mode operation type (e.g., "search_tables", "list_tables")
            query: Search query or filter
            tables_searched: List of table names searched
            results: Ranking/search results
        """
        data = {
            "operation": operation,
            "query": query,
            "tables_searched": tables_searched,
            "result_count": len(results) if isinstance(results, list) else 1,
            "timestamp": datetime.now().isoformat()
        }
        
        if isinstance(results, list) and len(results) > 0:
            data["top_results"] = results[:3]  # Show top 3 results
        else:
            data["results"] = results
        
        message = self._log_entry(
            LogLevel.SCOUT_MODE,
            f"Scout Mode: {operation}",
            data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {"event": "scout_mode", **data}
        self._add_to_buffer(message, "SCOUT_MODE", structured_payload)
    
    def intent_parsed(
        self,
        user_query: str,
        intent_type: str,
        confidence: float,
        missing_fields: List[str] = None,
        entities: List[str] = None
    ):
        """
        Log intent parsing result.
        
        Args:
            user_query: Original user query
            intent_type: Detected intent (clarify, query, schema_query, etc.)
            confidence: Confidence score (0-1)
            missing_fields: Fields that need clarification
            entities: Extracted entities
        """
        data = {
            "user_query": user_query[:100],  # Truncate long queries
            "intent_type": intent_type,
            "confidence": round(confidence, 3),
            "timestamp": datetime.now().isoformat()
        }
        
        if missing_fields:
            data["missing_fields"] = missing_fields
        
        if entities:
            data["extracted_entities"] = entities
        
        message = self._log_entry(
            LogLevel.INTENT_PARSE,
            f"Intent Parsed: {intent_type}",
            data,
            nested=False
        )
        
        level = self.logger.info if intent_type != "clarify" else self.logger.warning
        level(message)
        structured_payload = {"event": "intent_parsed", **data}
        self._add_to_buffer(message, "INTENT_PARSE", structured_payload)
    
    def schema_discovered(
        self,
        table_name: str,
        columns: List[Dict[str, str]],
        row_count: int = None,
        relationships: List[Dict[str, str]] = None
    ):
        """
        Log schema discovery for a table.
        
        Args:
            table_name: Table name
            columns: Column information
            row_count: Number of rows in table
            relationships: Foreign key relationships
        """
        data = {
            "table_name": table_name,
            "column_count": len(columns),
            "columns": columns[:5] if len(columns) > 5 else columns,  # Show first 5
            "timestamp": datetime.now().isoformat()
        }
        
        if row_count is not None:
            data["row_count"] = row_count
        
        if relationships:
            data["relationships"] = relationships
        
        if len(columns) > 5:
            data["columns_summary"] = f"... and {len(columns) - 5} more columns"
        
        message = self._log_entry(
            LogLevel.SCHEMA_DISCOVERY,
            f"Schema Discovered: {table_name}",
            data,
            nested=False
        )
        
        self.logger.debug(message)
        structured_payload = {"event": "schema_discovered", **data}
        self._add_to_buffer(message, "SCHEMA_DISCOVERY", structured_payload)
    
    def sql_generated(self, sql: str, reason: str, table_context: List[str] = None):
        """
        Log SQL query generation.
        
        Args:
            sql: Generated SQL query
            reason: Reason for this query
            table_context: Tables used in the query
        """
        data = {
            "sql": sql,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        if table_context:
            data["tables_used"] = table_context
        
        message = self._log_entry(
            LogLevel.SQL_GENERATION,
            "SQL Generated",
            data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {"event": "sql_generated", **data}
        self._add_to_buffer(message, "SQL_GENERATION", structured_payload)
    
    def query_executed(
        self,
        sql: str,
        rows_returned: int,
        duration_ms: float,
        error: str = None
    ):
        """
        Log query execution.
        
        Args:
            sql: Executed SQL query
            rows_returned: Number of rows returned
            duration_ms: Execution time
            error: Error message if failed
        """
        status = "✅ SUCCESS" if not error else "❌ FAILED"
        
        data = {
            "sql": sql[:100],  # Truncate long queries
            "status": status,
            "rows_returned": rows_returned,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        if error:
            data["error"] = error
        
        message = self._log_entry(
            LogLevel.QUERY_EXECUTION,
            "Query Executed",
            data,
            nested=False
        )
        
        level = self.logger.info if not error else self.logger.error
        level(message)
        structured_payload = {"event": "query_executed", **data}
        self._add_to_buffer(message, "QUERY_EXECUTION", structured_payload)
    
    def decision_made(self, decision: str, reason: str, options_considered: List[str] = None):
        """
        Log workflow decision.
        
        Args:
            decision: The decision made
            reason: Reasoning behind the decision
            options_considered: List of options that were considered
        """
        data = {
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        if options_considered:
            data["options_considered"] = options_considered
        
        message = self._log_entry(
            LogLevel.DECISION,
            f"Decision: {decision}",
            data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {"event": "decision_made", **data}
        self._add_to_buffer(message, "DECISION", structured_payload)
    
    def state_updated(self, state_key: str, old_value: Any = None, new_value: Any = None):
        """
        Log state updates.
        
        Args:
            state_key: Key being updated
            old_value: Previous value
            new_value: New value
        """
        data = {
            "state_key": state_key,
            "timestamp": datetime.now().isoformat()
        }
        
        if old_value is not None:
            data["old_value"] = str(old_value)[:100]
        if new_value is not None:
            data["new_value"] = str(new_value)[:100]
        
        message = self._log_entry(
            LogLevel.STATE_UPDATE,
            f"State Updated: {state_key}",
            data,
            nested=False
        )
        
        self.logger.debug(message)
        structured_payload = {"event": "state_updated", **data}
        self._add_to_buffer(message, "STATE_UPDATE", structured_payload)
    
    def timing_checkpoint(self, checkpoint_name: str, duration_ms: float):
        """
        Log timing checkpoint.
        
        Args:
            checkpoint_name: Name of the checkpoint
            duration_ms: Duration in milliseconds
        """
        data = {
            "checkpoint": checkpoint_name,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        message = self._log_entry(
            LogLevel.TIMING,
            f"Timing: {checkpoint_name}",
            data,
            nested=False
        )
        
        self.logger.debug(message)
        structured_payload = {"event": "timing_checkpoint", **data}
        self._add_to_buffer(message, "TIMING", structured_payload)
    
    def workflow_error(self, error_type: str, message: str, context: Dict[str, Any] = None):
        """
        Log workflow errors.
        
        Args:
            error_type: Type of error
            message: Error message
            context: Additional context
        """
        data = {
            "error_type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if context:
            data["context"] = context
        
        log_message = self._log_entry(
            LogLevel.ERROR,
            f"Error: {error_type}",
            data,
            nested=False
        )
        
        self.logger.error(log_message)
        structured_payload = {"event": "workflow_error", **data}
        self._add_to_buffer(log_message, "ERROR", structured_payload)
    
    def warning(self, title: str, details: str, context: Dict[str, Any] = None):
        """
        Log warnings.
        
        Args:
            title: Warning title
            details: Warning details
            context: Additional context
        """
        data = {
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        if context:
            data["context"] = context
        
        message = self._log_entry(
            LogLevel.WARNING,
            f"Warning: {title}",
            data,
            nested=False
        )
        
        self.logger.warning(message)
        structured_payload = {"event": "warning", **data, "title": title}
        self._add_to_buffer(message, "WARNING", structured_payload)
    
    def info(self, title: str, details: str = None, data: Dict[str, Any] = None):
        """
        Log informational messages.
        
        Args:
            title: Info title
            details: Info details
            data: Additional data
        """
        log_data = {
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            log_data["details"] = details
        
        if data:
            log_data.update(data)
        
        message = self._log_entry(
            LogLevel.INFO,
            title,
            log_data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {"event": "info", **log_data, "title": title}
        self._add_to_buffer(message, "INFO", structured_payload)
    
    def log_info(self, message: str, details: Dict[str, Any] = None):
        """
        Log informational messages with dict details.
        Alias for info() that accepts details as a dict.
        
        Args:
            message: Log message
            details: Details as a dictionary
        """
        log_data = {
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            log_data.update(details)
        
        log_message = self._log_entry(
            LogLevel.INFO,
            message,
            log_data,
            nested=False
        )
        
        self.logger.info(log_message)
        structured_payload = {"event": "info", **log_data, "message": message}
        self._add_to_buffer(log_message, "INFO", structured_payload)
    
    def set_node_context(self, node_name: str):
        """Set the current LangGraph node context for better logging organization."""
        self.current_node = node_name
    
    # ============= Phase 9: Intent Parser Deep Debugging =============
    
    def agent_entry(self, agent_name: str, state: Dict[str, Any]):
        """
        Log agent entry with complete state snapshot.
        
        Args:
            agent_name: Name of the agent/node being executed
            state: Current state snapshot
        """
        state_keys = list(state.keys())
        intent = state.get("intent", {})
        
        data = {
            "agent": agent_name,
            "state_keys_count": len(state_keys),
            "state_keys": state_keys,
            "has_intent": bool(intent),
            "timestamp": datetime.now().isoformat()
        }
        
        # Include intent details if present
        if intent:
            data["intent_operation"] = intent.get("operation", "?")
            data["intent_confidence"] = intent.get("confidence", 0)
            data["intent_keywords"] = intent.get("keywords_for_discovery", [])
            data["intent_entities"] = intent.get("primary_entities", [])
        
        message = self._log_entry(
            LogLevel.INFO,
            f"🚀 AGENT ENTRY: {agent_name}",
            data,
            nested=False
        )
        
        # Track timing for exit computation
        self._agent_timings[agent_name].append(time.perf_counter())

        self.logger.info(message)
        structured_payload = {
            "event": "agent_entry",
            "agent": agent_name,
            "state_keys": state_keys,
            "state_snapshot": state,
            "intent": intent,
        }
        self._add_to_buffer(message, "AGENT_ENTRY", structured_payload)
    
    def agent_exit(self, agent_name: str, before_state: Dict[str, Any], after_state: Dict[str, Any]):
        """
        Log agent exit with state delta.
        
        Args:
            agent_name: Name of the agent that executed
            before_state: State before execution
            after_state: State after execution
        """
        # Detect changes
        added_keys = set(after_state.keys()) - set(before_state.keys())
        removed_keys = set(before_state.keys()) - set(after_state.keys())
        changed_keys = []
        
        for key in set(before_state.keys()) & set(after_state.keys()):
            if before_state[key] != after_state[key]:
                changed_keys.append(key)
        
        data = {
            "agent": agent_name,
            "added_keys": list(added_keys),
            "removed_keys": list(removed_keys),
            "modified_keys": changed_keys,
            "timestamp": datetime.now().isoformat()
        }
        
        # Special tracking for intent changes
        if "intent" in changed_keys:
            before_intent = before_state.get("intent", {})
            after_intent = after_state.get("intent", {})
            
            intent_changes = {}
            for k in set(before_intent.keys()) | set(after_intent.keys()):
                if before_intent.get(k) != after_intent.get(k):
                    intent_changes[k] = {
                        "before": before_intent.get(k),
                        "after": after_intent.get(k)
                    }
            
            if intent_changes:
                data["intent_changes"] = intent_changes
        
        # Compute duration if entry recorded a start time
        duration_ms = None
        timings = self._agent_timings.get(agent_name)
        if timings:
            try:
                start_time = timings.pop()
                duration_ms = (time.perf_counter() - start_time) * 1000
                data["duration_ms"] = round(duration_ms, 2)
            except Exception:
                duration_ms = None
        elif agent_name in self._agent_timings:
            # Ensure list exists even if empty for future runs
            self._agent_timings[agent_name] = []

        message = self._log_entry(
            LogLevel.INFO,
            f"✅ AGENT EXIT: {agent_name}",
            data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {
            "event": "agent_exit",
            "agent": agent_name,
            "added_keys": list(added_keys),
            "removed_keys": list(removed_keys),
            "modified_keys": changed_keys,
            "before_state": before_state,
            "after_state": after_state,
        }
        if duration_ms is not None:
            structured_payload["duration_ms"] = round(duration_ms, 2)
        if "intent" in changed_keys:
            structured_payload["intent_changes"] = data.get("intent_changes", {})

        self._add_to_buffer(message, "AGENT_EXIT", structured_payload)
    
    def intent_parsed_phase9(self, intent: Dict[str, Any], parsing_method: str = "LLM"):
        """
        Log intent parsing (Phase 9 specific).
        
        Args:
            intent: Parsed intent dict
            parsing_method: How was it parsed (LLM, heuristic, etc.)
        """
        data = {
            "parsing_method": parsing_method,
            "operation": intent.get("operation", "?"),
            "confidence": intent.get("confidence", 0),
            "keywords_count": len(intent.get("keywords_for_discovery", [])),
            "keywords": intent.get("keywords_for_discovery", []),
            "entities": intent.get("primary_entities", []),
            "metrics": intent.get("metrics", []),
            "has_filters": len(intent.get("filters", [])) > 0,
            "has_time_window": intent.get("time_window") is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        message = self._log_entry(
            LogLevel.INTENT_PARSE,
            f"🧠 INTENT PARSED ({parsing_method})",
            data,
            nested=False
        )
        
        self.logger.info(message)
        structured_payload = {
            "event": "intent_parsed_phase9",
            "intent": intent,
            "parsing_method": parsing_method,
        }
        self._add_to_buffer(message, "INTENT_CHECK", structured_payload)
    
    def mcp_tool_invoked(self, tool_name: str, params: Dict[str, Any], agent: str = None):
        """
        Log MCP tool invocation.
        
        Args:
            tool_name: MCP tool name
            params: Tool parameters
            agent: Agent that triggered this call
        """
        data = {
            "tool": tool_name,
            "params": params,
            "timestamp": datetime.now().isoformat()
        }
        
        if agent:
            data["called_by_agent"] = agent
        
        message = self._log_entry(
            LogLevel.TOOL_CALL,
            f"📡 MCP TOOL: {tool_name}",
            data,
            nested=False
        )
        
        self.logger.debug(message)
        structured_payload = {
            "event": "mcp_tool_invoked",
            "tool": tool_name,
            "params": params,
            "agent": agent,
        }
        self._add_to_buffer(message, "MCP_CALL", structured_payload)
    
    def mcp_tool_result(self, tool_name: str, result: Dict[str, Any], error: str = None):
        """
        Log MCP tool result.
        
        Args:
            tool_name: MCP tool name
            result: Result from the tool
            error: Error message if failed
        """
        status = "✅ OK" if not error else "❌ ERROR"
        
        data = {
            "tool": tool_name,
            "status": status,
            "result_keys": list(result.keys()) if isinstance(result, dict) else "N/A",
            "timestamp": datetime.now().isoformat()
        }
        
        if error:
            data["error"] = error
        
        # Summarize result
        if isinstance(result, dict):
            if "candidates" in result:
                data["candidates_count"] = len(result.get("candidates", []))
                if result.get("candidates"):
                    data["top_candidates"] = [c.get("name", "?") for c in result.get("candidates", [])[:3]]
            if "rows" in result:
                data["rows_count"] = len(result.get("rows", []))
        
        message = self._log_entry(
            LogLevel.TOOL_RESULT,
            f"📊 MCP RESULT: {tool_name}",
            data,
            nested=False
        )
        
        level = self.logger.info if not error else self.logger.error
        level(message)
        structured_payload = {
            "event": "mcp_tool_result",
            "tool": tool_name,
            "status": status,
            "result": result,
            "error": error,
        }
        self._add_to_buffer(message, "MCP_RESULT", structured_payload)
    
    def _add_to_buffer(
        self,
        message: str,
        log_type: str,
        structured_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add message to thread-safe buffer and persist structured payload."""
        self._event_counter += 1
        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "type": log_type,
            "message": message,
            "session_id": self.session_id,
            "sequence": self._event_counter,
        }
        if self.current_node:
            entry["node"] = self.current_node
        if structured_data is not None:
            entry["data"] = structured_data

        sanitized_entry = _sanitize_for_serialization(entry)

        with _logs_lock:
            _logs_buffer.append(sanitized_entry)

        self._write_jsonl(sanitized_entry)
    
    @staticmethod
    def get_buffered_logs() -> List[Dict[str, Any]]:
        """Get and clear buffered logs."""
        with _logs_lock:
            logs = _logs_buffer.copy()
            _logs_buffer.clear()
            return logs
    
    @staticmethod
    def get_buffered_logs_no_clear() -> List[Dict[str, Any]]:
        """Get buffered logs without clearing."""
        with _logs_lock:
            return _logs_buffer.copy()


def log_tool_call(logger: DebugLogger):
    """Decorator for logging tool calls."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(tool_name: str, arguments: dict, *args, **kwargs):
            logger.tool_call(tool_name, arguments)
            try:
                import time
                start = time.time()
                result = await func(tool_name, arguments, *args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                logger.tool_result(tool_name, result, duration_ms=duration_ms)
                return result
            except Exception as e:
                logger.tool_result(tool_name, None, error=str(e))
                raise
        
        @wraps(func)
        def sync_wrapper(tool_name: str, arguments: dict, *args, **kwargs):
            logger.tool_call(tool_name, arguments)
            try:
                import time
                start = time.time()
                result = func(tool_name, arguments, *args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                logger.tool_result(tool_name, result, duration_ms=duration_ms)
                return result
            except Exception as e:
                logger.tool_result(tool_name, None, error=str(e))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Global logger instance
_debug_logger = None

def get_debug_logger(name: str = "langgraph", log_dir: str = None) -> DebugLogger:
    """Get or create global debug logger instance."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugLogger(name, log_dir)
    return _debug_logger


# Convenience imports
__all__ = [
    "DebugLogger",
    "LogLevel",
    "get_debug_logger",
    "log_tool_call"
]