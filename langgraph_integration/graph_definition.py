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
import json
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
from .prompts.repair import SQL_REPAIR_PROMPT, QUERY_SIMPLIFICATION

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
            Updated state with database index information or FAILED status
        """
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("index_database")
        
        try:
            logger.info(f"📚 Starting database catalog indexing...")
            if debug_logger:
                debug_logger.tool_call("index_database", {"action": "catalog_discovery"})
            
            database_index = await index_database()
            state["database_index"] = database_index
            
            # Check if indexing failed
            if database_index.get("status") == "FAILED":
                error_msg = database_index.get("error", "Unknown indexing error")
                logger.error(f"❌ Database indexing FAILED: {error_msg}")
                if debug_logger:
                    debug_logger.tool_result("index_database", None, error=error_msg)
                state["error_info"] = {
                    "type": "database_indexing_error",
                    "message": error_msg,
                    "context": "Failed to index database on startup",
                    "catalog_failed": True
                }
                # Still continue workflow but flag the error for user
                state["catalog_available"] = False
            else:
                # Success
                total_tables = database_index.get("total_tables", 0)
                schemas = database_index.get("schemas", [])
                page_info = database_index.get("page_info", {})
                
                logger.info(f"✅ Database catalog indexed successfully")
                logger.info(f"   Total tables: {total_tables}")
                logger.info(f"   Schemas found: {len(schemas)} ({', '.join(schemas[:5])}{'...' if len(schemas) > 5 else ''})")
                logger.info(f"   Pagination: page {page_info.get('current_page', 1)}/{page_info.get('total_pages', 1)}")
                
                if debug_logger:
                    debug_logger.tool_result(
                        "index_database",
                        {
                            "total_tables": total_tables,
                            "schemas": schemas,
                            "pagination": page_info
                        }
                    )
                
                state["catalog_available"] = True
            
        except Exception as e:
            logger.error(f"❌ Unexpected error indexing database: {e}", exc_info=True)
            if debug_logger:
                debug_logger.tool_result("index_database", None, error=str(e))
            state["error_info"] = {
                "type": "database_indexing_error",
                "message": str(e),
                "context": "Failed to index database on startup",
                "catalog_failed": True
            }
            state["catalog_available"] = False
        
        return state
    
    async def _parse_intent(self, state: WorkflowState) -> WorkflowState:
        """
        Parse user intent from conversation context and decide whether to clarify or query.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with intent analysis
        """
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("parse_intent")
        
        # Default safe intent analysis - guarantees non-None dict
        intent_analysis = {"operation": "query", "requirements": "", "entities": []}
        
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
            
            if debug_logger:
                debug_logger.log_info(
                    "Intent Parsing Started",
                    details={
                        "user_message": last_user_msg[:100] if last_user_msg else "N/A",
                        "conversation_turns": len(messages)
                    }
                )
            
            prompt = format_intent_parser_prompt(messages, schema)
            
            # SAFETY: Retry mechanism for incomplete LLM responses
            # If the LLM returns truncated JSON, retry with adjusted parameters
            max_retries = 2
            last_error = None
            for attempt in range(max_retries):
                response = await self.llm.ainvoke([SystemMessage(content=prompt)])
                
                # Parse the JSON response to extract intent information
                # SAFETY: Check response is valid before accessing .content
                if response and hasattr(response, 'content') and isinstance(response.content, str):
                    try:
                        # Strip any leading/trailing whitespace or newlines
                        cleaned_content = response.content.strip()
                        
                        # Find the start of the JSON object
                        json_start_index = cleaned_content.find('{')
                        if json_start_index == -1:
                            raise json.JSONDecodeError("No JSON object found", cleaned_content, 0)
                        
                        # Extract the JSON part of the string
                        json_string = cleaned_content[json_start_index:]
                        
                        # Try to find the end of the JSON object
                        # Look for closing brace
                        close_brace_index = json_string.rfind('}')
                        if close_brace_index != -1:
                            json_string = json_string[:close_brace_index + 1]
                        
                        intent_analysis = json.loads(json_string)
                        
                        # If parsing is successful, break the loop
                        break
                    except json.JSONDecodeError as e:
                        last_error = e
                        logger.warning(f"⚠️ Attempt {attempt + 1} failed: JSON parsing error: {e.msg}")
                        logger.warning(f"   Error position: {e.pos}")
                        if attempt < max_retries - 1:
                            logger.info("   Retrying with a new call...")
                            await asyncio.sleep(1)  # Wait before retrying
                        else:
                            logger.error("❌ All retries failed. Could not parse intent.")
                            raise ValueError(f"Failed to parse intent after {max_retries} retries. JSON error at position {e.pos}")
                    except Exception as e:
                        logger.warning(f"⚠️ Attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                        else:
                            raise ValueError(f"Failed to parse intent: {e}")
                else:
                    logger.warning(f"⚠️ Attempt {attempt + 1}: Invalid or empty response from LLM.")
                    if attempt == max_retries - 1:
                        raise ValueError("LLM returned an invalid or empty response.")




            
            state["intent_analysis"] = intent_analysis
            
            # Log the decision with comprehensive debug information
            operation = intent_analysis.get("operation", "unknown")
            missing_fields = intent_analysis.get("missing_fields", [])
            entities = intent_analysis.get("entities", [])
            
            logger.info(f"📝 Intent Analysis Complete:")
            logger.info(f"   Operation: {operation}")
            logger.info(f"   Confidence: {intent_analysis.get('confidence', 1.0)}")
            logger.info(f"   Entities: {entities}")
            
            if debug_logger:
                debug_logger.intent_parsed(
                    last_user_msg,
                    operation,
                    intent_analysis.get("confidence", 1.0),
                    missing_fields=missing_fields if missing_fields else None,
                    entities=entities if entities else None
                )
            
            # Log the decision with routing info
            if operation == "clarify":
                logger.warning(f"⚠️  Intent: CLARIFY - Missing fields: {missing_fields}")
                logger.info(f"   → Will route to clarification node")
            elif operation == "query":
                logger.info(f"✅ Intent: QUERY")
                if intent_analysis.get("sql"):
                    logger.info(f"   → Direct SQL provided: {intent_analysis.get('sql', 'N/A')[:50]}...")
                    logger.info(f"   → Will route to execute_direct (skip table selection)")
                else:
                    logger.info(f"   → Will route to scout mode (select_tables)")
                    logger.info(f"   → Then generate SQL using indexed tables")
            else:
                logger.info(f"ℹ️  Intent: {operation}")
            
            if intent_analysis.get("reasoning"):
                logger.debug(f"   Reasoning: {intent_analysis.get('reasoning')}")
            if intent_analysis.get("defaults_applied"):
                logger.info(f"   Defaults applied: {intent_analysis.get('defaults_applied')}")
            
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Error parsing intent: {e}")
            logger.debug(f"   Using safe fallback intent_analysis")
            # CRITICAL: ALWAYS set intent_analysis, even on error
            # This guarantees downstream code never sees None
            state["intent_analysis"] = intent_analysis
            if debug_logger:
                debug_logger.workflow_error("intent_parsing_error", str(e))
            
            # Map technical errors to user-friendly messages
            error_message = str(e)
            if "Incomplete JSON" in error_message or "truncated" in error_message.lower():
                user_message = "The system had trouble understanding your request due to high load. Please try a simpler question."
            elif "JSONDecodeError" in error_message or "JSON" in error_message:
                user_message = "The system had difficulty processing your request. Please try rephrasing it."
            else:
                user_message = "I had trouble understanding your request. Could you rephrase it?"
            
            state["error_info"] = {
                "type": "intent_parsing_error",
                "message": user_message,  # User-friendly message instead of technical error
                "technical_error": error_message,  # Store technical details for debugging
                "context": "Failed to parse user intent - using safe default"
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
        Applies answer-first defaults: prevents asking for schema/location/category.
        Handles incomplete/truncated JSON responses gracefully.
        
        Args:
            response_text: Raw JSON response from the LLM
            
        Returns:
            Structured intent analysis with operation, sql, missing_fields, etc.
            Clarify operations are downgraded to query with defaults when appropriate.
        """
        import json
        import re
        
        try:
            # Safety: Check for None or empty response
            if not response_text or not isinstance(response_text, str):
                logger.warning(f"Invalid response_text: {type(response_text)} = {response_text}")
                return self._parse_intent_response("")
            
            # CRITICAL: Check if response is incomplete (starts with { but no closing })
            # This prevents truncated LLM responses from causing cryptic errors
            if response_text.strip().startswith('{') and not response_text.strip().endswith('}'):
                logger.error(f"❌ LLM response is INCOMPLETE/TRUNCATED: {response_text[:80]}...")
                raise ValueError(f"Incomplete JSON response from LLM (truncated at token limit or timeout)")
            
            # Try to extract JSON from the response
            # Look for JSON block in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"No valid JSON found in response. Text: {response_text[:100]}")
                return self._parse_intent_response(response_text)
            
            json_str = json_match.group()
            parsed = json.loads(json_str)
            
            # Ensure required fields exist
            result = {
                "operation": parsed.get("operation", "query"),
                "reasoning": parsed.get("reasoning", ""),
            }
            
            if result["operation"] == "clarify":
                missing_fields = parsed.get("missing_fields", [])
                
                # ANSWER-FIRST DEFAULTS: Transform clarify → query with defaults
                # if only asking for schema/location/category
                schema_related = {
                    "schema information", "schema", "specific schema",
                    "location", "specific location", "region",
                    "category", "product category", "specific category",
                    "tables to query", "table names"
                }
                
                # Check if ALL missing fields are schema/location/category related
                missing_normalized = {f.lower() for f in missing_fields}
                
                # If only asking for these, apply defaults instead of clarifying
                if missing_normalized and missing_normalized.issubset(schema_related):
                    logger.info(f"🎯 Answer-first: Applying defaults instead of asking for {missing_normalized}")
                    # Downgrade to query operation with defaults
                    # (The SQL will be generated with defaults applied)
                    result["operation"] = "query"
                    result["defaults_applied"] = {
                        "location": "ALL_LOCATIONS" if "location" in missing_normalized or "specific location" in missing_normalized else None,
                        "category": "ALL_CATEGORIES" if "category" in missing_normalized or "product category" in missing_normalized else None,
                        "schema": "ALL_SCHEMAS" if "schema" in missing_normalized or "specific schema" in missing_normalized else None,
                    }
                    # Remove None values
                    result["defaults_applied"] = {k: v for k, v in result["defaults_applied"].items() if v is not None}
                    result["sql"] = parsed.get("sql", "")  # Use the LLM's SQL attempt
                    result["entities"] = []
                    result["requirements"] = result["reasoning"]
                else:
                    # Keep as clarify - there are legitimate missing fields
                    result["missing_fields"] = missing_fields
            else:
                result["sql"] = parsed.get("sql", "")
                # Convert to old format for compatibility
                result["entities"] = []
                result["requirements"] = result["reasoning"]
            
            return result
                
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error(f"   Problematic response: {response_text}")
            raise e
    
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
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("get_schema")
            debug_logger.log_info("Schema Discovery Started", details={"source": "MCP list_tables"})
        
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
        Select relevant tables using MCP search_tables (Phase 5 - Scout Mode).
        
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
            session_cache = state.get("session_described_tables", {}) or {}
            
            logger.info(f"🔍 SCOUT MODE: Analyzing user query: {user_input}")
            if debug_logger:
                debug_logger.tool_call("scout_table_search", {"query": user_input})
            
            # Extract keywords from user query (simple heuristic)
            # Remove common words and extract potential table/column names
            stop_words = {"what", "how", "many", "show", "get", "find", "list", "the", "a", "an", "in", "on", "at", "from", "to", "for", "of", "with"}
            words = user_input.lower().split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            
            if not keywords:
                # Fallback: use first few words
                keywords = words[:3]
            
            logger.info(f"📊 Extracted keywords: {keywords}")
            
            # Search for relevant tables using MCP search_tables
            search_keyword = " ".join(keywords[:2])  # Use first 2 keywords
            logger.info(f"🔎 Searching tables with keyword: '{search_keyword}'")
            if debug_logger:
                debug_logger.scout_mode_operation("search_tables", search_keyword, [], {"status": "searching"})
            
            search_response = await search_tables_mcp(search_keyword, page=1, page_size=5)
            
            if search_response.get("ok"):
                results = search_response.get("data", {}).get("results", [])
                logger.info(f"✅ Scout mode found {len(results)} matching tables")
                
                # Extract top 3 table names
                relevant_tables = []
                for result in results[:3]:
                    table_name = result.get("full_name", "")
                    if table_name:
                        relevant_tables.append(table_name)
                        logger.info(f"  ✓ Selected table: {table_name}")
                
                state["relevant_tables"] = relevant_tables
                logger.info(f"🎯 Selected {len(relevant_tables)} relevant tables for query")
                
                if debug_logger:
                    debug_logger.scout_mode_operation(
                        "search_results",
                        search_keyword,
                        relevant_tables,
                        results[:3]
                    )
                
                # Describe tables (use cache if available)
                tables_to_describe = []
                cached_tables = []
                for table_name in relevant_tables:
                    if table_name in session_cache:
                        cached_tables.append(table_name)
                    else:
                        tables_to_describe.append(table_name)
                
                if cached_tables:
                    logger.info(f"♻️  Using cached schemas for {len(cached_tables)} tables: {cached_tables}")
                
                # Fetch descriptions for new tables
                if tables_to_describe:
                    logger.info(f"📋 Fetching fresh schemas for {len(tables_to_describe)} new tables: {tables_to_describe}")
                    if debug_logger:
                        debug_logger.tool_call("describe_table_batch", {"tables": tables_to_describe})
                    
                    new_descriptions = await describe_table_batch(tables_to_describe)
                    session_cache.update(new_descriptions)
                    state["session_described_tables"] = session_cache
                    
                    logger.info(f"✅ Successfully described {len(tables_to_describe)} tables")
                    if debug_logger:
                        debug_logger.tool_result("describe_table_batch", f"{len(tables_to_describe)} tables described")
                
                # Build schema snippet from cached descriptions
                table_descriptions = {t: session_cache[t] for t in relevant_tables if t in session_cache}
                schema_snippet = build_schema_snippet(table_descriptions)
                state["schema_snippet"] = schema_snippet
                
                logger.info(f"📝 Built schema snippet ({len(schema_snippet)} chars) for {len(table_descriptions)} tables")
                logger.info(f"📌 Schema snippet preview:\n{schema_snippet[:300]}...")
                
            else:
                error_msg = search_response.get("error", "Unknown error")
                logger.warning(f"⚠️  Scout mode search failed: {error_msg}, using lightweight schema")
                if debug_logger:
                    debug_logger.workflow_error("scout_search_failed", error_msg)
                state["schema_snippet"] = state.get("schema", "No schema available")
            
        except Exception as e:
            logger.error(f"❌ Error in scout mode table selection: {e}", exc_info=True)
            if debug_logger:
                debug_logger.workflow_error("scout_mode_error", str(e))
            # Fallback to lightweight schema overview
            state["schema_snippet"] = state.get("schema", "No schema available")
            logger.info("⚠️  Falling back to schema overview")
        
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
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("generate_sql")
        
        try:
            intent = state.get("intent_analysis") or {}
            
            # Check if SQL was already provided by the intent parser
            if intent and "sql" in intent and intent["sql"]:
                state["sql_query"] = intent["sql"]
                logger.info(f"Using SQL from intent parser: {intent['sql']}")
                if debug_logger:
                    debug_logger.log_info("SQL Generation", details={
                        "source": "intent_parser",
                        "sql": intent['sql'][:100],
                        "table_context": intent.get("tables", [])
                    })
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
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("execute_query")
            debug_logger.log_info("Query Execution Started", details={
                "sql": state.get("sql_query", "unknown")[:100],
                "timeout_ms": 30000,
                "max_rows": 1000
            })
        
        try:
            import time
            sql_query = state["sql_query"]
            start_time = time.time()
            
            # PHASE 5: Use query_bounded_mcp instead of execute_sql_query
            results, actual_row_count = await query_bounded_mcp(sql_query, max_rows=1000, timeout_ms=30000)
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
                
                # Use actual row count from MCP response (not text line count)
                rows_count = actual_row_count
                
                # Log successful query execution with correct row count
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
            intent = state.get("intent_analysis") or {}
            sql_query = intent.get("sql", "")
            
            if not sql_query:
                raise ValueError("No SQL query provided in intent analysis")
            
            # Store the SQL query in state for consistency
            state["sql_query"] = sql_query
            
            # PHASE 5: Execute via query_bounded_mcp
            results, direct_row_count = await query_bounded_mcp(sql_query, max_rows=1000, timeout_ms=30000)
            
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
                logger.info(f"Direct query executed successfully: {sql_query} ({direct_row_count} rows)")
            
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
        Retry SQL query with automatic error correction using LLM repair (Phase 5+).
        
        This enhanced version uses the SQL_REPAIR_PROMPT to fix common MSSQL issues:
        - LIMIT → TOP syntax correction
        - Table/column name mismatches  
        - Date function corrections
        - FK relationship issues
        
        PHASE 5: Uses query_bounded_mcp for retry execution with LLM repair.
        
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
            
            # Get the original SQL, schema, and error info
            sql_query = state.get("sql_query", "")
            schema_snippet = state.get("schema_snippet", state.get("schema", ""))
            error_info = state.get("error_info", {})
            error_msg = error_info.get("message", "")
            relevant_tables = state.get("relevant_tables", [])
            
            logger.info(f"🔧 Attempting SQL repair (attempt {state['retry_count']}/{max_retries})...")
            logger.debug(f"   Original SQL: {sql_query[:80]}...")
            logger.debug(f"   Error: {error_msg}")
            
            # Step 1: Use LLM to repair SQL based on the error message
            try:
                # Build join plan info if available
                join_plan = {"tables": relevant_tables} if relevant_tables else {}
                
                repair_prompt = SQL_REPAIR_PROMPT.format(
                    sql_query=sql_query,
                    error_message=error_msg,
                    schema_snippet=schema_snippet,
                    join_plan=json.dumps(join_plan, indent=2) if join_plan else "{}"
                )
                
                logger.debug("   Invoking LLM for SQL repair...")
                response = await self.llm.ainvoke([SystemMessage(content=repair_prompt)])
                repaired_sql = response.content.strip()
                
                # Extract SQL from response (might have explanations)
                repaired_sql = self._extract_sql_from_response(repaired_sql)
                
                if not repaired_sql:
                    logger.warning("   LLM repair returned no SQL, retrying original")
                    repaired_sql = sql_query
                else:
                    logger.info(f"   ✅ LLM repaired SQL ({len(repaired_sql)} chars)")
                    if debug_logger:
                        debug_logger.sql_generated(
                            repaired_sql,
                            f"Repair attempt {state['retry_count']}: fixed {error_msg[:50]}",
                            table_context=relevant_tables
                        )
                
                state["sql_query"] = repaired_sql
                
            except Exception as repair_error:
                logger.warning(f"   Repair attempt failed ({repair_error}), retrying original SQL")
                # Fall back to original SQL if repair fails
                repaired_sql = sql_query
            
            # Step 2: Retry with repaired (or original) SQL
            logger.info(f"   🔄 Retrying query with repaired SQL...")
            results, retry_row_count = await query_bounded_mcp(repaired_sql, max_rows=1000, timeout_ms=30000)
            
            # Check if the retry was successful
            if results.startswith("Error") or results.startswith("QUERY_ERROR:"):
                error_msg = results.replace("QUERY_ERROR:", "").replace("Error executing query:", "").strip()
                logger.warning(f"   ⚠️  Retry still failed: {error_msg[:80]}...")
                
                # If this is attempt 1, we can try simplification on next retry
                # If this is attempt 2, we should give up and ask user
                state["error_info"] = {
                    "type": "query_retry_error",
                    "message": error_msg,
                    "context": f"Failed to execute SQL after repair attempt {state['retry_count']}: {repaired_sql[:100]}",
                    "sql_query": repaired_sql,
                    "retry_count": state["retry_count"],
                    "original_sql": sql_query
                }
            else:
                # Success! Clear error info and set results
                logger.info(f"   ✅ Query retry SUCCESSFUL after {state['retry_count']} repair attempt(s)")
                state["query_results"] = results
                state["error_info"] = None
                if debug_logger:
                    # Use actual row count from MCP response (already extracted in query_bounded_mcp)
                    debug_logger.query_executed(repaired_sql, retry_row_count, 0)
            
        except Exception as e:
            logger.error(f"Error in query retry: {e}", exc_info=True)
            state["error_info"] = {
                "type": "query_retry_error",
                "message": str(e),
                "context": f"Failed during query retry process",
                "retry_count": state.get("retry_count", 0)
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
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("format_results")
            result_type = "data_results" if state.get("query_results") else ("schema_explanation" if state.get("schema") else "unknown")
            debug_logger.log_info("Result Formatting Started", details={"result_type": result_type})
        
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
        # Set node context for debug logging
        if debug_logger:
            debug_logger.set_node_context("handle_error")
            error_info = state.get("error_info", {})
            debug_logger.log_info("Error Handling Started", details={
                "error_type": error_info.get("type", "unknown"),
                "error_message": error_info.get("message", "unknown")[:100]
            })
        
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
            intent = state.get("intent_analysis") or {}
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
        If catalog is unavailable, show friendly message instead of asking for clarification.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with clarification question or error message
        """
        try:
            # Check if catalog failed
            error_info = state.get("error_info") or {}
            if error_info.get("catalog_failed"):
                catalog_error = error_info.get("message", "catalog unavailable")
                state["final_response"] = (
                    "I couldn't load the data catalog right now. "
                    f"(Reason: {catalog_error[:50]}...) "
                    "I can still answer high-level questions, but for detailed queries "
                    "please try again in a moment once the catalog is available."
                )
                logger.warning(f"Clarify requested but catalog unavailable: {catalog_error}")
                if debug_logger:
                    debug_logger.decision_made("clarify_with_catalog_error", f"Catalog unavailable: {catalog_error}")
                return state
            
            from .prompts import format_clarification_prompt
            
            intent = state.get("intent_analysis") or {}
            if not intent or not isinstance(intent, dict):
                logger.warning(f"Intent analysis is invalid: {intent}")
                if debug_logger:
                    debug_logger.workflow_error("invalid_intent_analysis", f"intent_analysis={intent}")
                intent = {}
            
            missing_fields = intent.get("missing_fields", [])
            messages = state.get("messages", []) or []
            schema = state.get("schema", "No schema available")
            
            logger.info(f"🔍 Clarify: missing_fields={missing_fields}, intent_operation={intent.get('operation', 'unknown')}")
            if debug_logger:
                debug_logger.decision_made("clarify_question", f"Missing fields: {missing_fields}", missing_fields)
            
            # Generate clarifying question with schema context
            prompt = format_clarification_prompt(messages, missing_fields, schema)
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            
            clarification = response.content
            state["final_response"] = clarification
            
            logger.info(f"✅ Generated clarification: {clarification[:100]}...")
            if debug_logger:
                debug_logger.tool_result("format_clarification", clarification)
            
        except Exception as e:
            logger.error(f"❌ Error generating clarification: {e}", exc_info=True)
            if debug_logger:
                debug_logger.workflow_error("clarification_generation_error", str(e))
            state["final_response"] = "I need more information to help you. Could you please provide more details about what you're looking for?"
        
        return state
    
    def _route_after_intent(self, state: WorkflowState) -> str:
        """
        Route workflow after intent parsing.
        
        PHASE 8: Intent parser now ALWAYS returns operation="query" with keywords extracted.
        This node routes to table selection (select_tables) where MCP Scout discovers actual tables.
        """
        if state.get("error_info"):
            return "error"
        
        intent = state.get("intent_analysis") or {}
        operation = intent.get("operation", "query")
        
        # PHASE 8: New intent parser ALWAYS returns operation="query"
        # It extracts keywords (entities, requirements) but does NOT:
        # - Try to find specific tables (that's scout_mode's job)
        # - Generate SQL (that's generate_sql's job)
        # - Return "clarify" (table discovery is deferred to downstream)
        
        if operation == "query":
            # Always route to select_tables for table discovery via Scout
            return "query"  # Maps to "select_tables" in routing table
        elif operation == "clarify":
            # Legacy fallback (should never happen with new intent parser)
            logger.warning("⚠️  Intent parser returned 'clarify' - this should not happen with new implementation")
            return "clarify"
        else:
            # Handle any other operations (legacy support)
            logger.warning(f"Unknown operation: {operation}, defaulting to 'query'")
            return "query"
    
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
            
            # Retryable error types:
            # - QUERY_ERROR: syntax errors, database errors → repair agent can fix
            # - EXECUTION_ERROR: runtime issues → can be fixed by simplification
            # - query_execution_error, direct_query_execution_error: legacy types
            retryable_errors = {
                "QUERY_ERROR",              # Syntax errors, DB errors from MCP
                "EXECUTION_ERROR",          # Runtime failures
                "query_execution_error",    # Legacy routing
                "direct_query_execution_error"  # Legacy routing
            }
            
            if error_type in retryable_errors and retry_count < max_retries:
                logger.info(f"🔄 Routing {error_type} to retry (attempt {retry_count + 1}/{max_retries})")
                return "retry"
            else:
                logger.warning(f"❌ Error {error_type} not retryable or max retries ({max_retries}) exceeded")
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
            logger.error(f"Conversation workflow execution error: {e}", exc_info=True)
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


# Module-level graph instantiation (Phase 4)
# This is used by phase 4 integration tests and langgraph_service.py
try:
    graph = create_database_workflow().workflow
except Exception as e:
    logger.warning(f"Failed to instantiate module-level graph: {e}. Graph will be lazily created on first use.")
    graph = None


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