"""
ExecAndRecoveryAgent - Executes queries and recovers from failures.

This agent orchestrates safe query execution with automatic recovery:
1. Execute query via MCP query_bounded (safe, with limits)
2. On error: attempt repair (LLM-based or simplification)
3. Retry repaired query (max 2 attempts total)
4. On final failure: prepare for clarification

Safety guardrails:
- Read-only (SELECT only)
- Row caps (TOP 1000 default)
- Timeouts (30s default)
- Redaction (sensitive columns)
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, ExecAndRecoveryAgentInput, ExecAndRecoveryAgentOutput
from langgraph_integration.mcp_client import MCPDatabaseTool
from langgraph_integration.prompts.repair import (
    SQL_REPAIR_PROMPT,
    QUERY_SIMPLIFICATION
)

logger = logging.getLogger(__name__)


class ExecAndRecoveryAgent:
    """
    Agent for executing queries with automatic error recovery.
    
    Input contract: {sql_query, retry_count, join_plan, schema_snippet}
    Output contract: {exec_result, error_info, sql_query, retry_count}
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o",
        llm_temp: float = 0.0,
        max_retries: int = 2,
        row_limit: int = 1000,
        query_timeout_seconds: int = 30
    ):
        """
        Initialize ExecAndRecoveryAgent.
        
        Args:
            llm_model: LLM model name for SQL repair
            llm_temp: Temperature for LLM
            max_retries: Maximum retry attempts (default 2)
            row_limit: Maximum rows to return
            query_timeout_seconds: Query timeout in seconds
        """
        self.mcp = MCPDatabaseTool()
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.max_retries = max_retries
        self.row_limit = row_limit
        self.query_timeout_seconds = query_timeout_seconds

    async def build_subgraph(self) -> StateGraph:
        """
        Build the LangGraph subgraph for query execution and recovery.
        
        Nodes:
        - execute_query: Execute via query_bounded
        - check_result: Check if successful
        - repair_sql: Repair failed SQL (attempt 1)
        - retry_query: Retry repaired SQL
        - check_retry_result: Check retry result
        - simplify_query: Simplify query (attempt 2)
        - final_retry: Final retry attempt
        - prepare_error: Prepare error response
        
        Returns:
            Compiled LangGraph subgraph
        """
        graph = StateGraph(BaseState)

        # Define nodes
        graph.add_node("execute_query", self._execute_query_node)
        graph.add_node("check_result", self._check_result_node)
        graph.add_node("repair_sql", self._repair_sql_node)
        graph.add_node("retry_query", self._retry_query_node)
        graph.add_node("check_retry_result", self._check_retry_result_node)
        graph.add_node("simplify_query", self._simplify_query_node)
        graph.add_node("final_retry", self._final_retry_node)
        graph.add_node("prepare_error", self._prepare_error_node)

        # Define edges with conditional routing
        graph.add_edge("execute_query", "check_result")

        # From check_result:
        # - If successful -> END
        # - If error and retry_count < max_retries -> repair_sql
        # - Otherwise -> prepare_error

        def route_from_check_result(state: BaseState) -> str:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                # Success!
                logger.info("✅ Query executed successfully")
                return END
            elif state.get("retry_count", 0) < self.max_retries:
                # Retry
                logger.info(f"↻ Will attempt retry (attempt {state.get('retry_count', 0) + 1}/{self.max_retries})")
                return "repair_sql"
            else:
                # Out of retries
                logger.warning(f"❌ Out of retries ({self.max_retries} attempts)")
                return "prepare_error"

        graph.add_conditional_edges("check_result", route_from_check_result)

        # From repair_sql -> retry_query
        graph.add_edge("repair_sql", "retry_query")

        # From retry_query -> check_retry_result
        graph.add_edge("retry_query", "check_retry_result")

        def route_from_check_retry(state: BaseState) -> str:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                # Success on retry!
                logger.info("✅ Query succeeded after repair and retry")
                return END
            elif state.get("retry_count", 0) < self.max_retries:
                # Try simplification
                return "simplify_query"
            else:
                # Out of retries
                return "prepare_error"

        graph.add_conditional_edges("check_retry_result", route_from_check_retry)

        # From simplify_query -> final_retry
        graph.add_edge("simplify_query", "final_retry")

        # From final_retry -> END or prepare_error
        def route_from_final_retry(state: BaseState) -> str:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                logger.info("✅ Query succeeded after simplification")
                return END
            else:
                logger.warning("❌ All retry attempts failed")
                return "prepare_error"

        graph.add_conditional_edges("final_retry", route_from_final_retry)

        # From prepare_error -> END
        graph.add_edge("prepare_error", END)

        # Set entry point
        graph.set_entry_point("execute_query")

        return graph.compile()

    async def _execute_query_node(self, state: BaseState) -> BaseState:
        """
        Execute query via MCP query_bounded.
        
        Handles safety: row caps, timeouts, redaction.
        """
        logger.info("🚀 Executing query...")

        sql = state.get("sql_query", "")

        if not sql:
            error = {
                "type": "NO_SQL",
                "message": "No SQL query to execute",
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            logger.debug(f"Query: {sql[:100]}...")

            # Call MCP query_bounded with safety parameters
            timeout_ms = self.query_timeout_seconds * 1000
            result = await self.mcp.query_bounded(
                sql,
                max_rows=self.row_limit,
                timeout_ms=int(timeout_ms)
            )

            # Parse result
            parsed = self._parse_query_result(result)

            if parsed.get("ok"):
                logger.info(f"✅ Query executed: {parsed.get('row_count', 0)} rows, {parsed.get('execution_time_ms', 0)}ms")
                state["exec_result"] = parsed
            else:
                error_msg = parsed.get("error", "Unknown error")
                logger.warning(f"⚠️  Query failed: {error_msg}")
                state["error_info"] = {
                    "type": "QUERY_ERROR",
                    "message": error_msg,
                    "error": error_msg,
                    "stage": "execute"
                }
                state["exec_result"] = None

            return state

        except asyncio.TimeoutError as e:
            error = {
                "type": "TIMEOUT",
                "message": f"Query timed out after {self.query_timeout_seconds}s",
                "error": str(e),
                "stage": "execute"
            }
            logger.error(f"⏱️  {error['message']}")
            return {**state, "error_info": error}

        except Exception as e:
            error = {
                "type": "EXECUTION_ERROR",
                "message": f"Query execution failed: {str(e)}",
                "error": str(e),
                "stage": "execute",
                "sql": sql[:200]
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _check_result_node(self, state: BaseState) -> BaseState:
        """Check if query was successful."""
        # Routing happens in graph edges
        return state

    async def _repair_sql_node(self, state: BaseState) -> BaseState:
        """
        Attempt to repair failed SQL.
        
        Uses LLM to analyze error and suggest fix.
        """
        logger.info("🔧 Attempting SQL repair...")

        sql = state.get("sql_query", "")
        error_info = state.get("error_info", {})
        schema_snippet = state.get("schema_snippet", "")
        join_plan = state.get("join_plan", {})

        error_msg = error_info.get("message", error_info.get("error", "Unknown error"))

        try:
            # Use LLM to repair SQL
            repair_prompt = SQL_REPAIR_PROMPT.format(
                sql_query=sql,
                error_message=error_msg,
                schema_snippet=schema_snippet,
                join_plan=json.dumps(join_plan, indent=2)
            )

            logger.debug(f"  Sending repair prompt to LLM...")
            response = await self.llm.ainvoke(repair_prompt)
            repaired_sql = response.content.strip()

            # Extract SQL from response (might have explanations)
            repaired_sql = self._extract_sql(repaired_sql)

            if not repaired_sql:
                raise ValueError("LLM returned no SQL")

            logger.info(f"✅ LLM repaired SQL ({len(repaired_sql)} chars)")
            logger.debug(f"  Repaired: {repaired_sql[:100]}...")

            state["sql_query"] = repaired_sql
            state["retry_count"] = state.get("retry_count", 0) + 1

            return state

        except Exception as e:
            logger.warning(f"  Repair attempt failed: {e}")
            # Fall through to simplification
            return state

    async def _retry_query_node(self, state: BaseState) -> BaseState:
        """
        Retry repaired query.
        """
        logger.info(f"🔄 Retrying query (attempt {state.get('retry_count', 1)})...")

        sql = state.get("sql_query", "")

        if not sql:
            return state

        try:
            timeout_ms = self.query_timeout_seconds * 1000
            result = await self.mcp.query_bounded(
                sql,
                max_rows=self.row_limit,
                timeout_ms=int(timeout_ms)
            )

            parsed = self._parse_query_result(result)

            if parsed.get("ok"):
                logger.info(f"✅ Retry successful: {parsed.get('row_count', 0)} rows")
                state["exec_result"] = parsed
            else:
                logger.warning(f"  Retry failed: {parsed.get('error')}")
                state["error_info"] = {
                    "type": "RETRY_FAILED",
                    "message": parsed.get("error", "Unknown error"),
                    "stage": "retry"
                }

            return state

        except Exception as e:
            logger.warning(f"  Retry error: {e}")
            state["error_info"] = {
                "type": "RETRY_ERROR",
                "message": str(e),
                "stage": "retry"
            }
            return state

    async def _check_retry_result_node(self, state: BaseState) -> BaseState:
        """Check if retry was successful."""
        # Routing happens in graph edges
        return state

    async def _simplify_query_node(self, state: BaseState) -> BaseState:
        """
        Simplify query for another retry attempt.
        """
        logger.info("⚙️  Attempting to simplify query...")

        sql = state.get("sql_query", "")
        error_info = state.get("error_info", {})

        try:
            # Use LLM to simplify
            simplify_prompt = QUERY_SIMPLIFICATION.format(
                sql_query=sql,
                issue="Query too complex, may timeout or fail"
            )

            response = await self.llm.ainvoke(simplify_prompt)
            simplified_sql = response.content.strip()
            simplified_sql = self._extract_sql(simplified_sql)

            if not simplified_sql:
                logger.warning("  Simplification returned no SQL, using original")
                return state

            logger.info(f"✅ Simplified SQL ({len(simplified_sql)} chars)")
            state["sql_query"] = simplified_sql

            return state

        except Exception as e:
            logger.warning(f"  Simplification failed: {e}")
            return state

    async def _final_retry_node(self, state: BaseState) -> BaseState:
        """
        Final retry attempt with simplified query.
        """
        logger.info(f"🎯 Final retry attempt...")

        sql = state.get("sql_query", "")

        if not sql:
            return state

        try:
            timeout_ms = self.query_timeout_seconds * 1000
            result = await self.mcp.query_bounded(
                sql,
                max_rows=self.row_limit,
                timeout_ms=int(timeout_ms)
            )

            parsed = self._parse_query_result(result)

            if parsed.get("ok"):
                logger.info(f"✅ Final retry successful: {parsed.get('row_count', 0)} rows")
                state["exec_result"] = parsed
            else:
                logger.warning(f"  Final retry failed: {parsed.get('error')}")
                state["error_info"] = {
                    "type": "FINAL_RETRY_FAILED",
                    "message": parsed.get("error", "Unknown error"),
                    "all_attempts_failed": True
                }

            return state

        except Exception as e:
            logger.warning(f"  Final retry error: {e}")
            state["error_info"] = {
                "type": "FINAL_RETRY_ERROR",
                "message": str(e),
                "all_attempts_failed": True
            }
            return state

    async def _prepare_error_node(self, state: BaseState) -> BaseState:
        """
        Prepare error information for answer agent (will ask for clarification).
        """
        logger.info("❌ Query failed, preparing error response...")

        error_info = state.get("error_info", {})

        # Ensure error_info has all required fields
        if not error_info:
            error_info = {
                "type": "UNKNOWN_ERROR",
                "message": "Query execution failed for unknown reason",
                "suggestion": "Please try reformulating your question or providing more details."
            }

        # Add suggestion if missing
        if "suggestion" not in error_info:
            error_type = error_info.get("type", "")
            if error_type == "TIMEOUT":
                error_info["suggestion"] = "Query took too long. Try filtering by a specific time period or limit to specific products."
            elif error_type == "NO_RESULTS":
                error_info["suggestion"] = "No matching records found. Try a different date range or modify your filter criteria."
            else:
                error_info["suggestion"] = "Please try again or contact support if the issue persists."

        state["error_info"] = error_info
        logger.info(f"  Error type: {error_info.get('type')}")
        logger.info(f"  Suggestion: {error_info.get('suggestion')}")

        return state

    # Helper methods

    def _parse_query_result(self, result: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse MCP query_bounded result."""
        if not result or len(result) == 0:
            return {"ok": False, "error": "Empty result from MCP server"}

        try:
            content = result[0].get("text", "")
            data = json.loads(content) if isinstance(content, str) else content

            # Extract fields
            ok = data.get("ok", False)
            rows = data.get("rows", [])
            row_count = data.get("row_count", len(rows))
            execution_time_ms = data.get("execution_time_ms", 0)
            truncated = data.get("truncated", False)
            warnings = data.get("warnings", [])
            error = data.get("error")

            return {
                "ok": ok,
                "rows": rows,
                "row_count": row_count,
                "execution_time_ms": execution_time_ms,
                "truncated": truncated,
                "warnings": warnings,
                "error": error
            }
        except Exception as e:
            logger.warning(f"Failed to parse query result: {e}")
            return {"ok": False, "error": str(e)}

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from LLM response."""
        text = text.strip()

        # Remove markdown code fence
        if text.startswith("```sql"):
            text = text[6:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        # Remove explanations (text before SELECT)
        select_idx = text.upper().find("SELECT")
        if select_idx > 0:
            text = text[select_idx:]

        return text.strip()


# Exported function to create the agent
async def create_exec_recovery_agent(
    llm_model: str = "gpt-4o",
    max_retries: int = 2
) -> ExecAndRecoveryAgent:
    """Factory function to create an ExecAndRecoveryAgent instance."""
    return ExecAndRecoveryAgent(llm_model=llm_model, max_retries=max_retries)