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
import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple, Set

from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.discovery_models import DiscoveryRoleHints, RoleHintDimension, RoleHintFact
from langgraph_integration.contracts.state import BaseState, JoinPlanAndSQLAgentInput, JoinPlanAndSQLAgentOutput
from langgraph_integration.mcp_client import get_shared_mcp_tool, _extract_json_from_text
from langgraph_integration.templates.mssql_template_builder import MSSQLTemplateBuilder, TemplateBuildError

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
        self.mcp = get_shared_mcp_tool()
        self.max_joins = max_joins
        self.view_role_coverage_threshold = view_role_coverage_threshold
        self.row_limit = row_limit
        self.query_timeout_seconds = query_timeout_seconds

    def build_subgraph(self) -> StateGraph:
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

        # Define nodes (wrap async nodes for sync .invoke() compatibility)
        graph.add_node("check_view_coverage", lambda state: _run_async(self._check_view_coverage_node(state)))
        graph.add_node("fetch_relations", lambda state: _run_async(self._fetch_relations_node(state)))
        graph.add_node("build_join_plan", lambda state: _run_async(self._build_join_plan_node(state)))
        graph.add_node("generate_sql", lambda state: _run_async(self._generate_sql_node(state)))
        graph.add_node("validate_sql", lambda state: _run_async(self._validate_sql_node(state)))

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
        logger.info(f"👁️  [VIEW_CHECK] Input state keys: {list(state.keys())}")

        relevant_tables = state.get("relevant_tables", [])
        session_cache = state.get("session_described_tables", {})

        logger.info(f"👁️  [VIEW_CHECK] relevant_tables: {relevant_tables}")
        logger.info(f"👁️  [VIEW_CHECK] session_cache keys: {list(session_cache.keys())}")

        # Avoid view-first for customer revenue ranking (needs joins)
        intent = state.get("intent", {})
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        entities = [e.lower() for e in (intent.get("primary_entities") or [])]
        sum_customer_request = (any(m in ["sum", "total"] for m in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities))

        for table_name in relevant_tables:
            # Check cache
            if table_name in session_cache:
                table_info = session_cache[table_name]
                is_view = table_info.get("is_view", False)
                role_coverage = table_info.get("role_coverage", 0)

                if is_view and role_coverage >= self.view_role_coverage_threshold and not sum_customer_request:
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
        logger.info(f"🔗 [FETCH_REL] Input state keys: {list(state.keys())}")

        relevant_tables = state.get("relevant_tables", [])
        logger.info(f"🔗 [FETCH_REL] relevant_tables: {relevant_tables}")

        if not relevant_tables:
            logger.warning("No relevant tables to fetch relations for")
            return state

        try:
            fk_hints = []

            # Probe relations for up to 10 candidate tables to broaden FK graph
            for table_name in relevant_tables[:10]:  # widened scope but still bounded
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
        """Use discovery role hints to assemble a deterministic join plan."""
        logger.info("📋 Building join plan (template)")

        intent = state.get("intent", {}) or {}
        fk_hints = state.get("fk_hints", []) or []
        raw_role_hints = state.get("discovery_role_hints") or {}

        # Normalize payload: MCP sometimes returns fact_candidates/dimensions as stringified dicts.
        try:
            normalized_role_hints = self._normalize_role_hints_payload(raw_role_hints)
        except Exception as exc:
            logger.warning(f"⚠️ Failed to normalize discovery role hints payload: {exc}")
            normalized_role_hints = raw_role_hints if isinstance(raw_role_hints, dict) else {}

        try:
            role_hints = DiscoveryRoleHints.model_validate(normalized_role_hints)
        except Exception as exc:
            logger.warning(f"⚠️ Unable to parse discovery role hints after normalization: {exc}")
            role_hints = DiscoveryRoleHints()

        fact_candidate = self._select_fact_candidate(role_hints, intent)
        if fact_candidate is None:
            error = {
                "type": "FACT_NOT_FOUND",
                "message": "Unable to identify a fact table for this query.",
            }
            logger.error(error["message"])
            return {**state, "error_info": error}

        fact_table = fact_candidate.table

        join_plan: Dict[str, Any] = {
            "strategy": "template",
            "fact_table": fact_table,
            "primary_table": fact_table,
            "metric_candidates": fact_candidate.metric_candidates,
            "date_columns": fact_candidate.date_columns,
            "entity_keys": fact_candidate.entity_keys,
            "filters": intent.get("filters", []),
            "time_window": intent.get("time_window"),
            "joins": [],
            "dimensions": {},
            "fk_hints": fk_hints,
            "required_action": intent.get("required_action"),
            "fact_estimated_rows": fact_candidate.estimated_rows,
        }

        required_action = intent.get("required_action")

        def attach_dimension(role_name: str, required: bool = False) -> Optional[RoleHintDimension]:
            dimension = self._select_dimension(role_hints, role_name)
            if not dimension:
                if required:
                    logger.error(f"❌ Required dimension '{role_name}' missing from discovery role hints")
                return None
            canonical_role = self._canonical_entity(role_name)
            is_self_dimension = dimension.table == fact_table

            join_condition: Optional[str] = None
            if not is_self_dimension:
                join_condition = self._find_fk_condition(fact_table, dimension.table, fk_hints)
                if not join_condition:
                    logger.warning(
                        f"⚠️ No FK join condition available between {fact_table} and {dimension.table}"
                    )
                    join_condition = self._synthesize_join_condition(
                        fact_candidate,
                        dimension,
                        role_name,
                    )
                    if not join_condition:
                        if required:
                            logger.error(
                                f"❌ Unable to synthesize join condition between {fact_table} and {dimension.table}"
                            )
                            return None
                        # Keep dimension metadata for optional joins (used for labels)
                        join_condition = None

            join_plan["dimensions"][canonical_role or role_name] = {
                "table": dimension.table,
                "join_condition": join_condition,
                "id_columns": dimension.id_columns,
                "label_columns": dimension.label_columns,
                "self_join": is_self_dimension,
            }

            if join_condition:
                join_plan["joins"].append(
                    {
                        "table": dimension.table,
                        "on": join_condition,
                        "type": "INNER",
                        "role": canonical_role or role_name,
                    }
                )
            return dimension

        if required_action in {"topk_sum_by_customer", "sum_by_customer"}:
            customer_dim = attach_dimension("customer", required=True)
            if not customer_dim:
                error = {
                    "type": "DIMENSION_MISSING",
                    "message": "Customer dimension is required but was not identified in discovery.",
                }
                logger.error(error["message"])
                return {**state, "error_info": error}

        if required_action in {"topk_sum_by_product", "sum_by_product"}:
            product_dim = attach_dimension("product", required=True)
            if not product_dim:
                error = {
                    "type": "DIMENSION_MISSING",
                    "message": "Product dimension is required but was not identified in discovery.",
                }
                logger.error(error["message"])
                return {**state, "error_info": error}

        if required_action == "low_stock":
            attach_dimension("product", required=False)

        state["join_plan"] = join_plan
        return state

    async def _probe_columns(self, table_name: str) -> List[str]:
        """Probe a table/view for its column names using a small SELECT TOP 1 *."""
        try:
            # Prefer MCP get_column_index (faster, structured)
            try:
                idx = await self.mcp.get_column_index(table_name)
                if isinstance(idx, list) and idx:
                    # Tool returns list of column names directly
                    return [str(c) for c in idx if c]
                if isinstance(idx, dict):
                    cols = idx.get("columns") or idx.get("data") or []
                    if isinstance(cols, list) and cols:
                        return [str(c) for c in cols if c]
            except Exception:
                pass

            # Fallback: issue a TOP 1 probe and parse columns from the MCP JSON envelope
            probe_sql = f"SELECT TOP 1 * FROM {table_name}"
            result = await self.mcp.query_bounded(probe_sql, max_rows=1, timeout_ms=5000)
            if isinstance(result, dict) and result.get("ok"):
                columns = result.get("columns") or []
                if isinstance(columns, list) and columns:
                    return [str(c) for c in columns if c]
                rows = result.get("data") or []
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    return list(rows[0].keys())
            # Try sys catalog as a final fallback (MSSQL only)
            try:
                import os as _os
                if (_os.getenv("DB_DIALECT") or "").lower() == "mssql":
                    full = (table_name or "").strip()
                    if '.' in full:
                        parts = full.split('.')
                        schema = parts[-2]
                        obj = parts[-1]
                    else:
                        schema = 'dbo'
                        obj = full
                    sys_sql = (
                        "SELECT c.name AS col_name "
                        "FROM sys.columns c "
                        "JOIN sys.objects o ON c.object_id = o.object_id "
                        "JOIN sys.schemas s ON o.schema_id = s.schema_id "
                        f"WHERE s.name = '{schema}' AND o.name = '{obj}'"
                    )
                    sres = await self.mcp.query_bounded(sys_sql, max_rows=500, timeout_ms=5000)
                    if isinstance(sres, dict) and sres.get("ok"):
                        rows = sres.get("data") or []
                        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                            cols = [r.get("col_name") for r in rows if r.get("col_name")]
                            if cols:
                                return [str(c) for c in cols]
            except Exception:
                pass
            return []
        except Exception:
            return []

    async def _generate_sql_node(self, state: BaseState) -> BaseState:
        """
        Generate MSSQL query from join plan.
        """
        logger.info("🔨 Generating MSSQL query...")
        logger.info(f"🔨 [SQL_GEN] Input state keys: {list(state.keys())}")

        join_plan = state.get("join_plan")
        schema_snippet = state.get("schema_snippet", "")
        intent = state.get("intent", {})

        logger.info(f"🔨 [SQL_GEN] join_plan: {join_plan}")
        logger.info(f"🔨 [SQL_GEN] intent: {intent}")

        if not join_plan:
            error = {
                "type": "NO_PLAN",
                "message": "No join plan available for SQL generation",
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            # Enhanced SQL generation based on intent and metrics
            strategy = join_plan.get("strategy", "joins")
            intent = state.get("intent", {})
            metrics = intent.get("metrics", [])
            required_action = (intent.get("required_action") or "").lower()

            # Route based on analytic template if present
            analytic_template = intent.get("analytic_template")
            if analytic_template:
                logger.info(f"🎯 [TEMPLATE] Routing to template generator: {analytic_template}")
                if analytic_template == "COUNT_ENTITY":
                    return await self._generate_count_entity_sql(state)
                elif analytic_template == "TOP_K_BY_METRIC":
                    return await self._generate_top_k_by_metric_sql(state)
                elif analytic_template == "PERIOD_COMPARISON":
                    return await self._generate_period_comparison_sql(state)

            # Handle ranked_metrics (derived metrics like profit_margin with ranking)
            if required_action == "ranked_metrics":
                logger.info(f"🔨 [SQL_GEN] Routing to ranked metrics generator (derived metrics with ranking)")
                return await self._generate_ranked_metrics_sql(state)

            template_actions = {
                "topk_sum_by_customer",
                "sum_with_period",
                "sum_by_customer",
                "topk_sum_by_product",
                "sum_by_product",
                "low_stock",
                "growth_analysis",
                "comparative_analysis",
            }
            if required_action in template_actions:
                builder = MSSQLTemplateBuilder(join_plan=join_plan, intent=intent, row_limit=self.row_limit)
                try:
                    template_result = builder.build()
                except TemplateBuildError as exc:
                    return {**state, "error_info": exc.as_error_info()}

                state["sql_query"] = template_result["sql"]
                join_plan.update(template_result.get("metadata", {}))
                state["join_plan"] = join_plan
                return state

            parsed_top_k = intent.get("top_k")
            group_by_hint = (intent.get("group_by") or "").lower()
            # Heuristic: treat "how many"/"wie viele" as COUNT if metrics empty
            user_text = (state.get("user_input") or "").lower()
            if (not metrics) and ("how many" in user_text or "wie viele" in user_text):
                metrics = ["count"]
            time_window = intent.get("time_window")
            column_index = state.get("column_index", {}) or {}

            # PHASE 2: Intent-Driven SQL Generation Router
            # Route to specialized SQL generators based on required_action
            if required_action == "topk_sum_by_customer":
                logger.info(f"🔨 [SQL_GEN] Routing to TOP-K customer revenue generator")
                return await self._generate_topk_customer_revenue_sql(state)
            elif required_action == "sum_with_period":
                logger.info(f"🔨 [SQL_GEN] Routing to SUM with temporal period generator")
                return await self._generate_sum_with_period_sql(state)
            elif required_action == "trend_series":
                logger.info(f"🔨 [SQL_GEN] Routing to trend series generator")
                return await self._generate_trend_series_sql(state)
            elif required_action == "month_count":
                logger.info(f"🔨 [SQL_GEN] Routing to month-filtered count generator")
                return await self._generate_month_filtered_count_sql(state)
            elif required_action == "growth_analysis":
                logger.info(f"🔨 [SQL_GEN] Routing to growth analysis generator")
                return await self._generate_growth_analysis_sql(state)
            elif required_action == "department_productivity":
                logger.info(f"🔨 [SQL_GEN] Routing to department productivity generator")
                return await self._generate_department_productivity_sql(state)
            elif required_action == "comparative_analysis":
                logger.info(f"🔨 [SQL_GEN] Routing to comparative analysis generator")
                return await self._generate_comparative_analysis_sql(state)
            elif required_action == "interpret_previous":
                # This should be handled by the InterpretationAgent, not here
                logger.warning(f"🔨 [SQL_GEN] Received interpret_previous action - should be handled by InterpretationAgent")
                error = {
                    "type": "ROUTING_ERROR",
                    "message": "Interpretation requests should be routed to InterpretationAgent, not SQL generation",
                }
                return {**state, "error_info": error}

            # Continue with legacy logic for unrecognized actions

            # Determine if this is an aggregation query
            has_aggregation = any(m.lower() in ["count", "sum", "total", "avg", "average", "max", "min", "most"] for m in metrics)

            # Force join strategy for customer Top-K SUM so we can attach a customer dimension
            if required_action == "topk_sum_by_customer":
                strategy = "joins"

            # Extract TOP-K if present in user text
            def _parse_top_k(text: str) -> Optional[int]:
                import re
                m = re.search(r"top\s+(\d{1,3})", text, flags=re.IGNORECASE)
                try:
                    return int(m.group(1)) if m else None
                except Exception:
                    return None

            top_k = _parse_top_k(user_text)
            if top_k is None and ("top" in user_text):
                top_k = 5  # sensible default when user says "Top ..." without a number
            if parsed_top_k and isinstance(parsed_top_k, int):
                top_k = parsed_top_k
            logger.info(f"🔨 [SQL_GEN] Parsed top_k from user_text='{user_text}': {top_k}")

            # Detect time-series/trend requests (e.g., "over the last 3 years")
            def _parse_last_n_units(text: str) -> Optional[Tuple[str, int]]:
                import re
                # e.g., "last 3 years", "last three years"
                numerals = {
                    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
                }
                text = text.lower()
                m = re.search(r"last\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(year|years|month|months)", text)
                if not m:
                    return None
                n_raw = m.group(1)
                unit = m.group(2)
                try:
                    n = int(n_raw)
                except Exception:
                    n = numerals.get(n_raw, None)
                if not n:
                    return None
                return ("years" if "year" in unit else "months", n)

            def _contains_month_name(text: str) -> Optional[int]:
                months = {
                    "january":1, "february":2, "march":3, "april":4, "may":5, "june":6,
                    "july":7, "august":8, "september":9, "october":10, "november":11, "december":12,
                    # German
                    "januar":1, "februar":2, "märz":3, "maerz":3, "april":4, "mai":5, "juni":6,
                    "juli":7, "august":8, "september":9, "oktober":10, "november":11, "dezember":12
                }
                for k, v in months.items():
                    if k in text:
                        return v
                return None

            entities = [e.lower() for e in (intent.get("primary_entities") or [])]
            wants_count = any(m.lower() == "count" for m in metrics)
            last_n = _parse_last_n_units(user_text)
            month_literal = _contains_month_name(user_text)

            # Helper to pick a date column when needed by time filters
            async def _ensure_columns_for(table_name: str) -> List[str]:
                cols = column_index.get(table_name) if isinstance(column_index, dict) else None
                if cols:
                    return cols
                # Probe if missing
                probed = await self._probe_columns(table_name)
                if isinstance(column_index, dict):
                    column_index[table_name] = probed
                return probed

            def _pick_date_column(columns: List[str]) -> Optional[str]:
                tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung", "liefer", "rechn"]
                lc = [c.lower() for c in columns]
                for t in tokens:
                    for i, name in enumerate(lc):
                        if t in name:
                            return columns[i]
                return None

            # Trend (time series) by year for last N years
            if wants_count and last_n and strategy == "joins" or wants_count and last_n:
                primary_table = join_plan.get("primary_table")
                cols = await _ensure_columns_for(primary_table)
                date_col = _pick_date_column(cols)
                if date_col:
                    unit, n = last_n
                    if unit == "years":
                        sql = (
                            f"SELECT YEAR({date_col}) AS period_year, COUNT(*) AS total_count "
                            f"FROM {primary_table} "
                            f"WHERE {date_col} >= DATEADD(year, -{max(1,n)}, GETDATE()) "
                            f"GROUP BY YEAR({date_col}) ORDER BY period_year"
                        )
                        state["sql_query"] = sql
                        return state
                    elif unit == "months":
                        sql = (
                            f"SELECT FORMAT({date_col}, 'yyyy-MM') AS period_month, COUNT(*) AS total_count "
                            f"FROM {primary_table} "
                            f"WHERE {date_col} >= DATEADD(month, -{max(1,n)}, GETDATE()) "
                            f"GROUP BY FORMAT({date_col}, 'yyyy-MM') ORDER BY period_month"
                        )
                        state["sql_query"] = sql
                        return state

            # Specific month (e.g., "October"): default to current year
            if wants_count and month_literal is not None:
                primary_table = join_plan.get("primary_table")
                cols = await _ensure_columns_for(primary_table)
                date_col = _pick_date_column(cols)
                if date_col:
                    sql = (
                        f"SELECT COUNT(*) AS total_count FROM {primary_table} "
                        f"WHERE MONTH({date_col}) = {month_literal} AND YEAR({date_col}) = YEAR(GETDATE())"
                    )
                    state["sql_query"] = sql
                    return state

            # Normalize desire for SUM aggregation (sometimes not explicitly classified)
            entities_lc = [e.lower() for e in (intent.get("primary_entities") or [])]
            wants_sum = any((m or '').lower() in ["sum", "total"] for m in (metrics or []))
            if (not wants_sum) and ("top" in user_text):
                # Heuristic: Top-K implies an aggregate ranking; prefer SUM for sales/revenue style intents
                wants_sum = True

            if required_action == "topk_sum_by_customer":
                # Force SUM + GROUP BY customer
                metrics = list(set([*(metrics or []), "sum"]))
                entities_lc = [e.lower() for e in (intent.get("primary_entities") or [])]
                primary_table = join_plan.get("primary_table", "")
                joins = join_plan.get("joins", [])

                # Try to pick a better primary that has both customer key and amount column
                try:
                    candidates = (state.get("relevant_tables") or []) + (state.get("candidate_views") or [])
                    def has_tokens(cols: List[str], tokens: List[str]) -> bool:
                        lc = [c.lower() for c in cols or []]
                        return any(any(t in name for t in tokens) for name in lc)

                    sum_tokens = ["umsatz", "betrag", "amount", "total", "summe", "preis", "gesamtpreis", "netto", "brutto", "rechnungsbetrag"]
                    cust_key_tokens = ["kunde", "kundennr", "kundennummer", "customer", "adress", "adressid"]
                    label_tokens = ["name", "matchcode", "firma", "company"]

                    best_primary = primary_table
                    best_score = -1
                    for c in candidates[:10]:
                        name = c if isinstance(c, str) else (c.get("table_name") or c.get("name") or c.get("full_name") or "")
                        if not name:
                            continue
                        cols = column_index.get(name) if isinstance(column_index, dict) else None
                        if not cols:
                            cols = await self._probe_columns(name)
                            if isinstance(column_index, dict):
                                column_index[name] = cols
                        if not cols:
                            continue
                        has_amount = has_tokens(cols, sum_tokens)
                        has_cust_key = has_tokens(cols, cust_key_tokens)
                        has_label = has_tokens(cols, label_tokens)
                        # Score: require amount; prefer also customer key or label
                        score = (1 if has_amount else 0) + (1 if has_cust_key else 0) + (1 if has_label else 0)
                        if score > best_score:
                            best_score = score
                            best_primary = name
                        if best_score >= 3:
                            break
                    if best_primary and best_primary != primary_table and best_score > 0:
                        primary_table = best_primary
                        join_plan["primary_table"] = best_primary
                except Exception:
                    pass
                # Safeguard: if chosen primary is not sales-like, force a sales-view primary from candidate_views
                try:
                    def _looks_sales(nm: str) -> bool:
                        n = (nm or "").lower()
                        if any(x in n for x in ["berecht", "permission", "rechte", "user", "role", "auth"]):
                            return False
                        return any(t in n for t in ["vk","verkauf","rechnung","beleg","umsatz","invoice","order","position","umsatz","faktura"]) and not any(a in n for a in ["archiv","archive","ek","projekt"])
                    if not _looks_sales(primary_table):
                        cand_views = state.get("candidate_views", []) or []
                        for cv in cand_views:
                            nm = cv if isinstance(cv, str) else (cv.get("table_name") or cv.get("name") or cv.get("full_name") or "")
                            if nm and _looks_sales(nm):
                                primary_table = nm
                                join_plan["primary_table"] = nm
                                break
                except Exception:
                    pass
                # Ensure a customer-like dimension is present via dynamic column intersection (no name hardcodes)
                try:
                    def candidate_keys(cols: List[str]) -> List[str]:
                        keys = []
                        lc = [c.lower() for c in (cols or [])]
                        for i, nm in enumerate(lc):
                            if nm == 'id' or nm.endswith('_id') or nm.endswith('id') or 'nr' in nm or 'number' in nm:
                                keys.append((cols or [None])[i])
                        return keys

                    def has_label_column(cols: List[str]) -> bool:
                        lc = [c.lower() for c in (cols or [])]
                        return any(('name' in nm) or ('label' in nm) or ('title' in nm) for nm in lc)

                    # Probe primary columns
                    pcols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                    if not pcols:
                        pcols = await self._probe_columns(primary_table)
                        if isinstance(column_index, dict):
                            column_index[primary_table] = pcols
                    pkeys = set(candidate_keys(pcols))

                    has_join = any(isinstance(j, dict) and j.get("table") and j.get("on") for j in (joins or []))
                    if not has_join and pkeys:
                        candidates = (state.get("candidate_views") or []) + (state.get("relevant_tables") or [])
                        best_dim = None
                        best_pair = None
                        for c in candidates:
                            name = c if isinstance(c, str) else (c.get("table_name") or c.get("name") or c.get("full_name") or "")
                            if not name or name == primary_table:
                                continue
                            dcols = column_index.get(name) if isinstance(column_index, dict) else None
                            if not dcols:
                                dcols = await self._probe_columns(name)
                                if isinstance(column_index, dict):
                                    column_index[name] = dcols
                            if not dcols or not has_label_column(dcols):
                                continue
                            dkeys = set(candidate_keys(dcols))
                            # Prefer exact key-name intersections
                            inter = [k for k in pkeys if k in dkeys]
                            if inter:
                                best_dim = name
                                best_pair = (inter[0], inter[0])
                                break
                            # Otherwise try case-insensitive match without underscores
                            def norm(s: str) -> str:
                                return (s or '').lower().replace('_', '')
                            inter2 = [(pk, dk) for pk in pkeys for dk in dkeys if norm(pk) == norm(dk)]
                            if inter2:
                                best_dim = name
                                best_pair = inter2[0]
                                break
                        if best_dim and best_pair:
                            pk, dk = best_pair
                            joins = list(joins or [])
                            joins.append({
                                "table": best_dim,
                                "on": f"{primary_table}.{pk} = {best_dim}.{dk}",
                                "type": "LEFT"
                            })
                            join_plan["joins"] = joins
                except Exception:
                    pass
                # Ensure columns for primary
                cols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                if not cols:
                    probed = await self._probe_columns(primary_table)
                    column_index = dict(column_index or {})
                    column_index[primary_table] = probed
                try:
                    sql = self._generate_topk_sum_sql(primary_table, joins, column_index, time_window, top_k or 5)
                except AttributeError:
                    # Minimal inline builder fallback
                    pcols = column_index.get(primary_table, []) if isinstance(column_index, dict) else []
                    def pick_sum(columns: List[str]) -> Optional[str]:
                        toks = [
                            "umsatz", "betrag", "amount", "total", "summe", "value", "preis",
                            "gesamtpreis", "netto", "brutto", "rechnungsbetrag", "erloes", "erlös",
                            "umsatzbetrag", "positionswert", "gesamtwert"
                        ]
                        lc = [c.lower() for c in (columns or [])]
                        for t in toks:
                            for i, nm in enumerate(lc):
                                if t in nm:
                                    return (columns or [None])[i]
                        return None
                    def pick_name(columns: List[str]) -> Optional[str]:
                        lc = [c.lower() for c in (columns or [])]
                        for i, nm in enumerate(lc):
                            if ("name" in nm) or ("matchcode" in nm) or ("firma" in nm) or ("company" in nm):
                                return (columns or [None])[i]
                        return None
                    sum_col = pick_sum(pcols)
                    group_expr = None
                    on_clauses = []
                    for j in (joins or []):
                        jt = j.get("table"); on = j.get("on");
                        if jt and on:
                            on_clauses.append((jt, on))
                            jcols = column_index.get(jt, []) if isinstance(column_index, dict) else []
                            if not group_expr:
                                name_col = pick_name(jcols)
                                if name_col:
                                    group_expr = f"{jt}.{name_col}"
                    if not sum_col:
                        # last resort: count rows
                        select_agg = "COUNT(*) AS total_value"
                    else:
                        select_agg = f"SUM({primary_table}.{sum_col}) AS total_value"
                    sql = f"SELECT TOP {max(1, top_k or 5)} "
                    if group_expr:
                        sql += f"{group_expr} AS customer, "
                    sql += f"{select_agg} FROM {primary_table}"
                    for jt, on in on_clauses:
                        sql += f" LEFT JOIN {jt} ON {on}"
                    if group_expr:
                        sql += f" GROUP BY {group_expr} ORDER BY total_value DESC"
                    else:
                        sql += " ORDER BY (SELECT NULL)"
                # If SQL still lacks a SUM/GROUP BY, rebuild strictly from discovery-provided sources
                try:
                    up_sql = (sql or "").upper()
                    wants_sum_now = "SUM(" in up_sql and "GROUP BY" in up_sql
                    if not wants_sum_now:
                        pool: List[str] = []
                        for c in (state.get("relevant_tables") or []):
                            if isinstance(c, str):
                                pool.append(c)
                        for cv in (state.get("candidate_views") or []):
                            if isinstance(cv, str):
                                pool.append(cv)
                            elif isinstance(cv, dict):
                                nm = cv.get("table_name") or cv.get("name") or cv.get("full_name")
                                if nm:
                                    pool.append(nm)
                        def looks_salesy(name: str) -> bool:
                            n = (name or "").lower()
                            if any(x in n for x in ["berecht", "permission", "rechte", "user", "role", "auth"]):
                                return False
                            return any(t in n for t in ["vk","verkauf","rechnung","beleg","position","umsatz","invoice","order","position","umsatz","faktura"]) and not any(a in n for a in ["archiv","archive","ek","projekt"])
                        best = None
                        for name in pool:
                            if not looks_salesy(name):
                                continue
                            rc = column_index.get(name) if isinstance(column_index, dict) else None
                            if not rc:
                                rc = await self._probe_columns(name)
                                if isinstance(column_index, dict):
                                    column_index[name] = rc
                            if any(t in (c or '').lower() for c in (rc or []) for t in ["umsatz","betrag","amount","total","summe","preis","gesamtpreis","wert","vkpreis","verkaufspreis","vkwert","verkaufswert"]):
                                best = name
                                break
                        if best:
                            primary_table = best
                            # Build group-by
                            def pick_group_any(columns: List[str]) -> Optional[str]:
                                lc = [c.lower() for c in (columns or [])]
                                label_tokens = ["kunde","kunden","customer","matchcode","name","firma","company"]
                                key_tokens = ["kundennr","kunden_id","kundenid","adressid","customerid","kdnr","debitor","debitornr"]
                                for t in label_tokens:
                                    for i, nm in enumerate(lc):
                                        if t in nm:
                                            return (columns or [None])[i]
                                for t in key_tokens:
                                    for i, nm in enumerate(lc):
                                        if t in nm:
                                            return (columns or [None])[i]
                                return None
                            def pick_sum_any(columns: List[str]) -> Optional[str]:
                                lc = [c.lower() for c in (columns or [])]
                                for t in ["umsatz","betrag","amount","total","summe","preis","gesamtpreis","wert","vkpreis","verkaufspreis","vkwert","verkaufswert"]:
                                    for i, nm in enumerate(lc):
                                        if t in nm:
                                            return (columns or [None])[i]
                                return None
                            rc = column_index.get(primary_table, []) if isinstance(column_index, dict) else []
                            sumc = pick_sum_any(rc)
                            gc_expr = None
                            for j in (joins or []):
                                jt = j.get("table"); jcols = column_index.get(jt, []) if isinstance(column_index, dict) else []
                                if not jcols:
                                    jcols = await self._probe_columns(jt)
                                    if isinstance(column_index, dict):
                                        column_index[jt] = jcols
                                cand = pick_group_any(jcols)
                                if cand:
                                    gc_expr = f"{jt}.{cand}"
                                    break
                            if not gc_expr:
                                cand = pick_group_any(rc)
                                if cand:
                                    gc_expr = f"{primary_table}.{cand}"
                            sql = f"SELECT TOP {max(1, top_k or 5)} "
                            if gc_expr:
                                sql += f"{gc_expr} AS customer, "
                            if sumc:
                                sql += f"SUM({primary_table}.{sumc}) AS total_value FROM {primary_table}"
                            else:
                                sql += f"COUNT(*) AS total_value FROM {primary_table}"
                            for j in (joins or []):
                                jt = j.get("table"); on = j.get("on"); jt = jt or ""; on = on or ""
                                if jt and on:
                                    sql += f" LEFT JOIN {jt} ON {on}"
                            if gc_expr:
                                sql += f" GROUP BY {gc_expr} ORDER BY total_value DESC"
                            else:
                                sql += " ORDER BY (SELECT NULL)"
                except Exception:
                    pass

                state["sql_query"] = sql
                return state
            elif required_action == "trend_series":
                # Generate grouped trend series (year/month) using detected date columns
                primary_table = join_plan.get("primary_table", "")
                joins = join_plan.get("joins", [])
                granularity = (intent.get("time_granularity") or "year").lower()
                # Ensure columns available
                cols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                if not cols:
                    probed = await self._probe_columns(primary_table)
                    column_index = dict(column_index or {})
                    column_index[primary_table] = probed
                sql = self._generate_trend_series_sql(primary_table, joins, column_index, time_window, granularity)
                state["sql_query"] = sql
                return state
            elif required_action == "month_count":
                # Month literal path already handled above; ensure COUNT fallback
                primary_table = join_plan.get("primary_table", "")
                # Ensure columns are available so date filters can be applied
                try:
                    cols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                    if not cols:
                        probed = await self._probe_columns(primary_table)
                        column_index = dict(column_index or {})
                        column_index[primary_table] = probed
                        cols = probed
                except Exception:
                    pass
                # Prefer explicit BETWEEN using detected or fallback date column
                start = end = None
                if isinstance(time_window, dict):
                    start = time_window.get("start")
                    end = time_window.get("end")
                def pick_date(columns: List[str]) -> Optional[str]:
                    tokens = ["beleg", "datum", "date", "erfass", "buch", "liefer", "rechn"]
                    lc = [c.lower() for c in (columns or [])]
                    for t in tokens:
                        for i, nm in enumerate(lc):
                            if t in nm:
                                return (columns or [None])[i]
                    return None
                date_col = pick_date(cols or [])
                if (not date_col) and (start and end):
                    for fb in ["Belegdatum", "Erfassungsdatum", "Buchungsdatum", "Liefertermin", "Rechnungsdatum"]:
                        date_col = fb
                        break
                if start and end and date_col:
                    sql = (
                        f"SELECT COUNT(*) AS total_count FROM {primary_table} "
                        f"WHERE {date_col} >= '{start}' AND {date_col} <= '{end}'"
                    )
                else:
                    sql = self._generate_aggregation_sql_with_hints(primary_table, ["count"], time_window, column_index)
                state["sql_query"] = sql
                return state
            elif strategy == "view":
                # View-based query
                primary_table = join_plan.get("primary_table", "")
                filters = join_plan.get("where_filters", [])

                if has_aggregation or wants_sum:
                    # Prefer TOP-K SUM aggregated SQL for customer revenue intents even when using views
                    entities = entities_lc
                    if wants_sum and (top_k is not None) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities):
                        # Ensure we have columns, probe if missing
                        cols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                        if not cols:
                            probed = await self._probe_columns(primary_table)
                            column_index = dict(column_index or {})
                            column_index[primary_table] = probed
                        sql = self._generate_topk_sum_sql(primary_table, [], column_index, time_window, top_k)
                    else:
                        # Ensure date columns are available for time_window filters
                        try:
                            if time_window and (not (isinstance(column_index, dict) and column_index.get(primary_table))):
                                probed = await self._probe_columns(primary_table)
                                column_index = dict(column_index or {})
                                column_index[primary_table] = probed
                        except Exception:
                            pass
                    # Generate aggregation SQL based on intent using column_index hints
                    sql = self._generate_aggregation_sql_with_hints(primary_table, metrics, time_window, column_index)
                else:
                    # Regular SELECT * query
                    sql = f"SELECT TOP {self.row_limit} * FROM {primary_table}"
                    # Add WHERE clause if filters exist
                    if filters:
                        where_conditions = self._build_where_conditions(filters)
                        if where_conditions:
                            sql += " WHERE " + " AND ".join(where_conditions)

            else:
                # Join-based query
                primary_table = join_plan.get("primary_table", "")
                joins = join_plan.get("joins", [])
                filters = join_plan.get("where_filters", [])

                if has_aggregation or wants_sum:
                    # Try to produce a meaningful aggregate; ensure columns exist via probe if needed
                    if wants_sum and (top_k is not None):
                        cols = column_index.get(primary_table) if isinstance(column_index, dict) else None
                        if not cols:
                            probed = await self._probe_columns(primary_table)
                            column_index = dict(column_index or {})
                            column_index[primary_table] = probed
                        sql = self._generate_topk_sum_sql(primary_table, joins, column_index, time_window, top_k)
                    else:
                        # Ensure columns are available to enable date-based filters
                        try:
                            if time_window and (not (isinstance(column_index, dict) and column_index.get(primary_table))):
                                probed = await self._probe_columns(primary_table)
                                column_index = dict(column_index or {})
                                column_index[primary_table] = probed
                        except Exception:
                            pass
                    sql = self._generate_aggregation_sql_with_hints(primary_table, metrics, time_window, column_index)

                    # Add JOINs if present
                    for join in joins:
                        join_type = join.get("type", "INNER")
                        join_table = join.get("table", "")
                        join_condition = join.get("on", "")
                        sql += f" {join_type} JOIN {join_table} ON {join_condition}"

                    # Add time window filter if specified
                    where_conditions = []
                    if time_window:
                        where_conditions.extend(self._build_time_window_conditions(time_window))

                    if where_conditions:
                        sql += " WHERE " + " AND ".join(where_conditions)

                    sql += " ORDER BY (SELECT NULL)"  # Dummy ORDER BY to ensure query works
                else:
                    # Build FROM and JOINs for regular query
                    sql = f"SELECT TOP {self.row_limit} * FROM {primary_table}"

                    for join in joins:
                        join_type = join.get("type", "INNER")
                        join_table = join.get("table", "")
                        join_condition = join.get("on", "")
                        sql += f" {join_type} JOIN {join_table} ON {join_condition}"

                    # Add WHERE clause if filters exist
                    if filters:
                        where_conditions = self._build_where_conditions(filters)
                        if where_conditions:
                            sql += " WHERE " + " AND ".join(where_conditions)

            # Fallback correction: if we intended TOP-K SUM but ended with SELECT * (exploratory), force aggregate
            try:
                sql_upper = (sql or "").upper()
                if wants_sum and (top_k is not None):
                    if sql_upper.startswith("SELECT TOP ") and "* FROM" in sql_upper:
                        # Force regenerate using aggregate builder
                        primary_table = join_plan.get("primary_table", "")
                        joins = join_plan.get("joins", [])
                        logger.info("🔨 [SQL_GEN] Overriding exploratory SELECT * with TOP-K SUM aggregate SQL")
                        sql = self._generate_topk_sum_sql(primary_table, joins, column_index, time_window, top_k)
            except Exception:
                pass

            # 🔧 CRITICAL VALIDATION: Ensure SQL is valid before returning
            logger.info(f"🔨 [SQL_GEN] Generated SQL: '{sql}'")

            if not sql or sql.strip() == "":
                raise ValueError("Generated SQL is empty")

            if not sql.upper().startswith("SELECT"):
                raise ValueError(f"Generated SQL doesn't start with 'SELECT': {sql[:50]}")

            # Check for required table reference
            if "FROM" not in sql.upper():
                raise ValueError("Generated SQL has no FROM clause")

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

    def _extract_table_names_from_sql(self, sql: str) -> List[str]:
        """
        Extract all table names referenced in a SQL query.

        Finds tables in FROM and JOIN clauses.
        Handles [schema].[table] and schema.table formats.
        """
        import re
        table_names = []

        try:
            # Pattern to match table names in FROM and JOIN clauses
            # Matches: FROM|JOIN schema.table or schema.[table] or [schema].[table]
            pattern = r'(?:FROM|JOIN)\s+(?:\[?[\w_]+\]?\.)?(?:\[?[\w_]+\]?)'
            matches = re.finditer(pattern, sql, re.IGNORECASE)

            for match in matches:
                text = match.group(0)
                # Extract the table part after FROM/JOIN and any whitespace
                table_part = re.sub(r'(?:FROM|JOIN)\s+', '', text, flags=re.IGNORECASE).strip()
                if table_part:
                    # Remove brackets if present
                    table_part = table_part.replace('[', '').replace(']', '')
                    table_names.append(table_part)
        except Exception as e:
            logger.warning(f"Failed to extract table names from SQL: {e}")

        return table_names

    def _extract_cte_names(self, sql: str, select_idx: int) -> Set[str]:
        """
        Extract names of CTEs declared before the main SELECT statement.
        """
        import re

        cte_segment = sql[:select_idx]
        pattern = re.compile(r'(?i)\b([A-Za-z0-9_\[\]\.]+)\b\s+AS\s*\(')
        names = set()
        for match in pattern.finditer(cte_segment):
            raw = match.group(1)
            if not raw:
                continue
            normalized = self._normalize_table_name(raw)
            if normalized:
                names.add(normalized)
        return names

    def _normalize_table_name(self, table_name: str) -> str:
        """
        Normalize a table name for comparison.

        Handles:
        - schema.table vs just table
        - [schema].[table] vs schema.table
        - Case insensitivity
        """
        # Remove brackets
        normalized = table_name.replace('[', '').replace(']', '')
        # Lowercase for comparison
        normalized = normalized.lower().strip()
        return normalized

    async def _validate_sql_node(self, state: BaseState) -> BaseState:
        """
        Perform comprehensive SQL syntax validation with re-planning support.

        CRITICAL NEW FEATURE (Phase 11): Table name validation against discovered tables.

        Enhanced validation checks:
        - Starts with SELECT
        - Has FROM clause
        - Has column list (not just "SELECT")
        - Valid MSSQL keywords
        - Balanced parentheses/quotes
        - **ALL TABLE NAMES EXIST IN DISCOVERY RESULTS** ← NEW
        - Minimum SQL completeness
        """
        logger.info("✅ Validating SQL...")

        sql = state.get("sql_query", "")

        if not sql:
            error = {
                "type": "NO_SQL",
                "message": "No SQL query to validate",
                "replan_needed": True
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

        try:
            # Basic checks
            sql_stripped = sql.strip()
            if len(sql_stripped) < 10:  # Very short queries are likely incomplete
                raise ValueError(f"Query too short ({len(sql_stripped)} chars) - likely incomplete")

            sql_upper = sql_stripped.upper()

            if sql_upper.startswith("WITH"):
                select_idx = sql_upper.find("SELECT")
                if select_idx == -1:
                    raise ValueError("CTE query missing SELECT statement")
            elif sql_upper.startswith("SELECT"):
                select_idx = 0
            else:
                raise ValueError("Query must start with SELECT")

            effective_upper = sql_upper[select_idx:]
            effective_sql = sql_stripped[select_idx:]
            sql_words = effective_upper.split()
            cte_names = self._extract_cte_names(sql_stripped, select_idx)

            # 🚨 ENHANCED: Check for incomplete SELECT statements
            if effective_upper in ["SELECT", "SELECT DISTINCT"] or len(sql_words) < 4:
                raise ValueError("Incomplete SELECT statement - missing columns or FROM clause")

            if "FROM" not in effective_upper:
                raise ValueError("Query must have FROM clause")

            # 🚨 ENHANCED: Check for proper column specification (not just SELECT FROM)
            select_to_from = effective_upper[6:effective_upper.index("FROM")].strip()  # Skip "SELECT "
            if not select_to_from or select_to_from in ["", "DISTINCT"]:
                raise ValueError("Missing column specification between SELECT and FROM")

            # Check for balanced quotes and parentheses
            if sql.count("'") % 2 != 0:
                raise ValueError("Unbalanced quotes")

            if sql.count("(") != sql.count(")"):
                raise ValueError("Unbalanced parentheses")

            # No DML (only SELECT allowed)
            for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]:
                if keyword in sql_upper:
                    raise ValueError(f"Non-SELECT statement detected: {keyword}")

            # 🚨 ENHANCED: Check minimum table reference
            if not any(
                word not in MSSQL_FUNCTIONS
                for word in sql_words[sql_words.index("FROM") + 1 : sql_words.index("FROM") + 3]
                if sql_words.index("FROM") + 1 < len(sql_words)
            ):
                raise ValueError("Missing or invalid table reference after FROM")

            # 🚨🚨🚨 PHASE 11 CRITICAL FIX: Validate all table names exist in discovery results
            logger.info("🔍 Phase 11: Validating table names against discovered tables...")

            # Get discovered tables from state
            discovered_tables = set()

            # Add relevant_tables
            for t in (state.get("relevant_tables") or []):
                discovered_tables.add(self._normalize_table_name(t))

            # Add candidate_views
            for cv in (state.get("candidate_views") or []):
                if isinstance(cv, str):
                    discovered_tables.add(self._normalize_table_name(cv))
                elif isinstance(cv, dict):
                    name = cv.get("table_name") or cv.get("name") or cv.get("full_name")
                    if name:
                        discovered_tables.add(self._normalize_table_name(name))

            logger.info(f"✅ Discovered tables pool: {discovered_tables}")

            # Validate each SQL table is in the discovered set
            unknown_tables = []
            # NOTE: Phase 4/5 guardrails for required tables and semantic projections
            # have been moved to the orchestrator-level validate_sql node where we
            # have access to the validator's AST-derived tables_used metadata.
            # This local validation step now focuses solely on table-name sanity
            # via discovery results to catch obvious mismatches early.
            sql_tables = self._extract_table_names_from_sql(sql)
            logger.info(f"📊 Tables referenced in SQL (regex approximation): {sql_tables}")

            for sql_table in sql_tables:
                normalized = self._normalize_table_name(sql_table)

                if normalized in cte_names:
                    logger.info(f"  ✅ Table '{sql_table}' resolved via CTE definition")
                    continue

                # Check exact match
                if normalized in discovered_tables:
                    logger.info(f"  ✅ Table '{sql_table}' found in discovered tables")
                    continue

                # Check partial match (just the table name without schema)
                if '.' in normalized:
                    table_only = normalized.split('.')[-1]
                else:
                    table_only = normalized

                # Look for partial matches
                found = False
                for discovered in discovered_tables:
                    if discovered.endswith(table_only) or discovered == table_only:
                        logger.info(f"  ✅ Table '{sql_table}' matched as '{discovered}'")
                        found = True
                        break

                if not found:
                    unknown_tables.append(sql_table)
                    logger.warning(f"  ❌ Table '{sql_table}' NOT FOUND in discovered tables")

            if unknown_tables:
                raise ValueError(
                    f"SQL references unknown tables: {', '.join(unknown_tables)}. "
                    f"Discovered tables were: {', '.join(sorted(discovered_tables))}. "
                    f"This may indicate the discovery phase found wrong tables - check intent parsing."
                )

            logger.info("✅ SQL validation passed (including table name validation)")
            return state

        except Exception as e:
            # 🚨 ENHANCED: Mark validation errors as requiring re-planning
            error = {
                "type": "SQL_VALIDATION_ERROR",
                "message": f"SQL validation failed: {str(e)}",
                "error": str(e),
                "sql": sql[:200],
                "replan_needed": True,  # Signal that re-planning is needed
                "validation_stage": "syntax_and_table_check"
            }
            logger.error(f"❌ {error['message']}")
            logger.info("🔄 Validation failure detected - will trigger re-planning")
            return {**state, "error_info": error}

    # Helper methods

    def _parse_relations_result(self, result: List[Dict[str, Any]], table_name: str) -> List[Dict[str, Any]]:
        """Parse MCP list_relations result."""
        if not result or len(result) == 0:
            return []

        try:
            content = result[0].get("text", "")
            data = _extract_json_from_text(content) if content else {}

            relations = []
            if isinstance(data, dict):
                payload = data.get("data") if isinstance(data.get("data"), dict) else data
                relations = payload.get("neighbors") or payload.get("relations") or payload.get("relationships") or []
            elif isinstance(data, list):
                relations = data

            normalized = []
            for rel in relations or []:
                if not isinstance(rel, dict):
                    continue
                normalized.append(
                    {
                        "from_table": table_name,
                        "to_table": rel.get("related_table") or rel.get("to_table") or rel.get("table") or "",
                        "from_column": rel.get("from_column") or rel.get("column") or "",
                        "to_column": rel.get("to_column") or rel.get("related_column") or "",
                        "join_condition": rel.get("join_condition") or "",
                    }
                )

            return normalized
        except Exception as e:
            logger.warning(f"Failed to parse relations result: {e}")
            return []

    def _required_dimension_roles(self, required_action: str, intent: Dict[str, Any]) -> Set[str]:
        """Return canonical dimension roles required for the given action."""
        action = (required_action or "").lower()
        roles: Set[str] = set()

        if action in {"topk_sum_by_customer", "sum_by_customer"}:
            roles.add("customer")
        if action in {"topk_sum_by_product", "sum_by_product", "low_stock"}:
            roles.add("product")
        if action in {"growth_analysis", "comparative_analysis"}:
            # prefer customer/product dimensions when comparing over time by customer/product
            for entity in intent.get("primary_entities") or []:
                canonical = self._canonical_entity(entity)
                if canonical in {"customer", "product", "project"}:
                    roles.add(canonical)

        return roles

    def _select_fact_candidate(self, role_hints: DiscoveryRoleHints, intent: Dict[str, Any]) -> Optional[RoleHintFact]:
        """Choose the most appropriate fact table candidate for the current intent."""
        if not role_hints.fact_candidates:
            return None

        required_action = (intent.get("required_action") or "").lower()
        needs_metric = required_action in {
            "topk_sum_by_customer",
            "sum_by_customer",
            "topk_sum_by_product",
            "sum_by_product",
            "sum_with_period",
            "growth_analysis",
            "comparative_analysis",
            "low_stock",
        }

        ranked = list(role_hints.fact_candidates)
        required_roles = self._required_dimension_roles(required_action, intent)

        ranked.sort(
            key=lambda fc: (
                max(fc.metric_candidates.values()) if fc.metric_candidates else 0.0,
                fc.estimated_rows or 0,
            ),
            reverse=True,
        )

        if required_roles:
            for candidate in ranked:
                entity_keys = candidate.entity_keys or {}
                available_roles = {
                    self._canonical_entity(role): cols
                    for role, cols in entity_keys.items()
                    if cols
                }
                if all(role in available_roles for role in required_roles):
                    return candidate

        if not needs_metric:
            return ranked[0]

        for candidate in ranked:
            if candidate.metric_candidates:
                return candidate
        return ranked[0]

    def _select_dimension(self, role_hints: DiscoveryRoleHints, role: str) -> Optional[RoleHintDimension]:
        """Retrieve a dimension hint by canonical role."""
        if not role:
            return None
        canonical = self._canonical_entity(role)
        if canonical in role_hints.dimensions:
            return role_hints.dimensions[canonical]
        for key, value in role_hints.dimensions.items():
            if self._canonical_entity(key) == canonical:
                return value
        return None

    def _find_fk_condition(
        self,
        from_table: str,
        to_table: str,
        fk_hints: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Locate a join condition between two tables from FK hints."""
        if not from_table or not to_table or not fk_hints:
            return None

        for hint in fk_hints:
            if (
                hint.get("from_table") == from_table
                and hint.get("to_table") == to_table
                and hint.get("join_condition")
            ):
                return hint["join_condition"]
            if (
                hint.get("from_table") == to_table
                and hint.get("to_table") == from_table
                and hint.get("join_condition")
            ):
                return hint["join_condition"]
        return None

    def _synthesize_join_condition(
        self,
        fact_candidate: RoleHintFact,
        dimension: RoleHintDimension,
        role: str,
    ) -> Optional[str]:
        """Synthesize a join condition using entity key hints when explicit FK metadata is missing."""
        fact_keys = fact_candidate.entity_keys.get(self._canonical_entity(role)) or []
        dim_ids = dimension.id_columns or dimension.label_columns

        if not fact_keys or not dim_ids:
            return None

        left_col, right_col = self._match_entity_columns(fact_keys, dim_ids)
        if not left_col or not right_col:
            return None

        left_expr = self._format_qualified_column(fact_candidate.table, left_col)
        right_expr = self._format_qualified_column(dimension.table, right_col)
        return f"{left_expr} = {right_expr}"

    def _match_entity_columns(self, fact_cols: List[str], dim_cols: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Best-effort column matching based on normalized names."""
        import re

        def norm(value: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (value or "").lower())

        for f_col in fact_cols:
            nf = norm(f_col)
            if not nf:
                continue
            for d_col in dim_cols:
                nd = norm(d_col)
                if not nd:
                    continue
                if nf == nd or nf.endswith(nd) or nd.endswith(nf):
                    return f_col, d_col
        return None, None

    def _format_qualified_column(self, table: str, column: str) -> str:
        """Return [schema].[table].[column] with brackets."""
        schema, name = self._split_table_name(table)
        col = column.split(".")[-1].strip("[]")
        return f"[{schema.strip('[]')}].[{name.strip('[]')}].[{col}]"

    def _split_table_name(self, table: str) -> Tuple[str, str]:
        raw = (table or "").strip()
        if not raw:
            raise TemplateBuildError("Table name is required to format join condition.")
        stripped = raw.strip("[]")
        if "." in stripped:
            schema, name = stripped.split(".", 1)
        else:
            schema, name = "dbo", stripped
        schema = schema.strip("[]") or "dbo"
        name = name.strip("[]")
        if not name:
            raise TemplateBuildError("Invalid table name for join condition.", {"table": table})
        return schema, name

    def _canonical_entity(self, entity: str) -> str:
        """Map entity labels to canonical singular keys."""
        if not entity:
            return ""
        stripped = entity.strip().lower()
        mapping = {
            "customer": "customer",
            "customers": "customer",
            "kunde": "customer",
            "kunden": "customer",
            "adress": "customer",
            "adressen": "customer",
            "contact": "customer",
            "contacts": "customer",
            "product": "product",
            "products": "product",
            "produkt": "product",
            "produkte": "product",
            "artikel": "product",
            "artikelstamm": "product",
            "project": "project",
            "projects": "project",
            "projekt": "project",
            "projekte": "project",
        }
        if stripped in mapping:
            return mapping[stripped]
        if stripped.endswith("en") and stripped[:-2] in mapping:
            return mapping[stripped[:-2]]
        if stripped.endswith("s") and stripped[:-1] in mapping:
            return mapping[stripped[:-1]]
        return stripped

    async def _ensure_columns_probed_for_join_plan(self, join_plan: Dict[str, Any], column_index: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Ensure all tables in join plan have columns probed and available in column_index.

        Args:
            join_plan: Join plan with primary_table and joins
            column_index: Current column index dict to update

        Returns:
            Updated column_index with all tables probed
        """
        updated_index = dict(column_index) if column_index else {}

        # Probe primary table
        primary_table = join_plan.get("primary_table", "")
        if primary_table and primary_table not in updated_index:
            cols = await self._probe_columns(primary_table)
            updated_index[primary_table] = cols
            logger.debug(f"🔍 Probed {len(cols)} columns for primary table: {primary_table}")

        # Probe joined tables
        joins = join_plan.get("joins", [])
        for join in joins:
            join_table = join.get("table", "")
            if join_table and join_table not in updated_index:
                cols = await self._probe_columns(join_table)
                updated_index[join_table] = cols
                logger.debug(f"🔍 Probed {len(cols)} columns for joined table: {join_table}")

        return updated_index

    async def _generate_topk_customer_revenue_sql(self, state: BaseState) -> BaseState:
        """Generate TOP-K SUM aggregate SQL for customer revenue queries.

        Handles queries like: "Top 5 customers by revenue", "Wer sind unsere Top 5 Kunden nach Gesamtumsatz?"
        """
        logger.info(f"🔨 [TOPK_REVENUE] Generating TOP-K customer revenue SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}
        user_text = (state.get("user_input") or "").lower()

        # Extract TOP-K (default 5)
        top_k = intent.get("top_k", 5)
        if not isinstance(top_k, int) or top_k < 1:
            top_k = 5

        # Get primary table (should be sales/invoice table)
        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for revenue aggregation"}
            return {**state, "error_info": error}

        # Ensure ALL tables in join plan have columns probed
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)

        # Update state with probed columns
        state["column_index"] = column_index

        # Get primary table columns
        cols = column_index.get(primary_table, [])

        if not cols:
            error = {"type": "NO_COLUMNS", "message": f"No columns available for table {primary_table}"}
            return {**state, "error_info": error}

        # Find revenue/amount column
        def find_amount_column(columns: List[str]) -> Optional[str]:
            tokens = ["umsatz", "betrag", "amount", "total", "summe", "preis", "gesamtpreis",
                     "netto", "brutto", "rechnungsbetrag", "erloes", "erlös", "vkpreis", "vkwert",
                     "verkaufspreis", "verkaufswert", "positionswert", "gesamtwert"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        amount_col = find_amount_column(cols)
        if not amount_col:
            # Fallback: try to find any numeric column
            numeric_cols = []
            for col in cols:
                col_lower = col.lower()
                if any(token in col_lower for token in ["betrag", "wert", "preis", "sum", "total", "amount"]):
                    numeric_cols.append(col)
            if numeric_cols:
                amount_col = numeric_cols[0]
            else:
                # Last resort: use exploratory
                sql = f"SELECT TOP {top_k} * FROM {primary_table}"
                return {**state, "sql_query": sql}

        # Find customer key column (for GROUP BY)
        def find_customer_column(columns: List[str]) -> Optional[str]:
            # Prefer label columns first (name, matchcode)
            label_tokens = ["kunde", "kunden", "customer", "matchcode", "name", "firma", "company"]
            lc = [c.lower() for c in columns]
            for t in label_tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            # Fallback to ID columns
            id_tokens = ["kundennr", "kunden_nr", "kundenid", "kunden_id", "adressid", "adresse_id",
                        "customerid", "customer_id", "kundenummer", "kundennummer", "kdnr", "debitor", "debitornr"]
            for t in id_tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        customer_col = find_customer_column(cols)

        # If no customer column in primary table, try to find and join customer dimension
        joins = join_plan.get("joins", [])
        if not customer_col:
            logger.info(f"🔨 [TOPK_REVENUE] No customer column in {primary_table}, looking for customer dimension join")

            # Look for customer tables in relevant_tables/candidate_views
            relevant_tables = state.get("relevant_tables", [])
            candidate_views = state.get("candidate_views", [])

            customer_tables = []
            for table in relevant_tables + candidate_views:
                table_name = table if isinstance(table, str) else (table.get("table_name") or table.get("name") or table.get("full_name", ""))
                if any(keyword in table_name.lower() for keyword in ["kunde", "kunden", "customer", "adress", "adressen"]):
                    if not any(exclude in table_name.lower() for exclude in ["telefon", "phone", "contact"]):
                        customer_tables.append(table_name)

            if customer_tables:
                # Try to join the first customer table
                customer_table = customer_tables[0]
                logger.info(f"🔨 [TOPK_REVENUE] Attempting to join customer table: {customer_table}")

                # Probe customer table columns
                cust_cols = column_index.get(customer_table) if isinstance(column_index, dict) else None
                if not cust_cols:
                    cust_cols = await self._probe_columns(customer_table)
                    if isinstance(column_index, dict):
                        column_index[customer_table] = cust_cols

                # Find join keys (common between sales and customer tables)
                def find_join_keys(sales_cols: List[str], cust_cols: List[str]) -> Optional[Tuple[str, str]]:
                    # Look for common ID columns
                    sales_lc = [c.lower() for c in sales_cols]
                    cust_lc = [c.lower() for c in cust_cols]

                    # Common patterns
                    patterns = ["kundennr", "kunden_nr", "kundenid", "kunden_id", "adressid", "adresse_id",
                               "customerid", "customer_id", "kundenummer", "kundennummer", "debitor", "debitornr"]

                    for pattern in patterns:
                        sales_matches = [c for c, lc in zip(sales_cols, sales_lc) if pattern in lc]
                        cust_matches = [c for c, lc in zip(cust_cols, cust_lc) if pattern in lc]
                        if sales_matches and cust_matches:
                            return (sales_matches[0], cust_matches[0])
                    return None

                join_keys = find_join_keys(cols, cust_cols)
                if join_keys:
                    sales_key, cust_key = join_keys
                    joins.append({
                        "table": customer_table,
                        "on": f"{primary_table}.{sales_key} = {customer_table}.{cust_key}",
                        "type": "LEFT"
                    })

                    # Now try to find customer label column in joined table
                    customer_col = find_customer_column(cust_cols)
                    if customer_col:
                        customer_col = f"{customer_table}.{customer_col}"

        # Build the SQL
        if customer_col and amount_col:
            # Full TOP-K SUM GROUP BY
            from_clause = primary_table
            for join in joins:
                join_table = join.get("table", "")
                join_condition = join.get("on", "")
                join_type = join.get("type", "LEFT")
                if join_table and join_condition:
                    from_clause += f" {join_type} JOIN {join_table} ON {join_condition}"

            sql = f"SELECT TOP {top_k} {customer_col}, SUM({primary_table}.{amount_col}) AS total_revenue FROM {from_clause} GROUP BY {customer_col} ORDER BY total_revenue DESC"

            logger.info(f"🔨 [TOPK_REVENUE] Generated SQL: {sql}")
            return {**state, "sql_query": sql}

        elif amount_col:
            # Fallback: just sum by any available grouping column
            group_col = customer_col or find_customer_column(cols) or cols[0] if cols else "*"
            if group_col and group_col != "*":
                sql = f"SELECT TOP {top_k} {group_col}, SUM({amount_col}) AS total_revenue FROM {primary_table} GROUP BY {group_col} ORDER BY total_revenue DESC"
            else:
                sql = f"SELECT TOP {top_k} * FROM {primary_table}"
            return {**state, "sql_query": sql}

        else:
            # No amount column found, exploratory query
            sql = f"SELECT TOP {top_k} * FROM {primary_table}"
            logger.warning(f"🔨 [TOPK_REVENUE] No amount column found, using exploratory query")
            return {**state, "sql_query": sql}

    async def _generate_trend_series_sql(self, state: BaseState) -> BaseState:
        """Generate time-series trend SQL for queries like 'growth over last 3 years'."""
        logger.info(f"🔨 [TREND_SERIES] Generating trend series SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for trend analysis"}
            return {**state, "error_info": error}

        # Ensure ALL tables in join plan have columns probed
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        # Get time granularity
        time_granularity = intent.get("time_granularity", "year")
        user_text = (state.get("user_input") or "").lower()

        # Extract period from query
        def extract_time_period(text: str) -> Tuple[str, int]:
            import re
            numerals = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

            # "last N years/months"
            m = re.search(r"last\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(year|years|month|months)", text)
            if m:
                n_raw = m.group(1)
                unit = m.group(2)
                n = int(n_raw) if n_raw.isdigit() else numerals.get(n_raw, 3)
                period = "years" if "year" in unit else "months"
                return (period, n)

            # Default to last 3 years
            return ("years", 3)

        period, n = extract_time_period(user_text)

        # Get columns
        cols = column_index.get(primary_table, [])

        # Find date column
        def find_date_column(columns: List[str]) -> Optional[str]:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        date_col = find_date_column(cols)

        # Find count/sum column
        metrics = intent.get("metrics", [])
        if any(m.lower() in ["count"] for m in metrics):
            # Count query (e.g., "customer growth")
            if period == "years":
                if date_col:
                    sql = f"SELECT YEAR({date_col}) AS period, COUNT(*) AS total_count FROM {primary_table} WHERE {date_col} >= DATEADD(year, -{n}, GETDATE()) GROUP BY YEAR({date_col}) ORDER BY period"
                else:
                    sql = f"SELECT COUNT(*) AS total_count FROM {primary_table}"
            else:  # months
                if date_col:
                    sql = f"SELECT FORMAT({date_col}, 'yyyy-MM') AS period, COUNT(*) AS total_count FROM {primary_table} WHERE {date_col} >= DATEADD(month, -{n}, GETDATE()) GROUP BY FORMAT({date_col}, 'yyyy-MM') ORDER BY period"
                else:
                    sql = f"SELECT COUNT(*) AS total_count FROM {primary_table}"
        else:
            # Sum query (e.g., "revenue growth")
            amount_col = None
            amount_tokens = ["umsatz", "betrag", "amount", "total", "summe", "preis"]
            lc = [c.lower() for c in cols]
            for t in amount_tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        amount_col = cols[i]
                        break
                if amount_col:
                    break

            if amount_col and date_col:
                if period == "years":
                    sql = f"SELECT YEAR({date_col}) AS period, SUM({amount_col}) AS total_amount FROM {primary_table} WHERE {date_col} >= DATEADD(year, -{n}, GETDATE()) GROUP BY YEAR({date_col}) ORDER BY period"
                else:
                    sql = f"SELECT FORMAT({date_col}, 'yyyy-MM') AS period, SUM({amount_col}) AS total_amount FROM {primary_table} WHERE {date_col} >= DATEADD(month, -{n}, GETDATE()) GROUP BY FORMAT({date_col}, 'yyyy-MM') ORDER BY period"
            else:
                sql = f"SELECT TOP 100 * FROM {primary_table}"

        return {**state, "sql_query": sql}

    async def _generate_month_filtered_count_sql(self, state: BaseState) -> BaseState:
        """Generate month-filtered count SQL for queries like 'How many projects in October?'."""
        logger.info(f"🔨 [MONTH_COUNT] Generating month-filtered count SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}
        user_text = (state.get("user_input") or "").lower()

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for month count"}
            return {**state, "error_info": error}

        # Ensure ALL tables in join plan have columns probed
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        # Extract month name
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
            "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
        }

        month_num = None
        for month_name, num in months.items():
            if month_name in user_text:
                month_num = num
                break

        if not month_num:
            error = {"type": "NO_MONTH", "message": "Could not extract month from query"}
            return {**state, "error_info": error}

        # Get columns
        cols = column_index.get(primary_table, [])

        # Find date column
        def find_date_column(columns: List[str]) -> Optional[str]:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        date_col = find_date_column(cols)
        if not date_col:
            # Fallback: use exploratory
            sql = f"SELECT TOP 50 * FROM {primary_table}"
            return {**state, "sql_query": sql}

        # Generate SQL with month filter
        sql = f"SELECT COUNT(*) AS total_count FROM {primary_table} WHERE MONTH({date_col}) = {month_num} AND YEAR({date_col}) = YEAR(GETDATE())"

        return {**state, "sql_query": sql}

    async def _generate_sum_with_period_sql(self, state: BaseState) -> BaseState:
        """Generate SUM/TOTAL with temporal period SQL for queries like 'sales from Sept to Oct'."""
        logger.info(f"🔨 [SUM_WITH_PERIOD] Generating SUM with temporal period SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}
        user_text = (state.get("user_input") or "").lower()

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for SUM with period"}
            return {**state, "error_info": error}

        # Ensure ALL tables in join plan have columns probed
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        # Extract month names (handles "from Sept to Oct" or single month)
        months_dict = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
            "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
        }

        # Extract month range: "from September to October" or "September to October"
        month_start = None
        month_end = None
        import re
        for month_name, num in months_dict.items():
            if month_name in user_text:
                if month_start is None:
                    month_start = num
                else:
                    month_end = num

        if month_start is None:
            error = {"type": "NO_MONTH", "message": "Could not extract month(s) from query"}
            return {**state, "error_info": error}

        # Default: if only one month, use it as both start and end
        if month_end is None:
            month_end = month_start

        # Get columns
        cols = column_index.get(primary_table, [])

        # Find date column
        def find_date_column(columns: List[str]) -> Optional[str]:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        # Find amount column
        def find_amount_column(columns: List[str]) -> Optional[str]:
            tokens = ["umsatz", "betrag", "amount", "total", "summe", "preis", "wert", "gesamtpreis", "netto", "brutto"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        date_col = find_date_column(cols)
        amount_col = find_amount_column(cols)

        # Generate SQL
        if date_col and amount_col:
            sql = f"SELECT SUM({amount_col}) AS total_sum FROM {primary_table} WHERE MONTH({date_col}) BETWEEN {month_start} AND {month_end} AND YEAR({date_col}) = YEAR(GETDATE())"
        elif date_col:
            # No amount column; fallback to COUNT
            sql = f"SELECT COUNT(*) AS total_count FROM {primary_table} WHERE MONTH({date_col}) BETWEEN {month_start} AND {month_end} AND YEAR({date_col}) = YEAR(GETDATE())"
        else:
            # No date column; fallback to exploratory
            sql = f"SELECT TOP 50 * FROM {primary_table}"

        return {**state, "sql_query": sql}

    async def _generate_growth_analysis_sql(self, state: BaseState) -> BaseState:
        """Generate growth analysis SQL for queries like 'customer base growth over 3 years'."""
        logger.info(f"🔨 [GROWTH_ANALYSIS] Generating growth analysis SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for growth analysis"}
            return {**state, "error_info": error}

        # Ensure columns are available
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        user_text = (state.get("user_input") or "").lower()

        # Extract period (default 3 years)
        def extract_growth_period(text: str) -> int:
            import re
            numerals = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
            m = re.search(r"last\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(year|years)", text)
            if m:
                n_raw = m.group(1)
                n = int(n_raw) if n_raw.isdigit() else numerals.get(n_raw, 3)
                return n
            return 3

        years = extract_growth_period(user_text)

        # Get columns
        cols = column_index.get(primary_table, [])

        # Find date column
        def find_date_column(columns: List[str]) -> Optional[str]:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        date_col = find_date_column(cols)

        # Generate year-over-year growth SQL
        if date_col:
            sql = f"""
            SELECT
                YEAR({date_col}) AS year,
                COUNT(*) AS total_count,
                LAG(COUNT(*)) OVER (ORDER BY YEAR({date_col})) AS prev_year_count,
                CASE
                    WHEN LAG(COUNT(*)) OVER (ORDER BY YEAR({date_col})) > 0
                    THEN ROUND(
                        (CAST(COUNT(*) AS FLOAT) - LAG(COUNT(*)) OVER (ORDER BY YEAR({date_col}))) /
                        LAG(COUNT(*)) OVER (ORDER BY YEAR({date_col})) * 100, 2
                    )
                    ELSE NULL
                END AS growth_percent
            FROM {primary_table}
            WHERE {date_col} >= DATEADD(year, -{years}, GETDATE())
            GROUP BY YEAR({date_col})
            ORDER BY year
            """
        else:
            sql = f"SELECT COUNT(*) AS total_count FROM {primary_table}"

        return {**state, "sql_query": sql}

    async def _generate_department_productivity_sql(self, state: BaseState) -> BaseState:
        """Generate department productivity analysis SQL."""
        logger.info(f"🔨 [DEPARTMENT_PRODUCTIVITY] Generating department productivity SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for department productivity"}
            return {**state, "error_info": error}

        # Ensure columns are available
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        cols = column_index.get(primary_table, [])

        # Look for department/productivity columns
        def find_department_column(columns: List[str]) -> Optional[str]:
            tokens = ["department", "abteilung", "bereich", "gruppe", "team"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        def find_productivity_column(columns: List[str]) -> Optional[str]:
            tokens = ["productivity", "produktivitaet", "output", "performance", "leistung", "efficiency", "effizienz"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        dept_col = find_department_column(cols)
        prod_col = find_productivity_column(cols)

        if dept_col and prod_col:
            sql = f"SELECT {dept_col}, AVG({prod_col}) AS avg_productivity, COUNT(*) AS employee_count FROM {primary_table} GROUP BY {dept_col} ORDER BY avg_productivity DESC"
        elif dept_col:
            sql = f"SELECT {dept_col}, COUNT(*) AS employee_count FROM {primary_table} GROUP BY {dept_col} ORDER BY employee_count DESC"
        else:
            sql = f"SELECT TOP 100 * FROM {primary_table}"

        return {**state, "sql_query": sql}

    async def _generate_comparative_analysis_sql(self, state: BaseState) -> BaseState:
        """Generate comparative analysis SQL for queries like 'Q1 vs Q2 performance'."""
        logger.info(f"🔨 [COMPARATIVE_ANALYSIS] Generating comparative analysis SQL")

        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {}) or {}

        primary_table = join_plan.get("primary_table", "")
        if not primary_table:
            error = {"type": "NO_PRIMARY_TABLE", "message": "No primary table available for comparative analysis"}
            return {**state, "error_info": error}

        # Ensure columns are available
        column_index = await self._ensure_columns_probed_for_join_plan(join_plan, column_index)
        state["column_index"] = column_index

        user_text = (state.get("user_input") or "").lower()
        cols = column_index.get(primary_table, [])

        # Find date and value columns
        def find_date_column(columns: List[str]) -> Optional[str]:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "buchung"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        def find_value_column(columns: List[str]) -> Optional[str]:
            tokens = ["umsatz", "betrag", "amount", "total", "summe", "wert", "value", "preis"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        date_col = find_date_column(cols)
        value_col = find_value_column(cols)

        # Generate quarter-over-quarter comparison
        if date_col and value_col:
            sql = f"""
            SELECT
                DATEPART(year, {date_col}) AS year,
                DATEPART(quarter, {date_col}) AS quarter,
                SUM({value_col}) AS total_value,
                LAG(SUM({value_col})) OVER (ORDER BY DATEPART(year, {date_col}), DATEPART(quarter, {date_col})) AS prev_quarter_value,
                CASE
                    WHEN LAG(SUM({value_col})) OVER (ORDER BY DATEPART(year, {date_col}), DATEPART(quarter, {date_col})) > 0
                    THEN ROUND(
                        (SUM({value_col}) - LAG(SUM({value_col})) OVER (ORDER BY DATEPART(year, {date_col}), DATEPART(quarter, {date_col}))) /
                        LAG(SUM({value_col})) OVER (ORDER BY DATEPART(year, {date_col}), DATEPART(quarter, {date_col})) * 100, 2
                    )
                    ELSE NULL
                END AS change_percent
            FROM {primary_table}
            WHERE {date_col} >= DATEADD(year, -1, GETDATE())
            GROUP BY DATEPART(year, {date_col}), DATEPART(quarter, {date_col})
            ORDER BY year, quarter
            """
        elif value_col:
            sql = f"SELECT SUM({value_col}) AS total_value FROM {primary_table}"
        else:
            sql = f"SELECT TOP 100 * FROM {primary_table}"

        return {**state, "sql_query": sql}

    def _generate_aggregation_sql_with_hints(self, primary_table: str, metrics: List[str], time_window: Optional[str], column_index: Dict[str, List[str]]) -> str:
        """Heuristic aggregate SQL using column_index to pick columns."""
        cols = column_index.get(primary_table, []) if isinstance(column_index, dict) else []

        def pick_id_column(columns: List[str]) -> str:
            tokens = ["id", "nr", "nummer", "no", "key", "kunde", "kundennr", "customer"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return columns[0] if columns else "*"

        def pick_sum_column(columns: List[str]) -> str:
            tokens = ["umsatz", "betrag", "amount", "total", "summe", "value", "preis"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        def pick_date_column(columns: List[str]) -> str:
            tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted"]
            lc = [c.lower() for c in columns]
            for t in tokens:
                for i, name in enumerate(lc):
                    if t in name:
                        return columns[i]
            return None

        metrics_lc = [m.lower() for m in metrics or []]
        wants_count = any(m in ["count"] for m in metrics_lc) or (not metrics_lc)
        wants_sum = any(m in ["sum", "total"] for m in metrics_lc)

        where_conditions = []
        date_col = pick_date_column(cols)
        if not date_col and (not cols) and time_window:
            # Fallback: try common date columns seen in ERP views
            for fallback_col in ["Belegdatum", "Liefertermin", "Erfassungsdatum"]:
                date_col = fallback_col
                break
        if time_window and date_col:
            # Support dictionary-based time windows (with explicit start/end) and string heuristics
            tw_conds = []
            if isinstance(time_window, dict):
                start = time_window.get("start")
                end = time_window.get("end")
                if start and end:
                    tw_conds = [f"{date_col} >= '{start}'", f"{date_col} <= '{end}'"]
            else:
                tw = (time_window or "").lower()
            if "last month" in tw or "letzten monat" in tw:
                tw_conds = [
                    f"{date_col} >= DATEADD(month, -1, DATEADD(day, 1, EOMONTH(GETDATE(), -1)))",
                    f"{date_col} <= EOMONTH(GETDATE(), -1)"
                ]
            elif "this month" in tw or "diesen monat" in tw:
                tw_conds = [
                    f"{date_col} >= DATEADD(day, 1, EOMONTH(GETDATE(), -1))",
                    f"{date_col} <= EOMONTH(GETDATE())"
                ]
            elif "this year" in tw or "dieses jahr" in tw:
                tw_conds = [f"YEAR({date_col}) = YEAR(GETDATE())"]
            elif "last year" in tw or "letztes jahr" in tw:
                tw_conds = [f"YEAR({date_col}) = YEAR(GETDATE()) - 1"]
            else:
                tw_conds = []
            where_conditions.extend(tw_conds)

        if wants_sum:
            sum_col = pick_sum_column(cols)
            if not sum_col:
                # Fallback to exploratory
                sql = f"SELECT TOP 10 * FROM {primary_table}"
            else:
                sql = f"SELECT SUM({sum_col}) AS total_value FROM {primary_table}"
        elif wants_count:
            id_col = pick_id_column(cols)
            if id_col and id_col != "*":
                sql = f"SELECT COUNT(DISTINCT {id_col}) AS total_count FROM {primary_table}"
            else:
                sql = f"SELECT COUNT(*) AS total_count FROM {primary_table}"
        else:
            sql = f"SELECT TOP 10 * FROM {primary_table}"

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        return sql

    def _generate_topk_sum_sql(
        self,
        primary_table: str,
        joins: List[Dict[str, Any]],
        column_index: Dict[str, List[str]],
        time_window: Optional[str],
        top_k: int
    ) -> str:
        """Generate TOP-K SUM aggregate SQL grouped by a customer-like column.

        Heuristics:
        - sum column tokens: umsatz, betrag, amount, total, summe, value, preis
        - group column tokens: kunde, kunden, customer, matchcode, name, firma, company
        - If joins exist, prefer label columns from joined customer dimensions
        """
        pcols = column_index.get(primary_table, []) if isinstance(column_index, dict) else []

        def pick_sum_col(columns: List[str]) -> Optional[str]:
            tokens = [
                "umsatz", "betrag", "amount", "total", "summe", "value", "preis",
                "gesamtpreis", "netto", "brutto", "rechnungsbetrag", "erloes", "erlös",
                "umsatzbetrag", "positionswert", "gesamtwert", "wert", "vkpreis", "vkwert",
                "verkaufspreis", "verkaufswert"
            ]
            lc = [c.lower() for c in (columns or [])]
            for t in tokens:
                for i, nm in enumerate(lc):
                    if t in nm:
                        return (columns or [None])[i]
            return None

        def pick_group_rc(columns: List[str]) -> Optional[str]:
            """Pick a label-like column for GROUP BY (name, matchcode, etc.)"""
            tokens = ["kunde", "kunden", "customer", "matchcode", "name", "firma", "company"]
            lc = [c.lower() for c in (columns or [])]
            for t in tokens:
                for i, nm in enumerate(lc):
                    if t in nm:
                        return (columns or [None])[i]
            return None

        def pick_group_any(columns: List[str]) -> Optional[str]:
            """Fallback: pick any ID-like or label-like column"""
            lc = [c.lower() for c in (columns or [])]
            # Prefer label-like first, else id/key-like
            label_tokens = ["kunde", "kunden", "customer", "matchcode", "name", "firma", "company"]
            key_tokens = [
                "kundennr", "kunden_nr", "kundenid", "kunden_id", "adressid", "adresse_id",
                "customerid", "customer_id", "kundenummer", "kundennummer", "kdnr", "debitor", "debitornr"
            ]
            for t in label_tokens:
                for i, nm in enumerate(lc):
                    if t in nm:
                        return (columns or [None])[i]
            for t in key_tokens:
                for i, nm in enumerate(lc):
                    if t in nm:
                        return (columns or [None])[i]
            return None

        sum_col = pick_sum_col(pcols)
        group_col = None

        # Build FROM clause with JOINs
        from_clause = primary_table
        for j in (joins or []):
            jt = j.get("table")
            on = j.get("on")
            jtype = j.get("type", "LEFT")
            if jt and on:
                from_clause += f" {jtype} JOIN {jt} ON {on}"
                # Try to find group column from joined table
                jcols = column_index.get(jt, []) if isinstance(column_index, dict) else []
                if jcols and not group_col:
                    group_col = pick_group_rc(jcols)
                    if group_col:
                        group_col = f"{jt}.{group_col}"

        # If no group column from joins, try primary table
        if not group_col:
            g = pick_group_rc(pcols)
            if g:
                group_col = f"{primary_table}.{g}"
            else:
                # Ultimate fallback
                g2 = pick_group_any(pcols)
                if g2:
                    group_col = f"{primary_table}.{g2}"

        if not sum_col:
            # No sum column found, return exploratory
            return f"SELECT TOP {top_k} * FROM {from_clause}"

        if not group_col:
            # No group column, return simple SUM
            return f"SELECT SUM({sum_col}) AS total_revenue FROM {from_clause}"

        # Full TOP-K SUM GROUP BY
        sql = f"SELECT TOP {top_k} {group_col}, SUM({sum_col}) AS total_revenue FROM {from_clause}"

        # Add WHERE conditions for time_window if applicable
        where_conditions = []
        if time_window:
            # Try to find a date column
            def pick_date(columns: List[str]) -> Optional[str]:
                tokens = ["datum", "date", "zeit", "time", "created", "erfass", "belegdatum", "posted", "rechnung"]
                lc = [c.lower() for c in (columns or [])]
                for t in tokens:
                    for i, nm in enumerate(lc):
                        if t in nm:
                            return (columns or [None])[i]
                return None

            date_col = pick_date(pcols)
            if date_col:
                date_col = f"{primary_table}.{date_col}"
                tw = (time_window or "").lower()
                if "last month" in tw or "letzten monat" in tw:
                    where_conditions.extend([
                        f"{date_col} >= DATEADD(month, -1, DATEADD(day, 1, EOMONTH(GETDATE(), -1)))",
                        f"{date_col} <= EOMONTH(GETDATE(), -1)"
                    ])
                elif "this month" in tw or "diesen monat" in tw:
                    where_conditions.extend([
                        f"{date_col} >= DATEADD(day, 1, EOMONTH(GETDATE(), -1))",
                        f"{date_col} <= EOMONTH(GETDATE())"
                    ])
                elif "this year" in tw or "dieses jahr" in tw:
                    where_conditions.append(f"YEAR({date_col}) = YEAR(GETDATE())")
                elif "last year" in tw or "letztes jahr" in tw:
                    where_conditions.append(f"YEAR({date_col}) = YEAR(GETDATE()) - 1")

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)

        sql += f" GROUP BY {group_col} ORDER BY total_revenue DESC"
        return sql

    async def _generate_ranked_metrics_sql(self, state: BaseState) -> BaseState:
        """
        Generate SQL for ranked derived metrics (profit_margin, ROI, contribution_margin, etc.).

        For profit_margin, builds a query that:
        - Joins price and cost tables
        - Aggregates by product
        - Calculates (price - cost) / price
        - Orders by the metric descending
        - Limits to top_k
        """
        logger.info("🔨 [RANKED_METRICS] Generating SQL for ranked derived metrics")

        intent = state.get("intent", {}) or {}
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        group_by_hint = (intent.get("group_by") or "").lower()
        top_k = intent.get("top_k") or 10
        join_plan = state.get("join_plan") or {}
        relevant_tables = state.get("relevant_tables", [])
        column_index = state.get("column_index", {}) or {}

        try:
            # Detect which derived metric is requested
            if "profit_margin" in metrics:
                sql = self._build_profit_margin_query(
                    join_plan, group_by_hint, top_k, relevant_tables, column_index
                )
            elif "roi" in metrics:
                sql = self._build_roi_query(
                    join_plan, group_by_hint, top_k, relevant_tables, column_index
                )
            elif "contribution_margin" in metrics:
                sql = self._build_contribution_margin_query(
                    join_plan, group_by_hint, top_k, relevant_tables, column_index
                )
            else:
                logger.warning(f"⚠️ Unknown derived metric in {metrics}, falling back to simple top-k query")
                sql = f"SELECT TOP {top_k} * FROM {join_plan.get('fact_table', relevant_tables[0])}"

            logger.info(f"🔨 [RANKED_METRICS] Generated SQL: {sql}")
            state["sql_query"] = sql
            join_plan["required_action"] = "ranked_metrics_computed"
            state["join_plan"] = join_plan
            return state

        except Exception as exc:
            logger.error(f"❌ [RANKED_METRICS] Error generating ranked metrics SQL: {exc}", exc_info=True)
            return {
                **state,
                "error_info": {
                    "type": "RANKED_METRICS_ERROR",
                    "message": f"Failed to generate ranked metrics query: {str(exc)}"
                }
            }

    def _build_profit_margin_query(self, join_plan: Dict[str, Any], group_by_hint: str, top_k: int,
                                   relevant_tables: List[str], column_index: Dict[str, List[str]]) -> str:
        """
        Build SQL for profit margin calculation: (price - cost) / price
        Assumes price comes from KHKArtikelKunden and cost from KHKArtikelbewertungMEKHistorie
        """
        price_table = None
        cost_table = None
        price_col = None
        cost_col = None
        product_key = "AuspraegungID"
        product_col = "Artikelnummer"

        for table in relevant_tables:
            table_lower = table.lower()
            cols = column_index.get(table, []) or []
            cols_lower = [str(c).lower() for c in cols]

            if "preis" in table_lower or "kunden" in table_lower:
                if price_table is None:
                    price_table = table
                    if "einzelpreis" in cols_lower:
                        price_col = "Einzelpreis"
                    elif any("preis" in str(c).lower() for c in cols):
                        price_col = next(c for c in cols if "preis" in str(c).lower())

            if "bewertung" in table_lower or "ek" in table_lower:
                if cost_table is None:
                    cost_table = table
                    if "mittlererek" in cols_lower:
                        cost_col = "MittlererEK"
                    elif any("ek" in str(c).lower() for c in cols):
                        cost_col = next(c for c in cols if "ek" in str(c).lower())

        if not price_table or not price_col:
            price_table = join_plan.get("fact_table", relevant_tables[0])
            price_col = "Einzelpreis"

        if not cost_table or not cost_col:
            cost_table = relevant_tables[1] if len(relevant_tables) > 1 else price_table
            cost_col = "MittlererEK"

        if price_table == cost_table:
            sql = (
                f"SELECT TOP {top_k}\n"
                f"    {product_col},\n"
                f"    AVG(CAST({price_col} AS FLOAT)) AS avg_price,\n"
                f"    AVG(CAST({cost_col} AS FLOAT)) AS avg_cost,\n"
                f"    CAST((AVG(CAST({price_col} AS FLOAT)) - AVG(CAST({cost_col} AS FLOAT))) / NULLIF(AVG(CAST({price_col} AS FLOAT)), 0) * 100 AS DECIMAL(10, 2)) AS profit_margin_pct\n"
                f"FROM {price_table}\n"
                f"WHERE {price_col} IS NOT NULL AND {cost_col} IS NOT NULL\n"
                f"GROUP BY {product_col}\n"
                f"ORDER BY profit_margin_pct DESC"
            )
        else:
            sql = (
                f"SELECT TOP {top_k}\n"
                f"    p.{product_col},\n"
                f"    AVG(CAST(p.{price_col} AS FLOAT)) AS avg_price,\n"
                f"    AVG(CAST(c.{cost_col} AS FLOAT)) AS avg_cost,\n"
                f"    CAST((AVG(CAST(p.{price_col} AS FLOAT)) - AVG(CAST(c.{cost_col} AS FLOAT))) / NULLIF(AVG(CAST(p.{price_col} AS FLOAT)), 0) * 100 AS DECIMAL(10, 2)) AS profit_margin_pct\n"
                f"FROM {price_table} p\n"
                f"INNER JOIN {cost_table} c ON p.{product_key} = c.{product_key} AND p.Artikelnummer = c.Artikelnummer AND p.Mandant = c.Mandant\n"
                f"WHERE p.{price_col} IS NOT NULL AND c.{cost_col} IS NOT NULL\n"
                f"GROUP BY p.{product_col}\n"
                f"ORDER BY profit_margin_pct DESC"
            )

        return sql

    def _build_roi_query(self, join_plan: Dict[str, Any], group_by_hint: str, top_k: int,
                        relevant_tables: List[str], column_index: Dict[str, List[str]]) -> str:
        """Build SQL for ROI calculation (simplified)"""
        fact_table = join_plan.get("fact_table", relevant_tables[0])
        return f"SELECT TOP {top_k} * FROM {fact_table}"

    def _build_contribution_margin_query(self, join_plan: Dict[str, Any], group_by_hint: str, top_k: int,
                                        relevant_tables: List[str], column_index: Dict[str, List[str]]) -> str:
        """Build SQL for contribution margin calculation (simplified)"""
        fact_table = join_plan.get("fact_table", relevant_tables[0])
        return f"SELECT TOP {top_k} * FROM {fact_table}"

    async def _generate_count_entity_sql(self, state: BaseState) -> BaseState:
        """
        Template generator for COUNT_ENTITY queries.

        Used for questions like "How many customers do we have?"
        """
        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        template_params = intent.get("template_params", {})

        entity = template_params.get("entity", "rows")
        fact_table = join_plan.get("fact_table")

        if not fact_table:
            relevant_tables = state.get("relevant_tables", [])
            fact_table = relevant_tables[0] if relevant_tables else "dbo.table"

        filters = intent.get("filters", [])
        where_conditions = self._build_where_conditions(filters) if filters else []
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # COUNT_ENTITY is used for questions like "How many customers do we have?"
        # Using COUNT(*) is safe and portable across MSSQL/Postgres. If we later
        # want to count distinct keys, we can derive the PK from discovery
        # metadata, but COUNT(*) is correct for simple cardinality questions.
        sql = f"SELECT COUNT(*) AS {entity}_count\nFROM {fact_table}\n{where_clause}".strip()

        state["sql_query"] = sql
        logger.info(f"🎯 [TEMPLATE] COUNT_ENTITY SQL generated: {sql[:100]}...")
        return state

    async def _generate_top_k_by_metric_sql(self, state: BaseState) -> BaseState:
        """
        Template generator for TOP_K_BY_METRIC queries.

        Used for questions like "Which products have the highest profit margins?"
        """
        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        template_params = intent.get("template_params", {})

        metric = template_params.get("metric", "value")
        group_by = template_params.get("group_by", "id")
        top_k = template_params.get("top_k", 10)
        order = template_params.get("order", "desc")

        fact_table = join_plan.get("fact_table")
        if not fact_table:
            relevant_tables = state.get("relevant_tables", [])
            fact_table = relevant_tables[0] if relevant_tables else "dbo.table"

        filters = intent.get("filters", [])
        where_conditions = self._build_where_conditions(filters) if filters else []
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        sql = f"""SELECT TOP {top_k}
    {group_by},
    COUNT(*) AS record_count,
    AVG(CAST({metric} AS FLOAT)) AS avg_{metric}
FROM {fact_table}
{where_clause}
GROUP BY {group_by}
ORDER BY avg_{metric} {order.upper()}""".strip()

        state["sql_query"] = sql
        logger.info(f"🎯 [TEMPLATE] TOP_K_BY_METRIC SQL generated: {sql[:100]}...")
        return state

    async def _generate_period_comparison_sql(self, state: BaseState) -> BaseState:
        """
        Template generator for PERIOD_COMPARISON queries.

        Used for questions like "Compare sales in Q1 vs Q2"
        """
        intent = state.get("intent", {})
        join_plan = state.get("join_plan", {})
        template_params = intent.get("template_params", {})

        metric = template_params.get("metric", "COUNT(*)")
        group_by = template_params.get("group_by")
        time_window = template_params.get("time_window", {})

        fact_table = join_plan.get("fact_table")
        if not fact_table:
            relevant_tables = state.get("relevant_tables", [])
            fact_table = relevant_tables[0] if relevant_tables else "dbo.table"

        periods = template_params.get("periods", [])
        if not periods or not time_window:
            logger.warning("🎯 [TEMPLATE] PERIOD_COMPARISON: missing periods or time_window, falling back to generic query")
            sql = f"SELECT TOP 1000 * FROM {fact_table}"
        else:
            start = time_window.get("start")
            end = time_window.get("end")
            where_clause = ""
            if start and end:
                where_clause = f"WHERE order_date >= '{start}' AND order_date <= '{end}'"

            group_by_clause = f"GROUP BY {group_by}" if group_by else ""
            sql = f"""SELECT
    {group_by or 'COUNT(*) AS count'},
    {metric} AS metric_value
FROM {fact_table}
{where_clause}
{group_by_clause}
ORDER BY metric_value DESC""".strip()

        state["sql_query"] = sql
        logger.info(f"🎯 [TEMPLATE] PERIOD_COMPARISON SQL generated: {sql[:100]}...")
        return state


# Exported function to create the agent
async def create_join_sql_agent(
    llm_model: str = "gpt-4o",
    max_joins: int = 3
) -> JoinPlanAndSQLAgent:
    """Factory function to create a JoinPlanAndSQLAgent instance."""
    return JoinPlanAndSQLAgent(llm_model=llm_model, max_joins=max_joins)


    def _generate_aggregation_sql(self, primary_table: str, metrics: List[str], filters: List[Dict], time_window: Optional[str]) -> str:
        """Generate aggregation SQL for single table queries."""
        select_parts = []
        group_by_cols = []

        # For now, generate exploratory SQL that shows data structure
        # This is better than failing with hardcoded column names
        sql = f"SELECT TOP 10 * FROM {primary_table}"

        # Add time window filter if specified
        where_conditions = []
        if time_window:
            where_conditions.extend(self._build_time_window_conditions(time_window))

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)

        sql += " ORDER BY (SELECT NULL)"  # Dummy ORDER BY to ensure query works

        return sql


    def _build_where_conditions(self, filters: List[Dict]) -> List[str]:
        """Build WHERE conditions from filter list."""
        where_conditions = []
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                # Only quote non-numeric values
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
        return where_conditions

    def _build_time_window_conditions(self, time_window: str) -> List[str]:
        """Build time-based WHERE conditions."""
        conditions = []
        if isinstance(time_window, dict):
            start = time_window.get("start")
            end = time_window.get("end")
            # Caller must replace column name appropriately; here we default to a generic column
            # Prefer consumers to use _generate_aggregation_sql_with_hints which substitutes date_col
            if start and end:
                conditions.append(f"order_date >= '{start}'")
                conditions.append(f"order_date <= '{end}'")
            return conditions

        time_window_lower = (time_window or "").lower()

        if "last month" in time_window_lower:
            # Last month: from first day of previous month to last day of previous month
            conditions.append("order_date >= DATEADD(month, -1, DATEADD(day, 1, EOMONTH(GETDATE(), -1)))")
            conditions.append("order_date <= EOMONTH(GETDATE(), -1)")
        elif "this month" in time_window_lower:
            conditions.append("order_date >= DATEADD(day, 1, EOMONTH(GETDATE(), -1))")
            conditions.append("order_date <= EOMONTH(GETDATE())")
        elif "this year" in time_window_lower:
            conditions.append("YEAR(order_date) = YEAR(GETDATE())")
        elif "last year" in time_window_lower:
            conditions.append("YEAR(order_date) = YEAR(GETDATE()) - 1")

        return conditions



# Sync wrapper for LangGraph Studio
def build_join_sql_graph():
    """
    Build and return the join SQL agent graph for LangGraph Studio.

    This is a synchronous function that can be called by langgraph dev CLI.
    All node functions remain async and will be properly awaited by LangGraph at runtime.

    Returns:
        Compiled StateGraph for the join SQL agent
    """
    agent = JoinPlanAndSQLAgent()
    return agent.build_subgraph() #TODO CHECK WHY NOT USED
    def _normalize_role_hints_payload(self, payload: Any) -> Dict[str, Any]:
        """Normalize discovery_role_hints payload into structured dicts.

        The MCP discovery tool sometimes returns `fact_candidates` and `dimensions`
        as stringified Python dicts (e.g. "{'table': 'KHKVKBelege', ...}").
        This helper converts those into real dicts so that `DiscoveryRoleHints`
        can be parsed deterministically.
        """
        if not isinstance(payload, dict):
            return {}

        import ast

        # Normalize fact candidates
        raw_facts = payload.get("fact_candidates") or []
        norm_facts: List[Dict[str, Any]] = []
        for item in raw_facts:
            if isinstance(item, dict):
                norm_facts.append(item)
            elif isinstance(item, str):
                try:
                    parsed = ast.literal_eval(item)
                    if isinstance(parsed, dict):
                        norm_facts.append(parsed)
                    else:
                        logger.debug("[ROLE_HINTS] Ignoring non-dict fact_candidate parsed from string: %r", parsed)
                except Exception as exc:
                    logger.debug("[ROLE_HINTS] Failed to parse fact_candidate string %r: %s", item, exc)

        # Normalize dimensions (mapping role -> dict)
        raw_dims = payload.get("dimensions") or {}
        norm_dims: Dict[str, Dict[str, Any]] = {}
        if isinstance(raw_dims, dict):
            for key, val in raw_dims.items():
                if isinstance(val, dict):
                    norm_dims[key] = val
                elif isinstance(val, str):
                    try:
                        parsed = ast.literal_eval(val)
                        if isinstance(parsed, dict):
                            norm_dims[key] = parsed
                        else:
                            logger.debug(
                                "[ROLE_HINTS] Ignoring non-dict dimension parsed from string for key %s: %r",
                                key,
                                parsed,
                            )
                    except Exception as exc:
                        logger.debug(
                            "[ROLE_HINTS] Failed to parse dimension string for key %s: %r (%s)",
                            key,
                            val,
                            exc,
                        )

        normalized = dict(payload)
        normalized["fact_candidates"] = norm_facts
        normalized["dimensions"] = norm_dims
        return normalized
