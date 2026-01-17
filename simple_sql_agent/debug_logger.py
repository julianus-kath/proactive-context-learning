"""
Debug Logger for SQL Agent.

Writes structured JSON events to a log file that can be tailed
by debug_stream.py for live monitoring.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

# Default log file - can be overridden via environment variable
DEFAULT_LOG_FILE = "/tmp/sql_agent_debug.jsonl"


class DebugLogger:
    """Writes structured debug events to a JSONL log file."""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or os.getenv("SQL_AGENT_DEBUG_LOG", DEFAULT_LOG_FILE)
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """Ensure the log directory exists."""
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _write(self, event: Dict[str, Any]):
        """Write event to log file."""
        event["timestamp"] = self._timestamp()
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")
                f.flush()
        except Exception:
            pass  # Don't crash on logging errors

    def query_start(self, question: str):
        """Log start of query processing."""
        self._write({
            "type": "query_start",
            "question": question,
        })

    def llm_start(self):
        """Log LLM call starting."""
        self._write({
            "type": "llm_start",
        })

    def llm_end(self, content: str = "", has_tool_calls: bool = False):
        """Log LLM call completed."""
        self._write({
            "type": "llm_end",
            "content": content[:500] if content else "",
            "has_tool_calls": has_tool_calls,
        })

    def tool_call(self, tool_name: str, tool_input: Dict[str, Any]):
        """Log tool being called."""
        self._write({
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_input": tool_input,
        })

    def tool_result(self, tool_name: str, output: Any):
        """Log tool result."""
        # Truncate large outputs
        if isinstance(output, str) and len(output) > 1000:
            output = output[:1000] + "..."
        self._write({
            "type": "tool_result",
            "tool_name": tool_name,
            "output": output,
        })

    def final_answer(self, answer: str, sql_query: Optional[str] = None,
                     latency_ms: int = 0, iterations: int = 0):
        """Log final answer."""
        self._write({
            "type": "final_answer",
            "answer": answer,
            "sql_query": sql_query,
            "latency_ms": latency_ms,
            "iterations": iterations,
        })

    def error(self, error: str):
        """Log error."""
        self._write({
            "type": "error",
            "error": error,
        })

    def clear(self):
        """Clear the log file (for fresh start)."""
        try:
            with open(self.log_file, "w") as f:
                pass
        except Exception:
            pass


# Global singleton instance
_debug_logger: Optional[DebugLogger] = None


def get_debug_logger() -> DebugLogger:
    """Get the global debug logger instance."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugLogger()
    return _debug_logger

