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
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.mcp_client import MCPDatabaseTool
from langgraph_integration.debug_logger import get_debug_logger

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
        self.mcp = MCPDatabaseTool()

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

        self.graph = self._build_graph()

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
        graph.add_node("exec_recovery", self._exec_recovery_node)
        graph.add_node("answer", self._answer_node)

        # Special operation nodes - register async implementations directly
        graph.add_node("answer_schema", self._answer_schema_node)
        graph.add_node("answer_health", self._answer_health_node)
        graph.add_node("answer_error", self._answer_error_node)

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
            
            This determines which branch of the orchestrator to take:
            - "clarify": Ask user for clarification
            - "schema_query": Discover tables/views and explain schema
            - "health_check": Check system health
            - "execute_direct": Execute pre-written SQL
            - "error": Handle errors
            - "query" (default): Full query pipeline
            """
            intent = state.get("intent", {})
            operation = intent.get("operation", "query")

            logger.info(f"🚦 Routing operation: {operation}")

            if operation == "clarify":
                return "answer"
            elif operation == "schema_query":
                return "discovery_for_schema"
            elif operation == "health_check":
                return "answer_health"
            elif operation == "execute_direct":
                return "exec_recovery"
            elif operation == "error":
                return "answer_error"
            else:
                # Default: query → discovery → join_sql → exec → answer
                return "discovery"

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
            }
        )

        # ============= QUERY PIPELINE =============
        # Standard query flow: discovery → join_sql → exec_recovery → answer
        graph.add_edge("discovery", "join_sql")
        graph.add_edge("join_sql", "exec_recovery")
        graph.add_edge("exec_recovery", "answer")

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
            is_healthy = await self.mcp.health_check()
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
        Parse user intent using LLM-based semantic analysis (Phase 9).
        
        🆕 Phase 9: Replaces naive _simple_intent_parser with IntentParserAgent
        - Extracts structured ParsedIntent (not loose dict)
        - Produces clean keywords for discovery (NO noise from function words)
        - Returns metrics, filters, time_window for better ranking
        - Fixes double-keyword-extraction problem
        
        Returns: ParsedIntent with operation, entities, metrics, filters, keywords_for_discovery, confidence
        """
        debug_logger.agent_entry("parse_intent", dict(state))
        before_state = dict(state)
        
        logger.info("🧠 [PARSE_INTENT] ════════════════════════════════════════")
        logger.info("🧠 [PARSE_INTENT] STARTING INTENT PARSING (Phase 9)")
        logger.info("🧠 [PARSE_INTENT] ════════════════════════════════════════")

        user_input = state.get("user_input", "")
        messages = state.get("messages", [])

        if not user_input:
            error = {
                "type": "NO_INPUT",
                "message": "No user input provided"
            }
            logger.error("🧠 [PARSE_INTENT] ❌ No user input!")
            return {**state, "error_info": error}

        try:
            logger.info(f"🧠 [PARSE_INTENT] Query: \"{user_input}\"")
            logger.info(f"🧠 [PARSE_INTENT] Calling IntentParserAgent.parse()...")
            
            # 🆕 Phase 9: Use IntentParserAgent for semantic parsing
            intent = await self.intent_parser.parse(user_input)
            
            logger.info(f"🧠 [PARSE_INTENT] ✅ Intent parsing COMPLETE")
            logger.info(f"🧠 [PARSE_INTENT] ━━━ PARSED INTENT ━━━")
            logger.info(f"🧠 [PARSE_INTENT]   operation: {intent.get('operation')}")
            logger.info(f"🧠 [PARSE_INTENT]   primary_entities: {intent.get('primary_entities', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   metrics: {intent.get('metrics', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   filters: {intent.get('filters', [])}")
            logger.info(f"🧠 [PARSE_INTENT]   time_window: {intent.get('time_window')}")
            logger.info(f"🧠 [PARSE_INTENT]   keywords_for_discovery: {intent.get('keywords_for_discovery', [])} ← CRITICAL!")
            logger.info(f"🧠 [PARSE_INTENT]   confidence: {intent.get('confidence', 0):.2f}")
            
            # CRITICAL CHECK
            keywords = intent.get("keywords_for_discovery", [])
            if not keywords:
                logger.error("🧠 [PARSE_INTENT] ❌ CRITICAL: keywords_for_discovery is EMPTY!")
                logger.error("🧠 [PARSE_INTENT]    This will cause discovery to use fallback extraction")
                logger.error("🧠 [PARSE_INTENT]    Result: All 943 tables will be searched")
            else:
                logger.info(f"🧠 [PARSE_INTENT] ✅ Keywords OK: {keywords}")
            
            state["intent"] = intent
            logger.info(f"🧠 [PARSE_INTENT] ✅ Intent stored in state['intent']")
            logger.info(f"🧠 [PARSE_INTENT] ✅ Ready for ROUTE_OPERATION node")
            
            debug_logger.intent_parsed_phase9(intent, parsing_method="LLM")
            debug_logger.agent_exit("parse_intent", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "INTENT_PARSE_ERROR",
                "message": f"Failed to parse intent: {str(e)}",
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
        
        logger.info("🔗 [JOIN_SQL] ════════════════════════════════════════")
        logger.info("🔗 [JOIN_SQL] CRITICAL: NODE EXECUTION STARTED!")
        logger.info("🔗 [JOIN_SQL] If this log doesn't appear, the workflow STOPPED after DISCOVERY")
        logger.info("🔗 [JOIN_SQL] ════════════════════════════════════════")
        
        # SURGICAL DEBUG: Show input state
        logger.info("🔗 [JOIN_SQL] ━━━ INPUT STATE ━━━")
        logger.info(f"🔗 [JOIN_SQL] Input keys: {list(state.keys())}")
        
        # DEBUG: Check what we have from discovery
        relevant_tables = state.get("relevant_tables", [])
        schema_snippet = state.get("schema_snippet", "")
        error_info = state.get("error_info")
        
        logger.info(f"🔗 [JOIN_SQL] Received from discovery:")
        logger.info(f"🔗 [JOIN_SQL]   - relevant_tables: {len(relevant_tables)} tables {'✅ GOOD' if relevant_tables else '❌ EMPTY!'}")
        logger.info(f"🔗 [JOIN_SQL]   - schema_snippet: {len(schema_snippet)} chars")
        logger.info(f"🔗 [JOIN_SQL]   - error_info: {error_info}")
        
        if not relevant_tables:
            logger.error("🔗 [JOIN_SQL] ❌ CRITICAL: No relevant_tables from discovery!")
            logger.error("🔗 [JOIN_SQL] This means discovery FAILED or returned empty results")

        # Check for prior errors but only abort if we truly lack inputs
        if error_info:
            logger.warning("🔗 [JOIN_SQL] ⚠️  Prior error detected from discovery:")
            logger.warning(f"🔗 [JOIN_SQL]    type: {error_info.get('type')}")
            logger.warning(f"🔗 [JOIN_SQL]    message: {error_info.get('message')}")
            if not relevant_tables:
                logger.warning("🔗 [JOIN_SQL]    No relevant tables available → cannot proceed with join planning")
                return state
            else:
                logger.info("🔗 [JOIN_SQL]    Proceeding with join planning using available relevant_tables despite prior error")

        try:
            # Fast path: COUNT metric with a single primary entity and at least one relevant table
            intent = state.get("intent", {})
            metrics = intent.get("metrics", [])
            if relevant_tables and any((m or "").lower() == "count" for m in metrics):
                first_table = relevant_tables[0]
                simple_sql = f"SELECT COUNT(*) AS total_count FROM {first_table}"
                logger.info(f"🔗 [JOIN_SQL] Using COUNT fast path for table: {first_table}")
                state["join_plan"] = {"strategy": "count_fast_path", "table": first_table}
                state["sql_query"] = simple_sql
                return state

            # Build and run join_sql subgraph
            join_sql_graph = self.join_sql_agent.build_subgraph()

            # Invoke with input state using async API
            logger.info("🔗 [JOIN_SQL] Invoking join_sql subgraph with ainvoke()...")
            logger.info("🔗 [JOIN_SQL] (This enters join_sql subgraph nodes: validate_tables → plan_joins → generate_sql)")
            result = await join_sql_graph.ainvoke(state)
            logger.info("🔗 [JOIN_SQL] ✅ join_sql subgraph completed")

            # SURGICAL DEBUG: Show output state
            logger.info("🔗 [JOIN_SQL] ━━━ OUTPUT STATE ━━━")
            logger.info(f"🔗 [JOIN_SQL] Output keys: {list(result.keys())}")
            
            # Extract outputs
            join_plan = result.get("join_plan", {})
            sql_query = result.get("sql_query", "")
            
            logger.info(f"🔗 [JOIN_SQL] Extracting results:")
            logger.info(f"🔗 [JOIN_SQL]   ✓ join_plan keys: {list(join_plan.keys()) if join_plan else 'empty'}")
            logger.info(f"🔗 [JOIN_SQL]   ✓ sql_query: {len(sql_query)} chars")
            
            state["join_plan"] = join_plan
            state["sql_query"] = sql_query

            if result.get("error_info"):
                logger.error(f"🔗 [JOIN_SQL] ❌ Error from join_sql subgraph:")
                error = result["error_info"]
                logger.error(f"🔗 [JOIN_SQL]    type: {error.get('type')}")
                logger.error(f"🔗 [JOIN_SQL]    message: {error.get('message')}")
                state["error_info"] = error
            else:
                logger.info(f"🔗 [JOIN_SQL] ✅ JoinSQL complete: {len(sql_query)} char SQL generated")
                if sql_query:
                    logger.info(f"🔗 [JOIN_SQL]    Preview: {sql_query[:100]}...")
                else:
                    logger.warning(f"🔗 [JOIN_SQL]    ⚠️  SQL query is empty!")
            
            logger.info(f"🔗 [JOIN_SQL] ✅ State ready for EXEC_RECOVERY node")
            debug_logger.agent_exit("join_sql", before_state, dict(state))
            return state

        except Exception as e:
            error = {
                "type": "JOIN_SQL_ERROR",
                "message": f"JoinSQL agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"🔗 [JOIN_SQL] ❌ {error['message']}")
            import traceback
            logger.error(f"🔗 [JOIN_SQL] Traceback:\n{traceback.format_exc()}")
            result_state = {**state, "error_info": error}
            debug_logger.agent_exit("join_sql", before_state, dict(result_state))
            return result_state

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
            result = await exec_recovery_graph.ainvoke(state)
            logger.info("⚡ [EXEC_RECOVERY] ✅ exec_recovery subgraph completed")

            # SURGICAL DEBUG: Show output state
            logger.info("⚡ [EXEC_RECOVERY] ━━━ OUTPUT STATE ━━━")
            logger.info(f"⚡ [EXEC_RECOVERY] Output keys: {list(result.keys())}")

            # Extract outputs
            exec_result = result.get("exec_result", {})
            state["exec_result"] = exec_result
            state["sql_query"] = result.get("sql_query", state.get("sql_query", ""))
            state["retry_count"] = result.get("retry_count", 0)

            if result.get("error_info"):
                logger.error(f"⚡ [EXEC_RECOVERY] Error from exec_recovery: {result['error_info']}")
                state["error_info"] = result["error_info"]

            if exec_result.get("ok"):
                logger.info(
                    f"⚡ [EXEC_RECOVERY] ✅ EXECUTION SUCCESS: "
                    f"{exec_result.get('row_count', 0)} rows in {exec_result.get('execution_time_ms', 0)}ms"
                )
                # Ensure downstream answer formatting does not take error/clarify paths
                state["error_info"] = None
                state.setdefault("intent", {})["operation"] = "query"
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
            # Fast return: if we have a successful exec_result, synthesize a concise answer
            exec_result = state.get("exec_result", {}) or {}
            if isinstance(exec_result, dict) and exec_result.get("ok"):
                # Try to extract a scalar count if present in rows
                count_value = None
                rows = exec_result.get("rows") or exec_result.get("data") or []
                if isinstance(rows, list) and rows:
                    first = rows[0]
                    if isinstance(first, dict):
                        # Look for common count keys
                        for key in ["total_count", "count", "cnt", "total"]:
                            if key in first and isinstance(first[key], (int, float)):
                                count_value = int(first[key]) if isinstance(first[key], (int, float)) else None
                                break
                        # Fallback: any single numeric value
                        if count_value is None:
                            for v in first.values():
                                if isinstance(v, (int, float)):
                                    count_value = int(v)
                                    break
                if count_value is not None:
                    state["final_response"] = f"There are {count_value} customers."
                    logger.info("✅ Answer synthesized from exec_result (count)")
                    return state

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

    # ============= Helper methods =============

    # ❌ DEPRECATED: _simple_intent_parser removed in Phase 9
    # Replaced with IntentParserAgent.parse() for semantic parsing
    # Reason: Naive regex caused double-keyword-extraction problem
    # See: CHANGES_SUMMARY.md "Intent Parsing Architecture Gap"

    async def process_query(self, user_input: str) -> str:
        """
        High-level interface: process a query and return the final response.
        
        Args:
            user_input: User's natural language query
            
        Returns:
            Final response string (1-2 sentence answer or clarification)
        """
        logger.info(f"📝 Processing query: {user_input[:100]}...")

        try:
            # Create initial state
            initial_state = BaseState(
                user_input=user_input,
                messages=[],
                session_described_tables={},
                retry_count=0
            )

            # Run the graph using async API since we're in an async context
            # This allows proper handling of async nodes without blocking
            # Always use ainvoke for async compatibility
            result = await self.graph.ainvoke(initial_state)

            # Extract final response
            final_response = result.get("final_response", "No response generated")
            logger.info(f"✅ Query processed successfully")
            return final_response

        except Exception as e:
            logger.error(f"❌ Error processing query: {e}")
            return f"Error processing query: {str(e)}"


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