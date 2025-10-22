"""
Orchestrator Graph - Composes the 4 specialized agents.

Main workflow:
1. Index database (Scout catalog)
2. Parse intent
3. Route by operation:
   - clarify → AnswerAgent(clarify) → END
   - schema_query → DiscoveryAgent(schema) → AnswerAgent(schema_explain) → END
   - health_check → AnswerAgent(health) → END
   - query → DiscoveryAgent → JoinPlanAndSQLAgent → ExecAndRecoveryAgent → AnswerAgent → END
   - execute_direct → ExecAndRecoveryAgent → AnswerAgent → END

All agents communicate through BaseState with strict input/output contracts.
"""

import logging
import json
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
    
    Replaces the monolithic LangGraph with modular, composable agent workflow.
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
            max_joins: Maximum joins allowed (JoinPlanAndSQLAgent)
            max_retries: Maximum retry attempts (ExecAndRecoveryAgent)
            row_limit: Default row limit for queries
            query_timeout_seconds: Query timeout in seconds
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.mcp = MCPDatabaseTool()

        # Initialize agents
        self.discovery_agent = DiscoveryAgent(llm_model=llm_model, llm_temp=llm_temp)
        self.join_sql_agent = JoinPlanAndSQLAgent(
            llm_model=llm_model,
            llm_temp=llm_temp,
            max_joins=max_joins,
            row_limit=row_limit,
            query_timeout_seconds=query_timeout_seconds
        )
        self.exec_recovery_agent = ExecAndRecoveryAgent(
            llm_model=llm_model,
            llm_temp=llm_temp,
            max_retries=max_retries,
            row_limit=row_limit,
            query_timeout_seconds=query_timeout_seconds
        )
        self.answer_agent = AnswerAgent(llm_model=llm_model, llm_temp=llm_temp)

    def build_graph(self) -> StateGraph:
        """
        Build the complete orchestrator graph.
        
        Returns:
            Compiled LangGraph StateGraph
        """
        graph = StateGraph(BaseState)

        # Define nodes
        graph.add_node("index_database", self._index_database_node)
        graph.add_node("parse_intent", self._parse_intent_node)
        graph.add_node("route_operation", self._route_operation_node)

        # Agent nodes
        graph.add_node("discovery", self._discovery_node)
        graph.add_node("join_sql", self._join_sql_node)
        graph.add_node("exec_recovery", self._exec_recovery_node)
        graph.add_node("answer", self._answer_node)

        # Special operation nodes
        graph.add_node("answer_schema", self._answer_schema_node)
        graph.add_node("answer_health", self._answer_health_node)
        graph.add_node("answer_error", self._answer_error_node)

        # Linear path: index → parse → route
        graph.add_edge(START, "index_database")
        graph.add_edge("index_database", "parse_intent")
        graph.add_edge("parse_intent", "route_operation")

        # Routing from parse_intent
        def route_operation(state: BaseState) -> str:
            intent = state.get("intent", {})
            operation = intent.get("operation", "query")

            logger.info(f"🚦 Routing by operation: {operation}")

            if operation == "clarify":
                return "answer"  # Ask for clarification
            elif operation == "schema_query":
                return "discovery"  # Then answer_schema
            elif operation == "health_check":
                return "answer_health"
            elif operation == "execute_direct":
                return "exec_recovery"  # SQL provided by parser
            elif operation == "error":
                return "answer_error"
            else:
                # Default: query → discovery → join_sql → exec → answer
                return "discovery"

        graph.add_conditional_edges("route_operation", route_operation)

        # Query flow: discovery → join_sql → exec_recovery → answer
        graph.add_edge("discovery", "join_sql")
        graph.add_edge("join_sql", "exec_recovery")
        graph.add_edge("exec_recovery", "answer")

        # Schema flow: discovery → answer_schema
        graph.add_edge("discovery", "answer_schema")

        # Terminal nodes
        graph.add_edge("answer", END)
        graph.add_edge("answer_schema", END)
        graph.add_edge("answer_health", END)
        graph.add_edge("answer_error", END)

        return graph.compile()

    # ============= Node implementations =============

    async def _index_database_node(self, state: BaseState) -> BaseState:
        """
        Load Scout catalog (existing index_database logic).
        
        Initializes MCP connection and loads metadata.
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

            logger.info("✅ Database indexed and MCP available")
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
        Parse user intent (existing parse_intent logic).
        
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

    async def _discovery_node(self, state: BaseState) -> BaseState:
        """Run DiscoveryAgent subgraph."""
        logger.info("🔍 Running DiscoveryAgent...")

        try:
            # Build and run discovery subgraph
            discovery_graph = await self.discovery_agent.build_subgraph()

            # Invoke with input state
            result = discovery_graph.invoke(state)

            # Extract outputs
            state["relevant_tables"] = result.get("relevant_tables")
            state["schema_snippet"] = result.get("schema_snippet")
            state["candidate_views"] = result.get("candidate_views")
            state["session_described_tables"] = result.get("session_described_tables", state.get("session_described_tables", {}))

            if result.get("error_info"):
                state["error_info"] = result["error_info"]

            logger.info(f"✅ Discovery complete: {len(result.get('relevant_tables', []))} table(s)")
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
        """Run JoinPlanAndSQLAgent subgraph."""
        logger.info("📋 Running JoinPlanAndSQLAgent...")

        # Check for prior errors
        if state.get("error_info"):
            logger.warning("  Prior error detected, skipping join planning")
            return state

        try:
            # Build and run join_sql subgraph
            join_sql_graph = await self.join_sql_agent.build_subgraph()

            # Invoke with input state
            result = join_sql_graph.invoke(state)

            # Extract outputs
            state["join_plan"] = result.get("join_plan")
            state["sql_query"] = result.get("sql_query")

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
        """Run ExecAndRecoveryAgent subgraph."""
        logger.info("🚀 Running ExecAndRecoveryAgent...")

        # Check for prior errors
        if state.get("error_info"):
            logger.warning("  Prior error detected, will attempt recovery")

        try:
            # Build and run exec_recovery subgraph
            exec_recovery_graph = await self.exec_recovery_agent.build_subgraph()

            # Invoke with input state
            result = exec_recovery_graph.invoke(state)

            # Extract outputs
            state["exec_result"] = result.get("exec_result")
            state["sql_query"] = result.get("sql_query", state.get("sql_query"))
            state["retry_count"] = result.get("retry_count", 0)

            if result.get("error_info"):
                state["error_info"] = result["error_info"]

            if state.get("exec_result", {}).get("ok"):
                logger.info(f"✅ Execution complete: {state['exec_result'].get('row_count', 0)} rows")
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
        """Run AnswerAgent subgraph (general result formatting)."""
        logger.info("✨ Running AnswerAgent...")

        try:
            # Build and run answer subgraph
            answer_graph = await self.answer_agent.build_subgraph()

            # Invoke with input state
            result = answer_graph.invoke(state)

            # Extract outputs
            state["final_response"] = result.get("final_response", "No response generated")

            logger.info(f"✅ Answer formatted")
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

    async def _answer_schema_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for schema explanation."""
        logger.info("📚 Answering schema question...")

        # Set operation to schema_query so AnswerAgent knows to explain
        state.setdefault("intent", {})["operation"] = "schema_query"

        # Run answer agent
        return await self._answer_node(state)

    async def _answer_health_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for health check."""
        logger.info("🏥 Checking health...")

        try:
            # Get health info from MCP
            is_healthy = await self.mcp.health_check()

            state["health_status"] = {
                "ok": is_healthy,
                "db_connected": is_healthy,
                "tables_count": 0,  # TODO: get from catalog
                "views_count": 0,   # TODO: get from catalog
                "timestamp": None
            }

            # Set operation to health_check
            state.setdefault("intent", {})["operation"] = "health_check"

            # Run answer agent
            return await self._answer_node(state)

        except Exception as e:
            error = {
                "type": "HEALTH_CHECK_ERROR",
                "message": f"Health check failed: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    async def _answer_error_node(self, state: BaseState) -> BaseState:
        """Route to AnswerAgent for error formatting."""
        logger.info("❌ Formatting error...")

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
        schema_keywords = ["what table", "schema", "database structure", "what columns", "what fields", "list table", "how many table"]
        if any(kw in user_lower for kw in schema_keywords):
            return {"operation": "schema_query", "entities": []}

        # Check for health check
        health_keywords = ["health", "status", "working", "running", "online", "available"]
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


# Export functions for easy usage

async def create_orchestrator(
    llm_model: str = "gpt-4o",
    max_joins: int = 3,
    max_retries: int = 2
) -> QueryOrchestrator:
    """Factory function to create QueryOrchestrator."""
    return QueryOrchestrator(
        llm_model=llm_model,
        max_joins=max_joins,
        max_retries=max_retries
    )


async def build_orchestrator_graph(orchestrator: QueryOrchestrator):
    """Build and compile the orchestrator graph."""
    return orchestrator.build_graph()