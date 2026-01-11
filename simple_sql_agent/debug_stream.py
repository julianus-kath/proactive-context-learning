"""
Debug Stream Viewer for Simple SQL Agent.

This script tails the agent's debug log file and displays events
in a formatted, colorized view. It does NOT run the agent - it only
observes the logs.

Usage:
    python debug_stream.py              # Watch default log file
    python debug_stream.py /path/to/log # Watch specific log file
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simple_sql_agent.agent import SQLAgentGraph

# Default log file location
DEFAULT_LOG_FILE = "/tmp/sql_agent_debug.jsonl"


class DebugStreamFormatter:
    """Formats and displays debug events from the log file."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.colors = {
            "RED": "\033[91m",
            "GREEN": "\033[92m",
            "YELLOW": "\033[93m",
            "BLUE": "\033[94m",
            "CYAN": "\033[96m",
            "GRAY": "\033[90m",
            "RESET": "\033[0m",
        }
        self.use_color = sys.stdout.isatty()

    def _styled(self, text: str, color: str) -> str:
        """Return colored text if terminal supports it."""
        if self.use_color:
            return f"{self.colors.get(color, '')}{text}{self.colors['RESET']}"
        return text

    def _line(self, char: str = "─", length: int = 80) -> str:
        return char * length

    def format_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Format a single event for display. Returns None to skip."""
        event_type = event.get("type", "unknown")
        timestamp = event.get("timestamp", "")

        if event_type == "query_start":
            question = event.get("question", "")
            return (
                f"\n{self._line('═')}\n"
                f"{self._styled('🔍 USER QUESTION', 'CYAN')} [{timestamp}]\n"
                f"{self._line('─')}\n"
                f"{question}\n"
                f"{self._line('═')}\n"
            )

        elif event_type == "tool_call":
            tool_name = event.get("tool_name", "unknown")
            tool_input = event.get("tool_input", {})
            lines = [
                f"\n{self._styled(f'🔧 TOOL CALL: {tool_name}', 'YELLOW')} [{timestamp}]",
                f"{self._line('┄', 60)}",
            ]
            if self.verbose and tool_input:
                lines.append("📥 Input:")
                lines.append(self._format_json(tool_input))
            return "\n".join(lines) + "\n"

        elif event_type == "tool_result":
            tool_name = event.get("tool_name", "unknown")
            output = event.get("output", "")
            lines = [
                f"{self._styled(f'✓ TOOL RESULT: {tool_name}', 'GREEN')} [{timestamp}]",
            ]
            if self.verbose:
                lines.append("📤 Output:")
                # Truncate long outputs
                if isinstance(output, str) and len(output) > 500:
                    output = output[:500] + "..."
                lines.append(self._format_json(output) if isinstance(output, dict) else f"  {output}")
            return "\n".join(lines) + "\n"

        elif event_type == "llm_start":
            return f"{self._styled('💭 LLM thinking...', 'BLUE')} [{timestamp}]\n"

        elif event_type == "llm_end":
            content = event.get("content", "")
            has_tool_calls = event.get("has_tool_calls", False)
            if has_tool_calls:
                return f"{self._styled('💭 LLM decided to use tools', 'BLUE')} [{timestamp}]\n"
            else:
                return (
                    f"{self._styled('💭 LLM response:', 'BLUE')} [{timestamp}]\n"
                    f"  {content[:200]}{'...' if len(content) > 200 else ''}\n"
                )

        elif event_type == "final_answer":
            answer = event.get("answer", "")
            sql = event.get("sql_query")
            latency = event.get("latency_ms", 0)
            iterations = event.get("iterations", 0)
            lines = [
                f"\n{self._line('═')}",
                f"{self._styled('✨ FINAL ANSWER', 'GREEN')} [{timestamp}]",
                f"{self._line('─')}",
                answer,
            ]
            if sql:
                lines.append(f"\n{self._styled('📋 SQL:', 'YELLOW')}")
                lines.append(sql)
            lines.append(f"\n{self._styled(f'⏱️  {latency}ms | {iterations} iterations', 'GRAY')}")
            lines.append(self._line('═'))
            return "\n".join(lines) + "\n"

        elif event_type == "error":
            error = event.get("error", "Unknown error")
            return (
                f"\n{self._line('═')}\n"
                f"{self._styled('❌ ERROR', 'RED')} [{timestamp}]\n"
                f"{self._line('─')}\n"
                f"{error}\n"
                f"{self._line('═')}\n"
            )

        # Skip unknown events
        return None

    def _format_json(self, obj: Any, max_lines: int = 15) -> str:
        """Format object as indented JSON with truncation."""
        try:
            if isinstance(obj, (dict, list)):
                text = json.dumps(obj, indent=2, default=str)
            else:
                text = str(obj)

            lines = text.split('\n')
            result = []
            for line in lines[:max_lines]:
                result.append(f"  {line}")
            if len(lines) > max_lines:
                result.append(f"  ... ({len(lines) - max_lines} more lines)")
            return "\n".join(result)
        except Exception:
            return f"  {str(obj)[:200]}"


def tail_log_file(log_file: str, formatter: DebugStreamFormatter):
    """
    Tail the log file and display formatted events.

    Similar to 'tail -f' but with formatting.
    """
    print(f"{formatter._styled('📡 Watching:', 'CYAN')} {log_file}")
    print(f"{formatter._styled('Press Ctrl+C to stop', 'GRAY')}\n")

    # Start from end of file if it exists
    try:
        with open(log_file, 'r') as f:
            f.seek(0, 2)  # Go to end

            while True:
                line = f.readline()
                if line:
                    try:
                        event = json.loads(line.strip())
                        formatted = formatter.format_event(event)
                        if formatted:
                            print(formatted, flush=True)
                    except json.JSONDecodeError:
                        # Not JSON, print raw
                        print(line.strip())
                else:
                    time.sleep(0.1)  # Wait for new content

    except FileNotFoundError:
        print(f"{formatter._styled('⏳ Waiting for log file...', 'YELLOW')}")
        # Wait for file to be created
        while not os.path.exists(log_file):
            time.sleep(0.5)
        # File exists now, start tailing
        tail_log_file(log_file, formatter)
    except KeyboardInterrupt:
        print(f"\n{formatter._styled('👋 Stopped watching', 'GRAY')}")


async def stream_agent_execution(
    agent: "SQLAgentGraph",
    question: str,
    max_iterations: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream agent execution events for HTTP clients.

    This function runs the agent and yields events in real-time,
    suitable for Server-Sent Events (SSE) streaming.

    Args:
        agent: The SQLAgentGraph instance
        question: User question to process
        max_iterations: Optional override for max LLM calls

    Yields:
        Dict events with type, content, and metadata
    """
    from langchain_core.messages import HumanMessage

    limit = max_iterations or getattr(agent, 'max_iterations', 15)

    initial_state = {
        "messages": [HumanMessage(content=question)],
    }

    config = {"recursion_limit": limit}

    sql_query = None
    iterations = 0
    start_time = time.time()

    try:
        # Yield start event
        yield {
            "type": "query_start",
            "question": question,
            "timestamp": datetime.now().isoformat(),
        }

        async for event in agent.graph.astream_events(
            initial_state,
            config=config,
            version="v2"
        ):
            event_type = event.get("event", "")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # LLM starts thinking
            if event_type == "on_chat_model_start":
                yield {
                    "type": "llm_start",
                    "timestamp": datetime.now().isoformat(),
                }

            # LLM finished
            elif event_type == "on_chat_model_end":
                iterations += 1
                output = event_data.get("output")
                if output and hasattr(output, "tool_calls") and output.tool_calls:
                    for tool_call in output.tool_calls:
                        tool_name = tool_call.get("name")
                        tool_input = tool_call.get("args", {})

                        yield {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "timestamp": datetime.now().isoformat(),
                        }

                        if tool_name == "execute_query":
                            sql_query = tool_input.get("sql")

                elif output and hasattr(output, "content") and output.content:
                    yield {
                        "type": "llm_response",
                        "content": output.content,
                        "timestamp": datetime.now().isoformat(),
                    }

            # Tool execution completes
            elif event_type == "on_tool_end":
                tool_output = event_data.get("output", "")

                # Extract content from ToolMessage if needed
                if hasattr(tool_output, "content"):
                    tool_output_str = tool_output.content
                else:
                    tool_output_str = str(tool_output) if tool_output else ""

                # Truncate large outputs
                if len(tool_output_str) > 1000:
                    tool_output_str = tool_output_str[:1000] + "..."

                yield {
                    "type": "tool_result",
                    "tool_name": event_name,
                    "output": tool_output_str,
                    "timestamp": datetime.now().isoformat(),
                }

        # Yield final event
        latency_ms = int((time.time() - start_time) * 1000)
        yield {
            "type": "complete",
            "sql_query": sql_query,
            "iterations": iterations,
            "latency_ms": latency_ms,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    """Main entry point."""
    # Get log file from args or use default
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        log_file = os.getenv("SQL_AGENT_DEBUG_LOG", DEFAULT_LOG_FILE)

    formatter = DebugStreamFormatter(verbose=True)
    tail_log_file(log_file, formatter)


if __name__ == "__main__":
    main()
