"""
Debug Stream for Simple SQL Agent.

Provides real-time streaming of agent execution logs, showing:
- User questions
- SQL queries generated
- Agent input/output at each step
- Tool calls and results
"""

import logging
import json
import sys
from typing import Any, Dict, AsyncGenerator, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DebugStreamFormatter:
    """Formats and outputs detailed debug stream information."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.step_count = 0

    def _format_timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def log_query_start(self, question: str) -> None:
        """Log the start of query processing."""
        self._print_line("═")
        self._print_styled("🔍 USER QUESTION", "CYAN")
        self._print_line("─")
        print(question)
        self._print_line("═")
        print()

    def log_node_entry(self, node_name: str, input_state: Dict[str, Any]) -> None:
        """Log agent entry to a processing node."""
        self._print_styled(f"➡️  ENTRY: {node_name}", "BLUE")
        self._print_line("┄", length=60)
        
        if self.verbose and input_state:
            print("📥 Input State:")
            self._print_json_safe(input_state, indent=2, max_lines=15)
        print()

    def log_node_exit(self, node_name: str, output_state: Dict[str, Any]) -> None:
        """Log agent exit from a processing node."""
        self._print_styled(f"⬅️  EXIT: {node_name}", "GREEN")
        self._print_line("┄", length=60)
        
        if self.verbose and output_state:
            print("📤 Output State:")
            self._print_json_safe(output_state, indent=2, max_lines=15)
        print()

    def log_tool_execution(self, tool_name: str, tool_input: Dict[str, Any], tool_output: Any) -> None:
        """Log tool execution with input and output."""
        self._print_styled(f"🔧 TOOL: {tool_name}", "YELLOW")
        self._print_line("┄", length=60)
        
        print("📥 Input:")
        self._print_json_safe(tool_input, indent=2, max_lines=10)
        
        print("\n📤 Output:")
        self._print_json_safe(tool_output, indent=2, max_lines=20)
        print()

    def log_sql_generated(self, sql: str) -> None:
        """Log generated SQL query."""
        self._print_styled("📝 SQL GENERATED", "YELLOW")
        self._print_line("┄", length=60)
        print(sql)
        print()

    def log_sql_execution_result(self, sql: str, row_count: int, rows: list) -> None:
        """Log SQL execution result."""
        self._print_styled("🗄️  SQL EXECUTION RESULT", "YELLOW")
        self._print_line("┄", length=60)
        print(f"Query: {sql[:100]}...")
        print(f"Rows: {row_count}")
        if rows:
            print("First row:")
            self._print_json_safe(rows[0], indent=2, max_lines=10)
        print()

    def log_agent_thought(self, thought: str) -> None:
        """Log agent thought/reasoning."""
        self._print_styled("💭 AGENT THOUGHT", "BLUE")
        self._print_line("┄", length=60)
        print(thought)
        print()

    def log_final_answer(self, answer: str, sql_query: Optional[str] = None, latency_ms: int = 0) -> None:
        """Log the final answer."""
        self._print_line("═")
        self._print_styled("✨ FINAL ANSWER", "GREEN")
        self._print_line("─")
        print(answer)
        if sql_query:
            print()
            self._print_styled("📋 SQL EXECUTED", "YELLOW")
            print(sql_query)
        print()
        self._print_styled(f"⏱️  Latency: {latency_ms}ms", "GRAY")
        self._print_line("═")
        print()

    def log_error(self, error: str) -> None:
        """Log an error."""
        self._print_line("═")
        self._print_styled("❌ ERROR", "RED")
        self._print_line("─")
        print(error)
        self._print_line("═")
        print()

    def _print_json_safe(self, obj: Any, indent: int = 2, max_lines: int = 20) -> None:
        """Safely print JSON with truncation."""
        try:
            if isinstance(obj, (dict, list)):
                text = json.dumps(obj, indent=indent, default=str)
            else:
                text = str(obj)
            
            lines = text.split('\n')
            for i, line in enumerate(lines[:max_lines]):
                print(f"  {line}")
            
            if len(lines) > max_lines:
                print(f"  ... ({len(lines) - max_lines} more lines)")
        except Exception as e:
            print(f"  {str(obj)[:200]}")

    def _print_line(self, char: str = "─", length: int = 80) -> None:
        """Print a decorative line."""
        print(char * length)

    def _print_styled(self, text: str, color: str) -> None:
        """Print colored text if terminal supports it."""
        colors = {
            "RED": "\033[91m",
            "GREEN": "\033[92m",
            "YELLOW": "\033[93m",
            "BLUE": "\033[94m",
            "CYAN": "\033[96m",
            "GRAY": "\033[90m",
            "RESET": "\033[0m",
        }
        if sys.stdout.isatty():
            print(f"{colors.get(color, '')}{text}{colors['RESET']}")
        else:
            print(text)


async def stream_agent_execution(
    agent: "SQLAgentGraph",
    question: str,
    debug_formatter: Optional[DebugStreamFormatter] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream agent execution events with detailed logging.

    Yields events with the following structure:
    {
        "type": "node_entry|node_exit|tool_call|tool_result|thought|sql_execution|final_answer|error",
        "timestamp": "HH:MM:SS.mmm",
        "data": {...}
    }
    """
    if debug_formatter is None:
        debug_formatter = DebugStreamFormatter()

    debug_formatter.log_query_start(question)

    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    import time

    start_time = time.time()
    step_count = 0
    last_tool_name = None
    last_tool_input = None

    try:
        initial_state = {
            "messages": [HumanMessage(content=question)],
        }

        debug_formatter.log_node_entry("ReActAgent", initial_state)
        yield {
            "type": "node_entry",
            "timestamp": debug_formatter._format_timestamp(),
            "node": "ReActAgent",
            "input_state": initial_state,
        }

        config = {"recursion_limit": 50}
        result = await agent.graph.ainvoke(initial_state, config=config)

        messages = result.get("messages", [])

        debug_formatter.log_node_exit("ReActAgent", {"message_count": len(messages)})
        yield {
            "type": "node_exit",
            "timestamp": debug_formatter._format_timestamp(),
            "node": "ReActAgent",
            "output_state": {"message_count": len(messages)},
        }

        for i, msg in enumerate(messages):
            if isinstance(msg, AIMessage):
                step_count += 1

                if msg.content:
                    debug_formatter.log_agent_thought(msg.content)
                    yield {
                        "type": "thought",
                        "timestamp": debug_formatter._format_timestamp(),
                        "step": step_count,
                        "content": msg.content,
                    }

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.get("name", "unknown")
                        tool_input = tool_call.get("args", {})
                        last_tool_name = tool_name
                        last_tool_input = tool_input

                        debug_formatter.log_node_entry(f"Tool:{tool_name}", {"input": tool_input})
                        yield {
                            "type": "tool_entry",
                            "timestamp": debug_formatter._format_timestamp(),
                            "step": step_count,
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        }

            elif isinstance(msg, ToolMessage):
                tool_name = msg.name if hasattr(msg, "name") else "tool"
                content = msg.content if hasattr(msg, "content") else str(msg)

                tool_output = content
                try:
                    if isinstance(content, str):
                        tool_output = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    tool_output = content

                debug_formatter.log_tool_execution(tool_name, last_tool_input or {}, tool_output)
                yield {
                    "type": "tool_result",
                    "timestamp": debug_formatter._format_timestamp(),
                    "tool_name": tool_name,
                    "tool_output": tool_output,
                }

                if tool_name == "execute_query":
                    if isinstance(tool_output, dict) and "rows" in tool_output:
                        row_count = len(tool_output.get("rows", []))
                        rows = tool_output.get("rows", [])
                        sql = tool_output.get("sql", last_tool_input.get("sql") if last_tool_input else None)
                        
                        if sql:
                            debug_formatter.log_sql_execution_result(sql, row_count, rows)
                            yield {
                                "type": "sql_execution",
                                "timestamp": debug_formatter._format_timestamp(),
                                "sql": sql,
                                "row_count": row_count,
                                "rows": rows[:5],
                            }

                debug_formatter.log_node_exit(f"Tool:{tool_name}", {"output_rows": len(tool_output) if isinstance(tool_output, list) else 1})
                yield {
                    "type": "tool_exit",
                    "timestamp": debug_formatter._format_timestamp(),
                    "tool_name": tool_name,
                }

        final_message = messages[-1] if messages else None
        final_answer = ""
        if final_message:
            final_answer = getattr(final_message, "content", str(final_message))

        sql_query = None
        for msg in messages:
            if hasattr(msg, "tool_calls"):
                for call in msg.tool_calls:
                    if call.get("name") == "execute_query":
                        args = call.get("args", {})
                        sql_query = args.get("sql", sql_query)

        latency_ms = int((time.time() - start_time) * 1000)

        debug_formatter.log_final_answer(final_answer, sql_query, latency_ms)

        yield {
            "type": "final_answer",
            "timestamp": debug_formatter._format_timestamp(),
            "answer": final_answer,
            "sql_query": sql_query,
            "latency_ms": latency_ms,
            "success": True,
            "step_count": step_count,
        }

    except Exception as e:
        error_msg = str(e)
        debug_formatter.log_error(error_msg)
        yield {
            "type": "error",
            "timestamp": debug_formatter._format_timestamp(),
            "error": error_msg,
            "success": False,
        }


async def debug_stream_cli(agent: "SQLAgentGraph", question: str) -> None:
    """
    Run the debug stream from command line.

    This provides a nice interactive view of agent execution.
    """
    formatter = DebugStreamFormatter(verbose=True)

    async for event in stream_agent_execution(agent, question, formatter):
        pass
