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
import concurrent.futures
import re
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, ExecAndRecoveryAgentInput, ExecAndRecoveryAgentOutput
from langgraph_integration.mcp_client import get_shared_mcp_tool
from langgraph_integration.prompts.repair import (
    SQL_REPAIR_PROMPT,
    QUERY_SIMPLIFICATION
)
from langgraph_integration.utils.sql_normalizer import prepare_sql_for_execution

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
        self.mcp = get_shared_mcp_tool()
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.max_retries = max_retries
        self.row_limit = row_limit
        self.query_timeout_seconds = query_timeout_seconds

    async def __call__(self, state: BaseState) -> BaseState:
        """
        Execute the exec recovery workflow.

        Builds the graph and invokes it with the given state.
        """
        graph = self.build_subgraph()
        compiled_graph = graph.compile()

        # Invoke the graph with the state
        result = await compiled_graph.ainvoke(state)
        return result

    def build_subgraph(self) -> StateGraph:
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

        # Define nodes (use async nodes directly to avoid thread/event loop issues)
        graph.add_node("execute_query", self._execute_query_node)
        graph.add_node("check_result", self._check_result_node)
        graph.add_node("repair_sql", self._repair_sql_node)
        graph.add_node("retry_query", self._retry_query_node)
        graph.add_node("check_retry_result", self._check_retry_result_node)
        graph.add_node("simplify_query", self._simplify_query_node)
        graph.add_node("final_retry", self._final_retry_node)
        graph.add_node("prepare_error", self._prepare_error_node)

        # Define edges with conditional routing
        from typing import Literal
        
        graph.add_edge("execute_query", "check_result")

        # From check_result:
        # - If successful -> END
        # - If error and retry_count < max_retries -> repair_sql
        # - Otherwise -> prepare_error

        def route_from_check_result(state: BaseState) -> Literal["repair_sql", "prepare_error", "__end__"]:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                # Success!
                logger.info("✅ Query executed successfully")
                return "__end__"
            elif state.get("retry_count", 0) < self.max_retries:
                # Retry
                logger.info(f"↻ Will attempt retry (attempt {state.get('retry_count', 0) + 1}/{self.max_retries})")
                return "repair_sql"
            else:
                # Out of retries
                logger.warning(f"❌ Out of retries ({self.max_retries} attempts)")
                return "prepare_error"

        graph.add_conditional_edges(
            "check_result",
            route_from_check_result,
            {
                "repair_sql": "repair_sql",
                "prepare_error": "prepare_error",
                "__end__": END,
            }
        )

        # From repair_sql -> retry_query
        graph.add_edge("repair_sql", "retry_query")

        # From retry_query -> check_retry_result
        graph.add_edge("retry_query", "check_retry_result")

        def route_from_check_retry(state: BaseState) -> Literal["simplify_query", "prepare_error", "__end__"]:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                # Success on retry!
                logger.info("✅ Query succeeded after repair and retry")
                return "__end__"
            elif state.get("retry_count", 0) < self.max_retries:
                # Try simplification
                return "simplify_query"
            else:
                # Out of retries
                return "prepare_error"

        graph.add_conditional_edges(
            "check_retry_result",
            route_from_check_retry,
            {
                "simplify_query": "simplify_query",
                "prepare_error": "prepare_error",
                "__end__": END,
            }
        )

        # From simplify_query -> final_retry
        graph.add_edge("simplify_query", "final_retry")

        # From final_retry -> END or prepare_error
        def route_from_final_retry(state: BaseState) -> Literal["prepare_error", "__end__"]:
            if state.get("exec_result") and state["exec_result"].get("ok"):
                logger.info("✅ Query succeeded after simplification")
                return "__end__"
            else:
                logger.warning("❌ All retry attempts failed")
                return "prepare_error"

        graph.add_conditional_edges(
            "final_retry",
            route_from_final_retry,
            {
                "prepare_error": "prepare_error",
                "__end__": END,
            }
        )

        # From prepare_error -> END
        graph.add_edge("prepare_error", END)

        # Set entry point
        graph.set_entry_point("execute_query")

        return graph.compile()

    async def _execute_query_node(self, state: BaseState) -> BaseState:
        """
        Execute query via MCP query_bounded.
        
        Handles safety: row caps, timeouts, redaction.
        Also normalizes SQL dialect (LIMIT → TOP for MSSQL).
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
            # Step 1: Normalize SQL dialect and validate
            # This catches edge cases where LLM generates LIMIT instead of TOP
            try:
                normalized_sql, normalization_warnings = prepare_sql_for_execution(sql)
                if normalization_warnings:
                    for warning in normalization_warnings:
                        logger.info(f"⚠️  {warning}")
                sql = normalized_sql
                state["sql_query"] = normalized_sql  # Update state with normalized query
            except ValueError as e:
                error = {
                    "type": "SQL_VALIDATION_ERROR",
                    "message": f"SQL validation failed: {str(e)}",
                    "error": str(e),
                    "stage": "validation"
                }
                logger.warning(f"⚠️  {error['message']}")
                state["error_info"] = error
                state["exec_result"] = None
                return state
            
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

                # Plan-level lightweight fallback: if zero rows, try COUNT(*) on primary table when available
                try:
                    if parsed.get("row_count", 0) == 0:
                        join_plan = state.get("join_plan", {}) or {}
                        primary_table = join_plan.get("primary_table")
                        if primary_table:
                            logger.info(f"🔍 Zero rows: probing primary table count for {primary_table}")
                            probe_sql = f"SELECT COUNT(*) AS total_count FROM {primary_table}"
                            probe_result = await self.mcp.query_bounded(
                                probe_sql,
                                max_rows=1,
                                timeout_ms=int(timeout_ms)
                            )
                            probe_parsed = self._parse_query_result(probe_result)
                            if probe_parsed.get("ok"):
                                # Prefer non-zero count if available
                                rows = probe_parsed.get("rows") or probe_parsed.get("data") or []
                                if rows:
                                    first = rows[0]
                                    # If count > 0, adopt probe result
                                    count_val = None
                                    if isinstance(first, dict):
                                        count_val = next((int(v) for k, v in first.items() if isinstance(v, (int, float))), None)
                                    if isinstance(first, list) and first:
                                        count_val = int(first[0]) if isinstance(first[0], (int, float)) else None
                                    if count_val is not None and count_val > 0:
                                        logger.info(f"🔁 Replacing zero-row result with primary-table COUNT(*)={count_val}")
                                        state["exec_result"] = probe_parsed
                except Exception as _:
                    # Do not fail the flow on probe errors
                    pass
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
        Includes robust extraction and validation.
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
            llm_response = response.content.strip()

            # 🔧 Stage 1: Extract SQL from response (robust extraction)
            repaired_sql = self._extract_sql(llm_response)

            if not repaired_sql:
                raise ValueError("Failed to extract valid SQL from LLM response (likely returned explanatory text)")
            
            # 🔧 Stage 2: Validate extracted SQL
            if not self._validate_extracted_sql(repaired_sql):
                raise ValueError("Extracted SQL failed validation (likely multiple statements or dangerous keywords)")

            logger.info(f"✅ LLM repaired SQL ({len(repaired_sql)} chars)")
            logger.debug(f"  Repaired: {repaired_sql[:100]}...")

            state["sql_query"] = repaired_sql
            state["retry_count"] = state.get("retry_count", 0) + 1

            return state

        except Exception as e:
            logger.warning(f"  Repair attempt failed: {e}")
            # 🔧 FIX: Mark that repair failed and don't use broken SQL
            state["error_info"] = {
                "type": "REPAIR_FAILED",
                "message": f"SQL repair attempt failed: {str(e)}",
                "error": str(e),
                "stage": "repair"
            }
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
        Includes robust extraction and validation.
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
            llm_response = response.content.strip()
            
            # 🔧 Stage 1: Extract SQL from response (robust extraction)
            simplified_sql = self._extract_sql(llm_response)

            if not simplified_sql:
                # 🔧 FIX: LLM returned explanatory text or no SQL
                logger.warning("⚠️  Simplification returned no valid SQL (likely explanatory text), using original")
                return state
            
            # 🔧 Stage 2: Validate extracted SQL
            if not self._validate_extracted_sql(simplified_sql):
                logger.warning(f"⚠️  Simplified query failed validation, using original")
                return state

            logger.info(f"✅ Simplified SQL ({len(simplified_sql)} chars)")
            logger.debug(f"  Simplified: {simplified_sql[:100]}...")
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
        """Parse MCP query result (handles both bounded JSON and unbounded text formats)."""
        try:
            logger.debug(f"Parsing query result: {result[:2] if result else 'None'}")
            # Handle case where MCP returns malformed response
            if not result or len(result) == 0:
                return {"ok": False, "error": "Empty result from MCP server"}

            first_result = result[0]
            if isinstance(first_result, str):
                # MCP returned a string error message
                return {"ok": False, "error": first_result}

            if not isinstance(first_result, dict):
                return {"ok": False, "error": f"Unexpected result type: {type(first_result)}"}

            content = first_result.get("text", "")

            # Try to parse as JSON first (for query_bounded responses). The server returns
            # human-readable text plus a JSON block after 'Full response (JSON):'.
            try:
                text = content if isinstance(content, str) else str(content)
                data = None
                if isinstance(text, str):
                    marker = "Full response (JSON):"
                    if marker in text:
                        json_part = text.split(marker, 1)[-1].strip()
                        # In case there is leading text before '{', trim to first '{'
                        brace_idx = json_part.find('{')
                        if brace_idx >= 0:
                            json_part = json_part[brace_idx:]
                        data = json.loads(json_part)
                    else:
                        # Fallback: try parsing from the last '{' occurrence
                        last_brace = text.rfind('{')
                        if last_brace >= 0:
                            json_part = text[last_brace:]
                            data = json.loads(json_part)
                else:
                    data = content

                if isinstance(data, dict):
                    # This is a JSON response from query_bounded
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
            except Exception:
                # Not JSON or failed to extract JSON - handle as text-table format
                logger.info("Received text table response from unbounded query, parsing manually...")

                if not content or "Query execution failed" in content:
                    return {"ok": False, "error": content or "Query execution failed"}

                # Parse the text table format
                lines = content.strip().split('\n')
                if len(lines) < 3:
                    return {"ok": False, "error": "Invalid table format"}

                # Extract row count from header
                header_match = re.search(r'Query Results \((\d+) rows\)', lines[0])
                if not header_match:
                    return {"ok": False, "error": "Could not parse row count"}

                row_count = int(header_match.group(1))

                if row_count == 0:
                    return {
                        "ok": True,
                        "rows": [],
                        "row_count": 0,
                        "execution_time_ms": 0,
                        "truncated": False,
                        "warnings": [],
                        "error": None
                    }

                # Find data rows (skip header and separator)
                data_start = 2  # Skip "Query Results (X rows):" and blank line
                if data_start >= len(lines):
                    return {"ok": False, "error": "No data rows found"}

                # Extract column headers
                header_line = lines[data_start]
                columns = [col.strip() for col in header_line.split('|')]

                # Extract data rows
                rows = []
                for line in lines[data_start + 2:]:  # Skip headers and separator
                    if line.strip():
                        values = [val.strip() for val in line.split('|')]
                        if len(values) == len(columns):
                            row_dict = {}
                            for col, val in zip(columns, values):
                                # Try to convert to number
                                try:
                                    # Check if it's an integer
                                    if '.' not in val:
                                        row_dict[col] = int(val)
                                    else:
                                        row_dict[col] = float(val)
                                except ValueError:
                                    row_dict[col] = val
                            rows.append(row_dict)

                return {
                    "ok": True,
                    "rows": rows,
                    "row_count": len(rows),
                    "execution_time_ms": 0,  # Not provided in text format
                    "truncated": False,
                    "warnings": [],
                    "error": None
                }

        except Exception as e:
            logger.warning(f"Failed to parse query result: {e}")
            logger.warning(f"Raw content: {content[:200]}...")
            return {"ok": False, "error": str(e)}

    def _extract_sql(self, text: str) -> str:
        """
        🔧 ROBUST FIX: Extract single SQL statement from LLM response.
        
        Handles multiple scenarios:
        - Markdown code fences (```sql ... ```)
        - Explanations before/after SQL
        - Multiple SELECT statements (extracts only clean one)
        - Markdown markers (#, ##, etc.)
        - Special tokens (CANNOT_FIX, CANNOT_SIMPLIFY)
        
        Returns: Single clean SQL statement or empty string if extraction fails
        """
        text = text.strip()
        
        # Stage 1: Check for special tokens (LLM indicating it cannot fix)
        if "CANNOT_FIX" in text or "CANNOT_SIMPLIFY" in text:
            logger.warning("❌ LLM indicated it cannot repair/simplify this query")
            return ""
        
        # Stage 2: Extract from markdown code fence if present (preferred)
        sql_from_fence = self._extract_from_code_fence(text)
        if sql_from_fence:
            logger.debug("✅ Extracted SQL from markdown code fence")
            return sql_from_fence
        
        # Stage 3: Extract first SELECT...semicolon (fallback)
        sql_from_select = self._extract_select_to_semicolon(text)
        if sql_from_select:
            logger.debug("✅ Extracted SQL from SELECT statement")
            return sql_from_select
        
        # Stage 4: Nothing valid found
        logger.warning("⚠️  Could not extract valid SQL from LLM response")
        logger.debug(f"  Response preview: {text[:300]}...")
        return ""

    def _extract_from_code_fence(self, text: str) -> str:
        """Extract SQL from markdown code fence (```sql ... ```)."""
        # Check for multiple code fences (suggests multiple examples - reject)
        fence_count = text.count("```")
        if fence_count > 2:  # Each fence pair = 2 backticks, so >2 means multiple fences
            logger.warning(f"⚠️  Multiple code fences detected ({fence_count//2} blocks) - ambiguous response")
            return ""
        
        # Find ```sql block
        fence_start = text.find("```sql")
        if fence_start < 0:
            fence_start = text.find("```SQL")
        if fence_start < 0:
            return ""  # No code fence found
        
        fence_start += 6  # Skip "```sql"
        
        # Find closing fence
        fence_end = text.find("```", fence_start)
        if fence_end < 0:
            # No closing fence - take to end
            fence_end = len(text)
        
        sql = text[fence_start:fence_end].strip()
        
        if not sql:
            return ""  # Empty fence
        
        # Validate: must start with SELECT (after whitespace, possibly after SQL comments)
        upper_sql = sql.upper().lstrip()
        # Allow SQL comments (-- comment) before SELECT
        if upper_sql.startswith("--"):
            # Skip the comment line and check the next line
            lines = sql.lstrip().split("\n")
            for line in lines:
                if line.strip() and not line.strip().startswith("--"):
                    upper_sql = line.upper()
                    break
        
        if not upper_sql.startswith("SELECT"):
            logger.warning("⚠️  Code fence does not contain SELECT statement")
            return ""
        
        # Remove trailing markdown (###, ##, etc. or other code fences)
        lines = sql.split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # Stop at markdown markers or other code fences
            if stripped.startswith("#") or stripped.startswith("```"):
                logger.debug(f"  Stopping extraction at markdown: {stripped[:30]}")
                break
            clean_lines.append(line)
        
        sql = "\n".join(clean_lines).strip()
        
        if not sql:
            return ""
        
        # Remove trailing semicolons for consistency
        sql = sql.rstrip(";").strip()
        
        # Validate no multiple SELECTs
        if sql.upper().count("SELECT") > 1:
            logger.warning(f"⚠️  Multiple SELECT statements found in fence - ambiguous")
            return ""
        
        return sql

    def _extract_select_to_semicolon(self, text: str) -> str:
        """
        Fallback: Extract SELECT statement from first SELECT to first semicolon.
        This handles responses without code fences.
        """
        # Find first SELECT (case-insensitive)
        select_idx = text.upper().find("SELECT")
        if select_idx < 0:
            return ""
        
        # Find first semicolon after SELECT
        semicolon_idx = text.find(";", select_idx)
        if semicolon_idx < 0:
            # No semicolon - might be unfinished
            logger.debug("⚠️  SELECT found but no terminating semicolon")
            return ""
        
        sql = text[select_idx:semicolon_idx].strip()
        
        if not sql:
            return ""
        
        # Validate: single SELECT only, no multiple statements
        if text[select_idx:semicolon_idx].upper().count("SELECT") > 1:
            logger.warning("⚠️  Multiple SELECT statements found - cannot disambiguate")
            return ""
        
        # Check for additional SQL statements after this one (indicates multiple statements)
        after_sql = text[semicolon_idx+1:].strip()
        if after_sql:
            # Check if there's another SELECT after the semicolon
            if "SELECT" in after_sql.upper()[:100]:  # Check first 100 chars
                logger.warning("⚠️  Multiple SQL statements detected (SELECT found after first statement)")
                return ""
        
        return sql

    def _validate_extracted_sql(self, sql: str) -> bool:
        """Validate extracted SQL is a single, complete SELECT."""
        sql = sql.strip()
        
        # Must start with SELECT
        if not sql.upper().startswith("SELECT"):
            logger.error("❌ Extracted SQL does not start with SELECT")
            return False
        
        # Must not have multiple statements
        statement_count = sql.upper().count("SELECT")
        if statement_count > 1:
            logger.error(f"❌ Multiple SELECT statements ({statement_count}) found")
            return False
        
        # Must not have dangerous statements
        dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "EXEC", "EXECUTE"]
        for keyword in dangerous_keywords:
            if keyword in sql.upper():
                logger.error(f"❌ Dangerous keyword found: {keyword}")
                return False
        
        # Minimum sanity check: has FROM clause
        if "FROM" not in sql.upper():
            logger.warning(f"⚠️  SQL missing FROM clause (might be incomplete)")
            # Don't fail on this - it could be a valid edge case
        
        return True


# Exported function to create the agent
async def create_exec_recovery_agent(
    llm_model: str = "gpt-4o",
    max_retries: int = 2
) -> ExecAndRecoveryAgent:
    """Factory function to create an ExecAndRecoveryAgent instance."""
    return ExecAndRecoveryAgent(llm_model=llm_model, max_retries=max_retries)


# Sync wrapper for LangGraph Studio
def build_exec_recovery_graph():
    """
    Build and return the execution recovery agent graph for LangGraph Studio.
    
    This is a synchronous function that can be called by langgraph dev CLI.
    All node functions remain async and will be properly awaited by LangGraph at runtime.
    
    Returns:
        Compiled StateGraph for the exec recovery agent
    """
    agent = ExecAndRecoveryAgent()
    return agent.build_subgraph()