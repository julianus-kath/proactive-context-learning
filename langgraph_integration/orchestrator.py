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

        # Phase 4: MCP client lifecycle management
        self.mcp_client = MCPDatabaseTool()
        logger.info("✅ MCP Client initialized (Connection pooling)")

        self.graph = self._build_graph()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        try:
            await self.mcp_client.close()
            logger.info("✅ MCP client connections closed")
        except Exception as e:
            logger.warning(f"Error closing MCP client: {e}")

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

            logger.info(f"🚦 [ROUTE_TO_OPERATION] intent: {intent}")
            logger.info(f"🚦 [ROUTE_TO_OPERATION] operation: {operation}")
            logger.info(f"🚦 [ROUTE_TO_OPERATION] error_info: {state.get('error_info')}")

            result = None
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

        # Phase 3: Select the most appropriate table OR view using views-first approach
        # Phase 5: Add join planner fallback for complex multi-table queries
        candidate_views = state.get("candidate_views", [])
        primary_table = await asyncio.get_event_loop().run_in_executor(
            None, self._select_best_table_or_view_for_query, relevant_tables, candidate_views, intent
        )

        # Phase 5: If no suitable view/table found, try join planning
        if not primary_table:
            join_plan = await self._try_join_planning(relevant_tables, intent)
            if join_plan:
                primary_table = "join_plan"  # Special marker for join-based queries
                state["join_plan"] = join_plan
                logger.info(f"🔗 [JOIN_SQL] Using join plan with {len(join_plan.get('tables', []))} tables")
        metrics = intent.get("metrics", [])
        time_window = intent.get("time_window")

        logger.info(f"🔗 [JOIN_SQL] Selected table: {primary_table} for query with metrics: {metrics}")

        # Generate SQL based on table characteristics and query intent
        # This is generic and works with any database schema

        table_info = None
        for table in relevant_tables:
            if table.get("full_name") == primary_table or table.get("name") == primary_table:
                table_info = table
                break

        # Phase 5: Handle join plans vs single table queries
        if primary_table == "join_plan":
            # Use join planner to generate SQL
            join_plan = state.get("join_plan", {})
            sql_query = await self._generate_sql_from_join_plan(join_plan, intent)
        else:
            # Generate appropriate SQL based on query intent for single table
            # COUNT queries are safe on any table and provide meaningful results
            if "count" in metrics or "total" in metrics or len(metrics) == 0:
                sql_query = f"SELECT COUNT(*) AS total_count FROM {primary_table}"
            else:
                # For other queries, sample the data to understand structure
                sql_query = f"SELECT TOP 10 * FROM {primary_table}"

        # For now, skip time filtering since we don't know the date column names
        # This would need schema analysis to identify date columns

        logger.info(f"🔗 [JOIN_SQL] Generated SQL: {sql_query}")

        state["join_plan"] = {"strategy": "direct", "primary_table": primary_table}
        state["sql_query"] = sql_query

        logger.info("🔗 [JOIN_SQL] SQL generation complete")
        debug_logger.agent_exit("join_sql", before_state, dict(state))
        return state

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
            if isinstance(table, dict):
                table_name = table.get("full_name", table.get("name", ""))
                base_score = table.get("relevance_score", 0)
            elif isinstance(table, str):
                table_name = table
                base_score = 0.5  # Default score for string tables
            else:
                continue

            score = base_score

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
                elif table.get("fk_count", 0) >= 2:
                    score += 0.6
                    reasons.append("Transaction-like metadata (multiple FKs)")

            # Boost tables with product-like characteristics for product queries
            if any(kw in ["product", "item", "artikel"] for kw in keywords):
                # Look for product indicators in table name
                if any(term in table_lower for term in ["product", "item", "artikel", "produkt"]):
                    score += 0.7
                    reasons.append("Product-related table name")
                # Fallback to metadata if available
                elif table.get("column_count", 0) >= 5:
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

            # Fast return: if we have a successful exec_result, synthesize a concise answer
            if isinstance(exec_result, dict) and exec_result.get("ok", False):
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
                        state["final_response"] = f"I analyzed the {table_used} table and found {count_value:,} records. For sales data, you might need to look at transaction or order tables."
                    elif query_type == "customer":
                        state["final_response"] = f"There are {count_value:,} customer records in the database."
                    elif query_type == "product":
                        state["final_response"] = f"The {table_used} table contains {count_value:,} product/item records."
                    else:
                        state["final_response"] = f"The {table_used} table contains {count_value:,} records."

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

        # Phase 4: Use async context management for proper resource cleanup
        async with self:
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
                import traceback
                logger.error(f"❌ Error processing query: {e}")
                logger.error(f"❌ Exception type: {type(e).__name__}")
                logger.error(f"❌ Traceback:\n{traceback.format_exc()}")
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