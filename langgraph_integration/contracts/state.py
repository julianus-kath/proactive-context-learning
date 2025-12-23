"""
Shared state contracts for multi-agent system.

Each agent has explicit input/output contracts via TypedDict.
BaseState is the union of all fields; individual agents only consume/produce their declared fields.
"""

from typing import Any, Dict, List, Optional, TypedDict, Literal


class ParsedIntent(TypedDict, total=False):
    """
    Structured intent output from IntentParserAgent.
    Replaces loose dict with clear, semantic structure.
    
    This is the SINGLE SOURCE OF TRUTH for intent information.
    Discovery and other agents consume ONLY from this, not from user_input.
    """
    
    # Operation type (determines routing)
    operation: Literal["query", "schema_query", "health_check"]
    
    # Semantic entities (2-3 max, cleaned nouns)
    # e.g., ["products", "inventory"] NOT ["Which", "have", "below"]
    primary_entities: List[str]
    
    # Metrics/measures the user wants
    # e.g., ["count", "total_quantity", "average_price"]
    metrics: List[str]
    
    # Structured filters extracted from intent
    # e.g., [{"field": "inventory", "operator": "<", "value": "100"}]
    filters: List[Dict[str, Any]]
    
    # Time window constraints if present
    # e.g., {"period": "last_30_days", "start": "2024-11-01", "end": "2024-12-01"}
    time_window: Optional[Dict[str, Any]]
    
    # CLEAN keywords for discovery search (NO noise from "Which", "how", "many")
    # Built from primary_entities, metrics, and semantic analysis
    # e.g., ["products", "inventory", "stock"]
    keywords_for_discovery: List[str]
    
    # Original user input (for reference only, never re-parsed)
    raw_query: str
    
    # Confidence score [0.0..1.0] that intent parsing is correct
    confidence: float
    
    # Analytic template classification (e.g., "COUNT_ENTITY", "TOP_K_BY_METRIC", "PERIOD_COMPARISON")
    # Enables specialized SQL generation for common query archetypes
    analytic_template: Optional[str]
    
    # Required action for SQL generation (e.g., "sum_with_period", "topk_sum_by_customer")
    # Aligned with JoinPlanAndSQLAgent routing
    required_action: Optional[str]
    
    # Template-specific parameters (e.g., {"metric": "profit_margin", "top_k": 10, "group_by": "product"})
    # Populated when analytic_template is set
    template_params: Optional[Dict[str, Any]]


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
    # 🆕 PHASE 9: Structured intent (ParsedIntent) replacing loose dict
    # Produced by IntentParserAgent (semantic, LLM-based), consumed by Discovery & others
    intent: ParsedIntent  # Structured: operation, entities, metrics, filters, clean keywords

    # Catalog + concept mediation
    catalog: Dict[str, Any]
    inferred_concepts: List[str]
    seed_tables: List[str]
    concept_hints: Dict[str, Any]
    discovery_log: Dict[str, Any]

    # Discovery phase outputs
    relevant_tables: List[str]  # ["dbo.sales_orders", "dbo.order_items", ...]
    schema_snippet: str  # Compact schema description (≤3 tables/views)
    candidate_views: List[Dict[str, Any]]  # Views matching intent, ranked
    # 🆕 PHASE 7.2: Indexed column names from Scout Catalog
    column_index: Dict[str, List[str]]  # {"dbo.table1": ["col1", "col2", ...], ...}
    discovery_role_hints: Dict[str, Any]  # Structured hints for planner (fact/dim metadata)
    discovery_result: Dict[str, Any]  # Summary info for downstream reporting

    # Join planning & SQL generation
    join_plan: Dict[str, Any]  # {strategy: "view"|"joins", path:[...], fk_hints:[...], ...}
    sql_query: str  # Generated MSSQL query

    # Execution & recovery
    exec_result: Dict[str, Any]  # {ok, data, row_count, execution_time_ms, truncated, warnings}
    # NOTE: error_info is optional at runtime; many agents omit it or explicitly
    #       set it to None when clearing prior errors. The orchestrator and
    #       agents must therefore treat it as Optional[Dict[str, Any]] and
    #       normalize before mutating.
    error_info: Optional[Dict[str, Any]]  # {type, message, context, suggestion}

    # 🆕 PHASE 10a: Result validation (catch silent failures)
    validation_result: Dict[str, Any]  # {valid, issue, suggestion, retry_action}

    # Final answer
    final_response: str  # Natural language answer or explanation

    # Metadata
    retry_count: int  # Number of retry attempts
    session_described_tables: Optional[Dict[str, Any]]  # Cache of described table metadata
    health_status: Dict[str, Any]  # {ok, db_connected, tables_count, views_count, ...}
    eval_run_id: Optional[str]
    eval_query_id: Optional[str]
    executed_tool_calls: List[Dict[str, Any]]

    # 🆕 PHASE 10b: Retry & candidate tracking (prevent infinite loops)
    tried_candidate_tables: List[str]  # Tables we've already attempted and failed on
    retry_attempt_count: int  # Number of retries on current candidate set
    max_retries_per_candidate_set: int  # Circuit breaker threshold (e.g., 2)
    skip_tables: List[str]  # Tables to skip in discovery filter (passed to subgraph)

    # LLM budget configuration
    llm_budget_safety_margin: int  # Safety buffer before hitting hard budget

    # Global orchestration budgets (logical stop conditions, independent of graph recursion_limit)
    plan_attempt_count: int  # Number of full plan/validate cycles attempted
    max_total_plans: int  # Max allowed plan/validation cycles before giving up
    exec_attempt_count: int  # Number of execution/recovery cycles attempted
    max_exec_attempts: int  # Max allowed execution attempts before giving up

    # Phase 2b: Repair loop control (validation/exec caps + no-progress detector)
    validation_attempt_count: int  # Number of times result validation has been run
    exec_recovery_attempt_count: int  # Number of times exec_recovery has been invoked
    repair_no_progress_count: int  # Number of times a repeated repair signature was observed
    repair_signatures_seen: Dict[str, int]  # Map of repair_signature -> occurrence count
    last_exec_error_signature: Optional[str]  # Last execution error signature used for diagnostics
    stop_reason: Optional[str]  # High-level reason why planning/repair stopped early

    # LLM usage accounting (Phase 1 instrumentation)
    # llm_usage tracks per-node buckets plus a "total" aggregate, e.g.:
    # {"intent": 1, "discovery": 2, "join": 1, "repair": 3, "answer": 1, "total": 8}
    llm_usage: Dict[str, int]
    node_entry_counts: Dict[str, int]  # How many times each orchestrator node was entered
    loop_events: Dict[str, int]  # Counters for loop-related events (filled in later phases)
    answer_mode: Optional[str]  # "llm" | "deterministic_from_data" | other modes in later phases

    # Global LLM budget counters (kept for backward compatibility; total_llm_calls mirrors llm_usage["total"])
    total_llm_calls: int  # Total number of LLM calls across all agents
    max_llm_calls: int  # Global LLM call budget
    total_graph_cycles: int  # Number of validation-driven cycles back to discovery/join_sql
    max_graph_cycles: int  # Max allowed graph cycles before giving up

    # Loop helper state (introduced in Phase 1, used by later phases)
    discovery_cache: Optional[Dict[str, Any]]  # Cached discovery outputs keyed by input fingerprint
    last_sql_query: Optional[str]  # Last SQL text produced by join/sql validator
    last_join_plan: Optional[Dict[str, Any]]  # Last join plan structure
    last_join_inputs_fingerprint: Optional[str]  # Fingerprint of last join inputs (tables + intent)
    required_tables_from_kpi: Optional[List[str]]  # Canonical table names derived from KPI expressions
    # Required-relations guardrail (Phase 4)
    required_enforcement_attempts: int  # How many times required-table enforcement has been applied
    last_required_missing_tables: Optional[List[str]]  # Last missing required tables set
    forced_tables: List[str]  # Tables that must be included by discovery/join (canonical)

    # Database dialect/schema (used by SQL helpers and future canonicalization)
    db_dialect: str  # "postgres" | "mssql"
    db_default_schema: str  # e.g., "public" or "dbo"

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
    - relevant_table_details: sanitized metadata for candidate tables/views
    - error_info: if discovery fails
    """

    relevant_tables: List[str]
    schema_snippet: str
    candidate_views: List[Dict[str, Any]]
    session_described_tables: Dict[str, Any]
    column_index: Dict[str, List[str]]  # 🆕 Exact column names for each table
    relevant_table_details: List[Dict[str, Any]]
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
    - exec_result: {ok, data, row_count, execution_time_ms, truncated, warnings}
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


def merge_error_info(state: BaseState, payload: Dict[str, Any]) -> None:
    """
    Safely merge error information into the state.

    Normalizes BaseState["error_info"] so that callers can update it even when
    previous nodes left it unset or explicitly set it to None.
    """
    existing = state.get("error_info")
    if not isinstance(existing, dict):
        existing = {}

    if isinstance(payload, dict):
        existing.update(payload)

    state["error_info"] = existing
