"""
Simple SQL Agent using LangGraph.

A single ReAct agent with 6 tools for text-to-SQL conversion.
"""

import json
import logging
import os
import re
from collections import defaultdict
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

    # Check for error (English and German keywords)
    content_lower = content.lower()
    error_keywords = ["failed", "error", "fehler", "fehlgeschlagen", "ungültig", "nicht gefunden"]
    if any(kw in content_lower for kw in error_keywords):
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


def _normalize_table_name(name: str) -> str:
    """Normalize table names for stable comparisons across schema-qualified formats."""
    if not isinstance(name, str):
        return ""
    cleaned = name.strip().lower().replace("[", "").replace("]", "").replace('"', "")
    if not cleaned:
        return ""
    # Keep only the last two parts to normalize db.schema.table -> schema.table
    parts = [p for p in cleaned.split(".") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return parts[-1] if parts else ""


def _extract_tables_from_sql(sql: Optional[str]) -> List[str]:
    """Extract table names from FROM/JOIN clauses."""
    if not isinstance(sql, str) or not sql.strip():
        return []
    pattern = r"(?:FROM|JOIN)\s+([a-zA-Z0-9_\.\"`\[\]]+)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    unique: List[str] = []
    seen = set()
    for raw in matches:
        normalized = _normalize_table_name(raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _extract_json_from_tool_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON payloads embedded in MCP text responses."""
    if not isinstance(text, str) or not text.strip():
        return None
    candidates = [text.strip()]
    marker = "Full response (JSON):"
    if marker in text:
        candidates.append(text.split(marker, 1)[-1].strip())
    # Last-resort brace slicing
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1].strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue
    return None


def _extract_discovery_tables(tool_output: str) -> List[Dict[str, Any]]:
    """
    Parse discovery/search tool outputs into ranked table candidates.

    Returns list of {"name": str, "relevance": float|None}.
    """
    if not isinstance(tool_output, str):
        return []

    extracted: List[Dict[str, Any]] = []
    seen = set()

    payload = _extract_json_from_tool_text(tool_output)
    if payload and isinstance(payload.get("data"), dict):
        for item in payload["data"].get("results", []):
            if not isinstance(item, dict):
                continue
            name = item.get("full_name") or item.get("name")
            normalized = _normalize_table_name(name or "")
            if not normalized or normalized in seen:
                continue
            score = item.get("relevance_score")
            try:
                score = float(score) if score is not None else None
            except Exception:
                score = None
            extracted.append({"name": normalized, "relevance": score})
            seen.add(normalized)

    # Fallback parsing from human-readable discovery output.
    if not extracted:
        for line in tool_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # discover_tables tool format: "### public.orders (relevance: 0.92, ~830 rows)"
            match = re.match(r"^###\s+([^\s(]+)\s+\(relevance:\s*([0-9]*\.?[0-9]+)", stripped, re.IGNORECASE)
            if match:
                normalized = _normalize_table_name(match.group(1))
                if normalized and normalized not in seen:
                    extracted.append({"name": normalized, "relevance": float(match.group(2))})
                    seen.add(normalized)
                continue
            # search_tables Scout format: "1. public.orders" or "• public.orders (...)"
            bullet_match = re.match(r"^(?:\d+\.\s+|•\s+)([a-zA-Z0-9_\.\"`\[\]]+)", stripped)
            if bullet_match:
                normalized = _normalize_table_name(bullet_match.group(1))
                if normalized and normalized not in seen:
                    extracted.append({"name": normalized, "relevance": None})
                    seen.add(normalized)

    return extracted


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

    async def arun(
        self,
        input: Union[str, List[Dict]],
        max_iterations: Optional[int] = None,
        query_contract: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            sql_history: List[str] = []
            retrieval_log: List[Dict[str, Any]] = []
            retrieved_candidates: List[Dict[str, Any]] = []
            tool_call_counts: Dict[str, int] = defaultdict(int)
            execute_query_calls = 0
            llm_discovery_turns = 0
            llm_join_turns = 0
            llm_answer_turns = 0
            discovery_tools = {
                "discover_tables",
                "search_tables",
                "list_tables",
                "get_schema",
                "get_column_index",
            }

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
                        has_discovery_turn = False
                        has_join_turn = False
                        debug_log.llm_end(has_tool_calls=True)
                        for tool_call in output.tool_calls:
                            tool_name = tool_call.get("name")
                            tool_input = tool_call.get("args", {})
                            last_tool_input[tool_name] = tool_input
                            tool_call_counts[tool_name] += 1
                            debug_log.tool_call(tool_name, tool_input)

                            if tool_name in discovery_tools:
                                has_discovery_turn = True
                            if tool_name == "execute_query":
                                has_join_turn = True
                                sql_query = tool_input.get("sql")
                                if isinstance(sql_query, str) and sql_query.strip():
                                    sql_history.append(sql_query)
                        if has_discovery_turn:
                            llm_discovery_turns += 1
                        if has_join_turn:
                            llm_join_turns += 1
                    elif output and hasattr(output, "content") and output.content:
                        final_answer = output.content
                        llm_answer_turns += 1
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

                    if event_name in discovery_tools:
                        tool_input = last_tool_input.get(event_name, {})
                        discovery_query = ""
                        if isinstance(tool_input, dict):
                            discovery_query = str(tool_input.get("query") or "")
                        extracted = _extract_discovery_tables(tool_output_str)
                        if extracted:
                            retrieved_candidates.extend(extracted)
                        retrieval_log.append(
                            {
                                "tool_name": event_name,
                                "query": discovery_query,
                                "top_tables": [row["name"] for row in extracted[:5]],
                                "table_scores": extracted[:5],
                            }
                        )

                    # Parse execute_query results
                    if event_name == "execute_query" and tool_output_str:
                        execute_query_calls += 1
                        exec_result = parse_query_result(tool_output_str)
                        if sql_query:
                            exec_result["sql_query"] = sql_query

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Consolidate retrieved top-k tables by best relevance score
            best_scores: Dict[str, float] = {}
            for candidate in retrieved_candidates:
                table_name = _normalize_table_name(candidate.get("name", ""))
                if not table_name:
                    continue
                score = candidate.get("relevance")
                try:
                    score_value = float(score) if score is not None else 0.0
                except Exception:
                    score_value = 0.0
                if table_name not in best_scores or score_value > best_scores[table_name]:
                    best_scores[table_name] = score_value

            retrieved_tables_topk = [
                name
                for name, _ in sorted(best_scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
            ]
            if not retrieved_tables_topk and sql_query:
                retrieved_tables_topk = _extract_tables_from_sql(sql_query)[:5]

            same_tables_suppressed = 0
            previous_tables: List[str] = []
            for entry in retrieval_log:
                tables = entry.get("top_tables") or []
                if tables and previous_tables and tables == previous_tables:
                    same_tables_suppressed += 1
                if tables:
                    previous_tables = tables

            seen_sql = set()
            same_sql_suppressed = 0
            for statement in sql_history:
                normalized_sql = " ".join(statement.lower().split())
                if normalized_sql in seen_sql:
                    same_sql_suppressed += 1
                else:
                    seen_sql.add(normalized_sql)

            discovery_entries = sum(tool_call_counts.get(name, 0) for name in discovery_tools)
            llm_usage = {
                "total": iterations,
                "intent": 0,
                "discovery": llm_discovery_turns,
                "join": llm_join_turns,
                "repair": max(0, execute_query_calls - 1),
                "answer": llm_answer_turns,
            }
            node_entry_counts = {
                "discovery": discovery_entries,
                "join_sql": execute_query_calls,
            }
            loop_events = {
                "discovery_reentered_same_tables": same_tables_suppressed,
                "join_sql_regenerated_same_sql": same_sql_suppressed,
            }

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
                "llm_usage": llm_usage,
                "node_entry_counts": node_entry_counts,
                "loop_events": loop_events,
                "total_llm_calls": iterations,
                "total_graph_cycles": iterations,
                "retrieval_log": retrieval_log,
                "retrieved_tables_topk": retrieved_tables_topk,
                "tool_call_counts": dict(tool_call_counts),
                "query_contract": query_contract,
                "model_name": self.model_name,
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            debug_log.error(str(e))
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}",
                "sql_query": None,
                "success": False,
                "error": str(e),
                "llm_usage": {"total": 0, "intent": 0, "discovery": 0, "join": 0, "repair": 0, "answer": 0},
                "node_entry_counts": {"discovery": 0, "join_sql": 0},
                "loop_events": {
                    "discovery_reentered_same_tables": 0,
                    "join_sql_regenerated_same_sql": 0,
                },
                "total_llm_calls": 0,
                "total_graph_cycles": 0,
                "retrieval_log": [],
                "retrieved_tables_topk": [],
                "model_name": self.model_name,
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
