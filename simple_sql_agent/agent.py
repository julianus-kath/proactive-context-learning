"""
Simple SQL Agent using LangGraph.

A single ReAct agent with 6 tools for text-to-SQL conversion.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from simple_sql_agent.state import SQLAgentState
from simple_sql_agent.tools import list_tables, get_schema, get_column_index, discover_tables, execute_query
from simple_sql_agent.prompts import get_system_prompt, load_concepts
from simple_sql_agent.debug_logger import get_debug_logger

logger = logging.getLogger(__name__)


def parse_query_result(content: str) -> Dict[str, Any]:
    """
    Parse execute_query tool output into structured result.

    The tool output looks like:
    ```
    Query executed successfully in 19ms
    Returned 5 rows

    | product_name |
    |---|
    | Chai |
    | Chang |
    ...
    ```

    Returns:
        Dict with ok, rows, columns, row_count
    """
    result = {
        "ok": True,
        "rows": [],
        "data": [],
        "columns": [],
        "row_count": 0,
    }

    if not content:
        return result

    lines = content.strip().split('\n')

    # Check for error
    if "failed" in content.lower() or "error" in content.lower():
        result["ok"] = False
        result["error"] = content
        return result

    # Extract row count from "Returned X rows"
    for line in lines:
        if "Returned" in line and "row" in line:
            match = re.search(r'Returned (\d+) row', line)
            if match:
                result["row_count"] = int(match.group(1))
                break

    # Parse markdown table
    table_started = False
    header_parsed = False
    separator_seen = False

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Detect table header row (starts with |)
        if line.startswith('|') and not header_parsed:
            # Parse column names
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts and not all(p.replace('-', '') == '' for p in parts):
                result["columns"] = parts
                header_parsed = True
                table_started = True
            continue

        # Skip separator row (|---|---|)
        if line.startswith('|') and all(c in '|-' or c == ' ' for c in line.replace('|', '')):
            separator_seen = True
            continue

        # Parse data rows
        if table_started and separator_seen and line.startswith('|'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts and result["columns"]:
                # Create dict with column names
                row = {}
                for i, col in enumerate(result["columns"]):
                    row[col] = parts[i] if i < len(parts) else ""
                result["rows"].append(row)
                result["data"].append(row)

    # If we couldn't parse row_count from text, use parsed rows
    if result["row_count"] == 0 and result["rows"]:
        result["row_count"] = len(result["rows"])

    return result


class SQLAgentGraph:
    """
    Simple SQL Agent using LangGraph's ReAct pattern.

    This replaces the complex 8-agent system with a single ReAct agent
    that has 6 tools: list_tables, search_tables, get_schema, get_column_index,
    validate_sql, execute_query.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        concepts_path: Optional[str] = None,
        max_iterations: int = 15,
    ):
        """
        Initialize the SQL agent.

        Args:
            model_name: OpenAI model to use
            temperature: LLM temperature (0 = deterministic)
            concepts_path: Path to concepts.json for domain knowledge
            max_iterations: Max LLM calls per query (default: 15)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_iterations = max_iterations

        # Load domain concepts
        self.concepts = load_concepts(concepts_path)
        logger.info(f"Loaded {len(self.concepts)} domain concepts")

        # Initialize LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
        )

        # Build the agent graph
        self.graph = self._build_graph()
        logger.info("SQLAgentGraph initialized successfully")

    def _build_graph(self):
        """
        Build the LangGraph agent.

        Uses create_react_agent for a simple Think -> Act -> Observe loop.
        """
        # Tools: discover_tables is primary for comprehensive discovery
        # get_column_index for verifying exact column names
        # list_tables, get_schema for fallback/detailed info
        tools = [discover_tables, list_tables, get_schema, get_column_index, execute_query]

        # Get system prompt with domain knowledge
        system_prompt = get_system_prompt(self.concepts)

        # Create the ReAct agent with system prompt as first message
        # In newer LangGraph versions, use 'prompt' parameter
        agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )

        return agent

    def _convert_messages(self, messages: List[Dict]) -> List:
        """
        Convert frontend message format to LangChain messages.

        Args:
            messages: List of dicts with 'role' and 'content' keys

        Returns:
            List of LangChain message objects
        """
        result = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
        return result

    async def arun(self, input: Union[str, List[Dict]], max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the agent on a user question or conversation.

        Args:
            input: Either a single question string OR list of message dicts [{role, content}]
            max_iterations: Override max LLM calls for this query (uses self.max_iterations if None)

        Returns:
            Dict with answer, sql_query (if any), and metadata
        """
        import time
        start_time = time.time()

        # Handle both single question and conversation formats
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
            question = input
        else:
            messages = self._convert_messages(input)
            # Extract last user message for logging
            question = ""
            for msg in reversed(input):
                if msg.get("role") == "user":
                    question = msg.get("content", "")
                    break

        limit = max_iterations or self.max_iterations
        logger.info(f"Processing question: {question[:100]}... (max_iterations={limit})")

        # Get debug logger for live logging
        debug_log = get_debug_logger()
        debug_log.query_start(question)

        # Create initial state with full message history
        initial_state = {
            "messages": messages,
        }

        try:
            config = {"recursion_limit": limit}

            # Track state during streaming
            final_answer = ""
            sql_query = None
            exec_result = None
            iterations = 0
            last_tool_input = {}

            # Use astream_events for real-time logging
            async for event in self.graph.astream_events(
                initial_state,
                config=config,
                version="v2"
            ):
                event_type = event.get("event", "")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # LLM starts thinking
                if event_type == "on_chat_model_start":
                    debug_log.llm_start()

                # LLM finished - check for tool calls or final answer
                elif event_type == "on_chat_model_end":
                    iterations += 1
                    output = event_data.get("output")
                    if output and hasattr(output, "tool_calls") and output.tool_calls:
                        debug_log.llm_end(has_tool_calls=True)
                        for tool_call in output.tool_calls:
                            tool_name = tool_call.get("name")
                            tool_input = tool_call.get("args", {})
                            last_tool_input[tool_name] = tool_input
                            debug_log.tool_call(tool_name, tool_input)

                            if tool_name == "execute_query":
                                sql_query = tool_input.get("sql")
                    elif output and hasattr(output, "content") and output.content:
                        final_answer = output.content
                        debug_log.llm_end(content=final_answer, has_tool_calls=False)

                # Tool execution completes
                elif event_type == "on_tool_end":
                    tool_output = event_data.get("output", "")

                    # Extract content from ToolMessage if needed
                    if hasattr(tool_output, "content"):
                        tool_output_str = tool_output.content
                    else:
                        tool_output_str = str(tool_output) if tool_output else ""

                    debug_log.tool_result(event_name, tool_output_str)

                    # Parse execute_query results
                    if event_name == "execute_query" and tool_output_str:
                        exec_result = parse_query_result(tool_output_str)
                        if sql_query:
                            exec_result["sql_query"] = sql_query

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log final result
            debug_log.final_answer(
                answer=final_answer,
                sql_query=sql_query,
                latency_ms=latency_ms,
                iterations=iterations
            )

            return {
                "answer": final_answer,
                "sql_query": sql_query,
                "exec_result": exec_result,
                "success": True,
                "message_count": iterations,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            debug_log.error(str(e))
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}",
                "sql_query": None,
                "success": False,
                "error": str(e),
            }

    def run(self, question: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for arun().

        Args:
            question: Natural language question

        Returns:
            Dict with answer and metadata
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.arun(question))
                    return future.result(timeout=120)
            else:
                return loop.run_until_complete(self.arun(question))
        except RuntimeError:
            return asyncio.run(self.arun(question))


# Factory function for easy creation
def create_sql_agent(
    model_name: str = "gpt-4o",
    temperature: float = 0.0,
    concepts_path: Optional[str] = None,
    max_iterations: int = 15,
) -> SQLAgentGraph:
    """
    Create a new SQL agent instance.

    Args:
        model_name: OpenAI model to use (default: gpt-4o)
        temperature: LLM temperature (default: 0.0 for deterministic)
        concepts_path: Path to concepts.json (optional, uses default)
        max_iterations: Max LLM calls per query (default: 15)

    Returns:
        SQLAgentGraph instance
    """
    return SQLAgentGraph(
        model_name=model_name,
        temperature=temperature,
        concepts_path=concepts_path,
        max_iterations=max_iterations,
    )


# For testing
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Create agent
    agent = create_sql_agent()

    # Test question
    question = "How many customers do we have?"

    # Run
    result = asyncio.run(agent.arun(question))

    print("\n" + "=" * 50)
    print("QUESTION:", question)
    print("=" * 50)
    print("ANSWER:", result["answer"])
    if result.get("sql_query"):
        print("SQL:", result["sql_query"])
    print("SUCCESS:", result["success"])
