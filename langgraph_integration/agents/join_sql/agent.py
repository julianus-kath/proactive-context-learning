"""
JoinPlanAndSQLAgent - Builds join plans and generates MSSQL queries.

This agent orchestrates the join planning and SQL generation phase:
1. Analyze relevant tables and FK relationships
2. Build join plan (preferred view vs. joins)
3. Generate MSSQL SELECT statement
4. Validate SQL syntax (basic)

Views-first strategy: if a single view covers the intent with role_coverage >= 0.70, prefer it.
Otherwise, plan joins with ≤3 hops using FK relationships.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, JoinPlanAndSQLAgentInput, JoinPlanAndSQLAgentOutput
from langgraph_integration.mcp_client import MCPDatabaseTool
from langgraph_integration.prompts.join_sql import (
    JOIN_PLANNER_PROMPT,
    SQL_GENERATOR_PROMPT_MSSQL,
    VIEWS_PREFERENCE
)

logger = logging.getLogger(__name__)

# MSSQL keywords and functions (for validation)
MSSQL_FUNCTIONS = {
    "TOP", "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL",
    "GROUP", "BY", "ORDER", "HAVING", "DATEADD", "GETDATE", "ISNULL", "COALESCE",
    "CAST", "CONVERT", "DATEDIFF", "EOMONTH", "DATEFROMPARTS", "COUNT", "SUM", "AVG",
    "MIN", "MAX", "DISTINCT", "AS", "ON", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN"
}


class JoinPlanAndSQLAgent:
    """
    Agent for building join plans and generating MSSQL queries.
    
    Input contract: {intent, relevant_tables, schema_snippet, session_described_tables}
    Output contract: {join_plan, sql_query, error_info}
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o",
        llm_temp: float = 0.0,
        max_joins: int = 3,
        view_role_coverage_threshold: float = 0.70,
        row_limit: int = 1000,
        query_timeout_seconds: int = 30
    ):
        """
        Initialize JoinPlanAndSQLAgent.
        
        Args:
            llm_model: LLM model name for SQL generation
            llm_temp: Temperature for LLM
            max_joins: Maximum number of joins allowed
            view_role_coverage_threshold: Threshold for views-first strategy
            row_limit: Default row limit for queries
            query_timeout_seconds: Query timeout in seconds
        """
        self.mcp = MCPDatabaseTool()
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.max_joins = max_joins
        self.view_role_coverage_threshold = view_role_coverage_threshold
        self.row_limit = row_limit
        self.query_timeout_seconds = query_timeout_seconds

    async def build_subgraph(self) -> StateGraph:
        """
        Build the LangGraph subgraph for join planning and SQL generation.
        
        Nodes:
        - check_view_coverage: Check if a single view covers the intent
        - fetch_relations: Fetch FK relationships for join planning
        - build_join_plan: Build join strategy (view vs. joins)
        - generate_sql: Generate MSSQL query from plan
        - validate_sql: Basic syntax validation
        
        Returns:
            Compiled LangGraph subgraph
        """
        graph = StateGraph(BaseState)

        # Define nodes
        graph.add_node("check_view_coverage", self._check_view_coverage_node)
        graph.add_node("fetch_relations", self._fetch_relations_node)
        graph.add_node("build_join_plan", self._build_join_plan_node)
        graph.add_node("generate_sql", self._generate_sql_node)
        graph.add_node("validate_sql", self._validate_sql_node)

        # Define edges and conditional routing
        graph.add_edge("check_view_coverage", "fetch_relations")
        graph.add_edge("fetch_relations", "build_join_plan")
        graph.add_edge("build_join_plan", "generate_sql")
        graph.add_edge("generate_sql", "validate_sql")
        graph.add_edge("validate_sql", END)

        # Set entry point
        graph.set_entry_point("check_view_coverage")

        return graph.compile()

    async def _check_view_coverage_node(self, state: BaseState) -> BaseState:
        """
        Check if a single view can satisfy the query (views-first strategy).
        
        If any relevant_table is a view with role_coverage >= 0.70:
        - Store it as preferred view in join_plan
        """
        logger.info("👁️  Checking for high-coverage views...")

        relevant_tables = state.get("relevant_tables", [])
        session_cache = state.get("session_described_tables", {})

        for table_name in relevant_tables:
            # Check cache
            if table_name in session_cache:
                table_info = session_cache[table_name]
                is_view = table_info.get("is_view", False)
                role_coverage = table_info.get("role_coverage", 0)

                if is_view and role_coverage >= self.view_role_coverage_threshold:
                    logger.info(
                        f"✅ Found high-coverage view: {table_name} (role_coverage={role_coverage:.2f})"
                    )
                    state["join_plan"] = {
                        "strategy": "view",
                        "primary_table": table_name,
                        "reason": f"Single view covers intent with role_coverage={role_coverage:.2f}"
                    }
                    return state

        logger.info("ℹ️  No high-coverage view found, will plan joins...")
        return state

    async def _fetch_relations_node(self, state: BaseState) -> BaseState:
        """
        Fetch FK relationships for relevant tables to guide join planning.
        """
        logger.info("🔗 Fetching table relationships...")

        relevant_tables = state.get("relevant_tables", [])

        if not relevant_tables:
            logger.warning("No relevant tables to fetch relations for")
            return state

        try:
            fk_hints = []

            for table_name in relevant_tables[:self.max_joins]:  # Limit to prevent explosion
                try:
                    logger.debug(f"  Fetching relations for {table_name}...")
                    result = await self.mcp.list_relations(table_name)
                    parsed = self._parse_relations_result(result, table_name)
                    fk_hints.extend(parsed)
                except Exception as e:
                    logger.warning(f"  Failed to fetch relations for {table_name}: {e}")
                    continue

            if not fk_hints:
                logger.warning("No FK relationships found")
            else:
                logger.info(f"✅ Found {len(fk_hints)} FK relationships")

            state["fk_hints"] = fk_hints
            return state

        except Exception as e:
            error = {
                "type": "RELATION_FETCH_ERROR",
                "message": f"Failed to fetch relationships: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _build_join_plan_node(self, state: BaseState) -> BaseState:
        """
        Build join plan from schema and relationships.
        
        Strategy: views-first or joins (max 3 hops)
        """
        logger.info("📋 Building join plan...")

        # Check if already have a view plan
        if state.get("join_plan") and state["join_plan"].get("strategy") == "view":
            logger.info("✅ Using view-based plan")
            return state

        relevant_tables = state.get("relevant_tables", [])
        intent = state.get("intent", {})
        fk_hints = state.get("fk_hints", [])

        if not relevant_tables:
            error = {
                "type": "NO_TABLES",
                "message": "No relevant tables available for join planning",
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            # Simple join plan: fact table (first) + dimensions (rest)
            join_plan = {
                "strategy": "joins",
                "primary_table": relevant_tables[0],
                "joins": [],
                "fk_hints": fk_hints,
                "where_filters": intent.get("filters", []),
                "select_columns": [],
                "groupby_columns": [],
                "limit": self.row_limit,
                "reason": f"Using {len(relevant_tables)} table(s) with joins"
            }

            # Add dimensions as joins
            for i, table in enumerate(relevant_tables[1:]):
                if i >= self.max_joins - 1:  # Limit to max_joins - 1 (since we have primary)
                    break

                # Find FK relationship if available
                fk_hint = None
                for hint in fk_hints:
                    if hint.get("from_table") == relevant_tables[0] and hint.get("to_table") == table:
                        fk_hint = hint
                        break

                join_condition = (
                    fk_hint.get("join_condition", "")
                    if fk_hint
                    else f"{relevant_tables[0]}.id = {table}.id"
                )

                join_plan["joins"].append({
                    "table": table,
                    "on": join_condition,
                    "type": "INNER"
                })

            logger.info(f"✅ Built join plan: {len(join_plan['joins'])} join(s)")

            state["join_plan"] = join_plan
            return state

        except Exception as e:
            error = {
                "type": "PLAN_BUILD_ERROR",
                "message": f"Failed to build join plan: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _generate_sql_node(self, state: BaseState) -> BaseState:
        """
        Generate MSSQL query from join plan.
        """
        logger.info("🔨 Generating MSSQL query...")

        join_plan = state.get("join_plan")
        schema_snippet = state.get("schema_snippet", "")
        intent = state.get("intent", {})

        if not join_plan:
            error = {
                "type": "NO_PLAN",
                "message": "No join plan available for SQL generation",
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            # Simple SQL generation
            strategy = join_plan.get("strategy", "joins")

            if strategy == "view":
                # View-based query
                primary_table = join_plan.get("primary_table", "")
                filters = join_plan.get("where_filters", [])

                sql = f"SELECT TOP {self.row_limit} * FROM {primary_table}"

                # Add WHERE clause if filters exist
                if filters:
                    where_conditions = []
                    for f in filters:
                        if isinstance(f, dict):
                            col = f.get("column", "")
                            op = f.get("operator", "=")
                            val = f.get("value", "")
                            # Only quote non-numeric values
                            # Check if value is numeric (int/float) or looks like a number
                            val_str = str(val).strip()
                            try:
                                # Try to parse as float; if successful, it's numeric
                                float(val_str)
                                condition = f"{col} {op} {val_str}"  # No quotes for numeric
                            except ValueError:
                                # Not numeric, quote it
                                condition = f"{col} {op} '{val_str}'"  # Quotes for string
                            where_conditions.append(condition)
                        else:
                            where_conditions.append(str(f))

                    if where_conditions:
                        sql += " WHERE " + " AND ".join(where_conditions)

            else:
                # Join-based query
                primary_table = join_plan.get("primary_table", "")
                joins = join_plan.get("joins", [])
                filters = join_plan.get("where_filters", [])

                # Build FROM and JOINs
                sql = f"SELECT TOP {self.row_limit} * FROM {primary_table}"

                for join in joins:
                    join_type = join.get("type", "INNER")
                    join_table = join.get("table", "")
                    join_condition = join.get("on", "")
                    sql += f" {join_type} JOIN {join_table} ON {join_condition}"

                # Add WHERE clause if filters exist
                if filters:
                    where_conditions = []
                    for f in filters:
                        if isinstance(f, dict):
                            col = f.get("column", "")
                            op = f.get("operator", "=")
                            val = f.get("value", "")
                            # Only quote non-numeric values
                            # Check if value is numeric (int/float) or looks like a number
                            val_str = str(val).strip()
                            try:
                                # Try to parse as float; if successful, it's numeric
                                float(val_str)
                                condition = f"{col} {op} {val_str}"  # No quotes for numeric
                            except ValueError:
                                # Not numeric, quote it
                                condition = f"{col} {op} '{val_str}'"  # Quotes for string
                            where_conditions.append(condition)
                        else:
                            where_conditions.append(str(f))

                    if where_conditions:
                        sql += " WHERE " + " AND ".join(where_conditions)

            logger.info(f"✅ Generated SQL ({len(sql)} chars)")
            logger.debug(f"SQL: {sql[:200]}...")

            state["sql_query"] = sql
            return state

        except Exception as e:
            error = {
                "type": "SQL_GEN_ERROR",
                "message": f"Failed to generate SQL: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _validate_sql_node(self, state: BaseState) -> BaseState:
        """
        Perform basic SQL syntax validation.
        
        Checks:
        - Starts with SELECT
        - Has FROM clause
        - Valid MSSQL keywords
        - Balanced parentheses/quotes
        """
        logger.info("✅ Validating SQL...")

        sql = state.get("sql_query", "")

        if not sql:
            error = {
                "type": "NO_SQL",
                "message": "No SQL query to validate",
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            # Basic checks
            sql_upper = sql.upper().strip()

            if not sql_upper.startswith("SELECT"):
                raise ValueError("Query must start with SELECT")

            if "FROM" not in sql_upper:
                raise ValueError("Query must have FROM clause")

            # Check for balanced quotes and parentheses
            if sql.count("'") % 2 != 0:
                raise ValueError("Unbalanced quotes")

            if sql.count("(") != sql.count(")"):
                raise ValueError("Unbalanced parentheses")

            # No DML (only SELECT allowed)
            for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]:
                if keyword in sql_upper:
                    raise ValueError(f"Non-SELECT statement detected: {keyword}")

            logger.info("✅ SQL validation passed")
            return state

        except Exception as e:
            error = {
                "type": "SQL_VALIDATION_ERROR",
                "message": f"SQL validation failed: {str(e)}",
                "error": str(e),
                "sql": sql[:200]
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    # Helper methods

    def _parse_relations_result(self, result: List[Dict[str, Any]], table_name: str) -> List[Dict[str, Any]]:
        """Parse MCP list_relations result."""
        if not result or len(result) == 0:
            return []

        try:
            content = result[0].get("text", "")
            data = json.loads(content) if isinstance(content, str) else content

            # Handle different response formats
            if isinstance(data, dict):
                relations = data.get("relations", data.get("relationships", data.get("fk", [])))
            elif isinstance(data, list):
                relations = data
            else:
                return []

            # Normalize format
            normalized = []
            for rel in relations:
                if isinstance(rel, dict):
                    normalized.append({
                        "from_table": table_name,
                        "to_table": rel.get("related_table", rel.get("to_table", "")),
                        "from_column": rel.get("from_column", rel.get("column", "")),
                        "to_column": rel.get("to_column", rel.get("related_column", "")),
                        "join_condition": rel.get("join_condition", "")
                    })

            return normalized
        except Exception as e:
            logger.warning(f"Failed to parse relations result: {e}")
            return []


# Exported function to create the agent
async def create_join_sql_agent(
    llm_model: str = "gpt-4o",
    max_joins: int = 3
) -> JoinPlanAndSQLAgent:
    """Factory function to create a JoinPlanAndSQLAgent instance."""
    return JoinPlanAndSQLAgent(llm_model=llm_model, max_joins=max_joins)