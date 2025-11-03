"""
Multi-Agent Orchestrator - ACTIVE PRODUCTION SYSTEM (Phase 8)

Composes 4 specialized agents to answer any ERP question:
1. DiscoveryAgent: Finds relevant tables/views (Scout mode, semantic ranking, role-based)
2. JoinPlanAndSQLAgent: Plans joins and generates MSSQL queries (views-first strategy, FK analysis)
3. ExecAndRecoveryAgent: Executes safely and recovers from errors (row caps, timeouts, repair logic)
4. AnswerAgent: Formats results naturally (1-2 sentence summaries)

This orchestrator replaces the monolithic DatabaseWorkflow with a modular, composable design
that enables better reasoning, testability, and maintenance.

ARCHITECTURE CHANGE (ADR-0019):
- BEFORE: Single DatabaseWorkflow class (12+ methods, mixed concerns)
- AFTER: 4 specialized agents composed by orchestrator (separation of concerns)
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
from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.mcp_client import MCPDatabaseTool

logger = logging.getLogger(__name__)


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
        logger.info("🚀 Initializing multi-agent orchestrator...")
        
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
        logger.info("📚 Indexing database...")

        try:
            # Check MCP health
            is_healthy = await self.mcp.health_check()
            if not is_healthy:
                error = {
                    "type": "MCP_UNAVAILABLE",
                    "message": "MCP server is not responding"
                }
                logger.error(f"❌ {error['message']}")
                return {**state, "error_info": error}

            logger.info("✅ Database indexed, MCP available")
            return state

        except Exception as e:
            error = {
                "type": "INDEX_ERROR",
                "message": f"Failed to index database: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _parse_intent_node(self, state: BaseState) -> BaseState:
        """
        Parse user intent to determine operation type and entities.
        
        Returns: {operation, entities, filters, time_window, ...}
        """
        logger.info("🧠 Parsing intent...")

        user_input = state.get("user_input", "")
        messages = state.get("messages", [])

        if not user_input:
            error = {
                "type": "NO_INPUT",
                "message": "No user input provided"
            }
            return {**state, "error_info": error}

        try:
            # Simple intent parsing (can be enhanced with LLM)
            intent = self._simple_intent_parser(user_input)
            logger.info(f"✅ Intent parsed: operation={intent['operation']}")
            state["intent"] = intent
            return state

        except Exception as e:
            error = {
                "type": "INTENT_PARSE_ERROR",
                "message": f"Failed to parse intent: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _route_operation_node(self, state: BaseState) -> BaseState:
        """Routing node (actual routing done via conditional_edges)."""
        return state

    # ============= Agent nodes (subgraph invocations) =============

    async def _discovery_node(self, state: BaseState) -> BaseState:
        """
        Run DiscoveryAgent subgraph.
        
        Finds relevant tables/views using Scout semantic search, ranks by role coverage.
        Output: relevant_tables, schema_snippet, candidate_views, column_index
        """
        logger.info("🔍 Running DiscoveryAgent...")

        try:
            # Build and run discovery subgraph
            discovery_graph = self.discovery_agent.build_subgraph()

            # Invoke with input state using async API
            result = await discovery_graph.ainvoke(state)

            # Extract outputs and update state
            state["relevant_tables"] = result.get("relevant_tables", [])
            state["schema_snippet"] = result.get("schema_snippet", "")
            state["candidate_views"] = result.get("candidate_views", [])
            state["column_index"] = result.get("column_index", {})
            state["session_described_tables"] = result.get(
                "session_described_tables",
                state.get("session_described_tables", {})
            )

            if result.get("error_info"):
                state["error_info"] = result["error_info"]

            logger.info(
                f"✅ Discovery complete: {len(result.get('relevant_tables', []))} table(s), "
                f"{len(result.get('candidate_views', []))} view(s)"
            )
            return state

        except Exception as e:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": f"Discovery agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _join_sql_node(self, state: BaseState) -> BaseState:
        """
        Run JoinPlanAndSQLAgent subgraph.
        
        Plans joins (views-first strategy, FK relationships) and generates MSSQL.
        Output: join_plan, sql_query
        """
        logger.info("📋 Running JoinPlanAndSQLAgent...")

        # Check for prior errors
        if state.get("error_info"):
            logger.warning("  Prior error detected, skipping join planning")
            return state

        try:
            # Build and run join_sql subgraph
            join_sql_graph = self.join_sql_agent.build_subgraph()

            # Invoke with input state using async API
            result = await join_sql_graph.ainvoke(state)

            # Extract outputs
            state["join_plan"] = result.get("join_plan", {})
            state["sql_query"] = result.get("sql_query", "")

            if result.get("error_info"):
                state["error_info"] = result["error_info"]

            logger.info(f"✅ JoinSQL complete: {len(result.get('sql_query', ''))} char SQL")
            return state

        except Exception as e:
            error = {
                "type": "JOIN_SQL_ERROR",
                "message": f"JoinSQL agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _exec_recovery_node(self, state: BaseState) -> BaseState:
        """
        Run ExecAndRecoveryAgent subgraph.
        
        Executes query safely (row caps, timeouts) and recovers from errors via LLM repair.
        Output: exec_result, error_info, retry_count
        """
        logger.info("🚀 Running ExecAndRecoveryAgent...")

        # Check for prior errors
        if state.get("error_info"):
            logger.warning("  Prior error detected, will attempt recovery")

        try:
            # Build and run exec_recovery subgraph
            exec_recovery_graph = self.exec_recovery_agent.build_subgraph()

            # Invoke with input state using async API
            result = await exec_recovery_graph.ainvoke(state)

            # Extract outputs
            state["exec_result"] = result.get("exec_result", {})
            state["sql_query"] = result.get("sql_query", state.get("sql_query", ""))
            state["retry_count"] = result.get("retry_count", 0)

            if result.get("error_info"):
                state["error_info"] = result["error_info"]

            if state.get("exec_result", {}).get("ok"):
                logger.info(
                    f"✅ Execution complete: {state['exec_result'].get('row_count', 0)} rows, "
                    f"{state['exec_result'].get('execution_time_ms', 0)}ms"
                )
            else:
                logger.warning("⚠️  Execution failed, error_info set for answer agent")

            return state

        except Exception as e:
            error = {
                "type": "EXEC_ERROR",
                "message": f"Execution agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _answer_node(self, state: BaseState) -> BaseState:
        """
        Run AnswerAgent subgraph (general result formatting).
        
        Formats successful results, errors, or clarification requests as natural language.
        Output: final_response
        """
        logger.info("✨ Running AnswerAgent...")

        try:
            # Build and run answer subgraph
            answer_graph = self.answer_agent.build_subgraph()

            # Invoke with input state using async API
            result = await answer_graph.ainvoke(state)

            # Extract outputs
            state["final_response"] = result.get("final_response", "No response generated")

            logger.info("✅ Answer formatted")
            return state

        except Exception as e:
            error = {
                "type": "ANSWER_ERROR",
                "message": f"Answer agent failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            state["final_response"] = f"Error formatting response: {str(e)}"
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

    def _simple_intent_parser(self, user_input: str) -> Dict[str, Any]:
        """
        Simple intent parsing (can be enhanced with LLM).
        
        Returns: {operation, entities, filters, ...}
        """
        user_lower = user_input.lower()

        # Check for schema query
        schema_keywords = [
            "what table", "schema", "database structure", "what columns",
            "what fields", "list table", "how many table"
        ]
        if any(kw in user_lower for kw in schema_keywords):
            return {"operation": "schema_query", "entities": []}

        # Check for health check
        health_keywords = [
            "health", "status", "working", "running", "online", "available"
        ]
        if any(kw in user_lower for kw in health_keywords):
            return {"operation": "health_check", "entities": []}

        # Default: query operation
        # Extract entities (simple heuristic)
        entities = []
        words = user_input.split()
        for word in words:
            if len(word) > 3 and word not in ["show", "how", "many", "with", "from", "into"]:
                entities.append(word.strip("?,.!"))

        return {
            "operation": "query",
            "entities": entities[:3],
            "filters": {},
            "time_window": None
        }

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