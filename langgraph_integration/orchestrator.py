"""
Multi-Agent Orchestrator - ACTIVE PRODUCTION SYSTEM (Phase 9)

Composes 5 specialized agents to answer any ERP question:
0. IntentParserAgent: Semantic intent parsing (🆕 Phase 9: fixes double-keyword-extraction)
1. DiscoveryAgent: Finds relevant tables/views (Scout mode, semantic ranking, role-based)
2. JoinPlanAndSQLAgent: Plans joins and generates MSSQL queries (views-first strategy, FK analysis)
3. ExecAndRecoveryAgent: Executes safely and recovers from errors (row caps, timeouts, repair logic)
4. AnswerAgent: Formats results naturally (1-2 sentence summaries)

This orchestrator replaces the monolithic DatabaseWorkflow with a modular, composable design
that enables better reasoning, testability, and maintenance.

ARCHITECTURE CHANGE (Phase 9):
- BEFORE: _simple_intent_parser() → naive regex, double extraction by discovery
- AFTER: IntentParserAgent() → LLM-based semantic parsing, clean structured keywords
- BENEFIT: Discovery called ONCE with clean keywords, ~3 candidates instead of 943×N

ARCHITECTURE CHANGE (ADR-0019):
- BEFORE: Single DatabaseWorkflow class (12+ methods, mixed concerns)
- AFTER: 5 specialized agents composed by orchestrator (separation of concerns)
- BENEFIT: Each agent focuses on its phase; reasoning is optimized per phase
"""

import logging
import json
import os
import asyncio
import uuid
import copy
import time
import re
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import ValidationError

from langgraph_integration.contracts.state import BaseState, merge_error_info
from langgraph_integration.contracts.response_envelope import (
    ErrorInfo as ErrorInfoModel,
    ResponseEnvelope,
)
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent
from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.agents.sql_validator.agent import SQLValidatorAgent
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.result_validator.agent import build_result_validator_node
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.agents.interpretation.agent import InterpretationAgent
from langgraph_integration.concept_mapper import ConceptMapper
from langgraph_integration.mcp_client import get_shared_mcp_tool
from langgraph_integration.debug_logger import get_debug_logger
from langgraph_integration.utils.runtime_config import (
    get_db_default_schema,
    get_db_dialect,
    get_llm_budget_safety_margin,
    get_max_graph_cycles,
    get_max_llm_calls,
    get_default_answer_mode,
    get_max_validation_attempts,
    get_max_exec_recovery_attempts,
    get_max_no_progress_repeats,
)
from langgraph_integration.guardrails.required_relations import (
    evaluate_required_relations,
)
from langgraph_integration.utils.canonical_names import canonical_table_name

# Scout Mode is handled by MCP server, not accessed directly from LangGraph

logger = logging.getLogger(__name__)
debug_logger = get_debug_logger()


