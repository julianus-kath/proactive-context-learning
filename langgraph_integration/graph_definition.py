"""
LangGraph Workflow Definition for MCP Database Integration
Phase 2 Blueprint Implementation
Phase 5 Enhancement: MCP-only orchestration with discovery tools

This module defines the LangGraph workflow that:
1. Parses user intent
2. Uses MCP discovery tools for progressive schema exploration
3. Generates safe SQL via LLM with schema_snippet (≤3 tables)
4. Executes queries via query_bounded
5. Formats results back to the user
"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .mcp_client import (
    # Legacy functions (deprecated in Phase 5)
    get_database_schema, 
    execute_sql_query, 
    execute_sql_query_with_retry,
    get_table_information, 
    health_check,
    index_database,
    get_all_schemas,
    get_schema_index,
    get_selective_schema,
    # PHASE 5: New MCP discovery tool functions
    list_tables_mcp,
    search_tables_mcp,
    describe_table_mcp,
    describe_table_batch,
    list_relations_mcp,
    query_bounded_mcp,
    build_schema_snippet
)
from .prompts import (
    format_intent_parser_prompt,
    format_sql_generator_prompt,
    format_result_formatter_prompt,
    format_error_handler_prompt,
    format_schema_explainer_prompt,
    format_sample_data_prompt,
    format_health_check_prompt
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import debug logger for comprehensive logging
try:
    from .debug_logger import get_debug_logger
    debug_logger = get_debug_logger()
except ImportError:
    debug_logger = None

# State definition for the workflow
class WorkflowState(TypedDict):
    """
    State for the LangGraph workflow.
    
    PHASE 5 ENHANCEMENT: Added schema_snippet and session_described_tables
    for MCP-only orchestration with progressive discovery.
    """
    messages: List[Dict[str, Any]]
    user_input: str
    intent_analysis: Optional[Dict[str, Any]]
    schema: Optional[str]  # DEPRECATED: Use schema_snippet instead
    schema_snippet: Optional[str]  # PHASE 5: Compact schema (≤3 tables)
    database_index: Optional[Dict[str, Any]]
    sql_query: Optional[str]
    query_results: Optional[str]
    error_info: Optional[Dict[str, Any]]
    final_response: Optional[str]
    retry_count: int
    # PHASE 5: Session management for discovery tools
    session_described_tables: Optional[Dict[str, Dict[str, Any]]]  # Cache of described tables
    relevant_tables: Optional[List[str]]  # Tables selected for current query
    is_schema_query: Optional[bool]  # True if user is asking about schema/tables


@dataclass
class IntentAnalysis:
    """Structure for intent analysis results."""
    operation: str
    entities: List[str]
    requirements: str
    confidence: float = 1.0




class DatabaseWorkflow:
    """
    LangGraph workflow for database interactions via MCP server.
    
    This class implements the Phase 2 Blueprint workflow that parses user intent,
    generates SQL, calls the MCP server, and formats results.
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        """
        Initialize the database workflow.
        
        Args:
            model_name: OpenAI model to use
            temperature: Temperature for LLM responses
        """
        # Ensure environment variables are loaded
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
        
        # Verify API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        try:
            self.llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)
            # Test the API key with a simple call
            logger.info("Testing OpenAI API key...")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise ValueError(f"OpenAI API key is invalid or expired: {e}")
        
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow.
        
        Returns:
            Compiled StateGraph workflow
        """
        # Create the workflow graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("index_database", self._index_database)
        workflow.add_node("parse_intent", self._parse_intent)
        workflow.add_node("clarify", self._clarify)
        workflow.add_node("get_schema", self._get_schema)
        workflow.add_node("select_tables", self._select_tables)  # PHASE 1: New node
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("execute_direct", self._execute_direct)
        workflow.add_node("retry_query", self._retry_query)
        workflow.add_node("format_results", self._format_results)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("explain_schema", self._explain_schema)
        workflow.add_node("show_sample_data", self._show_sample_data)
        workflow.add_node("health_check", self._health_check)
        
        # Define the workflow edges - index database first, then get schema for informed intent parsing
        workflow.add_edge(START, "index_database")
        workflow.add_edge("index_database", "get_schema")
        workflow.add_edge("get_schema", "parse_intent")
        workflow.add_conditional_edges(
            "parse_intent",
            self._route_after_intent,
            {
                "clarify": "clarify",
                "query": "select_tables",  # PHASE 1: Route to table selection first
                "execute_direct": "execute_direct",
                "schema_query": "explain_schema",
                "data_query": "select_tables",  # PHASE 1: Route to table selection first
                "analysis_query": "select_tables",  # PHASE 1: Route to table selection first
                "sample_data": "show_sample_data",
                "health_check": "health_check",
                "error": "handle_error"
            }
        )
        
        # PHASE 1: Table selection before SQL generation
        workflow.add_edge("select_tables", "generate_sql")
        
        # Schema query path
        workflow.add_edge("explain_schema", "format_results")
        
        # Data/analysis query path (schema already retrieved)
        workflow.add_conditional_edges(
            "generate_sql",
            self._route_after_sql_generation,
            {
                "execute": "execute_query",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "execute_query",
            self._route_after_execution,
            {
                "format": "format_results",
                "retry": "retry_query",
                "error": "handle_error"
            }
        )
        
        # Sample data path
        workflow.add_edge("show_sample_data", "format_results")
        
        # Health check path
        workflow.add_edge("health_check", "format_results")
        
        # Retry query path
        workflow.add_conditional_edges(
            "retry_query",
            self._route_after_retry,
            {
                "format": "format_results",
                "error": "handle_error"
            }
        )
        
        # Direct execution path (when SQL is provided by intent parser)
        workflow.add_conditional_edges(
            "execute_direct",
            self._route_after_execution,
            {
                "format": "format_results",
                "retry": "retry_query",
                "error": "handle_error"
            }
        )
        
        # Clarification path
        workflow.add_edge("clarify", END)
        
        # All paths end at format_results, handle_error, or clarify
        workflow.add_edge("format_results", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def _index_database(self, state: WorkflowState) -> WorkflowState:
        """
        Index the database on startup to discover all schemas and tables.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with database index information
        """
        try:
            database_index = await index_database()
            state["database_index"] = database_index
            
            # Log the indexing results
            total_tables = database_index.get("total_tables", 0)
            schemas = database_index.get("schemas", [])
            logger.info(f"Database indexed: {total_tables} tables across {len(schemas)} schemas: {', '.join(schemas)}")
            
        except Exception as e:
            logger.error(f"Error indexing database: {e}")
            state["error_info"] = {
                "type": "database_indexing_error",
                "message": str(e),
                "context": "Failed to index database on startup"
            }
        
        return state
    
    async def _parse_intent(self, state: WorkflowState) -> WorkflowState:
        """
        Parse user intent from conversation context and decide whether to clarify or query.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with intent analysis
        """
        try:
            # Use the full conversation messages and schema for context-aware intent parsing
            messages = state.get("messages", [])
            schema = state.get("schema", "No schema available")
            
            # Get last user message for logging
            last_user_msg = ""
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break
                elif hasattr(msg, "type") and msg.type == "user":
                    last_user_msg = str(msg.content)
                    break
            
            prompt = format_intent_parser_prompt(messages, schema)
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            
            # Parse the JSON response to extract intent information
            intent_text = response.content
            intent_analysis = self._parse_intent_json_response(intent_text)
            
            state["intent_analysis"] = intent_analysis
            
            # Log the decision with comprehensive debug information
            if debug_logger:
                operation = intent_analysis.get("operation", "unknown")
                missing_fields = intent_analysis.get("missing_fields", [])
                entities = intent_analysis.get("entities", [])
                
                debug_logger.intent_parsed(
                    last_user_msg,
                    operation,
                    intent_analysis.get("confidence", 1.0),
                    missing_fields=missing_fields if missing_fields else None,
                    entities=entities if entities else None
                )
            
            # Log the decision
            if intent_analysis["operation"] == "clarify":
                logger.info(f"Intent: CLARIFY - Missing: {intent_analysis.get('missing_fields', [])}")
            else:
                logger.info(f"Intent: QUERY - SQL: {intent_analysis.get('sql', 'N/A')[:50]}...")
            
        except Exception as e:
            logger.error(f"Error parsing intent: {e}")
            if debug_logger:
                debug_logger.workflow_error("intent_parsing_error", str(e))
            state["error_info"] = {
                "type": "intent_parsing_error",
                "message": str(e),
                "context": "Failed to parse user intent"
            }
        
        return state
    
    def _parse_intent_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the intent analysis response from the LLM.
        
        Args:
            response_text: Raw response from the LLM
            
        Returns:
            Structured intent analysis
        """
        # Simple parsing - in production, you might want more robust parsing
        lines = response_text.strip().split('\n')
        
        operation = "DATA_QUERY"  # default
        entities = []
        requirements = ""
        
        for line in lines:
            if line.startswith("Operation:"):
                operation = line.split(":", 1)[1].strip()
            elif line.startswith("Entities:"):
                entities_text = line.split(":", 1)[1].strip()
                entities = [e.strip().strip('[]') for e in entities_text.split(",") if e.strip()]
            elif line.startswith("Requirements:"):
                requirements = line.split(":", 1)[1].strip()
        
        return {
            "operation": operation,
            "entities": entities,
            "requirements": requirements
        }
    
    def _parse_intent_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the JSON intent analysis response from the LLM.
        
        Args:
            response_text: Raw JSON response from the LLM
            
        Returns:
            Structured intent analysis with operation, sql, missing_fields, etc.
        """
        import json
        import re
        
        try:
            # Try to extract JSON from the response
            # Look for JSON block in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                
                # Ensure required fields exist
                result = {
                    "operation": parsed.get("operation", "query"),
                    "reasoning": parsed.get("reasoning", ""),
                }
                
                if result["operation"] == "clarify":
                    result["missing_fields"] = parsed.get("missing_fields", [])
                else:
                    result["sql"] = parsed.get("sql", "")
                    # Convert to old format for compatibility
                    result["entities"] = []
                    result["requirements"] = result["reasoning"]
                
                return result
                
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            
        # Fallback to old parsing method
        return self._parse_intent_response(response_text)
    
    async def _get_schema(self, state: WorkflowState) -> WorkflowState:
        """
        Get database schema overview using MCP discovery tools (Phase 5).
        
        PHASE 5: Instead of full schema dump, we get a lightweight table list
        for intent parsing. Detailed schema is fetched later via describe_table.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with lightweight schema overview
        """
        try:
            # Initialize session cache if not present
            if state.get("session_described_tables") is None:
                state["session_described_tables"] = {}
            
            # Get first page of tables for overview (lightweight)
            tables_response = await list_tables_mcp(page=1, page_size=50)
            
            if tables_response.get("ok"):
                tables = tables_response.get("data", {}).get("tables", [])
                pagination = tables_response.get("data", {}).get("pagination", {})
                
                # Build lightweight schema overview (just table names and row counts)
                schema_lines = ["Available Tables:"]
                for table in tables:
                    full_name = table.get("full_name", "")
                    row_count = table.get("row_count", 0)
                    schema_lines.append(f"  - {full_name} ({row_count} rows)")
                
                total_tables = pagination.get("total_items", len(tables))
                if total_tables > len(tables):
                    schema_lines.append(f"\n... and {total_tables - len(tables)} more tables")
                    schema_lines.append("Use search_tables or list_tables with filters to explore more.")
                
                state["schema"] = "\n".join(schema_lines)
                logger.info(f"Schema overview retrieved: {len(tables)} tables shown (of {total_tables} total)")
            else:
                error_msg = tables_response.get("error", "Unknown error")
                logger.error(f"Error getting table list: {error_msg}")
                state["schema"] = "Schema information unavailable"
            
        except Exception as e:
            logger.error(f"Error getting schema overview: {e}")
            state["error_info"] = {
                "type": "schema_retrieval_error",
                "message": str(e),
                "context": "Failed to retrieve database schema overview"
            }
            state["schema"] = "Schema information unavailable"
        
        return state
    
    async def _select_tables(self, state: WorkflowState) -> WorkflowState:
        """
        Select relevant tables using MCP search_tables (Phase 5).
        
        PHASE 5: Uses search_tables to find relevant tables based on keywords
        extracted from user query. Then calls describe_table for ≤3 tables
        to build a compact schema_snippet.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with schema_snippet (≤3 tables)
        """
        try:
            user_input = state["user_input"]
            session_cache = state.get("session_described_tables", {})
            
            # Extract keywords from user query (simple heuristic)
            # Remove common words and extract potential table/column names
            stop_words = {"what", "how", "many", "show", "get", "find", "list", "the", "a", "an", "in", "on", "at", "from", "to", "for", "of", "with"}
            words = user_input.lower().split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            
            if not keywords:
                # Fallback: use first few words
                keywords = words[:3]
            
            # Search for relevant tables using MCP search_tables
            search_keyword = " ".join(keywords[:2])  # Use first 2 keywords
            logger.info(f"Searching tables with keyword: '{search_keyword}'")
            
            search_response = await search_tables_mcp(search_keyword, page=1, page_size=5)
            
            if search_response.get("ok"):
                results = search_response.get("data", {}).get("results", [])
                
                # Extract top 3 table names
                relevant_tables = []
                for result in results[:3]:
                    table_name = result.get("full_name", "")
                    if table_name:
                        relevant_tables.append(table_name)
                
                state["relevant_tables"] = relevant_tables
                logger.info(f"Found {len(relevant_tables)} relevant tables: {relevant_tables}")
                
                # Describe tables (use cache if available)
                tables_to_describe = []
                for table_name in relevant_tables:
                    if table_name not in session_cache:
                        tables_to_describe.append(table_name)
                
                # Fetch descriptions for new tables
                if tables_to_describe:
                    logger.info(f"Describing {len(tables_to_describe)} new tables: {tables_to_describe}")
                    new_descriptions = await describe_table_batch(tables_to_describe)
                    session_cache.update(new_descriptions)
                    state["session_described_tables"] = session_cache
                else:
                    logger.info(f"All {len(relevant_tables)} tables already in session cache")
                
                # Build schema snippet from cached descriptions
                table_descriptions = {t: session_cache[t] for t in relevant_tables if t in session_cache}
                schema_snippet = build_schema_snippet(table_descriptions)
                state["schema_snippet"] = schema_snippet
                
                logger.info(f"Built schema snippet ({len(schema_snippet)} chars) for {len(table_descriptions)} tables")
            else:
                error_msg = search_response.get("error", "Unknown error")
                logger.warning(f"Search failed: {error_msg}, using lightweight schema")
                state["schema_snippet"] = state.get("schema", "No schema available")
            
        except Exception as e:
            logger.error(f"Error selecting tables: {e}")
            # Fallback to lightweight schema overview
            state["schema_snippet"] = state.get("schema", "No schema available")
            logger.info("Falling back to schema overview")
        
        return state
    
    async def _generate_sql(self, state: WorkflowState) -> WorkflowState:
        """
        Generate SQL query based on intent and schema_snippet (Phase 5).
        
        PHASE 5: Uses compact schema_snippet (≤3 tables) instead of full schema.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with generated SQL
        """
        try:
            intent = state["intent_analysis"]
            
            # Check if SQL was already provided by the intent parser
            if "sql" in intent and intent["sql"]:
                state["sql_query"] = intent["sql"]
                logger.info(f"Using SQL from intent parser: {intent['sql']}")
                if debug_logger:
                    debug_logger.sql_generated(
                        intent["sql"],
                        "Provided by intent parser",
                        table_context=intent.get("tables", [])
                    )
                return state
            
            # PHASE 5: Use schema_snippet instead of full schema
            schema_snippet = state.get("schema_snippet", state.get("schema", "No schema available"))
            user_input = state["user_input"]
            
            prompt = format_sql_generator_prompt(
                schema=schema_snippet,  # Use compact snippet
                operation=intent.get("operation", "DATA_QUERY"),
                entities=intent.get("entities", []),
                requirements=intent.get("requirements", ""),
                user_input=user_input
            )
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            sql_query = self._extract_sql_from_response(response.content)
            
            state["sql_query"] = sql_query
            logger.info(f"SQL generated: {sql_query}")
            
            # Log SQL generation with comprehensive information
            if debug_logger:
                tables_used = state.get("relevant_tables", [])
                reason = f"Intent: {intent.get('operation', 'unknown')}"
                if intent.get("entities"):
                    reason += f", Entities: {', '.join(intent.get('entities', []))}"
                
                debug_logger.sql_generated(
                    sql_query,
                    reason,
                    table_context=tables_used if tables_used else None
                )
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            if debug_logger:
                debug_logger.workflow_error("sql_generation_error", str(e))
            state["error_info"] = {
                "type": "sql_generation_error",
                "message": str(e),
                "context": "Failed to generate SQL query"
            }
        
        return state
    
    def _extract_sql_from_response(self, response_text: str) -> str:
        """
        Extract SQL query from LLM response.
        
        Args:
            response_text: Raw response from the LLM
            
        Returns:
            Extracted SQL query
        """
        # Look for SQL query in the response
        lines = response_text.strip().split('\n')
        sql_lines = []
        in_sql_block = False
        
        for line in lines:
            if '```sql' in line.lower():
                in_sql_block = True
                continue
            elif '```' in line and in_sql_block:
                break
            elif in_sql_block:
                sql_lines.append(line)
            elif line.strip().upper().startswith(('SELECT', 'WITH')):
                # Direct SQL without code block
                sql_lines.append(line)
        
        if sql_lines:
            return '\n'.join(sql_lines).strip()
        
        # Fallback: return the whole response if no SQL block found
        return response_text.strip()
    
    async def _execute_query(self, state: WorkflowState) -> WorkflowState:
        """
        Execute SQL query via MCP query_bounded (Phase 5).
        
        PHASE 5: Uses query_bounded for all query execution with safety controls.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with query results
        """
        try:
            import time
            sql_query = state["sql_query"]
            start_time = time.time()
            
            # PHASE 5: Use query_bounded_mcp instead of execute_sql_query
            results = await query_bounded_mcp(sql_query, max_rows=1000, timeout_ms=30000)
            duration_ms = (time.time() - start_time) * 1000
            
            # Check if the result indicates an error
            if results.startswith("Error") or results.startswith("QUERY_ERROR:"):
                error_msg = results[12:]  # Remove "QUERY_ERROR:" prefix
                state["error_info"] = {
                    "type": "query_execution_error",
                    "message": error_msg,
                    "context": f"Failed to execute SQL: {sql_query}",
                    "sql_query": sql_query
                }
                # Initialize retry count if not set
                if "retry_count" not in state:
                    state["retry_count"] = 0
                
                # Log query execution error
                if debug_logger:
                    debug_logger.query_executed(sql_query, 0, duration_ms, error=error_msg)
            else:
                state["query_results"] = results
                logger.info("Query executed successfully")
                
                # Count rows in results (rough estimate)
                rows_count = len(results.split('\n')) if results else 0
                
                # Log successful query execution
                if debug_logger:
                    debug_logger.query_executed(sql_query, rows_count, duration_ms)
                
                # PHASE 1: Track used tables for session context
                if state.get("relevant_tables"):
                    session_tables = state.get("session_used_tables", [])
                    # Add relevant tables to session (keep last 5 unique)
                    for table in state["relevant_tables"]:
                        if table not in session_tables:
                            session_tables.append(table)
                    # Keep only last 5 tables
                    state["session_used_tables"] = session_tables[-5:]
                    logger.debug(f"Session tables updated: {state['session_used_tables']}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing query: {error_msg}")
            if debug_logger:
                debug_logger.query_executed(state.get("sql_query", "unknown"), 0, 0, error=error_msg)
            state["error_info"] = {
                "type": "query_execution_error",
                "message": error_msg,
                "context": f"Failed to execute SQL: {state.get('sql_query', 'Unknown query')}"
            }
        
        return state
    
    async def _execute_direct(self, state: WorkflowState) -> WorkflowState:
        """
        Execute SQL query directly when provided by intent parser (Phase 5).
        
        PHASE 5: Uses query_bounded_mcp for execution.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with query results
        """
        try:
            # Get SQL from intent analysis
            intent = state["intent_analysis"]
            sql_query = intent.get("sql", "")
            
            if not sql_query:
                raise ValueError("No SQL query provided in intent analysis")
            
            # Store the SQL query in state for consistency
            state["sql_query"] = sql_query
            
            # PHASE 5: Execute via query_bounded_mcp
            results = await query_bounded_mcp(sql_query, max_rows=1000, timeout_ms=30000)
            
            # Check if the result indicates an error
            if results.startswith("Error") or results.startswith("QUERY_ERROR:"):
                error_msg = results.replace("QUERY_ERROR:", "").replace("Error executing query:", "").strip()
                state["error_info"] = {
                    "type": "direct_query_execution_error",
                    "message": error_msg,
                    "context": f"Failed to execute direct SQL: {sql_query}",
                    "sql_query": sql_query
                }
                # Initialize retry count if not set
                if "retry_count" not in state:
                    state["retry_count"] = 0
            else:
                state["query_results"] = results
                logger.info(f"Direct query executed successfully: {sql_query}")
            
        except Exception as e:
            logger.error(f"Error executing direct query: {e}")
            state["error_info"] = {
                "type": "direct_query_execution_error",
                "message": str(e),
                "context": f"Failed to execute direct SQL: {state.get('intent_analysis', {}).get('sql', 'Unknown query')}"
            }
        
        return state
    
    async def _retry_query(self, state: WorkflowState) -> WorkflowState:
        """
        Retry SQL query with automatic error correction (Phase 5).
        
        PHASE 5: Uses query_bounded_mcp for retry execution.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with retry results
        """
        try:
            retry_count = state.get("retry_count", 0)
            max_retries = 2
            
            if retry_count >= max_retries:
                # Max retries exceeded, keep the error
                logger.error(f"Max retries ({max_retries}) exceeded for query")
                return state
            
            # Increment retry count
            state["retry_count"] = retry_count + 1
            
            # Get the original SQL and schema
            sql_query = state.get("sql_query", "")
            schema_snippet = state.get("schema_snippet", state.get("schema", ""))
            error_info = state.get("error_info", {})
            error_msg = error_info.get("message", "")
            
            logger.info(f"Attempting to retry query (attempt {state['retry_count']}): {sql_query}")
            
            # PHASE 5: Use query_bounded_mcp for retry
            # TODO: In future, could use LLM to fix SQL based on error message
            results = await query_bounded_mcp(sql_query, max_rows=1000, timeout_ms=30000)
            
            # Check if the retry was successful
            if results.startswith("Error") or results.startswith("QUERY_ERROR:"):
                error_msg = results.replace("QUERY_ERROR:", "").replace("Error executing query:", "").strip()
                state["error_info"] = {
                    "type": "query_retry_error",
                    "message": error_msg,
                    "context": f"Failed to execute SQL after retry: {sql_query}",
                    "sql_query": sql_query,
                    "retry_count": state["retry_count"]
                }
            else:
                # Success! Clear error info and set results
                state["query_results"] = results
                state["error_info"] = None
                logger.info(f"Query retry successful after {state['retry_count']} attempts")
            
        except Exception as e:
            logger.error(f"Error in query retry: {e}")
            state["error_info"] = {
                "type": "query_retry_error",
                "message": str(e),
                "context": f"Failed during query retry process"
            }
        
        return state
    
    async def _format_results(self, state: WorkflowState) -> WorkflowState:
        """
        Format results for user presentation.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with formatted response
        """
        try:
            user_input = state["user_input"]
            
            # Handle different types of responses
            if state.get("query_results"):
                # Data query results
                prompt = format_result_formatter_prompt(
                    user_input=user_input,
                    sql_query=state["sql_query"],
                    raw_results=state["query_results"]
                )
            elif state.get("schema"):
                # Schema explanation
                prompt = format_schema_explainer_prompt(
                    schema=state["schema"],
                    user_input=user_input
                )
            else:
                # Fallback
                prompt = f"Provide a helpful response to: {user_input}"
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            state["final_response"] = response.content
            
            state["messages"].append({
                "role": "assistant",
                "content": response.content
            })
            
            logger.info("Results formatted successfully")
            
        except Exception as e:
            logger.error(f"Error formatting results: {e}")
            state["final_response"] = f"I encountered an error while formatting the results: {str(e)}"
            state["messages"].append({
                "role": "assistant",
                "content": state["final_response"]
            })
        
        return state
    
    async def _handle_error(self, state: WorkflowState) -> WorkflowState:
        """
        Handle errors and provide helpful error messages.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with error response
        """
        try:
            error_info = state.get("error_info", {})
            user_input = state["user_input"]
            
            prompt = format_error_handler_prompt(
                user_input=user_input,
                error_type=error_info.get("type", "unknown_error"),
                error_message=error_info.get("message", "Unknown error occurred"),
                context=error_info.get("context", "")
            )
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            state["final_response"] = response.content
            
            state["messages"].append({
                "role": "assistant",
                "content": response.content
            })
            
            logger.info("Error handled successfully")
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            state["final_response"] = "I'm sorry, I encountered an unexpected error. Please try again or contact support."
            state["messages"].append({
                "role": "assistant",
                "content": state["final_response"]
            })
        
        return state
    
    async def _explain_schema(self, state: WorkflowState) -> WorkflowState:
        """
        Get and explain database schema.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with schema explanation
        """
        try:
            schema = await get_database_schema()
            state["schema"] = schema
            logger.info("Schema retrieved for explanation")
            
        except Exception as e:
            logger.error(f"Error getting schema for explanation: {e}")
            state["error_info"] = {
                "type": "schema_retrieval_error",
                "message": str(e),
                "context": "Failed to retrieve database schema for explanation"
            }
        
        return state
    
    async def _show_sample_data(self, state: WorkflowState) -> WorkflowState:
        """
        Show sample data from requested table.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with sample data
        """
        try:
            intent = state["intent_analysis"]
            entities = intent.get("entities", [])
            
            # Default to customers table if no specific table mentioned
            table_name = entities[0] if entities else "customers"
            
            sample_data = await get_table_information(table_name)
            state["query_results"] = sample_data
            
            logger.info(f"Sample data retrieved for table: {table_name}")
            
        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            state["error_info"] = {
                "type": "sample_data_error",
                "message": str(e),
                "context": "Failed to retrieve sample data"
            }
        
        return state
    
    async def _health_check(self, state: WorkflowState) -> WorkflowState:
        """
        Perform system health check.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with health status
        """
        try:
            is_healthy = await self.mcp_tool.health_check()
            health_status = "System is healthy and operational" if is_healthy else "System is experiencing issues"
            
            state["query_results"] = health_status
            logger.info(f"Health check completed: {health_status}")
            
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            state["error_info"] = {
                "type": "health_check_error",
                "message": str(e),
                "context": "Failed to perform health check"
            }
        
        return state
    
    async def _clarify(self, state: WorkflowState) -> WorkflowState:
        """
        Generate a clarifying question based on missing information.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with clarification question
        """
        try:
            from .prompts import format_clarification_prompt
            
            intent = state.get("intent_analysis", {})
            missing_fields = intent.get("missing_fields", [])
            messages = state.get("messages", [])
            schema = state.get("schema", "No schema available")
            
            # Generate clarifying question with schema context
            prompt = format_clarification_prompt(messages, missing_fields, schema)
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            
            clarification = response.content
            state["final_response"] = clarification
            
            logger.info(f"Generated clarification: {clarification[:100]}...")
            
        except Exception as e:
            logger.error(f"Error generating clarification: {e}")
            state["final_response"] = "I need more information to help you. Could you please provide more details about what you're looking for?"
        
        return state
    
    def _route_after_intent(self, state: WorkflowState) -> str:
        """Route workflow after intent parsing."""
        if state.get("error_info"):
            return "error"
        
        intent = state.get("intent_analysis", {})
        operation = intent.get("operation", "DATA_QUERY")
        
        # Handle new conversation-aware operations
        if operation == "clarify":
            return "clarify"
        elif operation == "query":
            # Check if SQL is already provided
            if "sql" in intent and intent["sql"]:
                return "execute_direct"  # Skip schema and SQL generation
            else:
                return "query"  # Go through normal flow
        
        # Handle legacy operations
        routing_map = {
            "SCHEMA_QUERY": "schema_query",
            "DATA_QUERY": "data_query", 
            "ANALYSIS_QUERY": "analysis_query",
            "SAMPLE_DATA": "sample_data",
            "HEALTH_CHECK": "health_check"
        }
        
        return routing_map.get(operation, "data_query")
    
    def _route_after_sql_generation(self, state: WorkflowState) -> str:
        """Route workflow after SQL generation."""
        if state.get("error_info"):
            return "error"
        return "execute"
    
    def _route_after_execution(self, state: WorkflowState) -> str:
        """Route workflow after query execution."""
        error_info = state.get("error_info")
        if error_info:
            # Check if this is a retryable error
            error_type = error_info.get("type", "")
            retry_count = state.get("retry_count", 0)
            max_retries = 2
            
            if (error_type in ["query_execution_error", "direct_query_execution_error"] and 
                retry_count < max_retries):
                return "retry"
            else:
                return "error"
        return "format"
    
    def _route_after_retry(self, state: WorkflowState) -> str:
        """Route workflow after query retry."""
        if state.get("error_info"):
            return "error"
        return "format"
    
    async def process_query(self, user_input: str) -> str:
        """
        Process a user query through the complete workflow.
        
        Args:
            user_input: User's natural language query
            
        Returns:
            Formatted response
        """
        initial_state = WorkflowState(
            messages=[{"role": "user", "content": user_input}],
            user_input=user_input,
            intent_analysis=None,
            schema=None,
            database_index=None,
            sql_query=None,
            query_results=None,
            error_info=None,
            final_response=None,
            retry_count=0
        )
        
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            return final_state.get("final_response", "I'm sorry, I couldn't process your request.")
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return f"I encountered an error processing your request: {str(e)}"
    
    async def process_conversation(self, messages: list) -> dict:
        """
        Process a conversation with full context through the complete workflow.
        
        Args:
            messages: List of conversation messages [{"role": "user", "content": "..."}, ...]
            
        Returns:
            Dict with response details including operation type and content
        """
        # Extract the last user message for backward compatibility
        last_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        initial_state = WorkflowState(
            messages=messages.copy(),
            user_input=last_user_message,
            intent_analysis=None,
            schema=None,
            database_index=None,
            sql_query=None,
            query_results=None,
            error_info=None,
            final_response=None,
            retry_count=0
        )
        
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Check if this was a clarification or query
            intent = final_state.get("intent_analysis", {})
            operation = intent.get("operation", "query")
            
            result = {
                "final_response": final_state.get("final_response", "I'm sorry, I couldn't process your request."),
                "operation": operation,
                "status": "success"
            }
            
            if operation == "clarify":
                result["clarification"] = result["final_response"]
            
            return result
            
        except Exception as e:
            logger.error(f"Conversation workflow execution error: {e}")
            return {
                "final_response": f"I encountered an error while processing your request: {str(e)}",
                "operation": "error",
                "status": "error"
            }


# Factory function for creating the workflow
def create_database_workflow(model_name: str = "gpt-4o", temperature: float = 0.0) -> DatabaseWorkflow:
    """
    Create a database workflow instance.
    
    Args:
        model_name: OpenAI model to use
        temperature: Temperature for LLM responses
        
    Returns:
        DatabaseWorkflow instance
    """
    return DatabaseWorkflow(model_name=model_name, temperature=temperature)


# Example usage
async def main():
    """Example usage of the database workflow."""
    workflow = create_database_workflow()
    
    # Test queries
    test_queries = [
        "What tables are available in the database?",
        "How many customers do we have?",
        "Show me the top 5 products by sales",
        "Can you show me some sample customer data?",
        "Is the system working properly?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"{'='*50}")
        
        response = await workflow.process_query(query)
        print(f"Response: {response}")


if __name__ == "__main__":
    asyncio.run(main())