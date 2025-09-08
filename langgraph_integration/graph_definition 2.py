"""
LangGraph Workflow Definition for MCP Database Integration
Phase 2 Blueprint Implementation

This module defines the LangGraph workflow that:
1. Parses user intent
2. Generates safe SQL via LLM
3. Calls the MCP Server
4. Formats results back to the user
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

from .direct_db_client import get_database_schema, execute_sql_query, get_table_information, health_check
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

# State definition for the workflow
class WorkflowState(TypedDict):
    """State for the LangGraph workflow."""
    messages: List[Dict[str, Any]]
    user_input: str
    intent_analysis: Optional[Dict[str, Any]]
    schema: Optional[str]
    sql_query: Optional[str]
    query_results: Optional[str]
    error_info: Optional[Dict[str, Any]]
    final_response: Optional[str]


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
        workflow.add_node("parse_intent", self._parse_intent)
        workflow.add_node("clarify", self._clarify)
        workflow.add_node("get_schema", self._get_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("execute_direct", self._execute_direct)
        workflow.add_node("format_results", self._format_results)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("explain_schema", self._explain_schema)
        workflow.add_node("show_sample_data", self._show_sample_data)
        workflow.add_node("health_check", self._health_check)
        
        # Define the workflow edges - get schema first for informed intent parsing
        workflow.add_edge(START, "get_schema")
        workflow.add_edge("get_schema", "parse_intent")
        workflow.add_conditional_edges(
            "parse_intent",
            self._route_after_intent,
            {
                "clarify": "clarify",
                "query": "generate_sql",
                "execute_direct": "execute_direct",
                "schema_query": "explain_schema",
                "data_query": "generate_sql",
                "analysis_query": "generate_sql",
                "sample_data": "show_sample_data",
                "health_check": "health_check",
                "error": "handle_error"
            }
        )
        
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
                "error": "handle_error"
            }
        )
        
        # Sample data path
        workflow.add_edge("show_sample_data", "format_results")
        
        # Health check path
        workflow.add_edge("health_check", "format_results")
        
        # Direct execution path (when SQL is provided by intent parser)
        workflow.add_conditional_edges(
            "execute_direct",
            self._route_after_execution,
            {
                "format": "format_results",
                "error": "handle_error"
            }
        )
        
        # Clarification path
        workflow.add_edge("clarify", END)
        
        # All paths end at format_results, handle_error, or clarify
        workflow.add_edge("format_results", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
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
            prompt = format_intent_parser_prompt(messages, schema)
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            
            # Parse the JSON response to extract intent information
            intent_text = response.content
            intent_analysis = self._parse_intent_json_response(intent_text)
            
            state["intent_analysis"] = intent_analysis
            
            # Log the decision
            if intent_analysis["operation"] == "clarify":
                logger.info(f"Intent: CLARIFY - Missing: {intent_analysis.get('missing_fields', [])}")
            else:
                logger.info(f"Intent: QUERY - SQL: {intent_analysis.get('sql', 'N/A')[:50]}...")
            
        except Exception as e:
            logger.error(f"Error parsing intent: {e}")
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
        Get database schema from MCP server.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with schema information
        """
        try:
            schema = await get_database_schema()
            state["schema"] = schema
            logger.info("Schema retrieved successfully")
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            state["error_info"] = {
                "type": "schema_retrieval_error",
                "message": str(e),
                "context": "Failed to retrieve database schema"
            }
        
        return state
    
    async def _generate_sql(self, state: WorkflowState) -> WorkflowState:
        """
        Generate SQL query based on intent and schema.
        
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
                return state
            
            # Otherwise, generate SQL using the traditional method
            schema = state["schema"]
            user_input = state["user_input"]
            
            prompt = format_sql_generator_prompt(
                schema=schema,
                operation=intent.get("operation", "DATA_QUERY"),
                entities=intent.get("entities", []),
                requirements=intent.get("requirements", ""),
                user_input=user_input
            )
            
            response = await self.llm.ainvoke([SystemMessage(content=prompt)])
            sql_query = self._extract_sql_from_response(response.content)
            
            state["sql_query"] = sql_query
            logger.info(f"SQL generated: {sql_query}")
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
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
        Execute SQL query via MCP server.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with query results
        """
        try:
            sql_query = state["sql_query"]
            results = await execute_sql_query(sql_query)
            
            state["query_results"] = results
            logger.info("Query executed successfully")
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            state["error_info"] = {
                "type": "query_execution_error",
                "message": str(e),
                "context": f"Failed to execute SQL: {state.get('sql_query', 'Unknown query')}"
            }
        
        return state
    
    async def _execute_direct(self, state: WorkflowState) -> WorkflowState:
        """
        Execute SQL query directly when provided by intent parser.
        
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
            
            # Execute the query
            results = await execute_sql_query(sql_query)
            
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
            sql_query=None,
            query_results=None,
            error_info=None,
            final_response=None
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
            sql_query=None,
            query_results=None,
            error_info=None,
            final_response=None
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