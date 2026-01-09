"""
Simple SQL Agent using LangGraph.

A single ReAct agent with 5 tools for text-to-SQL conversion.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from simple_sql_agent.state import SQLAgentState
from simple_sql_agent.tools import list_tables, get_schema, search_tables, validate_sql, execute_query
from simple_sql_agent.prompts import get_system_prompt, load_concepts

logger = logging.getLogger(__name__)


class SQLAgentGraph:
    """
    Simple SQL Agent using LangGraph's ReAct pattern.

    This replaces the complex 8-agent system with a single ReAct agent
    that has 5 tools: list_tables, get_schema, search_tables, validate_sql, execute_query.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        concepts_path: Optional[str] = None,
    ):
        """
        Initialize the SQL agent.

        Args:
            model_name: OpenAI model to use
            temperature: LLM temperature (0 = deterministic)
            concepts_path: Path to concepts.json for domain knowledge
        """
        self.model_name = model_name
        self.temperature = temperature

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
        # Define tools - search_tables is key for exploration
        tools = [list_tables, search_tables, get_schema, validate_sql, execute_query]

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

    async def arun(self, question: str) -> Dict[str, Any]:
        """
        Run the agent on a user question.

        Args:
            question: Natural language question about the database

        Returns:
            Dict with answer, sql_query (if any), and metadata
        """
        logger.info(f"Processing question: {question[:100]}...")

        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=question)],
        }

        try:
            # Run the agent with increased recursion limit for complex queries
            config = {"recursion_limit": 50}
            result = await self.graph.ainvoke(initial_state, config=config)

            # Extract the final answer from messages
            messages = result.get("messages", [])
            final_message = messages[-1] if messages else None

            answer = ""
            if final_message:
                answer = getattr(final_message, "content", str(final_message))

            # Try to extract SQL from tool calls
            sql_query = None
            for msg in messages:
                if hasattr(msg, "tool_calls"):
                    for call in msg.tool_calls:
                        if call.get("name") == "execute_query":
                            args = call.get("args", {})
                            sql_query = args.get("sql", sql_query)

            return {
                "answer": answer,
                "sql_query": sql_query,
                "success": True,
                "message_count": len(messages),
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
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
) -> SQLAgentGraph:
    """
    Create a new SQL agent instance.

    Args:
        model_name: OpenAI model to use (default: gpt-4o)
        temperature: LLM temperature (default: 0.0 for deterministic)
        concepts_path: Path to concepts.json (optional, uses default)

    Returns:
        SQLAgentGraph instance
    """
    return SQLAgentGraph(
        model_name=model_name,
        temperature=temperature,
        concepts_path=concepts_path,
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
