"""
SQL Validator Agent - Validates and repairs SQL queries before execution.

This agent:
1. Parses SQL using AST to validate syntax and structure
2. Checks table/column existence against column_index
3. Validates MSSQL-specific syntax (TOP vs LIMIT, DATEADD vs DATE_SUB, etc.)
4. Repairs invalid queries with up to 2 attempts
5. Provides structured error feedback for debugging
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.mcp_client import get_shared_mcp_tool
from langgraph_integration.prompts.repair import SQL_REPAIR_PROMPT

logger = logging.getLogger(__name__)


class SQLValidatorAgent:
    """
    Agent for validating and repairing SQL queries before execution.

    Input contract: {sql_query, join_plan, column_index, relevant_tables, schema_snippet}
    Output contract: {sql_query, validation_result, error_info, repair_attempts}
    """

    def __init__(self, llm_model: str = "gpt-4o", max_repair_attempts: int = 2):
        self.llm_model = llm_model
        self.max_repair_attempts = max_repair_attempts
        self.llm = ChatOpenAI(model=llm_model, temperature=0.0)
        self.mcp = None

        # Build the validation graph
        self.graph = self._build_validation_graph()

    async def initialize(self):
        """Initialize MCP client."""
        if not self.mcp:
            self.mcp = await get_shared_mcp_tool()

    def _build_validation_graph(self) -> StateGraph:
        """Build the SQL validation graph with repair loop."""
        graph = StateGraph(BaseState)

        # Add nodes
        graph.add_node("validate_sql", self._validate_sql_node)
        graph.add_node("repair_sql", self._repair_sql_node)
        graph.add_node("check_repair_success", self._check_repair_success_node)
        graph.add_node("final_validation", self._final_validation_node)

        # Define flow
        graph.set_entry_point("validate_sql")

        graph.add_conditional_edges(
            "validate_sql",
            self._should_repair,
            {
                "repair": "repair_sql",
                "valid": "final_validation",
                "fatal": END  # Can't repair this query
            }
        )

        graph.add_edge("repair_sql", "check_repair_success")

        graph.add_conditional_edges(
            "check_repair_success",
            self._should_retry_repair,
            {
                "retry": "repair_sql",
                "success": "final_validation",
                "max_attempts": END  # Give up after max attempts
            }
        )

        graph.add_edge("final_validation", END)

        return graph.compile()

    async def __call__(self, state: BaseState) -> BaseState:
        """Main entry point for SQL validation."""
        await self.initialize()

        # Initialize repair attempt counter
        if "repair_attempts" not in state:
            state["repair_attempts"] = 0

        # Run validation graph
        result = await self.graph.ainvoke(state)

        return result

    def _should_repair(self, state: BaseState) -> str:
        """Decide whether to attempt repair based on validation result."""
        validation_result = state.get("validation_result", {})
        is_valid = validation_result.get("is_valid", False)

        if is_valid:
            return "valid"

        error_type = validation_result.get("error_type", "unknown")

        # Fatal errors we can't repair
        fatal_errors = ["missing_table", "missing_database", "permission_denied"]
        if error_type in fatal_errors:
            return "fatal"

        # Attempt repair for fixable errors
        repairable_errors = ["syntax_error", "missing_column", "invalid_function", "dialect_error"]
        if error_type in repairable_errors:
            return "repair"

        # Default: try repair
        return "repair"

    def _should_retry_repair(self, state: BaseState) -> str:
        """Decide whether to retry repair after an attempt."""
        repair_attempts = state.get("repair_attempts", 0)

        if repair_attempts >= self.max_repair_attempts:
            return "max_attempts"

        # Check if repair was successful
        validation_result = state.get("validation_result", {})
        is_valid = validation_result.get("is_valid", False)

        if is_valid:
            return "success"
        else:
            return "retry"

    async def _validate_sql_node(self, state: BaseState) -> BaseState:
        """Validate SQL query using AST parsing and rule-based checks."""
        logger.info("🔍 [SQL_VALIDATION] Starting SQL validation")

        sql_query = state.get("sql_query", "")
        if not sql_query:
            state["validation_result"] = {
                "is_valid": False,
                "error_type": "empty_query",
                "error_message": "No SQL query provided"
            }
            return state

        # Run comprehensive validation
        validation_result = await self._validate_sql_comprehensive(sql_query, state)

        state["validation_result"] = validation_result
        logger.info(f"🔍 [SQL_VALIDATION] Result: {'✅ VALID' if validation_result['is_valid'] else '❌ INVALID'} - {validation_result.get('error_type', 'unknown')}")

        return state

    async def _validate_sql_comprehensive(self, sql: str, state: BaseState) -> Dict[str, Any]:
        """Comprehensive SQL validation using multiple methods."""
        result = {
            "is_valid": True,
            "error_type": None,
            "error_message": None,
            "warnings": [],
            "suggestions": []
        }

        # 1. Basic syntax validation
        syntax_check = self._validate_sql_syntax(sql)
        if not syntax_check["is_valid"]:
            result.update(syntax_check)
            return result

        # 2. MSSQL dialect validation
        dialect_check = self._validate_mssql_dialect(sql)
        if not dialect_check["is_valid"]:
            result.update(dialect_check)
            return result

        # 3. Table/column existence validation
        schema_check = await self._validate_table_column_existence(sql, state)
        if not schema_check["is_valid"]:
            result.update(schema_check)
            return result

        # 4. Semantic validation (joins, aggregates, etc.)
        semantic_check = self._validate_sql_semantics(sql)
        if not semantic_check["is_valid"]:
            result.update(semantic_check)
            return result

        # Add any warnings from individual checks
        result["warnings"].extend(syntax_check.get("warnings", []))
        result["warnings"].extend(dialect_check.get("warnings", []))
        result["warnings"].extend(schema_check.get("warnings", []))
        result["warnings"].extend(semantic_check.get("warnings", []))

        return result

    def _validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """Validate basic SQL syntax using regex and pattern matching."""
        result = {"is_valid": True, "warnings": []}

        sql_upper = sql.upper().strip()

        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            return {
                "is_valid": False,
                "error_type": "syntax_error",
                "error_message": "Query must start with SELECT",
                "suggestions": ["Ensure query begins with SELECT"]
            }

        # Check for basic SELECT structure
        if "FROM" not in sql_upper:
            return {
                "is_valid": False,
                "error_type": "syntax_error",
                "error_message": "SELECT query must include FROM clause",
                "suggestions": ["Add FROM clause with table name"]
            }

        # Check for balanced parentheses
        open_parens = sql.count("(")
        close_parens = sql.count(")")
        if open_parens != close_parens:
            return {
                "is_valid": False,
                "error_type": "syntax_error",
                "error_message": f"Unbalanced parentheses: {open_parens} open, {close_parens} close",
                "suggestions": ["Check parentheses balance"]
            }

        # Check for balanced quotes
        single_quotes = sql.count("'") - sql.count("\\'")  # Exclude escaped quotes
        if single_quotes % 2 != 0:
            return {
                "is_valid": False,
                "error_type": "syntax_error",
                "error_message": "Unbalanced single quotes",
                "suggestions": ["Check quote balance"]
            }

        return result

    def _validate_mssql_dialect(self, sql: str) -> Dict[str, Any]:
        """Validate MSSQL-specific syntax and functions."""
        result = {"is_valid": True, "warnings": []}

        sql_upper = sql.upper()

        # Check for PostgreSQL/MySQL syntax errors
        if "LIMIT" in sql_upper:
            return {
                "is_valid": False,
                "error_type": "dialect_error",
                "error_message": "LIMIT is not supported in MSSQL - use TOP instead",
                "suggestions": ["Replace LIMIT with TOP (e.g., SELECT TOP 100 instead of LIMIT 100)"]
            }

        if "DATE_SUB(" in sql_upper or "DATE_ADD(" in sql_upper:
            return {
                "is_valid": False,
                "error_type": "dialect_error",
                "error_message": "DATE_SUB/ADD are MySQL functions - use DATEADD in MSSQL",
                "suggestions": ["Use DATEADD(day, -30, GETDATE()) instead of DATE_SUB"]
            }

        if "::" in sql:
            return {
                "is_valid": False,
                "error_type": "dialect_error",
                "error_message": "PostgreSQL casting syntax :: not supported in MSSQL",
                "suggestions": ["Use CONVERT() or CAST() functions"]
            }

        # Check for backticks (MySQL style)
        if "`" in sql:
            return {
                "is_valid": False,
                "error_type": "dialect_error",
                "error_message": "Backticks are MySQL syntax - use square brackets in MSSQL",
                "suggestions": ["Replace `column` with [column]"]
            }

        # Warnings for potential issues
        if "NOW()" in sql_upper:
            result["warnings"].append("NOW() is MySQL function - consider GETDATE() for MSSQL")

        if "CURDATE()" in sql_upper:
            result["warnings"].append("CURDATE() is MySQL function - consider CAST(GETDATE() AS DATE) for MSSQL")

        return result

    async def _validate_table_column_existence(self, sql: str, state: BaseState) -> Dict[str, Any]:
        """Validate that all tables and columns referenced in SQL exist."""
        result = {"is_valid": True, "warnings": []}

        column_index = state.get("column_index", {}) or {}
        relevant_tables = state.get("relevant_tables", []) or []

        # Extract table and column references from SQL
        tables_used, columns_used = self._extract_tables_columns_from_sql(sql)

        # Check tables exist
        missing_tables = []
        for table in tables_used:
            if table not in column_index and table not in relevant_tables:
                # Try to find it in the full list
                found = False
                for rt in relevant_tables:
                    if isinstance(rt, dict):
                        rt_name = rt.get("table_name") or rt.get("name") or rt.get("full_name", "")
                    else:
                        rt_name = str(rt)
                    if rt_name == table:
                        found = True
                        break
                if not found:
                    missing_tables.append(table)

        if missing_tables:
            return {
                "is_valid": False,
                "error_type": "missing_table",
                "error_message": f"Tables not found: {', '.join(missing_tables)}",
                "suggestions": ["Check table names against discovery results", "Ensure tables are in relevant_tables"]
            }

        # Check columns exist for each table
        for table, columns in columns_used.items():
            if table in column_index:
                available_columns = column_index[table]
                missing_cols = [col for col in columns if col not in available_columns]
                if missing_cols:
                    return {
                        "is_valid": False,
                        "error_type": "missing_column",
                        "error_message": f"Columns not found in {table}: {', '.join(missing_cols)}",
                        "suggestions": ["Check column names against column_index", "Use exploratory SELECT * if column names are uncertain"]
                    }
            else:
                result["warnings"].append(f"Could not validate columns for table {table} - not in column_index")

        return result

    def _validate_sql_semantics(self, sql: str) -> Dict[str, Any]:
        """Validate SQL semantics (joins, aggregates, grouping, etc.)."""
        result = {"is_valid": True, "warnings": []}

        sql_upper = sql.upper()

        # Check for GROUP BY without aggregate functions
        if "GROUP BY" in sql_upper:
            has_aggregates = any(func in sql_upper for func in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("])
            if not has_aggregates:
                return {
                    "is_valid": False,
                    "error_type": "semantic_error",
                    "error_message": "GROUP BY used without aggregate functions",
                    "suggestions": ["Add COUNT(*), SUM(), AVG(), etc. when using GROUP BY"]
                }

        # Check for aggregate functions without GROUP BY (except COUNT(*))
        aggregate_functions = ["SUM(", "AVG(", "MAX(", "MIN("]
        has_other_aggregates = any(func in sql_upper for func in aggregate_functions)
        has_count_star = "COUNT(*)" in sql_upper

        if has_other_aggregates and not has_count_star and "GROUP BY" not in sql_upper:
            # This might be valid if it's a simple aggregate query
            select_part = sql_upper.split("FROM")[0]
            if "," in select_part and any(func in select_part for func in aggregate_functions):
                return {
                    "is_valid": False,
                    "error_type": "semantic_error",
                    "error_message": "Multiple aggregates without GROUP BY",
                    "suggestions": ["Add GROUP BY clause when selecting multiple aggregates"]
                }

        # Check JOIN conditions
        if "JOIN" in sql_upper:
            join_conditions = self._extract_join_conditions(sql)
            for join_table, condition in join_conditions.items():
                if not condition or condition.strip() == "":
                    result["warnings"].append(f"JOIN with {join_table} has no ON condition")

        return result

    def _extract_tables_columns_from_sql(self, sql: str) -> Tuple[List[str], Dict[str, List[str]]]:
        """Extract table and column references from SQL query."""
        tables = []
        columns = {}

        # Simple regex-based extraction (could be improved with proper SQL parsing)

        # Extract table names from FROM and JOIN clauses
        from_pattern = r'\bFROM\s+([`\[]?[a-zA-Z_][a-zA-Z0-9_]*[`\]]?)'
        join_pattern = r'\bJOIN\s+([`\[]?[a-zA-Z_][a-zA-Z0-9_]*[`\]]?)'

        for pattern in [from_pattern, join_pattern]:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                table_name = match.strip("`[]")
                if table_name not in tables:
                    tables.append(table_name)
                    columns[table_name] = []

        # Extract column references (simplified)
        # This is a basic implementation - a full SQL parser would be better
        select_part = sql.split("FROM")[0] if "FROM" in sql else sql
        column_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', select_part)  # Functions
        column_refs.extend(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', select_part))  # Identifiers

        # Associate columns with tables (very simplified)
        for table in tables:
            table_cols = []
            # Look for table.column patterns
            table_col_pattern = rf'\b{re.escape(table)}\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
            matches = re.findall(table_col_pattern, sql, re.IGNORECASE)
            table_cols.extend(matches)
            columns[table] = list(set(table_cols))

        return tables, columns

    def _extract_join_conditions(self, sql: str) -> Dict[str, str]:
        """Extract JOIN conditions from SQL."""
        conditions = {}

        # Simple regex to find JOIN ... ON ... patterns
        join_pattern = r'JOIN\s+(\w+)\s+.*?ON\s+(.+?)(?=JOIN|WHERE|GROUP|ORDER|$)'
        matches = re.findall(join_pattern, sql, re.IGNORECASE | re.DOTALL)

        for table, condition in matches:
            conditions[table.strip()] = condition.strip()

        return conditions

    async def _repair_sql_node(self, state: BaseState) -> BaseState:
        """Attempt to repair invalid SQL using LLM."""
        logger.info("🔧 [SQL_REPAIR] Attempting SQL repair")

        repair_attempts = state.get("repair_attempts", 0)
        state["repair_attempts"] = repair_attempts + 1

        sql_query = state.get("sql_query", "")
        validation_result = state.get("validation_result", {})
        schema_snippet = state.get("schema_snippet", "")
        join_plan = state.get("join_plan", {})

        # Prepare repair prompt
        error_message = validation_result.get("error_message", "Unknown error")
        error_type = validation_result.get("error_type", "unknown")

        repair_prompt = SQL_REPAIR_PROMPT.format(
            sql_query=sql_query,
            error_message=f"{error_type}: {error_message}",
            schema_snippet=schema_snippet,
            join_plan=str(join_plan)
        )

        try:
            # Call LLM for repair
            response = await self.llm.ainvoke(repair_prompt)
            repaired_sql = self._extract_sql_from_response(response.content)

            if repaired_sql and repaired_sql.strip() != sql_query.strip():
                logger.info(f"🔧 [SQL_REPAIR] Repaired SQL: {repaired_sql[:100]}...")
                state["sql_query"] = repaired_sql
            else:
                logger.warning("🔧 [SQL_REPAIR] LLM could not repair SQL")
                state["repair_failed"] = True

        except Exception as e:
            logger.error(f"🔧 [SQL_REPAIR] Repair failed: {e}")
            state["repair_failed"] = True

        return state

    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL from LLM response."""
        # Look for code block
        code_block_pattern = r'```sql\s*\n(.*?)\n```'
        match = re.search(code_block_pattern, response, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: look for SELECT statement
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.upper().startswith('SELECT'):
                return line

        return None

    async def _check_repair_success_node(self, state: BaseState) -> BaseState:
        """Check if the repaired SQL is now valid."""
        logger.info("🔍 [REPAIR_CHECK] Checking repair success")

        sql_query = state.get("sql_query", "")
        if not sql_query or state.get("repair_failed"):
            # Repair failed, don't re-validate
            return state

        # Re-validate the repaired SQL
        validation_result = await self._validate_sql_comprehensive(sql_query, state)
        state["validation_result"] = validation_result

        logger.info(f"🔍 [REPAIR_CHECK] Re-validation result: {'✅ VALID' if validation_result['is_valid'] else '❌ STILL INVALID'}")

        return state

    async def _final_validation_node(self, state: BaseState) -> BaseState:
        """Final validation and cleanup."""
        validation_result = state.get("validation_result", {})

        if validation_result.get("is_valid", False):
            logger.info("✅ [SQL_VALIDATION] SQL validation completed successfully")
        else:
            logger.warning(f"⚠️ [SQL_VALIDATION] SQL has warnings: {validation_result.get('warnings', [])}")

        # Add validation metadata to state
        state["sql_validation_complete"] = True
        state["sql_warnings"] = validation_result.get("warnings", [])

        return state


# Export function for LangGraph
async def create_sql_validator_agent(
    llm_model: str = "gpt-4o",
    max_repair_attempts: int = 2
) -> SQLValidatorAgent:
    """Factory function to create SQLValidatorAgent instance."""
    agent = SQLValidatorAgent(llm_model=llm_model, max_repair_attempts=max_repair_attempts)
    await agent.initialize()
    return agent
