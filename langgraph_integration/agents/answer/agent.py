"""
AnswerAgent - Formats results and prepares final responses.

This agent handles the final output phase:
1. Format query results as natural language (1-2 sentences)
2. Explain schema for schema queries
3. Clarify ambiguous queries
4. Report health status
5. Present errors helpfully
"""

import json
import logging
from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, AnswerAgentInput, AnswerAgentOutput
from langgraph_integration.prompts.answer import (
    RESULT_FORMATTER_PROMPT,
    SCHEMA_EXPLAINER_PROMPT,
    CLARIFICATION_PROMPT,
    ERROR_RESPONSE_PROMPT,
    HEALTH_CHECK_RESPONSE
)

logger = logging.getLogger(__name__)


class AnswerAgent:
    """
    Agent for formatting and presenting final answers.
    
    Input contract: {user_input, exec_result, error_info, schema_snippet, intent, sql_query}
    Output contract: {final_response}
    """

    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        """
        Initialize AnswerAgent.
        
        Args:
            llm_model: LLM model name for response formatting
            llm_temp: Temperature for LLM (0.0 = deterministic)
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)

    async def build_subgraph(self) -> StateGraph:
        """
        Build the LangGraph subgraph for answer formatting.
        
        Nodes:
        - route_by_intent: Route to appropriate formatter (result/schema/error/clarify)
        - format_result: Format successful query results
        - explain_schema: Explain database schema
        - format_error: Format error message
        - format_clarification: Ask clarification question
        - format_health: Format health check response
        
        Returns:
            Compiled LangGraph subgraph
        """
        graph = StateGraph(BaseState)

        # Define nodes
        graph.add_node("route_by_intent", self._route_by_intent_node)
        graph.add_node("format_result", self._format_result_node)
        graph.add_node("explain_schema", self._explain_schema_node)
        graph.add_node("format_error", self._format_error_node)
        graph.add_node("format_clarification", self._format_clarification_node)
        graph.add_node("format_health", self._format_health_node)

        # Define edges and conditional routing
        graph.add_edge("route_by_intent", "format_result")  # Default
        
        # Note: Actual routing is done in _route_by_intent_node by returning different state
        graph.add_edge("format_result", END)
        graph.add_edge("explain_schema", END)
        graph.add_edge("format_error", END)
        graph.add_edge("format_clarification", END)
        graph.add_edge("format_health", END)

        # Set entry point
        graph.set_entry_point("route_by_intent")

        return graph.compile()

    async def _route_by_intent_node(self, state: BaseState) -> BaseState:
        """
        Route to appropriate formatter based on intent or state.
        
        Routes:
        - If error_info: format_error
        - If exec_result with rows: format_result
        - If intent.operation == schema_query: explain_schema
        - If intent.operation == clarify: format_clarification
        - If intent.operation == health_check: format_health
        """
        logger.info("🎯 AnswerAgent: Routing to formatter...")

        intent = state.get("intent", {})
        operation = intent.get("operation", "query")
        error_info = state.get("error_info")
        exec_result = state.get("exec_result")

        # Determine which formatter to use
        if error_info and error_info.get("type"):
            # Route to error formatter
            return await self._format_error_node(state)
        elif operation == "clarify":
            return await self._format_clarification_node(state)
        elif operation == "schema_query":
            return await self._explain_schema_node(state)
        elif operation == "health_check":
            return await self._format_health_node(state)
        else:
            # Default: format result
            return await self._format_result_node(state)

    async def _format_result_node(self, state: BaseState) -> BaseState:
        """
        Format successful query results as natural language.
        
        Output: 1-2 sentences maximum, NO technical jargon.
        """
        logger.info("✨ Formatting query result...")

        user_input = state.get("user_input", "")
        exec_result = state.get("exec_result", {})
        sql_query = state.get("sql_query", "")

        if not exec_result or not exec_result.get("ok"):
            # No results - fallback
            error_type = (state.get("error_info") or {}).get("type", "NO_RESULTS")
            if error_type == "NO_RESULTS":
                response = "No records found matching your criteria. Try adjusting your filters."
            else:
                response = "Query did not return results."
            logger.info(f"  No results: {response}")
            state["final_response"] = response
            return state

        try:
            rows = exec_result.get("rows", [])
            row_count = exec_result.get("row_count", len(rows))

            # Prepare results for LLM
            results_json = json.dumps(rows[:10], default=str)  # Limit to 10 rows for context
            truncated = exec_result.get("truncated", False)

            # Build formatter prompt
            format_prompt = RESULT_FORMATTER_PROMPT.format(
                user_input=user_input,
                sql_query=sql_query,
                results_json=results_json
            )

            logger.debug(f"  Formatting {row_count} row(s)...")

            # Call LLM to format
            response = await self.llm.ainvoke(format_prompt)
            formatted = response.content.strip()

            # Add truncation note if applicable
            if truncated:
                formatted += " (showing first 1000 rows)"

            logger.info(f"✅ Result formatted")
            logger.debug(f"  Response: {formatted[:100]}...")

            state["final_response"] = formatted
            return state

        except Exception as e:
            logger.error(f"❌ Failed to format result: {e}")
            # Fallback to simple summary
            row_count = exec_result.get("row_count", 0)
            fallback = f"Query returned {row_count} record(s)."
            state["final_response"] = fallback
            return state

    async def _explain_schema_node(self, state: BaseState) -> BaseState:
        """
        Explain database schema to user.
        
        Output: 1-2 sentences listing main tables, no technical details.
        """
        logger.info("📚 Explaining schema...")

        user_input = state.get("user_input", "")
        schema_snippet = state.get("schema_snippet", "")

        if not schema_snippet:
            response = "No schema information available."
            state["final_response"] = response
            return state

        try:
            # Build prompt
            explain_prompt = SCHEMA_EXPLAINER_PROMPT.format(
                schema_snippet=schema_snippet,
                user_input=user_input
            )

            logger.debug("  Calling LLM for schema explanation...")

            # Call LLM
            response = await self.llm.ainvoke(explain_prompt)
            explanation = response.content.strip()

            logger.info(f"✅ Schema explained")
            state["final_response"] = explanation
            return state

        except Exception as e:
            logger.error(f"❌ Failed to explain schema: {e}")
            # Fallback: just list table names
            try:
                tables = [line.split(":")[0].strip() for line in schema_snippet.split("\n") if ":" in line]
                fallback = f"Main tables: {', '.join(tables[:5])}."
                state["final_response"] = fallback
                return state
            except:
                state["final_response"] = schema_snippet[:200]
                return state

    async def _format_error_node(self, state: BaseState) -> BaseState:
        """
        Format error message for user.
        
        Output: 1-2 sentences, problem + suggestion.
        """
        logger.info("⚠️  Formatting error response...")

        user_input = state.get("user_input", "")
        error_info = state.get("error_info", {})

        if not error_info:
            response = "An error occurred. Please try again."
            state["final_response"] = response
            return state

        try:
            error_type = error_info.get("type", "UNKNOWN")
            error_message = error_info.get("message", "Unknown error")
            suggestion = error_info.get("suggestion", "")

            # Build prompt
            error_prompt = ERROR_RESPONSE_PROMPT.format(
                error_type=error_type,
                error_message=error_message,
                context=json.dumps(error_info.get("context", {})),
                user_input=user_input
            )

            logger.debug(f"  Error type: {error_type}")

            # Call LLM
            response = await self.llm.ainvoke(error_prompt)
            formatted_error = response.content.strip()

            logger.info(f"✅ Error formatted")
            state["final_response"] = formatted_error
            return state

        except Exception as e:
            logger.warning(f"⚠️  Failed to format error: {e}")
            # Fallback to simple message
            fallback = error_info.get("message", "An error occurred. Please try again.")
            if error_info.get("suggestion"):
                fallback += f" {error_info['suggestion']}"
            state["final_response"] = fallback
            return state

    async def _format_clarification_node(self, state: BaseState) -> BaseState:
        """
        Ask clarification question when intent is ambiguous.
        
        Output: Exactly ONE question, grounded in real column names.
        """
        logger.info("❓ Asking for clarification...")

        user_input = state.get("user_input", "")
        schema_snippet = state.get("schema_snippet", "")
        messages = state.get("messages", [])
        intent = state.get("intent", {})

        if not schema_snippet:
            response = "Could you clarify what information you're looking for?"
            state["final_response"] = response
            return state

        try:
            # Build prompt
            clarify_prompt = CLARIFICATION_PROMPT.format(
                user_input=user_input,
                schema_snippet=schema_snippet,
                messages=json.dumps(messages[-5:], default=str)  # Last 5 messages for context
            )

            logger.debug("  Calling LLM for clarification...")

            # Call LLM
            response = await self.llm.ainvoke(clarify_prompt)
            question = response.content.strip()

            logger.info(f"✅ Clarification question generated")
            state["final_response"] = question
            return state

        except Exception as e:
            logger.warning(f"⚠️  Failed to generate clarification: {e}")
            # Fallback to generic question
            fallback = "Could you provide more details about what you're looking for?"
            state["final_response"] = fallback
            return state

    async def _format_health_node(self, state: BaseState) -> BaseState:
        """
        Format health check response.
        
        Output: System status + basic info (tables count, DB connected, etc).
        """
        logger.info("🏥 Formatting health check...")

        health_status = state.get("health_status", {})

        if not health_status:
            response = "System health check not available."
            state["final_response"] = response
            return state

        try:
            # Build prompt
            health_prompt = HEALTH_CHECK_RESPONSE.format(
                health_status=json.dumps(health_status, indent=2)
            )

            logger.debug("  Calling LLM for health formatting...")

            # Call LLM
            response = await self.llm.ainvoke(health_prompt)
            formatted_health = response.content.strip()

            logger.info(f"✅ Health check formatted")
            state["final_response"] = formatted_health
            return state

        except Exception as e:
            logger.warning(f"⚠️  Failed to format health: {e}")
            # Fallback to simple summary
            ok = health_status.get("ok", False)
            db_connected = health_status.get("db_connected", False)
            tables = health_status.get("tables_count", 0)
            
            status = "✅ running" if ok else "❌ offline"
            db_status = "connected" if db_connected else "disconnected"
            
            fallback = f"System is {status}. Database {db_status} with {tables} tables."
            state["final_response"] = fallback
            return state


# Exported function to create the agent
async def create_answer_agent(llm_model: str = "gpt-4o") -> AnswerAgent:
    """Factory function to create an AnswerAgent instance."""
    return AnswerAgent(llm_model=llm_model)