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
import asyncio
import concurrent.futures
from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

from langgraph_integration.contracts.response_envelope import ResponseEnvelope
from langgraph_integration.contracts.state import BaseState, AnswerAgentInput, AnswerAgentOutput
from langgraph_integration.prompts.answer import (
    RESULT_FORMATTER_PROMPT,
    SCHEMA_EXPLAINER_PROMPT,
    CLARIFICATION_PROMPT,
    ERROR_RESPONSE_PROMPT,
    HEALTH_CHECK_RESPONSE
)

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions synchronously for LangGraph node compatibility."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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

    def build_subgraph(self) -> StateGraph:
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
        from typing import Literal
        
        graph = StateGraph(BaseState)

        # Define nodes (wrap async nodes for sync .invoke() compatibility)
        graph.add_node("route_by_intent", lambda state: _run_async(self._route_decision_node(state)))
        graph.add_node("format_result", lambda state: _run_async(self._format_result_node(state)))
        graph.add_node("explain_schema", lambda state: _run_async(self._explain_schema_node(state)))
        graph.add_node("format_error", lambda state: _run_async(self._format_error_node(state)))
        graph.add_node("format_clarification", lambda state: _run_async(self._format_clarification_node(state)))
        graph.add_node("format_health", lambda state: _run_async(self._format_health_node(state)))

        # Define conditional routing from router node
        def route_by_intent(state: BaseState) -> Literal[
            "format_result", "explain_schema", "format_error", 
            "format_clarification", "format_health"
        ]:
            """Route to appropriate formatter based on state."""
            intent = state.get("intent", {})
            operation = intent.get("operation", "query")
            error_info = state.get("error_info")

            # Priority routing
            if error_info and error_info.get("type"):
                return "format_error"
            elif operation == "clarify":
                return "format_clarification"
            elif operation == "schema_query":
                return "explain_schema"
            elif operation == "health_check":
                return "format_health"
            else:
                return "format_result"
        
        graph.add_conditional_edges(
            "route_by_intent",
            route_by_intent,
            {
                "format_result": "format_result",
                "explain_schema": "explain_schema",
                "format_error": "format_error",
                "format_clarification": "format_clarification",
                "format_health": "format_health",
            }
        )
        
        # All formatters end at END
        graph.add_edge("format_result", END)
        graph.add_edge("explain_schema", END)
        graph.add_edge("format_error", END)
        graph.add_edge("format_clarification", END)
        graph.add_edge("format_health", END)

        # Set entry point
        graph.set_entry_point("route_by_intent")

        return graph.compile()

    async def _route_decision_node(self, state: BaseState) -> BaseState:
        """
        Router node (passthrough).
        
        Actual routing decision is made by the route_by_intent() function in build_subgraph().
        This node just validates state and passes through; the conditional_edges mechanism
        calls the routing function and decides which formatter to invoke.
        """
        logger.debug("🎯 AnswerAgent: Router node (decision made by conditional edges)")
        return state

    async def _format_result_node(self, state: BaseState) -> BaseState:
        """
        Format successful query results as natural language.
        
        Output: 1-2 sentences maximum, NO technical jargon.
        """
        logger.info("✨ Formatting query result...")

        user_input = state.get("user_input", "")
        exec_result = state.get("exec_result", {})
        try:
            envelope = ResponseEnvelope.model_validate(exec_result)
            exec_result = envelope.model_dump(exclude_none=True)
            state["exec_result"] = exec_result
        except ValidationError as exc:
            logger.warning(f"  exec_result normalization failed: {exc}")
            exec_result = ResponseEnvelope(ok=False, data=[]).model_dump(exclude_none=True)
            state["exec_result"] = exec_result
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
            rows = exec_result.get("data") or []
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

            # Append compact rows/table appendix for transparency
            def _extract_from_tables(sql: str) -> list[str]:
                try:
                    import re
                    s = (sql or "").strip()
                    # Capture tokens after FROM and JOIN keywords
                    tables = []
                    for kw in [r"FROM\s+([\w\[\]\.]+)", r"JOIN\s+([\w\[\]\.]+)"]:
                        for m in re.finditer(kw, s, flags=re.IGNORECASE):
                            name = m.group(1)
                            if name and name not in tables:
                                tables.append(name)
                    return tables[:3]
                except Exception:
                    return []

            source_tables = _extract_from_tables(sql_query)
            preview_rows = rows[:5] if isinstance(rows, list) else []
            appendix = ""
            try:
                if preview_rows:
                    tables_str = ", ".join(source_tables) if source_tables else "Unknown"
                    appendix = "\n\n" + f"Tables: {tables_str}\n" + "```json\n" + json.dumps(preview_rows, default=str) + "\n```"
            except Exception:
                appendix = ""

            state["final_response"] = formatted + appendix
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
        if not isinstance(error_info, dict):
            error_info = {"type": "UNKNOWN", "message": str(error_info)}

        if not error_info:
            response = "An error occurred. Please try again."
            state["final_response"] = response
            return state

        try:
            error_type = error_info.get("type", "UNKNOWN")
            error_message = error_info.get("message", error_info.get("error", "Unknown error"))
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
            state["clarify"] = True
            state["clarification_question"] = response
            intent["needs_clarification"] = True
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
            state["clarify"] = True
            state["clarification_question"] = question
            intent["needs_clarification"] = True
            return state

        except Exception as e:
            logger.warning(f"⚠️  Failed to generate clarification: {e}")
            # Fallback to generic question
            fallback = "Could you provide more details about what you're looking for?"
            state["final_response"] = fallback
            state["clarify"] = True
            state["clarification_question"] = fallback
            intent["needs_clarification"] = True
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


# Sync wrapper for LangGraph Studio
def build_answer_graph():
    """
    Build and return the answer agent graph for LangGraph Studio.
    
    This is a synchronous function that can be called by langgraph dev CLI.
    All node functions remain async and will be properly awaited by LangGraph at runtime.
    
    Returns:
        Compiled StateGraph for the answer agent
    """
    agent = AnswerAgent()
    return agent.build_subgraph()