class QueryOrchestrator:
    """
    Orchestrates query processing through 4 specialized agents.
    
    Flow:
    1. index_database: Load Scout catalog (MCP health check)
    2. parse_intent: Extract operation type (query/schema_query/health_check/clarify)
    3. route_operation: Conditional routing based on operation
    
    For data queries:
    ├─ DiscoveryAgent: Find relevant tables/views (Scout semantic search, role-based ranking)
    ├─ JoinPlanAndSQLAgent: Plan joins, generate MSSQL (views-first, FK analysis)
    ├─ ExecAndRecoveryAgent: Execute safely, auto-repair on error (row caps, timeouts)
    └─ AnswerAgent: Format results (1-2 sentence natural language)
    
    For schema queries:
    ├─ DiscoveryAgent: List available tables/views
    └─ AnswerAgent: Explain schema structure
    
    For health checks/errors:
    └─ AnswerAgent: Handle directly
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o",
        llm_temp: float = 0.0,
        max_joins: int = 3,
        max_retries: int = 2,
        row_limit: int = 1000,
        query_timeout_seconds: int = 30
    ):
        """
        Initialize QueryOrchestrator with all agents.
        
        Args:
            llm_model: LLM model name (e.g., "gpt-4o")
            llm_temp: Temperature for LLM (0.0 = deterministic)
            max_joins: Maximum joins allowed in queries
            max_retries: Maximum retry attempts on execution failure
            row_limit: Default row limit for queries
            query_timeout_seconds: Query timeout in seconds
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.mcp = get_shared_mcp_tool()
        self.concept_mapper = ConceptMapper()
        # Persist core configuration for downstream nodes and helpers
        self.max_joins = max_joins
        self.max_retries = max_retries
        self.row_limit = row_limit
        self.query_timeout_seconds = query_timeout_seconds

        # Global orchestration and database configuration (env-driven, with safe defaults)
        self.max_llm_calls = get_max_llm_calls()
        self.llm_budget_safety_margin = get_llm_budget_safety_margin()
        self.db_dialect = get_db_dialect()
        self.db_default_schema = get_db_default_schema(self.db_dialect)
        self.max_graph_cycles = get_max_graph_cycles()
        # Phase 2b: Repair loop caps / no-progress thresholds
        self.max_validation_attempts = get_max_validation_attempts()
        self.max_exec_recovery_attempts = get_max_exec_recovery_attempts()
        self.max_no_progress_repeats = get_max_no_progress_repeats()
        # Default answer formatting strategy (LLM vs deterministic-from-data)
        self.default_answer_mode = get_default_answer_mode()

        # Initialize specialized agents
        logger.info("🚀 Initializing multi-agent orchestrator (Phase 9)...")
        logger.warning("ORCH_CF_FIX_ACTIVE version=cf_fix2 recursion_limit_default=1500 "
                       "max_total_plans=6 max_exec_attempts=6")
        
        # 🆕 Phase 9: IntentParserAgent for semantic parsing (fixes double-keyword-extraction)
        self.intent_parser = IntentParserAgent(llm_model=llm_model, llm_temp=llm_temp)
        logger.info("✅ IntentParserAgent initialized (Semantic intent parsing, clean keywords)")
        
        self.discovery_agent = DiscoveryAgent(llm_model=llm_model, llm_temp=llm_temp)
        logger.info("✅ DiscoveryAgent initialized (Scout semantic search)")
        
        self.join_sql_agent = JoinPlanAndSQLAgent(
            llm_model=llm_model,
            llm_temp=llm_temp,
            max_joins=max_joins,
            row_limit=row_limit,
            query_timeout_seconds=query_timeout_seconds
        )
        logger.info("✅ JoinPlanAndSQLAgent initialized (Views-first, MSSQL)")

        # 🆕 Phase 9: SQLValidatorAgent for pre-execution validation and repair
        self.sql_validator_agent = SQLValidatorAgent(llm_model=llm_model, max_repair_attempts=max_retries)
        logger.info("✅ SQLValidatorAgent initialized (AST validation, auto-repair)")
        
        self.exec_recovery_agent = ExecAndRecoveryAgent(
            llm_model=llm_model,
            llm_temp=llm_temp,
            max_retries=max_retries,
            row_limit=row_limit,
            query_timeout_seconds=query_timeout_seconds
        )
        logger.info("✅ ExecAndRecoveryAgent initialized (Safe execution, auto-repair)")
        
        self.answer_agent = AnswerAgent(llm_model=llm_model, llm_temp=llm_temp)
        logger.info("✅ AnswerAgent initialized (Result formatting)")
        self.interpret_agent = InterpretationAgent(llm_model=llm_model, llm_temp=llm_temp)
        logger.info("✅ InterpretationAgent initialized (Follow-up over prior results)")

        # Phase 4: MCP client lifecycle management
        self.mcp_client = get_shared_mcp_tool()
        logger.info("✅ MCP Client initialized (Shared connection pool)")

        # Cache last successful execution for interpretation follow-ups
        self._previous_exec_cache: Dict[str, Any] = {}

        self.graph = self._build_graph()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        # Shared MCP client is closed via process-level atexit in mcp_client
        return

    async def close(self):
        """Explicit cleanup method."""
        await self.__aexit__(None, None, None)

    def _normalize_error_info(self, error: Any) -> Optional[Dict[str, Any]]:
        """Ensure error_info payloads are consistent dictionaries."""
        if not error:
            return None

        try:
            if isinstance(error, ErrorInfoModel):
                return error.model_dump(exclude_none=True)
            envelope = ErrorInfoModel.model_validate(error)
            return envelope.model_dump(exclude_none=True)
        except ValidationError as exc:
            logger.warning(
                "payload_type_violation: error_info validation failed (%s)",
                exc,
            )
            raw_type = getattr(error, "type", None) or getattr(error, "__class__", type("Err", (), {})).__name__
            raw_message = getattr(error, "message", None) or getattr(error, "error", None) or str(error)
            fallback = {
                "type": str(raw_type or "UNKNOWN_ERROR"),
                "message": str(raw_message or "Unknown error"),
            }
            return ErrorInfoModel.model_validate(fallback).model_dump(exclude_none=True)
        except Exception as exc:
            logger.warning(
                "payload_type_violation: expected error_info dict, received %s (%s)",
                type(error).__name__,
                exc,
            )
            return ErrorInfoModel(
                type="UNKNOWN_ERROR",
                message=str(error),
            ).model_dump(exclude_none=True)

    def _coerce_exec_result(self, payload: Any) -> Dict[str, Any]:
        """Normalize exec_result payloads into ResponseEnvelope dictionaries."""
        if isinstance(payload, ResponseEnvelope):
            return payload.model_dump(exclude_none=True)

        try:
            envelope = ResponseEnvelope.model_validate(payload)
            return envelope.model_dump(exclude_none=True)
        except ValidationError as exc:
            logger.warning(
                "payload_type_violation: exec_result validation failed (%s)",
                exc,
            )
            if isinstance(payload, dict):
                fallback = {
                    "ok": bool(payload.get("ok")),
                    "data": payload.get("data") or payload.get("rows") or [],
                    "row_count": payload.get("row_count"),
                    "execution_time_ms": int(payload.get("execution_time_ms")) if isinstance(payload.get("execution_time_ms"), (int, float)) else payload.get("execution_time_ms"),
                    "truncated": bool(payload.get("truncated", False)),
                    "warnings": payload.get("warnings") or [],
                    "error": payload.get("error"),
                    "error_info": self._normalize_error_info(payload.get("error_info")),
                }
                envelope = ResponseEnvelope.model_validate(fallback)
                return envelope.model_dump(exclude_none=True)
        except Exception as exc:
            logger.warning(
                "payload_type_violation: expected exec_result dict, received %s (%s)",
                type(payload).__name__,
                exc,
            )

        # If we reach this point the payload was unusable; emit a safe default.
        return ResponseEnvelope(
            ok=False,
            data=[],
            error_info=ErrorInfoModel(
                type="INVALID_EXEC_RESULT",
                message="Execution result payload was malformed.",
            ),
        ).model_dump(exclude_none=True)

    def _increment_node_entry(self, state: BaseState, node_name: str) -> None:
        """
        Increment node entry counter for instrumentation.

        Keeps node_entry_counts optional and lazily initialized to maintain backward compatibility.
        """
        counts = state.get("node_entry_counts") or {}
        current = counts.get(node_name, 0)
        counts[node_name] = current + 1
        state["node_entry_counts"] = counts

    def _increment_loop_event(self, state: BaseState, event_key: str) -> None:
        """
        Increment a loop-related instrumentation counter.

        Keeps loop_events optional and lazily initialized.
        """
        events = state.get("loop_events") or {}
        events[event_key] = events.get(event_key, 0) + 1
        state["loop_events"] = events

    def _map_stage_to_llm_bucket(self, stage: str) -> str:
        """
        Map fine-grained stages to coarse LLM usage buckets.

        Buckets are designed to align with benchmark reporting:
        - "intent": intent parsing and related routing
        - "discovery": table/view discovery
        - "join": join planning and SQL generation
        - "repair": validation/repair/execution recovery/result validation
        - "answer": answer formatting
        """
        mapping = {
            "parse_intent": "intent",
            "intent": "intent",
            "discovery": "discovery",
            "join_sql": "join",
            "validate_sql": "repair",
            "sql_validator": "repair",
            "exec_recovery": "repair",
            "execution": "repair",
            "result_validator": "repair",
            "answer": "answer",
        }
        return mapping.get(stage, stage)

    def _get_remaining_llm_budget(self, state: BaseState) -> int:
        """
        Compute remaining LLM budget based on max_llm_calls and current usage.
        """
        max_calls = state.get("max_llm_calls", 0) or 20
        llm_usage = state.get("llm_usage") or {}
        total_usage = llm_usage.get("total", state.get("total_llm_calls", 0) or 0)
        remaining = max_calls - int(total_usage)
        return remaining

    def _build_discovery_fingerprint(self, state: BaseState) -> str:
        """
        Build a stable, hashable fingerprint for discovery inputs.

        Used to detect redundant discovery invocations and enable caching.
        """
        user_input = (state.get("user_input") or "").strip().lower()
        intent = state.get("intent") or {}
        intent_sig = {
            "operation": intent.get("operation"),
            "entities": intent.get("primary_entities") or [],
            "metrics": intent.get("metrics") or [],
            "filters": intent.get("filters") or [],
            "time_window": intent.get("time_window") or {},
            "analytic_template": intent.get("analytic_template"),
            "required_action": intent.get("required_action"),
        }
        skip_tables = sorted(state.get("skip_tables") or [])
        tried_tables = sorted(state.get("tried_candidate_tables") or [])
        seed_tables = sorted(state.get("seed_tables") or [])
        dialect = state.get("db_dialect") or self.db_dialect
        schema = state.get("db_default_schema") or self.db_default_schema
        payload = {
            "user_input": user_input,
            "intent": intent_sig,
            "skip_tables": skip_tables,
            "tried_tables": tried_tables,
            "seed_tables": seed_tables,
            "db_dialect": dialect,
            "db_default_schema": schema,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def _build_join_inputs_fingerprint(self, state: BaseState) -> str:
        """
        Build a stable fingerprint for join/SQL generation inputs.

        Captures relevant_tables + intent signature so we can detect redundant
        join planning/SQL generation cycles.
        """
        raw_tables = state.get("relevant_tables") or []
        table_names: List[str] = []
        for t in raw_tables:
            if isinstance(t, str):
                table_names.append(t)
            elif isinstance(t, dict):
                name = t.get("full_name") or t.get("name")
                if name:
                    table_names.append(str(name))
        table_names = sorted(set(table_names))

        intent = state.get("intent") or {}
        intent_sig = {
            "operation": intent.get("operation"),
            "entities": intent.get("primary_entities") or [],
            "metrics": intent.get("metrics") or [],
            "filters": intent.get("filters") or [],
            "time_window": intent.get("time_window") or {},
            "analytic_template": intent.get("analytic_template"),
            "required_action": intent.get("required_action"),
        }
        payload = {
            "tables": table_names,
            "intent": intent_sig,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def _sql_fingerprint(self, sql: str) -> str:
        """
        Build a stable fingerprint for SQL text for repair loop diagnostics.

        Normalizes whitespace and case and hashes the result so that
        repeated attempts with the same logical SQL can be detected.
        """
        try:
            import hashlib
            normalized = (sql or "").strip().lower()
            # Collapse internal whitespace to a single space to ignore formatting-only changes
            normalized = re.sub(r"\s+", " ", normalized)
            return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        except Exception:
            # Fall back to raw SQL if hashing fails for any reason
            return (sql or "").strip()

    def _exec_error_signature(self, exec_result: Dict[str, Any]) -> str:
        """
        Build a normalized execution error signature from exec_result.

        When the driver exposes structured error codes/SQLSTATE, those
        should be incorporated; for now we normalize the error message.
        """
        error_payload = None
        if isinstance(exec_result, dict):
            error_payload = exec_result.get("error") or exec_result.get("error_info")

        if isinstance(error_payload, dict):
            raw_msg = error_payload.get("message") or error_payload.get("error") or str(error_payload)
        else:
            raw_msg = str(error_payload) if error_payload is not None else ""

        # Normalize: lowercase, collapse whitespace, strip digits to reduce noise
        msg = (raw_msg or "").strip().lower()
        msg = re.sub(r"\s+", " ", msg)
        msg = re.sub(r"\d+", "#", msg)
        return msg or "<no_error>"

    def _repair_signature(self, state: BaseState) -> str:
        """
        Combine SQL and execution error into a single repair signature.

        Used by Phase 2b repair loop control to detect no-progress cycles.
        """
        sql_query = state.get("sql_query", "") or ""
        exec_result = state.get("exec_result") or {}
        sql_fp = self._sql_fingerprint(sql_query)
        err_sig = self._exec_error_signature(exec_result if isinstance(exec_result, dict) else {})
        state["last_exec_error_signature"] = err_sig
        return f"{sql_fp}::{err_sig}"

    def _derive_required_tables_from_kpi(
        self,
        kpi_expressions: Dict[str, str],
        dialect: str,
        default_schema: str,
    ) -> List[str]:
        """
        Derive required tables from KPI expressions by scanning for table-qualified
        identifiers and normalizing them via _canonical_table_name.

        Examples:
        - "CASE WHEN Products.UnitsInStock < Products.ReorderLevel THEN 1 END"
          → public.products (on Postgres with default_schema=public)
        - "AVG(DATEDIFF(day, Orders.OrderDate, Orders.ShippedDate))"
          → public.orders
        """
        if not kpi_expressions:
            return []

        sql_keywords = {
            "case",
            "when",
            "then",
            "else",
            "end",
            "and",
            "or",
            "not",
            "null",
            "count",
            "sum",
            "avg",
            "min",
            "max",
            "coalesce",
            "isnull",
            "convert",
            "cast",
            "dateadd",
            "datediff",
            "eomonth",
            "year",
            "month",
            "day",
            "distinct",
        }

        required: List[str] = []
        seen: set[str] = set()

        for _, expr in kpi_expressions.items():
            if not isinstance(expr, str) or not expr:
                continue
            text = expr

            # Bracketed schema/table patterns: [schema].[table]
            for schema, table in re.findall(r"\[([^\]]+)\]\.\[([^\]]+)\]", text):
                raw_name = f"{schema}.{table}"
                canonical = self._canonical_table_name(raw_name, dialect=dialect, default_schema=default_schema)
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    required.append(canonical)

            # Simple identifier prefix patterns: Products.UnitsInStock → Products
            for identifier in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.", text):
                ident_l = identifier.lower()
                if ident_l in sql_keywords:
                    continue
                canonical = self._canonical_table_name(identifier, dialect=dialect, default_schema=default_schema)
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    required.append(canonical)

        return required

    def _canonical_table_name(self, raw_name: str, dialect: str, default_schema: str) -> str:
        """
        Wrapper around the shared canonical_table_name utility.

        Kept as a method for backwards compatibility with existing call
        sites in the orchestrator, but the implementation is shared with
        other components (concept mapper, discovery, join planning).
        """
        return canonical_table_name(raw_name, dialect=dialect, schema=default_schema)

    def _check_llm_budget(self, state: BaseState, stage: str) -> BaseState:
        """
        Increment global LLM call counter and enforce max_llm_calls budget.

        Accounting rule (Phase 1 instrumentation):
        - Count once per LLM-using agent subgraph invocation (per-node LLM call),
          not per orchestrator node entry.
        - Deterministic paths that do NOT invoke an LLM-backed subgraph should
          skip this helper entirely so llm_usage reflects actual model calls.
        - Maintain both total_llm_calls (legacy) and llm_usage[...] buckets for per-node analysis.

        If the budget is exceeded, mark error_info and set clarify intent.
        """
        max_calls = state.get("max_llm_calls", 0) or 20
        total_calls = state.get("total_llm_calls", 0)
        if total_calls >= max_calls:
            logger.warning(
                "🧠 [BUDGET] LLM call budget exceeded at stage '%s' (%s/%s)",
                stage,
                total_calls,
                max_calls,
            )
            intent = state.get("intent") or {}
            intent["operation"] = "clarify"
            intent["needs_clarification"] = True
            intent["clarification_question"] = intent.get(
                "clarification_question",
                "This question would require more model calls than allowed in the current safety budget. Could you narrow down the scope?",
            )
            intent["ambiguity_reason"] = intent.get(
                "ambiguity_reason",
                "LLM call budget exceeded while trying to answer this question.",
            )
            state["intent"] = intent
            merge_error_info(
                state,
                {
                    "type": "LLM_BUDGET_EXCEEDED",
                    "message": "Global LLM call budget exceeded for this query.",
                    "stage": stage,
                    "total_llm_calls": total_calls,
                },
            )
            # Structured debug log for budget exhaustion
            debug_logger.info(
                "LLM_BUDGET_EXCEEDED",
                data={
                    "stage": stage,
                    "total_llm_calls": total_calls,
                    "max_llm_calls": max_calls,
                },
            )
            return state

        # Update per-node and total usage counters
        llm_usage = state.get("llm_usage") or {}
        bucket = self._map_stage_to_llm_bucket(stage)
        bucket_count = llm_usage.get(bucket, 0) + 1
        total_usage = llm_usage.get("total", 0) + 1
        llm_usage[bucket] = bucket_count
        llm_usage["total"] = total_usage
        state["llm_usage"] = llm_usage

        # Keep legacy counter in sync with llm_usage["total"] for backward compatibility
        state["total_llm_calls"] = total_usage

        # Emit structured debug log for this LLM usage event
        remaining_budget = max_calls - total_usage
        debug_logger.info(
            "LLM_CALL_SPENT",
            data={
                "stage": stage,
                "bucket": bucket,
                "bucket_calls": bucket_count,
                "total_llm_calls": total_usage,
                "max_llm_calls": max_calls,
                "remaining_budget": remaining_budget,
                "retry_attempt_count": state.get("retry_attempt_count", 0),
                "plan_attempt_count": state.get("plan_attempt_count", 0),
                "exec_attempt_count": state.get("exec_attempt_count", 0),
            },
        )

        # If we're approaching the hard budget, emit an early warning for diagnostics
        safety_margin = state.get("llm_budget_safety_margin", 0) or 0
        if remaining_budget <= safety_margin:
            debug_logger.warning(
                title="LLM_BUDGET_NEAR_LIMIT",
                details=(
                    f"Stage '{stage}' is near the LLM budget limit; "
                    f"{remaining_budget} calls remaining (safety_margin={safety_margin})."
                ),
                context={
                    "stage": stage,
                    "total_llm_calls": total_usage,
                    "max_llm_calls": max_calls,
                    "remaining_budget": remaining_budget,
                    "llm_budget_safety_margin": safety_margin,
                },
            )

        return state

    async def ainvoke(self, input_state: Dict, **kwargs):
        """
        Invoke the orchestrator graph with sensible defaults.
        
        Sets default recursion_limit=1500 if not provided (needed because
        subgraphs, nested agent calls, and internal tool invocations
        consume many recursion steps across the call stack).
        """
        config = kwargs.pop("config", {})
        if "recursion_limit" not in config:
            config["recursion_limit"] = 1500
        result = await self.graph.ainvoke(input_state, config=config, **kwargs)
        if isinstance(result, dict):
            result.setdefault("answer", result.get("final_response", ""))
        return result

    def _build_graph(self) -> StateGraph:
        """
        Build the complete orchestrator graph.
        
        Returns:
            Compiled LangGraph StateGraph ready for execution
        """
        from typing import Literal
        
        logger.info("🏗️  Building orchestrator graph...")
        graph = StateGraph(BaseState)

        # ============= Define all nodes (registered as async for ainvoke) =============
        # For ainvoke() compatibility, register nodes as their native async methods
        graph.add_node("index_database", self._index_database_node)
        graph.add_node("parse_intent", self._parse_intent_node)
        graph.add_node("concept_mapping", self._concept_mapping_node)
        graph.add_node("route_operation", self._route_operation_node)

        # Agent nodes (main flow) - register async implementations directly
        graph.add_node("discovery", self._discovery_node)
        graph.add_node("join_sql", self._join_sql_node)
        graph.add_node("validate_sql", self._validate_sql_node)
        graph.add_node("exec_recovery", self._exec_recovery_node)
        # 🆕 Phase 10a: Result validation node (catches silent failures)
        # Wrap result validator in an orchestrator method so we can instrument node entry/LLM usage.
        graph.add_node("result_validator", self._result_validator_async)
        graph.add_node("answer", self._answer_node)
        # interpretation node is added once above

        # Special operation nodes - register async implementations directly
        graph.add_node("answer_schema", self._answer_schema_node)
        graph.add_node("answer_health", self._answer_health_node)
        graph.add_node("answer_error", self._answer_error_node)
        # Interpretation node implementation
        graph.add_node("interpret", self._interpret_node)

        # ============= Define edges =============
        # Initial path: index → parse → route
        graph.add_edge(START, "index_database")
        graph.add_edge("index_database", "parse_intent")
        graph.add_edge("parse_intent", "concept_mapping")
        graph.add_edge("concept_mapping", "route_operation")

        # ============= CONDITIONAL ROUTING FROM route_operation =============
        # Based on operation type, route to appropriate handler
        def route_to_operation(state: BaseState) -> str:
            """
            Route to appropriate handler based on intent operation.

            Priority order:
            1. needs_clarification: Ask user for clarification (highest priority)
            2. error_info: Handle errors
            3. operation type: Route based on intent operation

            Branches:
            - "clarify": Ask user for clarification (needs_clarification=True)
            - "error": Handle errors (error_info present)
            - "schema_query": Discover tables/views and explain schema
            - "health_check": Check system health
            - "execute_direct": Execute pre-written SQL
            - "query" (default): Full query pipeline *TODO Default?
            #TODO CHAT with the agent
            """
            intent = state.get("intent", {})
            operation = intent.get("operation", "query")
            needs_clarification = intent.get("needs_clarification", False)
            error_info = state.get("error_info")

            logger.info(f"🚦 [ROUTE_TO_OPERATION] intent: {intent}")
            logger.info(f"🚦 [ROUTE_TO_OPERATION] operation: {operation}")
            logger.info(f"🚦 [ROUTE_TO_OPERATION] needs_clarification: {needs_clarification}")
            logger.info(f"🚦 [ROUTE_TO_OPERATION] error_info: {error_info}")

            # HIGHEST PRIORITY: Check for clarification needs
            if needs_clarification:
                logger.info("🚦 [ROUTE_TO_OPERATION] ⚠️  Query needs clarification, routing to answer")
                return "answer"

            # SECOND PRIORITY: Check for errors
            if error_info:
                logger.info("🚦 [ROUTE_TO_OPERATION] ❌ Error detected, routing to answer_error")
                return "answer_error"

            # THIRD PRIORITY: Route by required_action (refinement/interpretation)
            result = None
            try:
                required_action = intent.get("required_action")
                if required_action == "refine_previous":
                    logger.info("🚦 [ROUTE_TO_OPERATION] 🔄 Refinement query detected → discovery")
                    target_tables = intent.get("target_tables", [])
                    if target_tables:
                        logger.info(f"🚦 [ROUTE_TO_OPERATION]    Target tables: {target_tables}")
                        state["forced_tables"] = target_tables
                    return "discovery"
                elif required_action == "interpret_previous" and (state.get("previous_exec_result") or state.get("exec_result")):
                    logger.info("🚦 [ROUTE_TO_OPERATION] 🎯 Follow-up interpretation detected → interpret")
                    return "interpret"
            except Exception as e:
                logger.warning(f"🚦 [ROUTE_TO_OPERATION] Error checking required_action: {e}")
                pass
            if operation == "clarify":
                result = "answer"
            elif operation == "schema_query":
                result = "discovery_for_schema"
            elif operation == "health_check":
                result = "answer_health"
            elif operation == "execute_direct":
                result = "exec_recovery"
            elif operation == "error":
                result = "answer_error"
            else:
                # Default: query → discovery → join_sql → exec → answer
                result = "discovery"

            logger.info(f"🚦 [ROUTE_TO_OPERATION] Routing to: {result}")
            return result

        # Add conditional edges from route_operation with explicit mapping
        graph.add_conditional_edges(
            "route_operation",
            route_to_operation,
            {
                "answer": "answer",
                "discovery_for_schema": "discovery_for_schema",
                "answer_health": "answer_health",
                "exec_recovery": "exec_recovery",
                "answer_error": "answer_error",
                "discovery": "discovery",
                "interpret": "interpret",
            }
        )

        # ============= QUERY PIPELINE ============= TODO Still up to date?
        # Standard query flow: discovery → join_sql → validate_sql → exec_recovery → result_validator → (conditional) answer
        def route_discovery_result(state: BaseState) -> str:
            intent = state.get("intent") or {}
            if intent.get("needs_clarification"):
                logger.info("🔍 [DISCOVERY_ROUTE] Clarification requested after discovery → answer")
                return "answer"
            if state.get("error_info"):
                logger.info("🔍 [DISCOVERY_ROUTE] Error detected after discovery → answer_error")
                return "answer_error"
            relevant_tables = state.get("relevant_tables") or []
            if not relevant_tables:
                logger.info("🔍 [DISCOVERY_ROUTE] No relevant tables found → answer")
                return "answer"
            return "join_sql"

        graph.add_conditional_edges(
            "discovery",
            route_discovery_result,
            {
                "join_sql": "join_sql",
                "answer": "answer",
                "answer_error": "answer_error",
            }
        )
        graph.add_edge("join_sql", "validate_sql")
        graph.add_edge("validate_sql", "exec_recovery")
        # 🆕 Phase 10a: After exec, validate result before answering
        graph.add_edge("exec_recovery", "result_validator")
        
        # 🆕 Phase 10a: Conditional routing from result_validator based on validation outcome TODO explain this?
        def route_validation_result(state: BaseState) -> str:
            """
            Route based on validation result.
            Retry actions:
            - accept: validation passed, proceed to answer
            - try_next_candidate: validation failed, try next discovery candidate
            - replan_with_aggregation: missing GROUP BY, regenerate SQL
            - replan_with_filter: missing WHERE, regenerate SQL
            - ask_user: validation unclear, ask user for clarification
            """
            validation = state.get("validation_result", {}) or {}
            retry_action = validation.get("retry_action", "accept")
            
            logger.info(f"🚦 [VALIDATION_ROUTE] retry_action={retry_action}")

            # Phase 2b: Repair loop caps & no-progress detection
            validation_attempts = state.get("validation_attempt_count", 0)
            exec_recovery_attempts = state.get("exec_recovery_attempt_count", 0)
            max_validation_attempts = state.get("max_validation_attempts", 0) or getattr(self, "max_validation_attempts", 2)
            max_exec_recovery_attempts = state.get("max_exec_recovery_attempts", 0) or getattr(self, "max_exec_recovery_attempts", 2)
            max_no_progress_repeats = state.get("max_no_progress_repeats", 0) or getattr(self, "max_no_progress_repeats", 2)

            logger.info(
                "🚦 [VALIDATION_ROUTE] attempts: validation=%s/%s exec_recovery=%s/%s",
                validation_attempts,
                max_validation_attempts,
                exec_recovery_attempts,
                max_exec_recovery_attempts,
            )

            # No-progress detector: track repeated (SQL,error) signatures
            try:
                sig = self._repair_signature(state)
                seen = state.get("repair_signatures_seen") or {}
                count = seen.get(sig, 0) + 1
                seen[sig] = count
                state["repair_signatures_seen"] = seen
                state["repair_no_progress_count"] = state.get("repair_no_progress_count", 0) + (1 if count > 1 else 0)

                if count >= max_no_progress_repeats and max_no_progress_repeats > 0:
                    logger.warning(
                        "🚦 [VALIDATION] Repair no-progress detected for signature %s (count=%s/%s)",
                        sig,
                        count,
                        max_no_progress_repeats,
                    )
                    state["stop_reason"] = "repair_no_progress"
                    preview_sql = (state.get("sql_query", "") or "").strip()
                    preview_sql = preview_sql[:300] + ("..." if len(preview_sql) > 300 else "")
                    merge_error_info(
                        state,
                        {
                            "type": "REPAIR_NO_PROGRESS",
                            "stage": "validate_sql",
                            "message": "Validation/repair cycles repeated the same failing SQL and error without improvement.",
                            "suggestion": (
                                "Try narrowing the question (fewer tables/metrics) or phrasing it in a simpler way. "
                                "You can also try referencing specific tables if you know them."
                            ),
                            "context": {
                                "sql_preview": preview_sql,
                                "last_error_signature": state.get("last_exec_error_signature"),
                            },
                        },
                    )
                    return "answer"
            except Exception as e:
                logger.warning(f"🚦 [VALIDATION] Failed to compute repair signature: {e}")

            # 🧠 Budget-aware routing: if we are at or below the safety margin,
            # stop sending the graph back to discovery/join (which would require
            # additional LLM calls) and move toward answering with existing data.
            llm_usage = state.get("llm_usage") or {}
            max_calls = state.get("max_llm_calls", 0) or 20
            total_usage = llm_usage.get("total", state.get("total_llm_calls", 0) or 0)
            remaining_budget = max_calls - int(total_usage)
            safety_margin = state.get("llm_budget_safety_margin", 0) or 0
            if remaining_budget <= safety_margin:
                logger.warning(
                    "🚦 [VALIDATION] Remaining LLM budget at/below safety margin "
                    f"(remaining={remaining_budget}, safety_margin={safety_margin}); "
                    "disabling discovery/join retries and routing to 'answer'."
                )
                # Force accept-path so downstream goes directly to answer.
                validation["retry_action"] = "accept"
                state["validation_result"] = validation
                return "answer"

            # 🆕 Global plan budget: stop after too many plan/validate cycles
            plan_attempt = state.get("plan_attempt_count", 0)
            max_plans = state.get("max_total_plans", 6)
            if plan_attempt >= max_plans:
                logger.warning(
                    "🚦 [VALIDATION] Global plan budget exceeded "
                    f"({plan_attempt}/{max_plans}), routing to 'answer'"
                )
                 # Convert into a clarification-style failure to avoid burning more tokens
                intent = state.get("intent") or {}
                intent["operation"] = "clarify"
                intent["needs_clarification"] = True
                intent["clarification_question"] = intent.get(
                    "clarification_question",
                    "This question requires a complex analytic query and I could not find a stable plan within a safe number of attempts. Could you narrow down the scope or specify the main metric you care about?"
                )
                intent["ambiguity_reason"] = intent.get(
                    "ambiguity_reason",
                    "Maximum planning retries exceeded; query was too broad or complex for an automatic plan."
                )
                state["intent"] = intent
                merge_error_info(
                    state,
                    {
                        "type": "MAX_RETRIES_EXCEEDED",
                        "message": (
                            "The system attempted multiple discovery and planning cycles "
                            "but could not produce a stable query plan."
                        ),
                    },
                )
                return "answer"

            # Phase 2b: Hard caps on validation and exec_recovery attempts
            if retry_action in ("try_next_candidate", "replan_with_aggregation", "replan_with_filter"):
                if validation_attempts >= max_validation_attempts:
                    logger.warning(
                        "🚦 [VALIDATION] Max validation attempts reached (%s/%s); stopping repair loop",
                        validation_attempts,
                        max_validation_attempts,
                    )
                    state["stop_reason"] = "max_validation_attempts"
                    merge_error_info(
                        state,
                        {
                            "type": "REPAIR_LOOP_STUCK",
                            "stage": "validate_sql",
                            "message": (
                                "The system attempted to validate and repair the SQL multiple times "
                                "but could not produce a stable, executable query."
                            ),
                            "suggestion": (
                                "Try narrowing the question (fewer tables/metrics) or specifying a clearer metric "
                                "so the planner can generate a simpler query."
                            ),
                        },
                    )
                    return "answer"

            if retry_action == "try_next_candidate" and exec_recovery_attempts >= max_exec_recovery_attempts:
                logger.warning(
                    "🚦 [VALIDATION] Max exec_recovery attempts reached (%s/%s); stopping repair loop",
                    exec_recovery_attempts,
                    max_exec_recovery_attempts,
                )
                state["stop_reason"] = "max_exec_recovery_attempts"
                merge_error_info(
                    state,
                    {
                        "type": "REPAIR_LOOP_STUCK",
                        "stage": "exec_recovery",
                        "message": (
                            "The system attempted to execute and repair the query multiple times "
                            "but could not complete execution safely."
                        ),
                        "suggestion": (
                            "Consider asking a simpler question or focusing on a smaller subset of data."
                        ),
                    },
                )
                return "answer"
            # Increment plan attempt count when we're about to take a retry action
            if retry_action in ("try_next_candidate", "replan_with_aggregation", "replan_with_filter"):
                state["plan_attempt_count"] = plan_attempt + 1

            # 🆕 Circuit breaker: stop retrying per candidate set
            retry_attempt = state.get("retry_attempt_count", 0)
            max_retries = state.get("max_retries_per_candidate_set", 2)
            
            if retry_attempt >= max_retries:
                logger.warning(
                    f"🚦 [VALIDATION] Max retries exceeded "
                    f"({retry_attempt}/{max_retries}), routing to 'answer'"
                )
                merge_error_info(
                    state,
                    {
                        "type": "MAX_RETRIES_EXCEEDED",
                        "message": (
                            "All discovery candidates have been tried but the query "
                            "could not be executed successfully."
                        ),
                    },
                )
                return "answer"
            
            if retry_action == "try_next_candidate":
                state["retry_attempt_count"] = retry_attempt + 1
                logger.info(
                    f"🔄 Validation: Trying next candidate "
                    f"(attempt {state['retry_attempt_count']}/{max_retries})"
                )
                return "discovery"
            elif retry_action in ["replan_with_aggregation", "replan_with_filter"]:
                state["retry_attempt_count"] = retry_attempt + 1
                logger.info(
                    f"🔄 Validation: Replanning with {retry_action} "
                    f"(attempt {state['retry_attempt_count']}/{max_retries})"
                )
                return "join_sql"
            elif retry_action == "ask_user":
                logger.info("❓ Validation: Asking user for clarification")
                return "answer"
            else:  # accept or unknown
                logger.info("✅ Validation: Result accepted, proceeding to answer")
                return "answer"
        
        graph.add_conditional_edges(
            "result_validator",
            route_validation_result,
            {
                "discovery": "discovery",
                "join_sql": "join_sql",
                "answer": "answer",
            }
        )
        # Interpretation path is terminal
        graph.add_edge("interpret", END)

        # ============= SCHEMA QUERY PIPELINE =============
        # Schema discovery flow: discovery_for_schema → answer_schema
        # (We use a separate entry point node name to make the graph topology clear)
        graph.add_node("discovery_for_schema", self._discovery_node)  # Same implementation
        graph.add_edge("discovery_for_schema", "answer_schema")

        # ============= TERMINAL NODES =============
        graph.add_edge("answer", END)
        graph.add_edge("answer_schema", END)
        graph.add_edge("answer_health", END)
        graph.add_edge("answer_error", END)

        compiled = graph.compile()
        logger.info("✅ Orchestrator graph compiled successfully")
        logger.info(f"   Graph nodes: {list(compiled.nodes.keys())}")
        logger.info(f"   Query path: discovery → join_sql → validate_sql → exec_recovery → result_validator (conditional) → discovery|join_sql|answer")
        return compiled

    # Legacy-simple intent parser for tests and quick routes
    def _simple_intent_parser(self, text: str) -> Dict[str, Any]: #TODO remove?
        t = (text or "").lower()
        intent: Dict[str, Any] = {"operation": "query", "primary_entities": [], "entities": [], "metrics": [], "filters": []}
        # Health
        if any(k in t for k in ["health", "working", "status"]):
            intent["operation"] = "health_check"
            return intent
        # Schema
        if any(k in t for k in ["tables", "schema", "views"]):
            intent["operation"] = "schema_query"
        # Count
        if any(k in t for k in ["how many", "count", "anzahl", "wie viele"]):
            intent.setdefault("metrics", []).append("count")
        # Naive entities
        for word in ["customers", "customer", "products", "product", "orders", "sales"]:
            if word in t:
                intent.setdefault("primary_entities", []).append(word)
                intent.setdefault("entities", []).append(word)
        # Discovery keywords (used by DiscoveryAgent)
        kws = []
        for w in ["customers", "products", "orders", "sales"]:
            if w in t:
                kws.append(w)
        if kws:
            intent["keywords_for_discovery"] = list(dict.fromkeys(kws))
        return intent

    # ============= Catalog Management =============

    async def _get_or_build_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Get or build Scout catalog (idempotent).
        
        Attempts (in order):
        1. Fetch via MCP tool (scout_catalog_get)
        2. Load from local cache (data/catalog/scout_catalog.json)
        3. Trigger MCP rebuild and refetch
        
        Raises exception if all fail, never returns None/empty.
        """
        logger.info("📚 [CATALOG] Attempting to load/build Scout catalog...")

        def _entity_len(collection: Any) -> int:
            if isinstance(collection, dict):
                return len(collection)
            if isinstance(collection, list):
                return len(collection)
            return 0

        def _catalog_ready(payload: Any) -> bool:
            if not isinstance(payload, dict):
                return False
            return (_entity_len(payload.get("tables")) + _entity_len(payload.get("views"))) > 0
        
        # Try 1: Fetch via MCP tool
        try:
            logger.info("📚 [CATALOG] Attempt 1: Fetching via MCP (scout_catalog_get)...")
            catalog = await self.mcp.get_catalog(include_tables=True, include_views=True)
            if _catalog_ready(catalog):
                table_count = _entity_len(catalog.get("tables"))
                view_count = _entity_len(catalog.get("views"))
                logger.info(f"📚 [CATALOG] ✅ Loaded from MCP: {table_count} tables, {view_count} views")
                return catalog
            logger.info("📚 [CATALOG] Attempt 1 returned empty payload")
        except AttributeError:
            logger.warning("📚 [CATALOG] MCP client missing get_catalog(); falling back to cache")
        except Exception as e:
            logger.debug(f"📚 [CATALOG] Remote fetch failed: {e}")
        
        # Try 2: Load from file cache
        try:
            logger.info("📚 [CATALOG] Attempt 2: Trying to load from file cache...")
            catalog_path = "data/catalog/scout_catalog.json"
            if os.path.exists(catalog_path):
                with open(catalog_path, 'r', encoding='utf-8') as f:
                    catalog = json.load(f)
                if _catalog_ready(catalog):
                    table_count = _entity_len(catalog.get("tables"))
                    view_count = _entity_len(catalog.get("views"))
                    logger.info(f"📚 [CATALOG] ✅ Loaded from file: {table_count} tables, {view_count} views")
                    return catalog
        except Exception as e:
            logger.debug(f"📚 [CATALOG] File load failed: {e}")
        
        # Try 3: Build via MCP then refetch
        try:
            logger.info("📚 [CATALOG] Attempt 3: Building catalog via MCP...")
            build_result = await self.mcp.build_catalog(wait_for_completion=True)
            if not (isinstance(build_result, dict) and build_result.get("ok")):
                raise RuntimeError(build_result.get("error") if isinstance(build_result, dict) else "Catalog rebuild failed")
            catalog = await self.mcp.get_catalog(include_tables=True, include_views=True)
            if _catalog_ready(catalog):
                table_count = _entity_len(catalog.get("tables"))
                view_count = _entity_len(catalog.get("views"))
                logger.info(f"📚 [CATALOG] ✅ Built successfully: {table_count} tables, {view_count} views")
                return catalog
            raise RuntimeError("Catalog rebuild completed but no catalog was returned")
        except AttributeError:
            logger.warning("📚 [CATALOG] MCP client missing build_catalog(); cannot trigger rebuild")
        except Exception as e:
            logger.warning(f"📚 [CATALOG] Build attempt failed: {e}")
        
        # All attempts failed
        logger.error("📚 [CATALOG] ❌ All catalog loading strategies failed")
        raise RuntimeError(
            "Scout/Catalog initialization failed. "
            "Tried: MCP fetch, file load, and MCP build. "
            "Ensure MCP server is running and database is accessible."
        )

    # ============= Core node implementations =============

    async def _index_database_node(self, state: BaseState) -> BaseState:
        """
        HARD PREREQUISITE: Load Scout catalog and verify MCP availability.
        
        This node MUST ensure:
        1. MCP is healthy
        2. Scout/Catalog exists and is ready
        
        If either fails, the entire pipeline is blocked (no silent degradation).
        Discovery depends on this working.
        """
        debug_logger.agent_entry("index_database", dict(state))
        before_state = dict(state)
        
        logger.info("📚 [INDEX_DATABASE] ════════════════════════════════════════")
        logger.info("📚 [INDEX_DATABASE] HARD PREREQUISITE CHECK: Scout/Catalog")
        logger.info("📚 [INDEX_DATABASE] ════════════════════════════════════════")

        try:
            # Check MCP health
            logger.info("📚 [INDEX_DATABASE] Step 1/2: Checking MCP availability...")
            logger.info(f"📚 [INDEX_DATABASE] MCP URL: {getattr(self.mcp, 'mcp_url', 'unknown')}")
            is_healthy = await self.mcp.health_check()
            logger.info(f"📚 [INDEX_DATABASE] Health check result: {is_healthy}")

            if not is_healthy:
                error = {
                    "type": "MCP_UNAVAILABLE",
                    "message": "MCP server is not responding. Database access is unavailable."
                }
                logger.error(f"📚 [INDEX_DATABASE] ❌ HARD BLOCK: {error['message']}")
                result_state = {**state, "error_info": error}
                debug_logger.agent_exit("index_database", before_state, dict(result_state))
                return result_state

            logger.info("📚 [INDEX_DATABASE] ✅ MCP health check passed")
            
            # NEW: Verify Scout/Catalog is ready (HARD REQUIREMENT)
            logger.info("📚 [INDEX_DATABASE] Step 2/2: Verifying Scout/Catalog readiness...")
            try:
                # Attempt to get catalog or build it if missing
                catalog = await self._get_or_build_catalog()
                if not catalog:
                    raise ValueError("Catalog is empty or not available")
                
                table_count = len(catalog.get("tables", {}))
                view_count = len(catalog.get("views", {}))
                logger.info(f"📚 [INDEX_DATABASE] ✅ Catalog ready: {table_count} tables, {view_count} views")
                state["catalog"] = catalog
                
            except Exception as e:
                error = {
                    "type": "CATALOG_NOT_READY",
                    "message": f"Scout/Catalog is not available: {str(e)}. Discovery requires this to function.",
                    "error": str(e)
                }
                logger.error(f"📚 [INDEX_DATABASE] ❌ HARD BLOCK: {error['message']}")
                result_state = {**state, "error_info": error}
                debug_logger.agent_exit("index_database", before_state, dict(result_state))
                return result_state

            logger.info("📚 [INDEX_DATABASE] ✅ All prerequisites satisfied, pipeline may proceed")
            # Load last execution result for interpretation follow-ups (memory → disk)
            cache = self._previous_exec_cache or {}
            if cache:
                state["previous_exec_result"] = cache.get("exec_result")
                state["previous_sql"] = cache.get("sql_query")
                state["previous_sources"] = cache.get("sources") or []
                logger.info("📚 [INDEX_DATABASE] Loaded previous_exec_result from in-memory cache")
            else:
                try:
                    cache_path = os.path.join("data", "last_exec_result.json")
                    if os.path.exists(cache_path):
                        with open(cache_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                        state["previous_exec_result"] = payload.get("exec_result")
                        state["previous_sql"] = payload.get("sql_query")
                        state["previous_sources"] = payload.get("sources") or []
                        logger.info("📚 [INDEX_DATABASE] Loaded previous_exec_result for interpretation follow-ups")
                except Exception as e:
                    logger.warning(f"📚 [INDEX_DATABASE] Could not load last_exec_result cache: {e}")
            # Preflight warm-up: make a tiny list_tables call to stabilize /mcp endpoint
            try:
                logger.info("📚 [INDEX_DATABASE] Preflight: list_tables(page=1,page_size=1)")
                await self.mcp_client.list_tables(page=1, page_size=1)
            except Exception as warm_err:
                logger.warning(f"📚 [INDEX_DATABASE] Preflight warm-up failed (will continue): {warm_err}")
            debug_logger.agent_exit("index_database", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "INDEX_ERROR",
                "message": f"Failed to index database: {str(e)}",
                "error": str(e)
            }
            logger.error(f"📚 [INDEX_DATABASE] ❌ {error['message']}")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("index_database", before_state, dict(result_state))
            return result_state

    async def _parse_intent_node(self, state: BaseState) -> BaseState: #TODO Why is this in the query orhcestrator?
        """
        Parse user intent using LangGraph subgraph with agentic reasoning (Phase 9.1).

        IntentParserAgent is now a FULL LangGraph subgraph
        - Multi-step reasoning instead of single LLM call
        - Built-in error recovery and fallbacks
        - Conditional routing for ambiguous queries
        - State persistence across reasoning steps

        Subgraph flow:
        analyze_query → classify_operation → extract_entities → validate_intent
            ↓ (conditional)
        handle_ambiguity (if needed) → END

        Returns: Updated state with intent, confidence, and clarification flags
        """
        # Short-circuit if prior error exists (e.g., MCP unavailable)
        if state.get("error_info"):
            logger.warning("🧠 [PARSE_INTENT] Skipping intent parsing due to prior error_info")
            return state

        logger.info("🧠 [PARSE_INTENT] 🚀 NODE CALLED - Starting intent parsing")
        if not state.get("run_id"):
            state = {**state, "run_id": str(uuid.uuid4())}
        # Instrumentation: track node entry
        self._increment_node_entry(state, "parse_intent")
        debug_logger.agent_entry("parse_intent", dict(state))
        before_state = dict(state)

        logger.info("🧠 [PARSE_INTENT] ════════════════════════════════════════")
        logger.info("🧠 [PARSE_INTENT] STARTING AGENTIC INTENT PARSING (Phase 9.1)")
        logger.info("🧠 [PARSE_INTENT] ════════════════════════════════════════")

        user_input = state.get("user_input", "")
        messages = state.get("messages", [])

        if not user_input:
            error = {
                "type": "NO_INPUT",
                "message": "No user input provided"
            }
            logger.error("🧠 [PARSE_INTENT] ❌ No user input!")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("parse_intent", before_state, dict(result_state))
            return result_state

        try:
            logger.info(f"🧠 [PARSE_INTENT] Query: \"{user_input}\"")
            logger.info("🧠 [PARSE_INTENT] Building IntentParserAgent subgraph...")

            # LLM budget check
            state = self._check_llm_budget(state, "parse_intent")
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                logger.warning("🧠 [PARSE_INTENT] Exiting early due to LLM budget exhaustion")
                debug_logger.agent_exit("parse_intent", before_state, dict(state))
                return state

            # 🆕 Phase 9.1: Build and invoke intent parsing subgraph
            intent_subgraph = self.intent_parser.build_subgraph()
            logger.info("🧠 [PARSE_INTENT] ✅ Subgraph built, invoking...")

            result = await intent_subgraph.ainvoke(state)
            logger.info("🧠 [PARSE_INTENT] ✅ Intent parsing subgraph completed")

            # Extract results from subgraph
            intent = result.get("intent", {})
            logger.info(f"🧠 [PARSE_INTENT] Intent extracted: {intent}")

            if not intent:
                logger.error("🧠 [PARSE_INTENT] ❌ CRITICAL: No intent returned from subgraph!")
                error = {
                    "type": "INTENT_PARSE_ERROR",
                    "message": "Intent parsing subgraph returned no intent",
                    "error": "Subgraph execution failed"
                }
                result_state = {**state, "error_info": error}
                debug_logger.agent_exit("parse_intent", before_state, dict(result_state))
                return result_state

            logger.info("🧠 [PARSE_INTENT] ━━━ PARSED INTENT ━━━")
            logger.info(f"🧠 [PARSE_INTENT]   operation: {intent.get('operation')}")
            logger.info(f"🧠 [PARSE_INTENT]   primary_entities: {intent.get('primary_entities', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   metrics: {intent.get('metrics', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   filters: {intent.get('filters', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   time_window: {intent.get('time_window')}")
            logger.info(f"🧠 [PARSE_INTENT]   keywords_for_discovery: {intent.get('keywords_for_discovery', [])} ← CRITICAL!")
            logger.info(f"🧠 [PARSE_INTENT]   confidence: {intent.get('confidence', 0):.2f}")
            logger.info(f"🧠 [PARSE_INTENT]   needs_clarification: {intent.get('needs_clarification', False)}")

            # CRITICAL CHECK
            keywords = intent.get("keywords_for_discovery", [])
            needs_clarification = intent.get("needs_clarification", False)

            if needs_clarification:
                logger.warning("🧠 [PARSE_INTENT] ⚠️  Query needs clarification")
                logger.warning(f"🧠 [PARSE_INTENT]    Question: {intent.get('clarification_question', 'N/A')}")
                logger.warning(f"🧠 [PARSE_INTENT]    Reason: {intent.get('ambiguity_reason', 'N/A')}")
            elif not keywords:
                logger.error("🧠 [PARSE_INTENT] ❌ CRITICAL: keywords_for_discovery is EMPTY!")
                logger.error("🧠 [PARSE_INTENT]    This will cause discovery to use fallback extraction")
                logger.error("🧠 [PARSE_INTENT]    Result: All 943 tables will be searched")
            else:
                logger.info(f"🧠 [PARSE_INTENT] ✅ Keywords OK: {keywords}")

            # Store the parsed intent in state
            state["intent"] = intent
            logger.info("🧠 [PARSE_INTENT] ✅ Intent stored in state['intent']")
            logger.info("🧠 [PARSE_INTENT] ✅ Ready for ROUTE_OPERATION node")

            debug_logger.intent_parsed_phase9(intent, parsing_method="LangGraph_Subgraph")
            debug_logger.agent_exit("parse_intent", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "INTENT_PARSE_ERROR",
                "message": f"Failed to execute intent parsing subgraph: {str(e)}",
                "error": str(e)
            }
            logger.error(f"🧠 [PARSE_INTENT] ❌ EXCEPTION: {error['message']}")
            logger.error(f"🧠 [PARSE_INTENT] Error: {str(e)}")
            import traceback
            logger.error(f"🧠 [PARSE_INTENT] Traceback:\n{traceback.format_exc()}")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("parse_intent", before_state, dict(result_state))
            return result_state

    async def _concept_mapping_node(self, state: BaseState) -> BaseState:
        if state.get("error_info"):
            return state
        intent = state.get("intent", {}) or {}
        catalog = state.get("catalog") or {}
        mapped = self.concept_mapper.map(state.get("user_input", ""), intent, catalog.get("concepts"))
        state["inferred_concepts"] = mapped.get("concepts") or []
        raw_seed_tables = mapped.get("seed_tables") or []
        # Phase 5 (quick win): canonicalize seed tables early so the entire pipeline
        # sees consistent identifiers (especially on Postgres runs).
        dialect = state.get("db_dialect", self.db_dialect)
        default_schema = state.get("db_default_schema", self.db_default_schema)
        canonical_seed_tables: List[str] = []
        for t in raw_seed_tables:
            canonical_seed_tables.append(
                self._canonical_table_name(t, dialect=dialect, default_schema=default_schema)
            )
        state["seed_tables"] = canonical_seed_tables
        concept_hints = {
            "kpi_expressions": mapped.get("kpi_expressions") or {},
            "time_field_hints": mapped.get("time_field_hints") or [],
            "join_hints": mapped.get("join_hints") or {},
        }
        state["concept_hints"] = concept_hints

        # Phase 4: Derive required tables from KPI expressions so discovery/join can
        # enforce their presence (e.g., inventory_reorder → products table).
        kpi_expressions = concept_hints.get("kpi_expressions") or {}
        required_tables_from_kpi = self._derive_required_tables_from_kpi(
            kpi_expressions=kpi_expressions,
            dialect=dialect,
            default_schema=default_schema,
        )
        if required_tables_from_kpi:
            state["required_tables_from_kpi"] = required_tables_from_kpi

        log_payload = state.get("discovery_log") or {}
        log_payload.update({
            "query": state.get("user_input", ""),
            "keywords": intent.get("keywords_for_discovery") or [],
            "concepts": state["inferred_concepts"],
            "seed_tables": state["seed_tables"],
            "kpi_expressions": concept_hints.get("kpi_expressions"),
            "time_field_hints": concept_hints.get("time_field_hints"),
            "required_tables_from_kpi": required_tables_from_kpi,
            "concept_explanations": mapped.get("explanations") or [],
        })
        log_payload.setdefault("events", [])
        state["discovery_log"] = log_payload
        return state

    async def _route_operation_node(self, state: BaseState) -> BaseState:
        """
        Routing node (actual routing done via conditional_edges).
        
        This determines which branch to take based on intent operation.
        """
        debug_logger.agent_entry("route_operation", dict(state))
        before_state = dict(state)
        
        logger.info("🚦 [ROUTE] ════════════════════════════════════════")
        logger.info("🚦 [ROUTE] CONDITIONAL ROUTING DECISION")
        logger.info("🚦 [ROUTE] ════════════════════════════════════════")
        
        intent = state.get("intent", {})
        operation = intent.get("operation", "query")
        
        logger.info(f"🚦 [ROUTE] operation field: '{operation}'")
        
        if operation == "query":
            logger.info(f"🚦 [ROUTE] ✅ Routing decision: QUERY PIPELINE")
            logger.info(f"🚦 [ROUTE]    Path: discovery → join_sql → exec_recovery → answer")
        elif operation == "schema_query":
            logger.info(f"🚦 [ROUTE] ✅ Routing decision: SCHEMA QUERY")
            logger.info(f"🚦 [ROUTE]    Path: discovery_for_schema → answer_schema")
        elif operation == "health_check":
            logger.info(f"🚦 [ROUTE] ✅ Routing decision: HEALTH CHECK")
            logger.info(f"🚦 [ROUTE]    Path: answer_health")
        else:
            logger.warning(f"🚦 [ROUTE] ⚠️  Unknown operation: {operation}")
            logger.info(f"🚦 [ROUTE]    Defaulting to: query pipeline")
        
        logger.info(f"🚦 [ROUTE] ✅ Routing complete, conditional_edges will take it from here")
        debug_logger.agent_exit("route_operation", before_state, dict(state))
        return state

    # ============= Agent nodes (subgraph invocations) =============

    async def _discovery_node(self, state: BaseState) -> BaseState:
        """
        Run DiscoveryAgent subgraph.
        
        Finds relevant tables/views using Scout semantic search, ranks by role coverage.
        Output: relevant_tables, schema_snippet, candidate_views, column_index
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "discovery")
        debug_logger.agent_entry("discovery", dict(state))
        before_state = dict(state)
        
        logger.info("🔍 [DISCOVERY] Starting DiscoveryAgent...")
        
        # 🆕 Track retry attempts and pass skip list to discovery
        retry_attempt = state.get("retry_attempt_count", 0)
        max_retries = state.get("max_retries_per_candidate_set", 2)
        tried = state.get("tried_candidate_tables", [])
        
        if retry_attempt > 0:
            logger.info(
                f"🔍 [DISCOVERY] Retry attempt #{retry_attempt}/{max_retries} "
                f"(tried={tried})"
            )
        
        # Pass the skip list to discovery so it filters out tried candidates
        if tried:
            state["skip_tables"] = tried
        
        # Clear prior error context when re-entering discovery for retries
        if state.get("error_info"):
            logger.info("🔍 [DISCOVERY] Clearing previous error_info before new discovery attempt")
        state.pop("error_info", None)

        # Build discovery fingerprint for caching/loop control
        fingerprint = self._build_discovery_fingerprint(state)
        discovery_cache = state.get("discovery_cache") or {}
        cached_fp = discovery_cache.get("fingerprint")
        cached_payload = discovery_cache.get("payload") or {}

        # Budget-aware short circuit: if we're re-entering discovery near the hard budget,
        # avoid spending additional LLM calls and reuse cached results when possible.
        remaining_budget = self._get_remaining_llm_budget(state)
        safety_margin = state.get("llm_budget_safety_margin", 0) or 0
        if retry_attempt > 0 and remaining_budget <= safety_margin:
            self._increment_loop_event(state, "discovery_budget_short_circuit")
            logger.warning(
                "🔍 [DISCOVERY] Near LLM budget limit "
                f"(remaining={remaining_budget}, safety_margin={safety_margin}); "
                "reusing existing discovery results if available and skipping new LLM calls."
            )
            if cached_payload:
                # Restore cached discovery outputs
                for key in (
                    "relevant_tables",
                    "candidate_views",
                    "schema_snippet",
                    "column_index",
                    "session_described_tables",
                    "relevant_table_details",
                    "discovery_role_hints",
                    "discovery_result",
                ):
                    if key in cached_payload:
                        state[key] = cached_payload[key]
                debug_logger.agent_exit("discovery", before_state, dict(state))
                return state
        
        # SURGICAL DEBUG: Show input state
        logger.info("🔍 [DISCOVERY] ━━━ INPUT STATE ━━━")
        logger.info(f"🔍 [DISCOVERY] Input keys: {list(state.keys())}")
        
        # DEBUG: Check what we're receiving
        intent = state.get("intent", {})
        keywords = intent.get("keywords_for_discovery", [])
        logger.info(f"🔍 [DISCOVERY] Intent check:")
        logger.info(f"🔍 [DISCOVERY]   - intent present? {bool(intent)}")
        logger.info(f"🔍 [DISCOVERY]   - intent type: {type(intent)}")
        logger.info(f"🔍 [DISCOVERY]   - intent keys: {list(intent.keys()) if isinstance(intent, dict) else 'N/A'}")
        logger.info(f"🔍 [DISCOVERY]   - keywords_for_discovery: {keywords} {'✅ GOOD' if keywords else '❌ EMPTY!'}")
        logger.info(f"🔍 [DISCOVERY]   - operation: {intent.get('operation', 'N/A')}")
        logger.info(f"🔍 [DISCOVERY]   - confidence: {intent.get('confidence', 'N/A')}")
        
        if not keywords:
            logger.warning("🔍 [DISCOVERY] ⚠️  CRITICAL: No keywords_for_discovery! Intent parsing may have FAILED.")
            logger.warning("🔍 [DISCOVERY] This will cause discovery to use fallback extraction and get 943 candidates!")

        try:
            # Cache hit: fingerprint unchanged → reuse previous discovery outputs without LLM calls
            if cached_fp == fingerprint and cached_payload:
                self._increment_loop_event(state, "discovery_cache_hit")
                logger.info("🔍 [DISCOVERY] Cache hit: reusing previous discovery results; skipping discovery subgraph")
                for key in (
                    "relevant_tables",
                    "candidate_views",
                    "schema_snippet",
                    "column_index",
                    "session_described_tables",
                    "relevant_table_details",
                    "discovery_role_hints",
                    "discovery_result",
                ):
                    if key in cached_payload:
                        state[key] = cached_payload[key]
                debug_logger.agent_exit("discovery", before_state, dict(state))
                return state

            # LLM budget check
            state = self._check_llm_budget(state, "discovery")
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                logger.warning("🔍 [DISCOVERY] Exiting early due to LLM budget exhaustion")
                debug_logger.agent_exit("discovery", before_state, dict(state))
                return state

            # Build and run discovery subgraph
            discovery_graph = self.discovery_agent.build_subgraph()

            # Invoke with input state using async API
            logger.info("🔍 [DISCOVERY] Invoking discovery subgraph with ainvoke()...")
            logger.info("🔍 [DISCOVERY] (This enters discovery subgraph nodes: search_candidates → rank → filter → describe → build_schema)")
            result = await discovery_graph.ainvoke(state)
            logger.info("🔍 [DISCOVERY] ✅ Discovery subgraph completed")

            # SURGICAL DEBUG: Show output state
            logger.info("🔍 [DISCOVERY] ━━━ OUTPUT STATE ━━━")
            logger.info(f"🔍 [DISCOVERY] Output keys: {list(result.keys())}")
            
            # Extract outputs and update state
            logger.info("🔍 [DISCOVERY] Extracting results from discovery subgraph...")
            relevant_tables = result.get("relevant_tables", [])
            candidate_views = result.get("candidate_views", [])
            schema_snippet = result.get("schema_snippet", "")
            column_index = result.get("column_index", {})
            
            logger.info(f"🔍 [DISCOVERY]   ✓ relevant_tables count: {len(relevant_tables)}")
            logger.info(f"🔍 [DISCOVERY]   ✓ candidate_views count: {len(candidate_views)}")
            logger.info(f"🔍 [DISCOVERY]   ✓ schema_snippet length: {len(schema_snippet)} chars")
            logger.info(f"🔍 [DISCOVERY]   ✓ column_index keys: {len(column_index)}")
            
            if relevant_tables:
                logger.info(f"🔍 [DISCOVERY]   📊 Top 3 tables: {relevant_tables[:3]}")
            else:
                logger.warning(f"🔍 [DISCOVERY]   ⚠️  NO relevant_tables returned!")
            
            # 🆕 Track which candidate is being tried on this cycle
            if relevant_tables:
                first_table = relevant_tables[0]
                table_name = (
                    first_table.get("full_name")
                    if isinstance(first_table, dict)
                    else str(first_table)
                )
                tried = state.get("tried_candidate_tables", [])
                if table_name not in tried:
                    tried.append(table_name)
                    state["tried_candidate_tables"] = tried
                    logger.info(f"🔍 [DISCOVERY] Marking candidate as tried: {table_name}")
            
            # Update state with outputs
            state["relevant_tables"] = relevant_tables
            state["schema_snippet"] = schema_snippet
            state["candidate_views"] = candidate_views
            state["column_index"] = column_index
            state["session_described_tables"] = result.get(
                "session_described_tables",
                state.get("session_described_tables", {})
            )
            if "relevant_table_details" in result:
                state["relevant_table_details"] = result.get("relevant_table_details") or []
            if "discovery_role_hints" in result:
                state["discovery_role_hints"] = result.get("discovery_role_hints") or {}

            state["discovery_result"] = {
                "candidates_count": len(relevant_tables),
                "relevant_tables": relevant_tables,
                "role_hints": state.get("discovery_role_hints"),
                "schema_snippet": schema_snippet,
            }

            # Loop diagnostics: detect when repeated discovery returns identical table sets
            previous_tables = (cached_payload.get("relevant_tables") or []) if cached_payload else []
            if previous_tables and relevant_tables == previous_tables:
                self._increment_loop_event(state, "discovery_reentered_same_tables")

            # Persist discovery cache for future reuse
            state["discovery_cache"] = {
                "fingerprint": fingerprint,
                "payload": {
                    "relevant_tables": relevant_tables,
                    "candidate_views": candidate_views,
                    "schema_snippet": schema_snippet,
                    "column_index": column_index,
                    "session_described_tables": state.get("session_described_tables"),
                    "relevant_table_details": state.get("relevant_table_details"),
                    "discovery_role_hints": state.get("discovery_role_hints"),
                    "discovery_result": state.get("discovery_result"),
                },
            }

            error = self._normalize_error_info(result.get("error_info"))
            if error:
                logger.error("🔍 [DISCOVERY] ❌ ERROR from discovery subgraph:")
                logger.error(f"🔍 [DISCOVERY]    type: {error.get('type')}")
                logger.error(f"🔍 [DISCOVERY]    message: {error.get('message')}")
                state["error_info"] = error

            # FIX: Fail loud if discovery returns zero candidates
            if not relevant_tables and not state.get("error_info"):
                error_msg = (
                    "Discovery could not find any relevant tables for this query. "
                    f"Keywords attempted: {keywords}. "
                    "This could be because: (1) keywords don't match any table names, "
                    "(2) Scout/Catalog is not initialized, or (3) MCP is unavailable."
                )
                logger.error(f"🔍 [DISCOVERY] ❌ FAIL LOUD: {error_msg}")
                state["error_info"] = {
                    "type": "DISCOVERY_NO_CANDIDATES",
                    "message": error_msg,
                    "keywords_attempted": keywords,
                    "tables_found": 0,
                }
            elif not relevant_tables and state.get("error_info"):
                logger.error(f"🔍 [DISCOVERY] ❌ ZERO CANDIDATES + PRIOR ERROR")
            else:
                logger.info(f"🔍 [DISCOVERY] ✅ DISCOVERY COMPLETE: {len(relevant_tables)} table(s) found")
                logger.info(f"🔍 [DISCOVERY] ✅ State is ready for JOIN_SQL node")
            debug_logger.agent_exit("discovery", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": f"Discovery agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"🔍 [DISCOVERY] ❌ EXCEPTION: {error['message']}")
            import traceback
            logger.error(f"🔍 [DISCOVERY] Traceback:\n{traceback.format_exc()}")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("discovery", before_state, dict(result_state))
            return result_state

    async def _join_sql_node(self, state: BaseState) -> BaseState:
        """
        Run JoinPlanAndSQLAgent subgraph.

        Plans joins (views-first strategy, FK relationships) and generates MSSQL.
        Output: join_plan, sql_query
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "join_sql")
        debug_logger.agent_entry("join_sql", dict(state))
        before_state = dict(state)

        logger.info("🔗 [JOIN_SQL] Starting SQL generation")

        # Check what we have from discovery
        relevant_tables = state.get("relevant_tables", [])
        intent = state.get("intent", {})
        role_hints = state.get("discovery_role_hints")

        logger.info(f"🔗 [JOIN_SQL] relevant_tables: {relevant_tables}")
        logger.info(f"🔗 [JOIN_SQL] intent: {intent}")
        logger.info(f"🔗 [JOIN_SQL] discovery_role_hints keys: {list(role_hints.keys()) if isinstance(role_hints, dict) else role_hints}")

        if not relevant_tables:
            logger.warning("🔗 [JOIN_SQL] No relevant tables found")
            state["sql_query"] = ""
            state["join_plan"] = {}
            debug_logger.agent_exit("join_sql", before_state, dict(state))
            return state

        # Build join inputs fingerprint for loop control
        join_inputs_fingerprint = self._build_join_inputs_fingerprint(state)
        last_join_fp = state.get("last_join_inputs_fingerprint")
        existing_sql = (state.get("sql_query") or "").strip()

        remaining_budget = self._get_remaining_llm_budget(state)
        safety_margin = state.get("llm_budget_safety_margin", 0) or 0

        # If inputs are unchanged and we already have SQL, reuse it instead of regenerating.
        if last_join_fp == join_inputs_fingerprint and existing_sql:
            self._increment_loop_event(state, "join_inputs_cache_hit")
            logger.info(
                "🔗 [JOIN_SQL] Inputs unchanged and SQL already present; "
                "reusing existing SQL and skipping join subgraph."
            )
            debug_logger.agent_exit("join_sql", before_state, dict(state))
            return state

        # Budget-aware short circuit: when near the hard budget and SQL already exists,
        # avoid additional LLM calls for SQL regeneration.
        if remaining_budget <= safety_margin and existing_sql:
            self._increment_loop_event(state, "join_budget_short_circuit")
            logger.warning(
                "🔗 [JOIN_SQL] Near LLM budget limit "
                f"(remaining={remaining_budget}, safety_margin={safety_margin}); "
                "reusing existing SQL and skipping regeneration."
            )
            debug_logger.agent_exit("join_sql", before_state, dict(state))
            return state

        # Delegate to JoinPlanAndSQLAgent subgraph for robust planning and SQL generation
        try:
            # LLM budget check
            state = self._check_llm_budget(state, "join_sql")
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                logger.warning("🔗 [JOIN_SQL] Exiting early due to LLM budget exhaustion")
                debug_logger.agent_exit("join_sql", before_state, dict(state))
                return state

            join_graph = self.join_sql_agent.build_subgraph()
            join_result = await join_graph.ainvoke(state)
            sql_query = join_result.get("sql_query", "")
            join_plan = join_result.get("join_plan", {})
            if not sql_query:
                raise ValueError("Join SQL agent returned no SQL")

            # Loop diagnostics: detect identical SQL being regenerated
            last_sql = state.get("last_sql_query") or ""
            if last_sql and sql_query.strip() == str(last_sql).strip():
                self._increment_loop_event(state, "join_sql_regenerated_same_sql")

            state["sql_query"] = sql_query
            state["join_plan"] = join_plan
            state["last_sql_query"] = sql_query
            state["last_join_plan"] = join_plan
            state["last_join_inputs_fingerprint"] = join_inputs_fingerprint
            logger.info(f"🔗 [JOIN_SQL] Generated SQL (agent): {sql_query}")
        except Exception as e:
            logger.error(f"🔗 [JOIN_SQL] Join SQL agent failed: {e}", exc_info=True)
            # On failure, set empty SQL and let validate_sql node handle the error
            state["sql_query"] = ""
            state["join_plan"] = {}
            state["error_info"] = {"type": "join_sql_generation_failed", "message": str(e)}

        logger.info("🔗 [JOIN_SQL] SQL generation complete")
        debug_logger.agent_exit("join_sql", before_state, dict(state))
        return state

    async def _validate_sql_node(self, state: BaseState) -> BaseState:
        """
        Run SQLValidatorAgent for pre-execution validation and repair.

        Validates SQL syntax, MSSQL dialect, table/column existence, and repairs if needed.
        Output: validation_result, sql_query (potentially repaired)
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "validate_sql")
        debug_logger.agent_entry("validate_sql", dict(state))
        before_state = dict(state)

        logger.info("🔍 [VALIDATE_SQL] Starting SQL validation and repair")

        # Check if we have SQL to validate
        sql_query = state.get("sql_query", "")
        if not sql_query:
            logger.warning("🔍 [VALIDATE_SQL] No SQL query to validate")
            state["validation_result"] = {"is_valid": False, "error_type": "no_sql"}
            debug_logger.agent_exit("validate_sql", before_state, dict(state))
            return state

        # Phase 2b: increment validation attempt counter
        current_validation_attempts = state.get("validation_attempt_count", 0)
        state["validation_attempt_count"] = current_validation_attempts + 1

        # Run SQLValidatorAgent
        try:
            # LLM budget check
            state = self._check_llm_budget(state, "validate_sql")
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                logger.warning("🔍 [VALIDATE_SQL] Exiting early due to LLM budget exhaustion")
                debug_logger.agent_exit("validate_sql", before_state, dict(state))
                return state

            validation_state = await self.sql_validator_agent(state)
            state.update(validation_state)

            validation_result = state.get("validation_result", {})
            is_valid = validation_result.get("is_valid", False)
            error_type = validation_result.get("error_type", "unknown")

            # Phase 4: Normalize tables_used from SQL validation into canonical form
            # so downstream guardrails and diagnostics rely on a single naming scheme.
            try:
                raw_tables_used = validation_result.get("tables_used") or []
                dialect = state.get("db_dialect", self.db_dialect)
                default_schema = state.get("db_default_schema", self.db_default_schema)
                canonical_tables: List[str] = []
                base_tables: List[str] = []
                for raw in raw_tables_used:
                    if not raw:
                        continue
                    canonical = self._canonical_table_name(
                        str(raw),
                        dialect=dialect,
                        default_schema=default_schema,
                    )
                    canonical_tables.append(canonical)
                    base_tables.append(canonical.split(".")[-1])
                state["validator_tables_used"] = canonical_tables
                state["validator_tables_used_base"] = base_tables
                validation_result["tables_used_canonical"] = canonical_tables
                validation_result["tables_used_base"] = base_tables
                state["validation_result"] = validation_result
            except Exception as meta_exc:
                logger.debug(
                    f"🔍 [VALIDATE_SQL] Unable to normalize tables_used metadata: {meta_exc}"
                )

            # Orchestrator-level required-relations guardrail: enforce that tables
            # implied by KPI expressions are present in the final SQL, using
            # validator-derived tables_used metadata only (no regex).
            if is_valid:
                guardrail_error = evaluate_required_relations(state)
                if guardrail_error:
                    merge_error_info(state, guardrail_error)
                    logger.warning(
                        "🔍 [VALIDATE_SQL] Required-relations guardrail triggered: %s",
                        guardrail_error.get("type"),
                    )
                    debug_logger.agent_exit("validate_sql", before_state, dict(state))
                    return state

            if is_valid:
                logger.info("🔍 [VALIDATE_SQL] ✅ SQL validation passed")
            else:
                logger.warning(f"🔍 [VALIDATE_SQL] ❌ SQL validation failed: {error_type}")

                # Check if repair was attempted
                repair_attempts = state.get("repair_attempts", 0)
                if repair_attempts > 0:
                    logger.info(f"🔍 [VALIDATE_SQL] 🔧 Repair attempted {repair_attempts} time(s)")
                    # Check if repair succeeded
                    if validation_result.get("is_valid", False):
                        logger.info("🔍 [VALIDATE_SQL] ✅ Repair successful")
                    else:
                        logger.warning("🔍 [VALIDATE_SQL] ❌ Repair unsuccessful - proceeding with original SQL")

        except Exception as e:
            logger.error(f"🔍 [VALIDATE_SQL] Validation failed: {e}")
            state["validation_result"] = {
                "is_valid": False,
                "error_type": "validation_error",
                "error_message": str(e)
            }

        logger.info("🔍 [VALIDATE_SQL] Validation complete")
        debug_logger.agent_exit("validate_sql", before_state, dict(state))
        return state

    def _qualify_table_name(self, table_name: str) -> str:
        """
        Ensure table name is schema-qualified in a dialect-aware way.

        - Postgres: <schema>.<table> (schema from db_default_schema, default "public")
        - MSSQL: <database>.<schema>.<table> (database from env, default "OLLuisiDiener")
        - Already-qualified names are returned as-is.
        """
        raw = (table_name or "").strip()
        if not raw:
            return raw
        # If the name is already qualified (schema.table or db.schema.table), leave it alone.
        if "." in raw:
            return raw

        dialect = (getattr(self, "db_dialect", "") or "").lower()
        default_schema = (getattr(self, "db_default_schema", "") or "").strip() or (
            "public" if dialect == "postgres" else "dbo"
        )

        if dialect == "postgres":
            return f"{default_schema}.{raw}"

        if dialect == "mssql":
            db_name = (os.getenv("DB_MSSQL_DATABASE") or "").strip() or "OLLuisiDiener"
            return f"{db_name}.{default_schema}.{raw}"

        # Fallback: use schema.table form
        return f"{default_schema}.{raw}"

    def _select_best_table_or_view_for_query(self, tables, views, intent: Dict[str, Any]) -> str:
        """
        Select the most appropriate table OR view for the query based on intent.

        Phase 3: Views-first approach - prioritize views that contain pre-joined business data
        over raw tables that would require complex joins.
        """
        # Get query characteristics
        primary_entities = intent.get("primary_entities", [])
        keywords = intent.get("keywords_for_discovery", [])
        metrics = intent.get("metrics", [])
        operations = intent.get("operation", [])

        logger.info(f"🎯 [TABLE_SELECTION] Views-first selection for query")
        logger.info(f"🎯 [TABLE_SELECTION]   entities: {primary_entities}")
        logger.info(f"🎯 [TABLE_SELECTION]   keywords: {keywords}")
        logger.info(f"🎯 [TABLE_SELECTION]   metrics: {metrics}")
        logger.info(f"🎯 [TABLE_SELECTION]   available tables: {len(tables) if tables else 0}")
        logger.info(f"🎯 [TABLE_SELECTION]   available views: {len(views) if views else 0}")

        # Phase 3: VIEWS-FIRST APPROACH
        # 1. First, evaluate all views by business relevance
        if views:
            best_view = self._select_best_view_for_query(views, intent)
            if best_view:
                logger.info(f"🎯 [TABLE_SELECTION] ✅ Selected VIEW: {best_view}")
                return best_view

        # 2. Fallback to tables if no suitable views found
        logger.info(f"🎯 [TABLE_SELECTION] No suitable views found, evaluating tables...")
        best_table = self._select_best_table_for_query(tables, intent)
        if best_table:
            logger.info(f"🎯 [TABLE_SELECTION] ✅ Selected TABLE: {best_table}")
            return best_table

        logger.warning(f"🎯 [TABLE_SELECTION] ❌ No suitable table or view found")
        return ""

    def _select_best_view_for_query(self, views, intent: Dict[str, Any]) -> str:
        """
        Select the best view for the query using simple heuristics.
        
        NOTE: Complex ranking (ViewsRanker) lives on MCP server (Windows).
        Here we do lightweight client-side selection based on name/entity matching.
        """
        if not views:
            return ""

        primary_entities = intent.get("primary_entities", [])
        keywords = intent.get("keywords_for_discovery", [])

        # Simple heuristic: prefer views whose name matches primary entities or keywords
        search_terms = (primary_entities + keywords) if (primary_entities or keywords) else []
        search_terms_lower = [s.lower() for s in search_terms]

        best_view = None
        best_score = 0

        for view in views:
            if not isinstance(view, dict):
                continue

            view_name = (view.get("full_name") or view.get("name") or "").lower()
            if not view_name:
                continue

            # Score: count how many search terms appear in view name
            score = sum(1 for term in search_terms_lower if term in view_name)

            if score > best_score:
                best_score = score
                best_view = view.get("full_name") or view.get("name")

        if best_view and best_score > 0:
            logger.info(f"👁️ [VIEW_SELECTION] Selected view '{best_view}' (score: {best_score})")
            return best_view

        logger.debug(f"👁️ [VIEW_SELECTION] No views matched primary entities/keywords")
        return ""

    def _select_best_table_for_query(self, tables, intent: Dict[str, Any]) -> str:
        """Select the most appropriate table for the query based on intent (fallback when no views available)."""
        if not tables:
            return ""

        # Get query characteristics
        primary_entities = intent.get("primary_entities", [])
        keywords = intent.get("keywords_for_discovery", [])
        metrics = intent.get("metrics", [])

        # Handle both list of dicts and list of strings
        scored_tables = []
        for table in tables:
            reasons = []  # collect selection reasons for debugging
            if isinstance(table, dict):
                table_name = table.get("full_name", table.get("name", ""))
                base_score = table.get("relevance_score", 0)
            elif isinstance(table, str):
                table_name = table
                base_score = 0.5  # Default score for string tables
            else:
                continue

            score = base_score
            safe_table = table if isinstance(table, dict) else {}

            # Bonus for tables that match entity keywords
            table_lower = table_name.lower()
            for entity in primary_entities:
                if entity.lower() in table_lower:
                    score += 0.5

            for keyword in keywords:
                if keyword.lower() in table_lower:
                    score += 0.3

            # Generic preference based on available metadata patterns
            # Works even with incomplete metadata from MCP server

            # Boost tables with transaction-like characteristics for transaction queries
            if any(kw in ["sales", "revenue", "order", "transaction", "sale"] for kw in keywords):
                # Look for transaction indicators in table name
                if any(term in table_lower for term in ["order", "transaction", "sale", "invoice", "beleg", "rechnung"]):
                    score += 0.8
                    reasons.append("Transaction-related table name")
                # Fallback to metadata if available
                elif safe_table.get("fk_count", 0) >= 2:
                    score += 0.6
                    reasons.append("Transaction-like metadata (multiple FKs)")

            # Boost tables with product-like characteristics for product queries
            if any(kw in ["product", "item", "artikel"] for kw in keywords):
                # Look for product indicators in table name
                if any(term in table_lower for term in ["product", "item", "artikel", "produkt"]):
                    score += 0.7
                    reasons.append("Product-related table name")
                # Fallback to metadata if available
                elif safe_table.get("column_count", 0) >= 5:
                    score += 0.5
                    reasons.append("Product-like metadata (multiple columns)")

            # Boost tables with customer-like characteristics for customer queries
            if any(kw in ["customer", "kunde", "client"] for kw in keywords):
                # Look for customer indicators in table name
                if any(term in table_lower for term in ["customer", "kunde", "client", "kunden"]):
                    score += 0.6
                    reasons.append("Customer-related table name")
                # Fallback to basic scoring
                else:
                    score += 0.3
                    reasons.append("Potential customer table")

            scored_tables.append((table_name, score))

        # Sort by score and return best table
        scored_tables.sort(key=lambda x: x[1], reverse=True)
        best_table = scored_tables[0][0]

        logger.info(f"🔗 [TABLE_SELECTION] Selected {best_table} (score: {scored_tables[0][1]:.3f})")
        for table_name, score in scored_tables[:5]:  # Log top 5
            logger.debug(f"🔗 [TABLE_SELECTION]   {table_name}: {score:.3f}")

        return best_table

    async def _try_join_planning(self, relevant_tables: List[Dict[str, Any]], intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Phase 5: Try join planning as fallback when no suitable single table/view is found.

        NOTE: Join planning should be handled by MCP server, not LangGraph client.
        For now, disabled to avoid direct Scout catalog access from client.
        """
        # TODO: Implement join planning through MCP server API calls
        logger.debug("🔗 [JOIN_PLANNER] Join planning disabled - should be handled by MCP server")
        return None

    async def _generate_sql_from_join_plan(self, join_plan: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """
        Phase 5: Generate SQL from join plan.

        NOTE: SQL generation from join plans should be handled by MCP server.
        For now, return empty string to disable complex joins.
        """
        logger.debug("🔗 [JOIN_SQL] Join plan SQL generation disabled - should be handled by MCP server")
        return ""

    async def _exec_recovery_node(self, state: BaseState) -> BaseState:
        """
        Run ExecAndRecoveryAgent subgraph.
        
        Executes query safely (row caps, timeouts) and recovers from errors via LLM repair.
        Output: exec_result, error_info, retry_count
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "exec_recovery")
        debug_logger.agent_entry("exec_recovery", dict(state))
        before_state = dict(state)
        
        logger.info("⚡ [EXEC_RECOVERY] ════════════════════════════════════════")
        logger.info("⚡ [EXEC_RECOVERY] CRITICAL: NODE EXECUTION STARTED!")
        logger.info("⚡ [EXEC_RECOVERY] If this log doesn't appear, workflow stopped before this node")
        logger.info("⚡ [EXEC_RECOVERY] ════════════════════════════════════════")
        
        # SURGICAL DEBUG: Show input state
        logger.info("⚡ [EXEC_RECOVERY] ━━━ INPUT STATE ━━━")
        logger.info(f"⚡ [EXEC_RECOVERY] Input keys: {list(state.keys())}")
        
        sql_query = state.get("sql_query", "")
        error_info = state.get("error_info")
        
        logger.info(f"⚡ [EXEC_RECOVERY] sql_query: {len(sql_query)} chars")
        logger.info(f"⚡ [EXEC_RECOVERY] prior error_info: {error_info}")

        # Check for prior errors
        if error_info:
            logger.warning("⚡ [EXEC_RECOVERY] ⚠️  Prior error detected, will attempt recovery")

        # Global execution budget: stop after too many exec attempts
        exec_attempt = state.get("exec_attempt_count", 0)
        max_exec = state.get("max_exec_attempts", 6)
        if exec_attempt >= max_exec:
            logger.warning(
                "⚡ [EXEC_RECOVERY] Global execution budget exceeded "
                f"({exec_attempt}/{max_exec}), skipping exec_recovery and routing to answer"
            )
            merge_error_info(
                state,
                {
                    "type": "MAX_EXEC_ATTEMPTS_EXCEEDED",
                    "message": (
                        "The system attempted to execute or repair the query multiple times "
                        "but could not complete execution safely."
                    ),
                },
            )
            debug_logger.agent_exit("exec_recovery", before_state, dict(state))
            return state

        # Increment execution attempt count
        state["exec_attempt_count"] = exec_attempt + 1

        # Phase 2b: Track exec_recovery-specific attempts (separate from exec_attempt_count)
        exec_recovery_attempt = state.get("exec_recovery_attempt_count", 0)
        state["exec_recovery_attempt_count"] = exec_recovery_attempt + 1

        try:
            # LLM budget check (ExecAndRecoveryAgent uses LLM for repair/simplification)
            state = self._check_llm_budget(state, "exec_recovery")
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                logger.warning("⚡ [EXEC_RECOVERY] Exiting early due to LLM budget exhaustion")
                debug_logger.agent_exit("exec_recovery", before_state, dict(state))
                return state

            # Build and run exec_recovery subgraph
            exec_recovery_graph = self.exec_recovery_agent.build_subgraph()

            # Invoke with input state using async API
            logger.info("⚡ [EXEC_RECOVERY] Invoking exec_recovery subgraph...")
            logger.info("⚡ [EXEC_RECOVERY] This will run: execute_query → check_result → (repair_sql → retry_query → check_retry_result → (simplify_query → final_retry) → prepare_error) → END")

            # DEBUG: Add detailed error handling
            logger.info("⚡ [EXEC_RECOVERY] 🚀 About to call exec_recovery_graph.ainvoke()...")
            try:
                result = await exec_recovery_graph.ainvoke(state)
                logger.info("⚡ [EXEC_RECOVERY] ✅ exec_recovery subgraph completed successfully")
                logger.info(f"⚡ [EXEC_RECOVERY]   Result keys: {list(result.keys()) if result else 'None'}")
                if result:
                    exec_result = result.get("exec_result")
                    logger.info(f"⚡ [EXEC_RECOVERY]   exec_result: {exec_result} (type: {type(exec_result)})")
                    if exec_result and isinstance(exec_result, dict):
                        logger.info(f"⚡ [EXEC_RECOVERY]   exec_result.ok: {exec_result.get('ok')}")
                        logger.info(f"⚡ [EXEC_RECOVERY]   exec_result.error: {exec_result.get('error')}")
                        logger.info(f"⚡ [EXEC_RECOVERY]   exec_result.row_count: {exec_result.get('row_count')}")
            except Exception as subgraph_error:
                logger.error(f"⚡ [EXEC_RECOVERY] ❌ SUBGRAPH CRASHED: {subgraph_error}")
                logger.error(f"⚡ [EXEC_RECOVERY]   Error type: {type(subgraph_error).__name__}")
                import traceback
                logger.error(f"⚡ [EXEC_RECOVERY]   Traceback:\n{traceback.format_exc()}")
                raise subgraph_error

            # SURGICAL DEBUG: Show output state
            logger.info("⚡ [EXEC_RECOVERY] ━━━ OUTPUT STATE ━━━")
            logger.info(f"⚡ [EXEC_RECOVERY] Output keys: {list(result.keys())}")

            # Extract outputs
            exec_result_raw = result.get("exec_result")
            exec_result = self._coerce_exec_result(exec_result_raw)
            logger.info(
                "⚡ [EXEC_RECOVERY] Setting state['exec_result'] (normalized) keys: %s",
                list(exec_result.keys()),
            )
            state["exec_result"] = exec_result
            state["sql_query"] = result.get("sql_query", state.get("sql_query", ""))
            state["retry_count"] = result.get("retry_count", 0)

            error = self._normalize_error_info(result.get("error_info"))
            if error:
                logger.error(f"⚡ [EXEC_RECOVERY] Error from exec_recovery: {error}")
                state["error_info"] = error

            if exec_result.get("ok"):
                logger.info(
                    f"⚡ [EXEC_RECOVERY] ✅ EXECUTION SUCCESS: "
                    f"{exec_result.get('row_count', 0)} rows in {exec_result.get('execution_time_ms', 0)}ms"
                )
                # Ensure downstream answer formatting does not take error/clarify paths
                state["error_info"] = None
                state.setdefault("intent", {})["operation"] = "query"
                # Persist last successful result for interpretation follow-ups
                sources = []
                try:
                    os.makedirs("data", exist_ok=True)
                    # Derive source tables from join_plan/SQL
                    try:
                        jp = state.get("join_plan", {}) or {}
                        if isinstance(jp, dict):
                            pt = jp.get("primary_table")
                            if pt:
                                sources.append(pt)
                            for j in jp.get("joins", []) or []:
                                if isinstance(j, dict) and j.get("table"):
                                    sources.append(j.get("table"))
                    except Exception:
                        pass
                    cache = {
                        "exec_result": exec_result,
                        "sql_query": state.get("sql_query", ""),
                        "sources": list(dict.fromkeys([s for s in sources if s]))
                    }
                    with open(os.path.join("data", "last_exec_result.json"), "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False)
                    logger.info("⚡ [EXEC_RECOVERY] Cached last_exec_result for interpretation agent")
                except Exception as e:
                    logger.warning(f"⚡ [EXEC_RECOVERY] Failed to cache last_exec_result: {e}")
                finally:
                    self._previous_exec_cache = {
                        "exec_result": exec_result,
                        "sql_query": state.get("sql_query", ""),
                        "sources": list(dict.fromkeys([s for s in sources if s])),
                    }
            else:
                logger.warning(f"⚡ [EXEC_RECOVERY] ❌ Execution failed, error_info set for answer agent")

            logger.info(f"⚡ [EXEC_RECOVERY] ✅ State ready for ANSWER node")
            debug_logger.agent_exit("exec_recovery", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "EXEC_ERROR",
                "message": f"Execution agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("exec_recovery", before_state, dict(result_state))
            return result_state

    async def _answer_node(self, state: BaseState) -> BaseState:
        """
        Run AnswerAgent subgraph (general result formatting).
        
        Formats successful results, errors, or clarification requests as natural language.
        Output: final_response
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "answer")
        debug_logger.agent_entry("answer", dict(state))
        before_state = dict(state)
        
        logger.info("✨ Running AnswerAgent...")

        try:
            # DEBUG: Log what we received
            user_input = state.get("user_input", "")
            exec_result_raw = state.get("exec_result")
            logger.info(f"✨ [ANSWER] exec_result_raw from state: {exec_result_raw} (type: {type(exec_result_raw)})")
            exec_result = self._coerce_exec_result(exec_result_raw)
            state["exec_result"] = exec_result
            logger.info(f"✨ [ANSWER] exec_result normalized: {exec_result}")
            error_info = state.get("error_info")
            logger.info(f"✨ [ANSWER] exec_result present: {bool(exec_result)}")
            logger.info(f"✨ [ANSWER] exec_result type: {type(exec_result)}")
            logger.info(f"✨ [ANSWER] exec_result keys: {list(exec_result.keys()) if isinstance(exec_result, dict) else 'Not a dict'}")
            logger.info(f"✨ [ANSWER] exec_result.ok: {exec_result.get('ok') if isinstance(exec_result, dict) else 'Not a dict'}")
            logger.info(f"✨ [ANSWER] error_info: {error_info}")
            logger.info(f"✨ [ANSWER] intent.operation: {state.get('intent', {}).get('operation')}")

            # HIGHEST PRIORITY: Handle clarification requests from intent parsing
            intent = state.get("intent", {}) or {}
            needs_clarification = intent.get("needs_clarification", False)
            if needs_clarification:
                clarification_question = intent.get("clarification_question", "Could you please clarify your request?")
                suggested_options = intent.get("suggested_options", [])
                ambiguity_reason = intent.get("ambiguity_reason", "Your query needs clarification")

                logger.info(f"✨ [ANSWER] 📝 Handling clarification request: {clarification_question}")

                response_parts = [
                    f"I need a bit more information to help you effectively. {clarification_question}",
                    f"\n\nReason: {ambiguity_reason}"
                ]

                if suggested_options:
                    response_parts.append(f"\n\nHere are some options to consider:")
                    for i, option in enumerate(suggested_options, 1):
                        response_parts.append(f"{i}. {option}")

                state["final_response"] = "".join(response_parts)
                logger.info(f"✨ [ANSWER] ✅ Clarification response generated")
                debug_logger.agent_exit("answer", before_state, dict(state))
                return state

            # Determine preferred answer mode from config/state
            preferred_mode_raw = (state.get("answer_mode") or self.default_answer_mode or "llm_first")
            preferred_mode = str(preferred_mode_raw).strip().lower()
            prefer_deterministic = preferred_mode in {
                "deterministic_from_data",
                "deterministic",
                "data_first",
                "data_only",
            }

            # Deterministic data-based fallback when execution succeeded
            operation = intent.get("operation", "query")
            is_data_query = operation == "query"
            exec_ok = exec_result.get("ok", False) if isinstance(exec_result, dict) else False
            row_count = exec_result.get("row_count") if isinstance(exec_result, dict) else None
            remaining_budget = self._get_remaining_llm_budget(state)
            safety_margin = state.get("llm_budget_safety_margin", 0) or 0
            budget_error_type = (error_info or {}).get("type") if isinstance(error_info, dict) else None

            if is_data_query and exec_ok and (row_count is not None and row_count > 0) and (
                prefer_deterministic
                or remaining_budget <= safety_margin
                or budget_error_type == "LLM_BUDGET_EXCEEDED"
            ):
                logger.info(
                    "✨ [ANSWER] Using deterministic data-based answer "
                    f"(row_count={row_count}, remaining_budget={remaining_budget}, safety_margin={safety_margin})"
                )
                # Render deterministic answer from data without consuming additional LLM calls
                deterministic_text = await _format_execution_results(exec_result, intent, user_input)
                state["final_response"] = deterministic_text
                state["answer_mode"] = "deterministic_from_data"

                # If there was a budget error, mark it as degraded-but-successful answer
                if budget_error_type == "LLM_BUDGET_EXCEEDED":
                    merge_error_info(
                        state,
                        {
                            "type": "LLM_BUDGET_EXCEEDED_DEGRADED_ANSWER",
                            "message": "Returned a data-based answer without additional LLM formatting due to budget limits.",
                        },
                    )

                debug_logger.agent_exit("answer", before_state, dict(state))
                return state

            # FIX 2: HARD GROUNDING GATE - Prevent ungrounded answers
            # Check if we have meaningful execution results for a data query
            if is_data_query:
                exec_result = state.get("exec_result") or {}
                exec_ok = exec_result.get("ok", False) if isinstance(exec_result, dict) else False
                exec_error = exec_result.get("error") if isinstance(exec_result, dict) else None
                sql_query = state.get("sql_query", "").strip()
                
                # Hard gate: if no successful SQL execution for a data query, fail with structured error
                if not exec_ok or not sql_query or exec_error:
                    logger.warning("✨ [ANSWER] ⚠️  GROUNDING GATE ACTIVATED: Data query without valid execution")
                    logger.warning("✨   exec_ok=%s, has_sql=%s, exec_error=%s", exec_ok, bool(sql_query), exec_error)

                    existing_error = state.get("error_info") or {}
                    existing_type = existing_error.get("type") if isinstance(existing_error, dict) else None
                    existing_message = existing_error.get("message") if isinstance(existing_error, dict) else None
                    existing_suggestion = existing_error.get("suggestion") if isinstance(existing_error, dict) else None

                    # Prefer a domain-aware diagnostic when we already have a structured error
                    if isinstance(existing_error, dict) and existing_type:
                        logger.warning("✨ [ANSWER] Using existing structured error_info for grounding gate: %s", existing_type)
                        message_bits: List[str] = []
                        if existing_message:
                            message_bits.append(existing_message)
                        else:
                            message_bits.append("A structural issue in the query or schema prevented a safe answer.")
                        if existing_suggestion:
                            message_bits.append(existing_suggestion)
                        else:
                            message_bits.append(
                                "You can often fix this by narrowing the question or specifying different tables or metrics."
                            )

                        state["final_response"] = " ".join(message_bits)
                        state["error_info"] = existing_error
                        debug_logger.agent_exit("answer", before_state, dict(state))
                        return state

                    # Otherwise, fall back to a generic but safe diagnostic
                    error_msg = exec_error or "Query execution failed or produced no valid SQL"
                    state["error_info"] = {
                        "type": "UNGROUNDED_RESPONSE_PREVENTED",
                        "message": f"Cannot answer this query: {error_msg}. Please try a more specific question.",
                    }
                    state["final_response"] = (
                        "I wasn't able to retrieve the information needed to answer your question. "
                        "This could be because:\n"
                        "• The query was too vague\n"
                        "• The requested data doesn't exist in the database\n"
                        "• The relevant tables couldn't be identified\n\n"
                        "Please try rephrasing your question with more specific details."
                    )
                    logger.warning("✨ [ANSWER] ✅ Ungrounded response prevented, generic diagnostic returned")
                    debug_logger.agent_exit("answer", before_state, dict(state))
                    return state

            # Fast return: if we have a successful exec_result, optionally synthesize a concise count answer
            if isinstance(exec_result, dict) and exec_result.get("ok", False):
                intent = state.get("intent", {})
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                wants_count = "count" in metrics

                if not wants_count:
                    logger.info("✨ [ANSWER] Skipping count extraction (intent is not COUNT); delegating to AnswerAgent")
                    # Fall back to AnswerAgent subgraph for non-count queries
                    answer_graph = self.answer_agent.build_subgraph()
                    result = await answer_graph.ainvoke(state)
                    state["final_response"] = result.get("final_response", "No response generated")
                    logger.info("✅ Answer formatted by AnswerAgent")
                    debug_logger.agent_exit("answer", before_state, dict(state))
                    return state

                logger.info("✨ [ANSWER] ✅ exec_result is successful, trying to extract count...")

                # Try to extract a scalar count if present in rows
                count_value = None
                rows = exec_result.get("data") or []
                logger.info(f"✨ [ANSWER] rows/data: {rows}")

                if isinstance(rows, list) and rows:
                    first = rows[0]
                    logger.info(f"✨ [ANSWER] first row: {first}")
                    if isinstance(first, dict):
                        # Look for common count keys
                        for key in ["total_count", "count", "cnt", "total"]:
                            if key in first and isinstance(first[key], (int, float)):
                                count_value = int(first[key]) if isinstance(first[key], (int, float)) else None
                                logger.info(f"✨ [ANSWER] Found count key '{key}': {count_value}")
                                break
                        # Fallback: any single numeric value
                        if count_value is None:
                            for v in first.values():
                                if isinstance(v, (int, float)):
                                    count_value = int(v)
                                    logger.info(f"✨ [ANSWER] Found numeric value: {count_value}")
                                    break

                # Zero-result UX: if no rows, provide structured explanation and next steps
                if (exec_result.get("row_count") == 0) or (not rows):
                    logger.info("✨ [ANSWER] Zero rows returned; preparing structured zero-result message")
                    # Gather context
                    intent = state.get("intent", {})
                    time_window = intent.get("time_window")
                    join_plan = state.get("join_plan", {})
                    sql_query = state.get("sql_query", "")
                    primary = join_plan.get("primary_table") or (intent.get("selected_table") if isinstance(intent, dict) else None)
                    sources = []
                    if join_plan:
                        if join_plan.get("strategy") == "view":
                            sources = [join_plan.get("view_name") or primary]
                        elif join_plan.get("strategy") in ("joins", "direct"):
                            sources = [primary] + [j.get("table") for j in join_plan.get("joins", []) if isinstance(j, dict) and j.get("table")]
                    # Build message
                    scope_bits = []
                    if time_window:
                        scope_bits.append(f"time window: {time_window}")
                    scope_text = ", ".join(scope_bits) if scope_bits else "no explicit time window"
                    plan_bits = []
                    if sources:
                        plan_bits.append("sources: " + ", ".join([s for s in sources if s]))
                    if join_plan.get("joins"):
                        keys = [j.get("on") for j in join_plan.get("joins", []) if isinstance(j, dict) and j.get("on")]
                        if keys:
                            plan_bits.append("join keys: " + "; ".join(keys))
                    plan_text = "; ".join(plan_bits) if plan_bits else "single-source plan"
                    suggestions = [
                        "expand the time range (e.g., last quarter or 12 months)",
                        "try an alternative date column (e.g., Rechnungsdatum, Buchungsdatum)",
                        "consider a business view if available (e.g., vw_* Umsatz)",
                    ]
                    state["final_response"] = (
                        "No rows matched the current plan.\n"
                        f"- Scope: {scope_text}\n"
                        f"- Plan: {plan_text}\n"
                        f"- SQL preview: {sql_query[:180]}...\n"
                        "- Next steps: " + "; ".join(suggestions)
                    )
                    logger.info("✨ [ANSWER] ✅ Zero-result explanation generated")
                    debug_logger.agent_exit("answer", before_state, dict(state))
                    return state

                if count_value is not None:
                    # Provide a contextual response based on the query and table used
                    intent = state.get("intent", {})
                    primary_entities = intent.get("primary_entities", ["records"])
                    entity_name = primary_entities[0] if primary_entities else "records"
                    sql_query = state.get("sql_query", "")
                    table_used = "unknown"

                    # Extract table name from SQL
                    if "FROM" in sql_query.upper():
                        from_part = sql_query.upper().split("FROM")[1].split()[0]
                        table_used = from_part.replace("DBO.", "").replace("[", "").replace("]", "")

                    # Provide contextual response based on query and table characteristics
                    # Generic response that works with any database

                    query_lower = user_input.lower()
                    table_lower = table_used.lower()

                    # Determine query type from keywords
                    if any(word in query_lower for word in ["sales", "revenue", "transaction", "order"]):
                        query_type = "sales"
                    elif any(word in query_lower for word in ["customer", "client", "kunde"]):
                        query_type = "customer"
                    elif any(word in query_lower for word in ["product", "item", "artikel"]):
                        query_type = "product"
                    else:
                        query_type = "general"

                    # Generate appropriate response based on query type and table
                    if query_type == "sales":
                        base_text = f"I analyzed the {table_used} table and found {count_value:,} records. For sales data, you might need to look at transaction or order tables."
                    elif query_type == "customer":
                        base_text = f"There are {count_value:,} customer records in the database."
                    elif query_type == "product":
                        base_text = f"The {table_used} table contains {count_value:,} product/item records."
                    else:
                        base_text = f"The {table_used} table contains {count_value:,} records."

                    # Append compact rows appendix (first 5) for transparency
                    appendix = ""
                    try:
                        preview_rows = rows[:5] if isinstance(rows, list) else []
                        if preview_rows:
                            import json as _json
                            appendix = "\n\n" + f"Tables: {table_used}\n" + "```json\n" + _json.dumps(preview_rows) + "\n```"
                    except Exception:
                        appendix = ""

                    state["final_response"] = base_text + appendix

                    logger.info(f"✨ [ANSWER] ✅ Answer synthesized: '{state['final_response']}'")
                    debug_logger.agent_exit("answer", before_state, dict(state))
                    return state
                else:
                    logger.warning("✨ [ANSWER] ❌ Could not extract count from exec_result")
            else:
                logger.warning("✨ [ANSWER] ❌ exec_result not successful or missing")

            # If we get here, fall back to AnswerAgent subgraph (LLM-based formatting)

            # LLM budget check (AnswerAgent uses LLM for formatting)
            state = self._check_llm_budget(state, "answer")

            # If budget is now exhausted at the answer stage, prefer a deterministic
            # data-based answer when we already have executed SQL and rows.
            budget_error = state.get("error_info") or {}
            if isinstance(budget_error, dict) and budget_error.get("type") == "LLM_BUDGET_EXCEEDED":
                refreshed_exec = state.get("exec_result") or {}
                exec_ok_after_budget = refreshed_exec.get("ok", False) if isinstance(refreshed_exec, dict) else False
                row_count_after_budget = refreshed_exec.get("row_count") if isinstance(refreshed_exec, dict) else None

                if is_data_query and exec_ok_after_budget and (row_count_after_budget is not None and row_count_after_budget > 0):
                    logger.warning(
                        "✨ [ANSWER] LLM budget exhausted at answer stage; returning deterministic data-based answer"
                    )
                    deterministic_text = await _format_execution_results(refreshed_exec, intent, user_input)
                    state["final_response"] = deterministic_text
                    state["answer_mode"] = "deterministic_from_data"
                    merge_error_info(
                        state,
                        {
                            "type": "LLM_BUDGET_EXCEEDED_DEGRADED_ANSWER",
                            "message": "Returned a data-based answer without additional LLM formatting due to budget limits.",
                        },
                    )
                    debug_logger.agent_exit("answer", before_state, dict(state))
                    return state

            # If budget exhaustion turned the intent into a clarification request, return a clear diagnostic
            if state.get("error_info") and state.get("intent", {}).get("needs_clarification"):
                # Global LLM budget exhausted – provide a deterministic, user-friendly message
                intent = state.get("intent") or {}
                error_info = state.get("error_info") or {}
                err_type = str(error_info.get("type", "LLM_BUDGET_EXCEEDED"))
                stage = error_info.get("stage") or "answer"
                total_calls = error_info.get("total_llm_calls")

                clarification_question = intent.get(
                    "clarification_question",
                    "Could you narrow down the scope of your question?",
                )
                ambiguity_reason = intent.get(
                    "ambiguity_reason",
                    "LLM call budget exceeded while trying to answer this question.",
                )

                details: List[str] = []
                if stage:
                    details.append(f"stage: {stage}")
                if isinstance(total_calls, int):
                    details.append(f"model calls used: {total_calls}")
                detail_suffix = f" ({', '.join(details)})" if details else ""

                state["final_response"] = (
                    "I couldn't finish processing your request because the model call "
                    "budget for this query was reached"
                    f"{detail_suffix}. "
                    f"Reason: {ambiguity_reason} "
                    f"Suggestion: {clarification_question}"
                )

                logger.warning(
                    "✨ [ANSWER] Exiting early due to LLM budget exhaustion (%s)%s",
                    err_type,
                    f" at {stage}" if stage else "",
                )
                debug_logger.agent_exit("answer", before_state, dict(state))
                return state

            # Build and run answer subgraph
            answer_graph = self.answer_agent.build_subgraph()

            # Invoke with input state using async API
            result = await answer_graph.ainvoke(state)

            # Extract outputs
            state["final_response"] = result.get("final_response", "No response generated")
            if "clarify" in result:
                state["clarify"] = result.get("clarify")
            if result.get("clarification_question"):
                state["clarification_question"] = result.get("clarification_question")

            logger.info("✅ Answer formatted")
            debug_logger.agent_exit("answer", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "ANSWER_ERROR",
                "message": f"Answer agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            state["final_response"] = f"Error formatting response: {str(e)}"
            debug_logger.agent_exit("answer", before_state, dict(state))
            return state

    # ============= Special operation nodes =============

    async def _answer_schema_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for schema explanation."""
        logger.info("📚 Answering schema question...")

        # Set operation to schema_query so AnswerAgent knows to explain
        state.setdefault("intent", {})["operation"] = "schema_query"

        # Run answer agent
        return await self._answer_node(state)

    async def _answer_health_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for health check."""
        logger.info("🏥 Answering health check...")

        # Set operation to health_check so AnswerAgent knows what to return
        state.setdefault("intent", {})["operation"] = "health_check"

        try:
            health_status = await self.mcp.get_health_status()
        except Exception as e:
            logger.warning(f"Failed to retrieve health status: {e}")
            health_status = {
                "status": "error",
                "error": str(e),
            }
        state["health_status"] = health_status

        # Run answer agent
        return await self._answer_node(state)

    async def _answer_error_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for error handling."""
        logger.info("⚠️  Handling error...")

        # Set operation to error
        state.setdefault("intent", {})["operation"] = "error"

        # Ensure error_info is set
        if not state.get("error_info"):
            state["error_info"] = {
                "type": "UNKNOWN_ERROR",
                "message": "An error occurred",
                "operation": "error"
            }

        # Run answer agent
        return await self._answer_node(state)

    async def _interpret_node(self, state: BaseState) -> BaseState:
        """Route to InterpretationAgent for follow-up over prior results."""
        logger.info("🧩 Running InterpretationAgent (follow-up over previous results)...")
        try:
            interpret_graph = self.interpret_agent.build_subgraph()
            result = await interpret_graph.ainvoke(state)
            state["final_response"] = result.get("final_response", "No response generated")
            logger.info("✅ Interpretation complete")
            return state
        except Exception as e:
            logger.error(f"Interpretation failed: {e}")
            state["final_response"] = "I couldn't interpret the previous results due to an internal error."
            return state

    # ============= Helper methods =============

    # ❌ DEPRECATED: _simple_intent_parser removed in Phase 9
    # Replaced with IntentParserAgent.parse() for semantic parsing
    # Reason: Naive regex caused double-keyword-extraction problem
    # See: CHANGES_SUMMARY.md "Intent Parsing Architecture Gap"

    async def process_query(
        self,
        user_input: str,
        messages: Optional[List[Dict[str, str]]] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        High-level interface: delegate to the compiled LangGraph workflow so API consumers
        observe the exact same behaviour as direct graph executions.
        
        Args:
            user_input: The current user message/query
            messages: List of conversation messages ["role": ...]
            conversation_id: Optional conversation identifier for tracking
            metadata: Optional additional state fields to merge (e.g., eval IDs)
        """
        logger.info(f"📝 PROCESS_QUERY CALLED: {user_input[:100]}...")
        logger.info(f"📝 Conversation ID: {conversation_id}, Messages count: {len(messages) if messages else 0}")
        
        initial_state: Dict[str, Any] = {
            "user_input": user_input,
            "messages": messages or [],
            "conversation_id": conversation_id or "",
            # 🆕 Retry & candidate tracking (prevent infinite loops)
            "tried_candidate_tables": [],
            "retry_attempt_count": 0,
            "max_retries_per_candidate_set": 2,
            "skip_tables": [],
            # 🆕 Global orchestration budgets (logical stop conditions)
            "plan_attempt_count": 0,
            "max_total_plans": 4,
            "exec_attempt_count": 0,
            "max_exec_attempts": 4,
            # LLM budget tracking
            "total_llm_calls": 0,
            "max_llm_calls": self.max_llm_calls,
            # Phase 1 instrumentation: initialize usage/loop maps lazily (kept optional in contracts)
            "llm_usage": {},
            "node_entry_counts": {},
            "loop_events": {},
            # Graph cycle tracking (used by loop guards in later phases)
            "total_graph_cycles": 0,
            "max_graph_cycles": self.max_graph_cycles,
            # Database config for downstream helpers (e.g., canonicalization)
            "db_dialect": self.db_dialect,
            "db_default_schema": self.db_default_schema,
            # Budget safety margin to support budget-aware routing
            "llm_budget_safety_margin": self.llm_budget_safety_margin,
            # Default answer formatting preference (can be overridden per-query via metadata)
            "answer_mode": self.default_answer_mode,
            # Phase 2b: Repair loop control caps (can be overridden via metadata)
            "max_validation_attempts": self.max_validation_attempts,
            "max_exec_recovery_attempts": self.max_exec_recovery_attempts,
            "max_no_progress_repeats": self.max_no_progress_repeats,
            "validation_attempt_count": 0,
            "exec_recovery_attempt_count": 0,
            "repair_no_progress_count": 0,
            "repair_signatures_seen": {},
        }
        if metadata and isinstance(metadata, dict):
            for key, value in metadata.items():
                if value is not None:
                    initial_state[key] = value
        try:
            # Server-side timeout for full orchestration to avoid client-level timeouts.
            # Use the same query_timeout_seconds as an upper bound for now.
            timeout_s = max(self.query_timeout_seconds, 60)
            import asyncio as _asyncio
            result = await _asyncio.wait_for(self.ainvoke(initial_state), timeout=timeout_s)
            if isinstance(result, dict):
                result.setdefault("final_response", result.get("final_answer"))
                result.setdefault("final_answer", result.get("final_response"))
            return result
        except TimeoutError:
            logger.error("❌ [PROCESS_QUERY] Orchestrator timed out before completion", exc_info=True)
            return {
                "user_input": user_input,
                "intent": {},
                "relevant_tables": [],
                "candidate_views": [],
                "sql_query": "",
                "join_plan": {},
                "exec_result": None,
                "error_info": {
                    "type": "SERVER_TIMEOUT",
                    "message": "The server took too long to compute a plan or execute the query.",
                },
                "final_answer": "This request took too long to complete. Please narrow down the question or try again with a smaller scope.",
                "final_response": "This request took too long to complete. Please narrow down the question or try again with a smaller scope.",
            }
        except Exception as exc:
            logger.error("❌ [PROCESS_QUERY] Graph execution failed: %s", exc, exc_info=True)
            return {
                "user_input": user_input,
                "intent": {},
                "relevant_tables": [],
                "candidate_views": [],
                "sql_query": "",
                "join_plan": {},
                "exec_result": None,
                "error_info": {
                    "type": "PIPELINE_ERROR",
                    "message": str(exc),
                },
                "final_answer": "I ran into an internal error while processing your request.",
                "final_response": "I ran into an internal error while processing your request.",
            }


async def create_orchestrator(
    llm_model: str = "gpt-4o",
    llm_temp: float = 0.0,
    max_joins: int = 3,
    max_retries: int = 2,
    row_limit: int = 1000,
    query_timeout_seconds: int = 30,
) -> QueryOrchestrator:
    """
    Thin async factory for QueryOrchestrator.

    Provided for backwards compatibility with older tests and callers
    that expect a create_orchestrator() export.
    """
    return QueryOrchestrator(
        llm_model=llm_model,
        llm_temp=llm_temp,
        max_joins=max_joins,
        max_retries=max_retries,
        row_limit=row_limit,
        query_timeout_seconds=query_timeout_seconds,
    )


async def _result_validator_async(self, state: BaseState) -> BaseState:
    """
    Async wrapper for result validator node so we can attach instrumentation.

    NOTE: This is defined at module scope and then bound onto QueryOrchestrator
    to avoid issues with older bytecode caches during migration.
    """
    # Instrumentation: track node entry
    try:
        self._increment_node_entry(state, "result_validator")
    except Exception:
        pass
    return build_result_validator_node(state)


# Ensure QueryOrchestrator exposes _result_validator_async even if older
# bytecode caches omit the in-class definition.
if hasattr(QueryOrchestrator, "__mro__"):
    setattr(QueryOrchestrator, "_result_validator_async", _result_validator_async)

async def _format_execution_results(
    execution_result: Dict[str, Any],
    intent: Dict[str, Any],
    user_input: str,
) -> str:
    """Format execution results into a user-friendly deterministic response."""
    try:
        data = execution_result.get("data", [])
        row_count = execution_result.get("row_count", 0)
        execution_time = execution_result.get("execution_time_ms", 0)

        # DEBUG: Log data reception
        logger.debug(
            "📊 _format_execution_results: data=%s rows, row_count=%s, keys in exec_result=%s",
            len(data),
            row_count,
            list(execution_result.keys()),
        )

        # Handle different query types
        query_operation = intent.get("operation", "query")
        primary_entities = intent.get("primary_entities", [])
        metrics = intent.get("metrics", [])

        if not data:
            logger.warning(
                "⚠️  No data returned. execution_result keys=%s, row_count=%s",
                list(execution_result.keys()),
                row_count,
            )
            return (
                f"Your query '{user_input}' executed successfully but returned no data. "
                "This might mean there are no matching records in the database."
            )

        # Format based on query type
        if query_operation == "query" and "count" in metrics:
            # COUNT query - return the number
            if data and len(data) > 0 and len(data[0]) > 0:
                count_value = list(data[0].values())[0]
                entity_name = primary_entities[0] if primary_entities else "items"
                return f"There are {count_value} {entity_name} in the database."

        elif query_operation == "query" and metrics:
            # Aggregation query (SUM, AVG, etc.)
            if data and len(data) > 0:
                result_values = []
                for row in data[:5]:  # Show first 5 results
                    for key, value in row.items():
                        if key and value is not None:
                            result_values.append(f"{key}: {value}")
                result_str = ", ".join(result_values)
                return f"Query results: {result_str}"

        # Regular SELECT query
        if row_count == 1:
            # Single row result
            row = data[0]
            formatted_data = []
            for key, value in row.items():
                if value is not None:
                    formatted_data.append(f"{key}: {value}")
            return f"Found 1 result: {', '.join(formatted_data)}"
        elif row_count <= 10:
            # Small result set - show all
            response = f"Found {row_count} results:\n"
            for i, row in enumerate(data, 1):
                row_values = []
                for key, value in row.items():
                    if value is not None:
                        row_values.append(f"{key}: {value}")
                response += f"{i}. {', '.join(row_values)}\n"
            return response.rstrip()
        else:
            # Large result set - summarize
            columns = list(data[0].keys()) if data else []
            return (
                f"Found {row_count} results with columns: {', '.join(columns)}. "
                "Use a more specific query to see the actual data."
            )

    except Exception as e:
        logger.error(f"Error formatting execution results: {e}")
        return (
            "The query executed successfully and returned "
            f"{execution_result.get('row_count', 'unknown')} results, "
            "but I had trouble formatting them for display."
        )

    async def _probe_candidate_counts(self, table_names: List[str]) -> Dict[str, int]:
        """Quickly probe row counts per candidate to prioritize tables with data."""
        counts: Dict[str, int] = {}
        for t in table_names:
            if not t:
                continue
            qualified_t = self._qualify_table_name(str(t))
            sql = f"SELECT COUNT(*) AS c FROM {qualified_t}"
            try:
                result = await self.mcp.query_bounded(sql, max_rows=1, timeout_ms=5000)
                if isinstance(result, dict) and result.get("ok"):
                    data = result.get("data") or []
                    if isinstance(data, list) and data:
                        row0 = data[0]
                        if isinstance(row0, dict):
                            try:
                                counts[t] = int(next(iter(row0.values())))
                                continue
                            except Exception:
                                counts[t] = counts.get(t, 0)
                                continue
                    row_count = result.get("row_count")
                    if isinstance(row_count, (int, float)):
                        counts[t] = int(row_count)
                        continue
                counts[t] = counts.get(t, 0)
            except Exception:
                counts[t] = counts.get(t, 0)
        return counts

    async def _get_catalog_from_mcp(self) -> Optional[Dict[str, Any]]:
        """Get catalog data directly from MCP server."""
        try:
            # Try to access the catalog through the MCP client's scout runner
            logger.info("🔧 Attempting to get catalog data from MCP scout runner")

            # Check if the MCP client has access to scout runner
            # This is a bit of a hack, but we need to access the catalog somehow
            if hasattr(self.mcp, '_scout_runner') and self.mcp._scout_runner:
                catalog = self.mcp._scout_runner.get_catalog()
                if catalog:
                    logger.info(f"🔧 Retrieved catalog with {len(catalog.get('tables', {}))} tables")
                    return catalog

            # Alternative: Try to load catalog from the known file path
            import os
            catalog_path = "data/catalog/scout_catalog.json"
            if os.path.exists(catalog_path):
                import json
                with open(catalog_path, 'r', encoding='utf-8') as f:
                    catalog = json.load(f)
                logger.info(f"🔧 Loaded catalog from file with {len(catalog.get('tables', {}))} tables")
                return catalog

            logger.warning("🔧 Could not access catalog data")
            return None

        except Exception as e:
            logger.warning(f"🔧 Could not get catalog from MCP: {e}")
            return None

    async def _perform_local_semantic_search(self, catalog: Dict[str, Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform semantic search locally using TableRanker."""
        try:
            from mcp_server.table_ranker import TableRanker

            # Extract entities and operations from intent
            entities = []
            operations = []

            entities.extend(intent.get("primary_entities", []))
            entities.extend(intent.get("secondary_entities", []))
            entities.extend(intent.get("keywords_for_discovery", []))
            operations.extend(intent.get("metrics", []))
            operations.extend(intent.get("filters", []))

            if not entities:
                return []

            # Get tables from catalog
            tables_dict = catalog.get("tables", {})
            all_tables = []
            for name, data in tables_dict.items():
                all_tables.append({
                    "name": name,
                    "schema": data.get("schema", "dbo"),
                    "type": "table",
                    **data
                })

            # Perform semantic ranking
            ranker = TableRanker()
            ranked_tables = ranker.rank_tables(all_tables, entities, operations)

            # Convert to result format
            results = []
            for ranked in ranked_tables:
                results.append({
                    "name": ranked.name,
                    "schema": ranked.schema,
                    "score": ranked.score,
                    "reasons": ranked.reasons,
                    "estimated_rows": ranked.estimated_rows,
                    "column_count": ranked.column_count,
                    "fk_count": ranked.fk_count
                })

            logger.info(f"🔧 Local semantic search found {len(results)} tables")
            return results

        except Exception as e:
            logger.error(f"🔧 Local semantic search failed: {e}")
            return []

    async def invoke_agent(self, agent_name: str, state: Optional[BaseState] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_name = (agent_name or "").strip().lower()
        if not normalized_name:
            raise ValueError("agent_name is required")
        handler = self._get_agent_handler(normalized_name)
        if handler is None:
            raise ValueError(f"Unknown agent '{agent_name}'")
        state_payload: BaseState = copy.deepcopy(state or {})
        if options and isinstance(options, dict):
            overrides = options.get("state_overrides")
            if isinstance(overrides, dict):
                for key, value in overrides.items():
                    state_payload[key] = copy.deepcopy(value)
            extra = {k: v for k, v in options.items() if k != "state_overrides"}
            if extra:
                state_payload["agent_options"] = copy.deepcopy(extra)
        before_snapshot: BaseState = copy.deepcopy(state_payload)
        start = time.perf_counter()
        result_state = await handler(state_payload)
        if not isinstance(result_state, dict):
            raise ValueError(f"Agent '{normalized_name}' returned invalid state")
        normalized_state: BaseState = copy.deepcopy(result_state)
        exec_envelope: Optional[Dict[str, Any]] = None
        if normalized_state.get("exec_result") is not None:
            normalized_state["exec_result"] = self._coerce_exec_result(normalized_state.get("exec_result"))
            exec_envelope = normalized_state.get("exec_result")
        error_info = self._normalize_error_info(normalized_state.get("error_info"))
        if error_info:
            normalized_state["error_info"] = error_info
        data = []
        row_count = None
        truncated = False
        exec_error = None
        exec_ok = True
        if exec_envelope:
            data = exec_envelope.get("data") or []
            row_count = exec_envelope.get("row_count")
            truncated = bool(exec_envelope.get("truncated", False))
            exec_error = exec_envelope.get("error")
            exec_ok = bool(exec_envelope.get("ok", True))
        delta = self._compute_state_delta(before_snapshot, normalized_state)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        warnings = normalized_state.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = [str(warnings)]
        overall_ok = exec_ok and not bool(error_info)
        return {
            "agent": normalized_name,
            "ok": overall_ok,
            "data": data,
            "row_count": row_count,
            "execution_time_ms": elapsed_ms,
            "truncated": truncated,
            "warnings": warnings,
            "error": exec_error,
            "error_info": error_info,
            "input_state": before_snapshot,
            "output_state": normalized_state,
            "state_delta": delta,
        }

    def _get_agent_handler(self, normalized_name: str):
        mapping = {
            "intent_parser": self._parse_intent_node,
            "parse_intent": self._parse_intent_node,
            "discovery": self._discovery_node,
            "join_sql": self._join_sql_node,
            "sql_validator": self._validate_sql_node,
            "validate_sql": self._validate_sql_node,
            "exec_recovery": self._exec_recovery_node,
            "execution": self._exec_recovery_node,
            "result_validator": self._result_validator_async,
            "interpretation": self._interpret_node,
            "interpret": self._interpret_node,
            "answer": self._answer_node,
        }
        return mapping.get(normalized_name)

    async def _result_validator_async(self, state: BaseState) -> BaseState:
        """
        Async wrapper for result validator node so we can attach instrumentation.
        """
        # Instrumentation: track node entry
        self._increment_node_entry(state, "result_validator")
        return build_result_validator_node(state)

    def _compute_state_delta(self, before_state: BaseState, after_state: BaseState) -> Dict[str, Any]:
        delta = {
            "added": {},
            "removed": [],
            "updated": {},
        }
        for key, value in after_state.items():
            if key not in before_state:
                delta["added"][key] = value
            elif before_state[key] != value:
                delta["updated"][key] = {
                    "before": before_state[key],
                    "after": value,
                }
        for key in before_state.keys():
            if key not in after_state:
                delta["removed"].append(key)
        return delta


# ============= Factory and export functions =============

def create_query_orchestrator(
    llm_model: str = "gpt-4o",
    llm_temp: float = 0.0,
    max_joins: int = 3,
    max_retries: int = 2,
    row_limit: int = 1000,
    query_timeout_seconds: int = 30
) -> QueryOrchestrator:
    """
    Factory function to create a QueryOrchestrator instance.
    
    Args:
        llm_model: LLM model name
        llm_temp: Temperature for LLM
        max_joins: Maximum joins allowed
        max_retries: Maximum retry attempts
        row_limit: Row limit for queries
        query_timeout_seconds: Query timeout
        
    Returns:
        Initialized QueryOrchestrator instance
    """
    env_model = os.getenv("LANGGRAPH_LLM_MODEL") or os.getenv("OPENAI_MODEL")
    final_model = env_model.strip() if env_model and env_model.strip() else llm_model
    env_temp = os.getenv("LANGGRAPH_LLM_TEMP") or os.getenv("OPENAI_TEMPERATURE")
    final_temp = llm_temp
    if env_temp is not None and str(env_temp).strip() != "":
        try:
            final_temp = float(env_temp)
        except ValueError:
            logger.warning("Invalid LLM temperature '%s'. Using default %s", env_temp, llm_temp)
    return QueryOrchestrator(
        llm_model=final_model,
        llm_temp=final_temp,
        max_joins=max_joins,
        max_retries=max_retries,
        row_limit=row_limit,
        query_timeout_seconds=query_timeout_seconds
    )


# Module-level instance for FastAPI integration
_global_orchestrator: Optional[QueryOrchestrator] = None


def get_orchestrator() -> QueryOrchestrator:
    """Get or create the global orchestrator instance."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = create_query_orchestrator()
    return _global_orchestrator


# ============= LangGraph Studio Export =============

def build_graph():
    """
    Build and return the compiled multi-agent orchestrator graph.
    
    This function is used by LangGraph Studio (referenced in langgraph.json).
    It creates a fresh QueryOrchestrator instance and returns its compiled graph.
    
    Returns:
        Compiled LangGraph StateGraph ready for execution
    """
    orchestrator = create_query_orchestrator()
    return orchestrator.graph


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        orchestrator = create_query_orchestrator()
        
        # Test queries
        test_queries = [
            "Show me top 10 customers by total orders",
            "What tables exist in the database?",
            "Is the system healthy?",
        ]

        for query in test_queries:
            response = await orchestrator.process_query(query)
            print(f"Q: {query}")
            print(f"A: {response}")
            print()

    asyncio.run(main())
