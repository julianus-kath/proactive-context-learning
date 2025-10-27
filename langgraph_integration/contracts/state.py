"""
Shared state contracts for multi-agent system.

Each agent has explicit input/output contracts via TypedDict.
BaseState is the union of all fields; individual agents only consume/produce their declared fields.
"""

from typing import Any, Dict, List, Optional, TypedDict


class BaseState(TypedDict, total=False):
    """
    Full shared state for all agents.
    Agents use only the fields they declare as inputs/outputs.
    total=False means all fields are optional.
    """

    # Conversation & metadata
    messages: List[Dict[str, Any]]  # Conversation history
    user_input: str  # Current user query

    # Intent analysis (from parse_intent node)
    intent: Dict[str, Any]  # {operation, entities, filters, time_window, ...}

    # Discovery phase outputs
    relevant_tables: List[str]  # ["dbo.sales_orders", "dbo.order_items", ...]
    schema_snippet: str  # Compact schema description (≤3 tables/views)
    candidate_views: List[Dict[str, Any]]  # Views matching intent, ranked
    # 🆕 PHASE 7.2: Indexed column names from Scout Catalog
    column_index: Dict[str, List[str]]  # {"dbo.table1": ["col1", "col2", ...], ...}

    # Join planning & SQL generation
    join_plan: Dict[str, Any]  # {strategy: "view"|"joins", path:[...], fk_hints:[...], ...}
    sql_query: str  # Generated MSSQL query

    # Execution & recovery
    exec_result: Dict[str, Any]  # {ok, rows, row_count, execution_time_ms, truncated, warnings}
    error_info: Dict[str, Any]  # {type, message, context, suggestion}

    # Final answer
    final_response: str  # Natural language answer or explanation

    # Metadata
    retry_count: int  # Number of retry attempts
    session_described_tables: Optional[Dict[str, Any]]  # Cache of described table metadata
    health_status: Dict[str, Any]  # {ok, db_connected, tables_count, views_count, ...}

    # Deprecated/legacy (for backward compat during migration)
    schema: Optional[str]  # Full schema (deprecated; use schema_snippet)
    database_index: Optional[Dict]  # Deprecated
    query_results: Optional[str]  # Deprecated; use exec_result instead
    final_response_debug: Optional[str]  # Debug info


# Input/Output contracts per agent


class DiscoveryAgentInput(TypedDict, total=False):
    """
    Inputs consumed by DiscoveryAgent:
    - user_input: the query
    - intent: parsed intent (operation, entities, etc.)
    - session_described_tables: optional cache of prior describes
    """

    user_input: str
    intent: Dict[str, Any]
    session_described_tables: Optional[Dict[str, Any]]


class DiscoveryAgentOutput(TypedDict, total=False):
    """
    Outputs produced by DiscoveryAgent:
    - relevant_tables: list of ["dbo.table1", "dbo.table2"]
    - schema_snippet: compact schema (≤3 entities)
    - candidate_views: ranked views (if any)
    - session_described_tables: updated cache
    - column_index: 🆕 PHASE 7.2 indexed columns from Scout Catalog (prevents hallucination!)
    - error_info: if discovery fails
    """

    relevant_tables: List[str]
    schema_snippet: str
    candidate_views: List[Dict[str, Any]]
    session_described_tables: Dict[str, Any]
    column_index: Dict[str, List[str]]  # 🆕 Exact column names for each table
    error_info: Optional[Dict[str, Any]]


class JoinPlanAndSQLAgentInput(TypedDict, total=False):
    """
    Inputs consumed by JoinPlanAndSQLAgent:
    - intent: parsed intent
    - relevant_tables: tables to consider
    - schema_snippet: compact schema
    - session_described_tables: table metadata cache
    - column_index: 🆕 PHASE 7.2 indexed column names (prevents hallucination!)
    """

    intent: Dict[str, Any]
    relevant_tables: List[str]
    schema_snippet: str
    session_described_tables: Optional[Dict[str, Any]]
    column_index: Optional[Dict[str, List[str]]]  # 🆕 Pre-fetched from Discovery


class JoinPlanAndSQLAgentOutput(TypedDict, total=False):
    """
    Outputs produced by JoinPlanAndSQLAgent:
    - join_plan: {strategy, path, fk_hints, ...}
    - sql_query: MSSQL SELECT statement
    - error_info: if planning/generation fails
    """

    join_plan: Dict[str, Any]
    sql_query: str
    error_info: Optional[Dict[str, Any]]


class ExecAndRecoveryAgentInput(TypedDict, total=False):
    """
    Inputs consumed by ExecAndRecoveryAgent:
    - sql_query: the query to execute
    - retry_count: current retry attempt
    - join_plan: for context during repair
    - schema_snippet: for context during repair
    """

    sql_query: str
    retry_count: int
    join_plan: Optional[Dict[str, Any]]
    schema_snippet: Optional[str]


class ExecAndRecoveryAgentOutput(TypedDict, total=False):
    """
    Outputs produced by ExecAndRecoveryAgent:
    - exec_result: {ok, rows, row_count, execution_time_ms, truncated, warnings}
    - error_info: if execution fails after retries
    - sql_query: updated (repaired) SQL if retry succeeded
    - retry_count: updated retry count
    """

    exec_result: Optional[Dict[str, Any]]
    error_info: Optional[Dict[str, Any]]
    sql_query: Optional[str]
    retry_count: int


class AnswerAgentInput(TypedDict, total=False):
    """
    Inputs consumed by AnswerAgent:
    - user_input: original question
    - exec_result: execution results (if query succeeded)
    - error_info: error details (if execution failed)
    - schema_snippet: for schema explanation queries
    - intent: for context (e.g., operation type)
    - sql_query: for debugging/explanation
    """

    user_input: str
    exec_result: Optional[Dict[str, Any]]
    error_info: Optional[Dict[str, Any]]
    schema_snippet: Optional[str]
    intent: Optional[Dict[str, Any]]
    sql_query: Optional[str]


class AnswerAgentOutput(TypedDict, total=False):
    """
    Outputs produced by AnswerAgent:
    - final_response: natural language answer or explanation
    """

    final_response: str