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
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent
from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.agents.sql_validator.agent import create_sql_validator_agent
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.agents.interpretation.agent import InterpretationAgent
from langgraph_integration.mcp_client import get_shared_mcp_tool
from langgraph_integration.debug_logger import get_debug_logger

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

        # Initialize specialized agents
        logger.info("🚀 Initializing multi-agent orchestrator (Phase 9)...")
        
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

        # 🆕 Phase 9: SQLValidatorAgent for pre-execution validation and repair (lazy init)
        self.sql_validator_agent = None
        logger.info("✅ SQLValidatorAgent registered (AST validation, auto-repair)")
        
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
        graph.add_node("route_operation", self._route_operation_node)

        # Agent nodes (main flow) - register async implementations directly
        graph.add_node("discovery", self._discovery_node)
        graph.add_node("join_sql", self._join_sql_node)
        graph.add_node("validate_sql", self._validate_sql_node)
        graph.add_node("exec_recovery", self._exec_recovery_node)
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
        graph.add_edge("parse_intent", "route_operation")

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
            - "query" (default): Full query pipeline
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

            # THIRD PRIORITY: Route by operation type
            result = None
            # Follow-up interpretation path
            try:
                required_action = intent.get("required_action")
                if required_action == "interpret_previous" and (state.get("previous_exec_result") or state.get("exec_result")):
                    logger.info("🚦 [ROUTE_TO_OPERATION] 🎯 Follow-up interpretation detected → interpret")
                    return "interpret"
            except Exception:
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

        # ============= QUERY PIPELINE =============
        # Standard query flow: discovery → join_sql → validate_sql → exec_recovery → answer
        graph.add_edge("discovery", "join_sql")
        graph.add_edge("join_sql", "validate_sql")
        graph.add_edge("validate_sql", "exec_recovery")
        graph.add_edge("exec_recovery", "answer")
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
        logger.info(f"   Start → route_operation (conditional) → multiple paths → END")
        return compiled

    # Legacy-simple intent parser for tests and quick routes
    def _simple_intent_parser(self, text: str) -> Dict[str, Any]:
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

    # ============= Core node implementations =============

    async def _index_database_node(self, state: BaseState) -> BaseState:
        """
        Load Scout catalog and verify MCP availability.
        
        This ensures discovery will have access to semantic ranking and metadata.
        """
        debug_logger.agent_entry("index_database", dict(state))
        before_state = dict(state)
        
        logger.info("📚 [INDEX_DATABASE] Indexing database...")

        try:
            # Check MCP health
            logger.info("📚 [INDEX_DATABASE] Checking MCP availability...")
            logger.info(f"📚 [INDEX_DATABASE] MCP URL: {getattr(self.mcp, 'mcp_url', 'unknown')}")
            is_healthy = await self.mcp.health_check()
            logger.info(f"📚 [INDEX_DATABASE] Health check result: {is_healthy}")

            if not is_healthy:
                error = {
                    "type": "MCP_UNAVAILABLE",
                    "message": "MCP server is not responding"
                }
                logger.error(f"📚 [INDEX_DATABASE] ❌ {error['message']}")
                result_state = {**state, "error_info": error}
                debug_logger.agent_exit("index_database", before_state, dict(result_state))
                return result_state

            logger.info("📚 [INDEX_DATABASE] ✅ Database indexed, MCP available")
            # Load last execution result for interpretation follow-ups (persisted on disk)
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

    async def _parse_intent_node(self, state: BaseState) -> BaseState:
        """
        Parse user intent using LangGraph subgraph with agentic reasoning (Phase 9.1).

        🆕 Phase 9.1: IntentParserAgent is now a FULL LangGraph subgraph
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
        debug_logger.agent_entry("discovery", dict(state))
        before_state = dict(state)
        
        logger.info("🔍 [DISCOVERY] Starting DiscoveryAgent...")
        
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
            
            # Update state with outputs
            state["relevant_tables"] = relevant_tables
            state["schema_snippet"] = schema_snippet
            state["candidate_views"] = candidate_views
            state["column_index"] = column_index
            state["session_described_tables"] = result.get(
                "session_described_tables",
                state.get("session_described_tables", {})
            )

            if result.get("error_info"):
                logger.error(f"🔍 [DISCOVERY] ❌ ERROR from discovery subgraph:")
                error = result["error_info"]
                logger.error(f"🔍 [DISCOVERY]    type: {error.get('type')}")
                logger.error(f"🔍 [DISCOVERY]    message: {error.get('message')}")
                state["error_info"] = error

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
        debug_logger.agent_entry("join_sql", dict(state))
        before_state = dict(state)

        logger.info("🔗 [JOIN_SQL] Starting SQL generation")

        # Check what we have from discovery
        relevant_tables = state.get("relevant_tables", [])
        intent = state.get("intent", {})

        logger.info(f"🔗 [JOIN_SQL] relevant_tables: {relevant_tables}")
        logger.info(f"🔗 [JOIN_SQL] intent: {intent}")

        if not relevant_tables:
            logger.warning("🔗 [JOIN_SQL] No relevant tables found")
            state["sql_query"] = ""
            state["join_plan"] = {}
            debug_logger.agent_exit("join_sql", before_state, dict(state))
            return state

        # Delegate to JoinPlanAndSQLAgent subgraph for robust planning and SQL generation
        try:
            join_graph = self.join_sql_agent.build_subgraph()
            join_result = await join_graph.ainvoke(state)
            sql_query = join_result.get("sql_query", "")
            join_plan = join_result.get("join_plan", {})
            if not sql_query:
                raise ValueError("Join SQL agent returned no SQL")
            state["sql_query"] = sql_query
            state["join_plan"] = join_plan
            logger.info(f"🔗 [JOIN_SQL] Generated SQL (agent): {sql_query}")
        except Exception as e:
            logger.warning(f"🔗 [JOIN_SQL] Join SQL agent failed ({e}); falling back to simple selection")
            # Fallback to simple generator
        candidate_views = state.get("candidate_views", [])
        primary_table = await asyncio.get_event_loop().run_in_executor(
            None, self._select_best_table_or_view_for_query, relevant_tables, candidate_views, intent
        )
        metrics = intent.get("metrics", [])
        if not primary_table:
            state["sql_query"] = ""
            state["join_plan"] = {}
        else:
            # Ensure schema-qualified table names for MSSQL (OLLuisiDiener.dbo.TableName)
            qualified_table = self._qualify_table_name(primary_table)
            if "count" in metrics or "total" in metrics or len(metrics) == 0:
                state["sql_query"] = f"SELECT COUNT(*) AS total_count FROM {qualified_table}"
            else:
                state["sql_query"] = f"SELECT TOP 10 * FROM {qualified_table}"
        state["join_plan"] = {"strategy": "direct", "primary_table": primary_table}

        logger.info("🔗 [JOIN_SQL] SQL generation complete")
        debug_logger.agent_exit("join_sql", before_state, dict(state))
        return state

    async def _validate_sql_node(self, state: BaseState) -> BaseState:
        """
        Run SQLValidatorAgent for pre-execution validation and repair.

        Validates SQL syntax, MSSQL dialect, table/column existence, and repairs if needed.
        Output: validation_result, sql_query (potentially repaired)
        """
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

        # Ensure SQL validator is initialized
        if not self.sql_validator_agent:
            self.sql_validator_agent = await create_sql_validator_agent(llm_model="gpt-4o")

        # Run SQLValidatorAgent
        try:
            validation_state = await self.sql_validator_agent(state)
            state.update(validation_state)

            validation_result = state.get("validation_result", {})
            is_valid = validation_result.get("is_valid", False)
            error_type = validation_result.get("error_type", "unknown")

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
        """Ensure table name is schema-qualified for MSSQL."""
        if '.' in table_name:
            # Already qualified
            return table_name
        else:
            # Add default schema qualification for MSSQL
            return f"OLLuisiDiener.dbo.{table_name}"

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
        """Select the best view for the query using business relevance ranking."""
        if not views:
            return ""

        from mcp_server.table_ranker import ViewsRanker

        primary_entities = intent.get("primary_entities", [])
        keywords = intent.get("keywords_for_discovery", [])
        operations = intent.get("operation", [])

        # Convert views list to dict format expected by ViewsRanker
        views_dict = {}
        for view in views:
            if isinstance(view, dict):
                view_name = view.get("full_name", view.get("name", ""))
                if view_name:
                    views_dict[view_name] = view

        if not views_dict:
            return ""

        # Use ViewsRanker for intelligent view selection
        ranker = ViewsRanker()
        ranked_views = ranker.rank_views(
            views_dict,
            entities=primary_entities + keywords,  # Combine entities and keywords
            intent_operations=operations,
            query_context={"intent": intent}
        )

        if ranked_views and ranked_views[0].score > 0.3:  # Minimum threshold for view selection
            best_view = ranked_views[0]
            logger.info(f"👁️ [VIEW_SELECTION] Selected view '{best_view.full_name}' with score {best_view.score:.2f}")
            logger.info(f"👁️ [VIEW_SELECTION] Reasons: {', '.join(best_view.reasons[:2])}")
            return best_view.full_name

        logger.debug(f"👁️ [VIEW_SELECTION] No views met minimum score threshold (0.3)")
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

        try:
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
            exec_result = result.get("exec_result", {})
            logger.info(f"⚡ [EXEC_RECOVERY] Setting state['exec_result'] = {exec_result} (type: {type(exec_result)})")
            state["exec_result"] = exec_result
            state["sql_query"] = result.get("sql_query", state.get("sql_query", ""))
            state["retry_count"] = result.get("retry_count", 0)

            if result.get("error_info"):
                logger.error(f"⚡ [EXEC_RECOVERY] Error from exec_recovery: {result['error_info']}")
                state["error_info"] = result["error_info"]

            if isinstance(exec_result, dict) and exec_result.get("ok"):
                logger.info(
                    f"⚡ [EXEC_RECOVERY] ✅ EXECUTION SUCCESS: "
                    f"{exec_result.get('row_count', 0)} rows in {exec_result.get('execution_time_ms', 0)}ms"
                )
                # Ensure downstream answer formatting does not take error/clarify paths
                state["error_info"] = None
                state.setdefault("intent", {})["operation"] = "query"
                # Persist last successful result for interpretation follow-ups
                try:
                    os.makedirs("data", exist_ok=True)
                    # Derive source tables from join_plan/SQL
                    sources = []
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
        debug_logger.agent_entry("answer", dict(state))
        before_state = dict(state)
        
        logger.info("✨ Running AnswerAgent...")

        try:
            # DEBUG: Log what we received
            user_input = state.get("user_input", "")
            exec_result_raw = state.get("exec_result")
            logger.info(f"✨ [ANSWER] exec_result_raw from state: {exec_result_raw} (type: {type(exec_result_raw)})")
            exec_result = state.get("exec_result", {}) or {}
            logger.info(f"✨ [ANSWER] exec_result after default: {exec_result} (type: {type(exec_result)})")
            error_info = state.get("error_info")
            logger.info(f"✨ [ANSWER] exec_result present: {bool(exec_result)}")
            logger.info(f"✨ [ANSWER] exec_result type: {type(exec_result)}")
            logger.info(f"✨ [ANSWER] exec_result keys: {list(exec_result.keys()) if isinstance(exec_result, dict) else 'Not a dict'}")
            logger.info(f"✨ [ANSWER] exec_result.ok: {exec_result.get('ok') if isinstance(exec_result, dict) else 'Not a dict'}")
            logger.info(f"✨ [ANSWER] error_info: {error_info}")
            logger.info(f"✨ [ANSWER] intent.operation: {state.get('intent', {}).get('operation')}")

            # HIGHEST PRIORITY: Handle clarification requests from intent parsing
            intent = state.get("intent", {})
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
                rows = exec_result.get("rows") or exec_result.get("data") or []
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

            # If we get here, fall back to AnswerAgent subgraph

            # Build and run answer subgraph
            answer_graph = self.answer_agent.build_subgraph()

            # Invoke with input state using async API
            result = await answer_graph.ainvoke(state)

            # Extract outputs
            state["final_response"] = result.get("final_response", "No response generated")

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

    async def process_query(self, user_input: str) -> Dict[str, Any]:
        """
        High-level interface: process a query and return the complete processing state.

        Args:
            user_input: User's natural language query

        Returns:
            Dict containing processing state including final_answer, intent, sql_query, etc.
        """
        logger.info(f"📝 PROCESS_QUERY CALLED: {user_input[:100]}...")
        logger.info("📝 Starting graph execution...")

        # 🎯 COMPLETE AGENT PIPELINE: Intent → Discovery → SQL → Execution
        logger.info("🎯 [PIPELINE] Starting complete agent workflow")

        # Step 0: Parse intent
        intent_subgraph = self.intent_parser.build_subgraph()
        intent_result = await intent_subgraph.ainvoke(BaseState(user_input=user_input))
        intent = intent_result.get("intent", {})
        logger.info(f"🎯 [PIPELINE] Intent parsed: {intent}")

        # Check for clarification
        if intent.get("needs_clarification", False):
            clarification_question = intent.get("clarification_question", "Could you please clarify your request?")
            return f"I need more information: {clarification_question}"

        try:
            # 🎯 FULL PIPELINE: Discovery → SQL Generation → Execution
            logger.info("🎯 [FULL_PIPELINE] Starting complete agent workflow")

            # Step 1: Discovery - Find relevant tables
            logger.info("🎯 [FULL_PIPELINE] Step 1: Discovery")
            discovery_input = BaseState(
                user_input=user_input,
                intent=intent,
                messages=[],
                session_described_tables={}
            )

            discovery_result = await self._discovery_node(discovery_input)
            relevant_tables = discovery_result.get("relevant_tables", [])
            candidate_views = discovery_result.get("candidate_views", [])

            logger.info(f"🎯 [FULL_PIPELINE] Discovery found {len(relevant_tables)} tables, {len(candidate_views)} views")

            if not relevant_tables:
                return f"I couldn't find any relevant tables for your query '{user_input}'. This might be because the database uses different terminology than expected."

            # Step 2: SQL Generation - Create queries from discovered tables
            logger.info("🎯 [FULL_PIPELINE] Step 2: SQL Generation")
            join_sql_input = BaseState(
                user_input=user_input,
                intent=intent,
                relevant_tables=relevant_tables,
                candidate_views=candidate_views,
                messages=[],
                session_described_tables={}
            )

            join_sql_result = await self._join_sql_node(join_sql_input)
            sql_query = join_sql_result.get("sql_query", "")
            join_plan = join_sql_result.get("join_plan", {})

            logger.info(f"🎯 [FULL_PIPELINE] SQL generated: {len(sql_query)} chars")
            logger.info(f"🎯 [FULL_PIPELINE] Join plan: {join_plan}")

            if not sql_query:
                return {
                    "user_input": user_input,
                    "intent": intent,
                    "relevant_tables": relevant_tables,
                    "candidate_views": candidate_views,
                    "error_info": {"type": "SQL_GENERATION_ERROR", "message": "Could not generate SQL query"},
                    "final_answer": f"I found relevant tables but couldn't generate a SQL query for '{user_input}'. The table structure might be too complex for automatic SQL generation."
                }

            # Step 3: Execution - Run the SQL and get results
            logger.info("🎯 [FULL_PIPELINE] Step 3: SQL Execution")
            exec_input = BaseState(
                user_input=user_input,
                intent=intent,
                relevant_tables=relevant_tables,
                candidate_views=candidate_views,
                sql_query=sql_query,
                join_plan=join_plan,
                messages=[],
                session_described_tables={}
            )

            exec_result = await self._exec_recovery_node(exec_input)
            execution_result = exec_result.get("exec_result")
            error_info = exec_result.get("error_info")

            logger.info(f"🎯 [FULL_PIPELINE] Execution completed: {execution_result}")
            logger.info(f"🎯 [FULL_PIPELINE] Errors: {error_info}")

            # Step 4: Format and return results
            if error_info:
                # Be robust to non-dict error_info
                if isinstance(error_info, dict):
                    msg = error_info.get('message', error_info.get('error', 'Unknown error'))
                else:
                    msg = str(error_info)
                return {
                    "user_input": user_input,
                    "intent": intent,
                    "relevant_tables": relevant_tables,
                    "candidate_views": candidate_views,
                    "sql_query": sql_query,
                    "join_plan": join_plan,
                    "error_info": error_info,
                    "final_answer": f"I encountered an error executing the query: {msg}"
                }

            # If success but empty, try next candidates up to 2 more times
            tried = set()
            if join_plan and isinstance(join_plan, dict):
                pt = join_plan.get("primary_table")
                if pt:
                    tried.add(pt)

            attempts = 0
            while (execution_result and execution_result.get("ok") and execution_result.get("row_count", 0) == 0 
                   and attempts < 2 and relevant_tables):
                # Remove already tried primary from candidates
                filtered = []
                for t in relevant_tables:
                    tname = t if isinstance(t, str) else (t.get("full_name") or t.get("name", ""))
                    if tname and tname not in tried:
                        filtered.append(t)
                if not filtered:
                    break
                # Reorder remaining candidates by quick COUNT(*) probe
                try:
                    names = [x if isinstance(x, str) else (x.get("full_name") or x.get("name", "")) for x in filtered]
                    counts = await self._probe_candidate_counts([n for n in names if n])
                    def sort_key(x):
                        n = x if isinstance(x, str) else (x.get("full_name") or x.get("name", ""))
                        return counts.get(n, 0)
                    filtered.sort(key=sort_key, reverse=True)
                except Exception:
                    pass
                relevant_tables = filtered

                # Regenerate SQL with remaining candidates
                join_sql_input = BaseState(
                    user_input=user_input,
                    intent=intent,
                    relevant_tables=relevant_tables,
                    candidate_views=candidate_views,
                    messages=[],
                    session_described_tables={}
                )
                join_sql_result = await self._join_sql_node(join_sql_input)
                sql_query = join_sql_result.get("sql_query", "")
                join_plan = join_sql_result.get("join_plan", {})
                if join_plan and join_plan.get("primary_table"):
                    tried.add(join_plan.get("primary_table"))

                if not sql_query:
                    break

                exec_input = BaseState(
                    user_input=user_input,
                    intent=intent,
                    relevant_tables=relevant_tables,
                    candidate_views=candidate_views,
                    sql_query=sql_query,
                    join_plan=join_plan,
                    messages=[],
                    session_described_tables={}
                )
                exec_result = await self._exec_recovery_node(exec_input)
                execution_result = exec_result.get("exec_result")
                error_info = exec_result.get("error_info")
                attempts += 1
                if error_info:
                    break

            if execution_result and execution_result.get("ok"):
                # Format the actual data results
                final_answer = await self._format_execution_results(execution_result, intent, user_input)
                return {
                    "user_input": user_input,
                    "intent": intent,
                    "relevant_tables": relevant_tables,
                    "candidate_views": candidate_views,
                    "sql_query": sql_query,
                    "join_plan": join_plan,
                    "exec_result": execution_result,
                    "final_answer": final_answer
                }
            else:
                return {
                    "user_input": user_input,
                    "intent": intent,
                    "relevant_tables": relevant_tables,
                    "candidate_views": candidate_views,
                    "sql_query": sql_query,
                    "join_plan": join_plan,
                    "exec_result": execution_result,
                    "error_info": error_info,
                    "final_answer": f"The query executed but returned no results for '{user_input}'."
                }

        except Exception as e:
            logger.error(f"🎯 [FULL_PIPELINE] Pipeline failed: {e}")
            import traceback
            logger.error(f"🎯 [FULL_PIPELINE] Traceback: {traceback.format_exc()}")
            return {
                "user_input": user_input,
                "error_info": {"type": "PROCESSING_ERROR", "message": str(e)},
                "final_answer": f"I encountered an error processing your query '{user_input}': {str(e)}"
            }

    async def _format_execution_results(self, execution_result: Dict[str, Any], intent: Dict[str, Any], user_input: str) -> str:
        """Format execution results into user-friendly response."""
        try:
            data = execution_result.get("data", [])
            row_count = execution_result.get("row_count", 0)
            execution_time = execution_result.get("execution_time_ms", 0)

            # Handle different query types
            query_operation = intent.get("operation", "query")
            primary_entities = intent.get("primary_entities", [])
            metrics = intent.get("metrics", [])

            if not data:
                return f"Your query '{user_input}' executed successfully but returned no data. This might mean there are no matching records in the database."

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

            else:
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
                    return f"Found {row_count} results with columns: {', '.join(columns)}. Use a more specific query to see the actual data."

        except Exception as e:
            logger.error(f"Error formatting execution results: {e}")
            return f"The query executed successfully and returned {execution_result.get('row_count', 'unknown')} results, but I had trouble formatting them for display."

    async def _probe_candidate_counts(self, table_names: List[str]) -> Dict[str, int]:
        """Quickly probe row counts per candidate to prioritize tables with data."""
        counts: Dict[str, int] = {}
        for t in table_names:
            if not t:
                continue
            sql = f"SELECT COUNT(*) AS c FROM {t}"
            try:
                result = await self.mcp.query_bounded(sql, max_rows=1, timeout_ms=5000)
                if isinstance(result, list) and result and isinstance(result[0], dict):
                    # Extract JSON envelope if present
                    import json
                    text = result[0].get("text", "{}")
                    payload = json.loads(text) if isinstance(text, str) and text.strip().startswith("{") else {}
                    data = payload.get("data") or []
                    if isinstance(data, list) and data:
                        row0 = data[0]
                        c = 0
                        if isinstance(row0, dict):
                            # pick first value
                            try:
                                c = int(list(row0.values())[0])
                            except Exception:
                                c = 0
                        counts[t] = c
                        continue
                # Fallback if not in envelope shape
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
    return QueryOrchestrator(
        llm_model=llm_model,
        llm_temp=llm_temp,
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