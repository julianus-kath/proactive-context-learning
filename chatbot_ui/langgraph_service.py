"""
LangGraph Service - FastAPI wrapper for the LangGraph workflow
Provides HTTP endpoints for the chatbot UI to interact with the LangGraph workflow.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ValidationError, Field
import uvicorn
from dotenv import load_dotenv

from langgraph_integration.contracts.response_envelope import (
    ErrorInfo as ErrorInfoModel,
    ResponseEnvelope,
)

# Add the parent directory and langgraph_integration to the path
parent_dir = os.path.join(os.path.dirname(__file__), '..')
langgraph_dir = os.path.join(parent_dir, 'langgraph_integration')
sys.path.insert(0, parent_dir)
sys.path.insert(0, langgraph_dir)

try:
    # Import the new multi-agent orchestrator (ACTIVE - Phase 8)
    from langgraph_integration.orchestrator import create_query_orchestrator
    from langgraph_integration.debug_logger import get_debug_logger
except ImportError as e:
    print(f"Error importing LangGraph integration: {e}")
    print("Make sure you're running from the correct directory and langgraph_integration is available")
    print(f"Parent dir: {parent_dir}")
    print(f"LangGraph dir: {langgraph_dir}")
    sys.exit(1)

# Load environment variables from parent directory
env_path = os.path.join(parent_dir, '.env')
load_dotenv(env_path)

app = FastAPI(
    title="LangGraph Service",
    description="HTTP service wrapper for LangGraph database workflow",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    user_input: str
    api_key: Optional[str] = None
    # Optional per-query semantic contract payload (used in benchmark mode).
    # Passed through to the orchestrator via metadata["query_contract"].
    query_contract: Optional[Dict[str, Any]] = None

class ConversationRequest(BaseModel):
    messages: list
    conversation_id: Optional[str] = None
    api_key: Optional[str] = None

class QueryResponse(BaseModel):
    final_response: str
    exec_result: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    sources: Optional[list] = None
    error_info: Optional[Dict[str, Any]] = None
    discovery_log: Optional[Dict[str, Any]] = None
    status: str = "success"
    # Phase 1/2 diagnostics: propagate orchestrator instrumentation fields
    llm_usage: Optional[Dict[str, Any]] = None
    node_entry_counts: Optional[Dict[str, Any]] = None
    loop_events: Optional[Dict[str, Any]] = None
    total_llm_calls: Optional[int] = None
    total_graph_cycles: Optional[int] = None
    answer_mode: Optional[str] = None

class ConversationResponse(BaseModel):
    final_response: Optional[str] = None
    operation: Optional[str] = None
    clarification: Optional[str] = None
    clarify: bool = False
    question: Optional[str] = None
    response: Optional[str] = None
    messages: Optional[list] = None
    status: str = "success"

class AgentInvokeRequest(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict, description="Partial LangGraph state passed to the target agent")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Optional execution options (state overrides, dry-run flags, etc.)")
    api_key: Optional[str] = None

class AgentInvokeResponse(BaseModel):
    ok: bool
    agent: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: Optional[int] = None
    execution_time_ms: Optional[int] = None
    truncated: bool = False
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    error_info: Optional[Dict[str, Any]] = None
    # Full normalized state returned by the agent invocation (for debugging and targeted inspection)
    output_state: Optional[Dict[str, Any]] = None
    # Minimal state delta between input_state and output_state (added/removed/updated keys)
    state_delta: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    error: str
    status: str = "error"

class DebugLogEntry(BaseModel):
    timestamp: str
    type: str
    message: str
    session_id: str

class DebugLogsResponse(BaseModel):
    logs: list = []
    status: str = "success"

# Global orchestrator instance (Phase 9.1: Multi-agent system with IntentParserAgent subgraph)
orchestrator = None
debug_logger = None
logger = logging.getLogger(__name__)


def _validate_api_key(provided_key: Optional[str]):
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if provided_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.on_event("startup")
async def startup_event():
    """Initialize the multi-agent orchestrator on startup."""
    global orchestrator, debug_logger
    try:
        print("🚀 Initializing multi-agent orchestrator (Phase 9.1)...")
        orchestrator = create_query_orchestrator()
        debug_logger = get_debug_logger()
        print("✅ Multi-agent orchestrator initialized successfully")
        print("  ├─ IntentParserAgent (LangGraph subgraph, semantic parsing)")
        print("  ├─ DiscoveryAgent (Scout semantic search)")
        print("  ├─ JoinPlanAndSQLAgent (Views-first, MSSQL)")
        print("  ├─ ExecAndRecoveryAgent (Safe execution, auto-repair)")
        print("  └─ AnswerAgent (Result formatting)")
        print("✅ Debug logger initialized")
    except Exception as e:
        print(f"❌ Failed to initialize multi-agent orchestrator: {e}")
        raise


async def _invoke_named_agent(
    agent_name: str,
    request: AgentInvokeRequest,
    api_key_header: Optional[str],
) -> AgentInvokeResponse:
    """
    Helper to invoke a single orchestrator agent by name using partial state.

    This is used by the /agent/* endpoints so that tests and tools can
    exercise individual nodes (discovery, join_sql, validate_sql, exec_recovery,
    result_validator) without running the full pipeline.
    """
    global orchestrator

    # API key can be provided either via header or request body
    provided_key = api_key_header or request.api_key
    _validate_api_key(provided_key)

    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Multi-agent orchestrator not initialized")

    try:
        result = await orchestrator.invoke_agent(
            agent_name=agent_name,
            state=request.state or {},
            options=request.options or {},
        )
    except ValueError as exc:
        # Localized, agent-level input errors (e.g., unknown agent, bad state shape)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("❌ Error invoking agent '%s': %s", agent_name, exc)
        raise HTTPException(status_code=500, detail=f"Error invoking agent '{agent_name}': {exc}")

    return AgentInvokeResponse(
        ok=bool(result.get("ok", False)),
        agent=result.get("agent", agent_name),
        data=result.get("data") or [],
        row_count=result.get("row_count"),
        execution_time_ms=result.get("execution_time_ms"),
        truncated=bool(result.get("truncated", False)),
        warnings=result.get("warnings") or [],
        error=result.get("error"),
        error_info=result.get("error_info"),
        output_state=result.get("output_state"),
        state_delta=result.get("state_delta"),
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Multi-Agent Orchestrator (Phase 9.1)",
        "orchestrator_ready": orchestrator is not None,
        "agents": ["IntentParserAgent", "DiscoveryAgent", "JoinPlanAndSQLAgent", "ExecAndRecoveryAgent", "AnswerAgent"]
    }


@app.post("/agent/discovery", response_model=AgentInvokeResponse)
async def invoke_discovery_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the DiscoveryAgent with a partial LangGraph state.

    Typical usage:
    - Provide user_input and intent (including keywords_for_discovery)
    - Inspect relevant_tables, schema_snippet, and column_index in output_state
    """
    return await _invoke_named_agent("discovery", request, api_key_header)


@app.post("/agent/join_sql", response_model=AgentInvokeResponse)
async def invoke_join_sql_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the JoinPlanAndSQLAgent with a partial LangGraph state.

    Typical usage:
    - Provide intent and relevant_tables (and optionally schema_snippet/column_index)
    - Inspect sql_query and join_plan in output_state
    """
    return await _invoke_named_agent("join_sql", request, api_key_header)


@app.post("/agent/validate_sql", response_model=AgentInvokeResponse)
async def invoke_validate_sql_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the SQLValidatorAgent with a partial LangGraph state.

    Typical usage:
    - Provide sql_query (and join_plan/column_index for analytic queries)
    - Inspect validation_result and any repair attempts in output_state
    """
    return await _invoke_named_agent("validate_sql", request, api_key_header)


@app.post("/agent/exec_recovery", response_model=AgentInvokeResponse)
async def invoke_exec_recovery_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the ExecAndRecoveryAgent with a partial LangGraph state.

    Typical usage:
    - Provide validated sql_query and connection/runtime options in state
    - Inspect exec_result (rows, row_count, truncated) in output_state
    """
    return await _invoke_named_agent("exec_recovery", request, api_key_header)


@app.post("/agent/result_validator", response_model=AgentInvokeResponse)
async def invoke_result_validator_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the result validator node with a partial LangGraph state.

    Typical usage:
    - Provide exec_result, intent, and join_plan
    - Inspect validation_result and any warnings in output_state
    """
    return await _invoke_named_agent("result_validator", request, api_key_header)


@app.get("/debug/config")
async def debug_config():
    """
    Debug endpoint exposing key orchestrator configuration.
    Used to verify that the running service is using the expected control-flow settings.
    """
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    # We can't introspect recursion_limit from LangGraph at runtime,
    # but we can return the orchestrator's known defaults and budgets.
    state_defaults = {
        "max_total_plans": 4,
        "max_exec_attempts": 4,
        "max_llm_calls": getattr(orchestrator, "max_llm_calls", 20),
        "max_graph_cycles": getattr(orchestrator, "max_graph_cycles", 10),
        "llm_budget_safety_margin": getattr(orchestrator, "llm_budget_safety_margin", 2),
        "db_dialect": getattr(orchestrator, "db_dialect", None),
        "db_default_schema": getattr(orchestrator, "db_default_schema", None),
    }
    return {
        "status": "ok",
        "version": "cf_fix2",
        "defaults": state_defaults,
    }

@app.post("/process_query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_eval_run_id: Optional[str] = Header(default=None, alias="X-Eval-Run-Id"),
    x_eval_query_id: Optional[str] = Header(default=None, alias="X-Eval-Query-Id"),
):
    """
    Process a user query through the multi-agent orchestrator.
    
    Args:
        request: QueryRequest containing user_input and api_key
        
    Returns:
        QueryResponse with the final_response and optional details
    """
    global orchestrator
    
    # Validate API key
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate input
    if not request.user_input or not request.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input cannot be empty")
    
    # Check if orchestrator is initialized
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Multi-agent orchestrator not initialized")
    
    try:
        logger.info(f"📝 Processing query: {request.user_input[:100]}...")

        # Build metadata payload for orchestrator, including optional eval headers
        # and per-query semantic contracts used in benchmark mode.
        metadata: Dict[str, Any] = {}
        if request.query_contract is not None:
            metadata["query_contract"] = request.query_contract

        if x_eval_run_id:
            metadata["eval_run_id"] = x_eval_run_id
        if x_eval_query_id:
            metadata["eval_query_id"] = x_eval_query_id
        # If any eval identifiers are present, mark this query as a benchmark run.
        if x_eval_run_id or x_eval_query_id:
            metadata.setdefault("eval_mode", "benchmark")
        
        # Process the query through multi-agent orchestrator
        orchestrator_result = await orchestrator.process_query(
            user_input=request.user_input.strip(),
            metadata=metadata or None,
        )
        logger.info(f"📝 Orchestrator completed, result type: {type(orchestrator_result)}")

        # Ensure result is a dict
        if not isinstance(orchestrator_result, dict):
            logger.warning(f"⚠️  Orchestrator returned non-dict: {type(orchestrator_result)}")
            orchestrator_result = {"final_response": str(orchestrator_result)}

        # Normalize exec_result
        exec_result_data = None
        exec_payload = orchestrator_result.get("exec_result")
        if exec_payload is not None:
            try:
                envelope = ResponseEnvelope.model_validate(exec_payload)
                exec_result_data = envelope.model_dump(exclude_none=True)
                logger.debug(f"✅ exec_result normalized successfully")
            except ValidationError as exc:
                logger.warning(f"⚠️  exec_result validation failed: {exc}")
                exec_result_data = ResponseEnvelope(ok=False, data=[]).model_dump(exclude_none=True)

        # Normalize error_info
        error_info_data = None
        error_payload = orchestrator_result.get("error_info")
        if error_payload:
            try:
                normalized_error = ErrorInfoModel.model_validate(error_payload)
                error_info_data = normalized_error.model_dump(exclude_none=True)
                logger.debug(f"✅ error_info normalized successfully")
            except ValidationError as exc:
                logger.warning(f"⚠️  error_info validation failed: {exc}")
                error_info_data = ErrorInfoModel(
                    type="UNKNOWN_ERROR",
                    message=str(error_payload),
                ).model_dump(exclude_none=True)

        # Extract final response (required)
        response_text = (
            orchestrator_result.get("final_answer")
            or orchestrator_result.get("final_response")
        )

        if not response_text:
            logger.error("❌ No final_response or final_answer in orchestrator result")
            # Prefer a normalized error message if available
            if error_info_data and isinstance(error_info_data, dict):
                response_text = (
                    error_info_data.get("message")
                    or f"An error occurred: {error_info_data.get('type', 'UNKNOWN_ERROR')}"
                )
            else:
                raw_error = orchestrator_result.get("error_info")
                if isinstance(raw_error, dict):
                    response_text = raw_error.get("message") or str(raw_error)
                elif raw_error:
                    response_text = str(raw_error)
                else:
                    response_text = (
                        "I processed your query but couldn't generate a response. "
                        "Please check the server logs."
                    )

        # Extract optional fields
        sql_query = orchestrator_result.get("sql_query")
        sources = orchestrator_result.get("relevant_tables", [])
        discovery_log = orchestrator_result.get("discovery_log")
        
        logger.info(f"✅ Query processed successfully, response length: {len(response_text)}")
        
        # Ensure sources is JSON-serializable
        if sources and not isinstance(sources, list):
            sources = list(sources) if hasattr(sources, '__iter__') and not isinstance(sources, str) else []
        
        if discovery_log is not None and not isinstance(discovery_log, dict):
            try:
                discovery_log = dict(discovery_log)
            except Exception:
                logger.warning("⚠️  discovery_log was not a dict; coercing to string payload")
                discovery_log = {"raw": str(discovery_log)}
        
        # Create response with JSON-safe values
        response = QueryResponse(
            final_response=response_text,
            exec_result=exec_result_data,
            sql_query=sql_query,
            sources=sources or [],
            error_info=error_info_data,
            discovery_log=discovery_log,
            status="success",
            llm_usage=orchestrator_result.get("llm_usage"),
            node_entry_counts=orchestrator_result.get("node_entry_counts"),
            loop_events=orchestrator_result.get("loop_events"),
            total_llm_calls=orchestrator_result.get("total_llm_calls"),
            total_graph_cycles=orchestrator_result.get("total_graph_cycles"),
            answer_mode=orchestrator_result.get("answer_mode"),
        )
        
        # Ensure all fields are JSON-serializable before returning
        try:
            jsonable_encoder(response.model_dump(exclude_none=True))
        except Exception as e:
            logger.error(f"⚠️  Response may not be fully JSON-serializable: {e}")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"❌ CRITICAL: Error processing query: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/process_conversation", response_model=ConversationResponse)
async def process_conversation(
    request: ConversationRequest = Body(...),
    x_eval_run_id: Optional[str] = Header(default=None, alias="X-Eval-Run-Id"),
    x_eval_query_id: Optional[str] = Header(default=None, alias="X-Eval-Query-Id"),
):
    """
    Process a conversation with full context through the multi-agent orchestrator.
    
    Args:
        request: ConversationRequest containing messages and api_key
        
    Returns:
        ConversationResponse with the final_response or clarification
    """
    global orchestrator
    
    # Validate API key
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate input
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    
    # Check if orchestrator is initialized
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Multi-agent orchestrator not initialized")
    
    try:
        logger.info(f"📝 Processing conversation with {len(request.messages)} messages...")
        
        # Extract the last user message from conversation
        last_user_message = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="No user message found in conversation")
        
        logger.info(f"📝 Last user message: {last_user_message[:100]}...")
        logger.info(f"📝 Conversation ID: {request.conversation_id}")

        # Build metadata payload for orchestrator, including optional eval headers.
        metadata: Dict[str, Any] = {}
        if x_eval_run_id:
            metadata["eval_run_id"] = x_eval_run_id
        if x_eval_query_id:
            metadata["eval_query_id"] = x_eval_query_id
        if x_eval_run_id or x_eval_query_id:
            metadata.setdefault("eval_mode", "benchmark")

        # Process through multi-agent orchestrator with full conversation context
        result = await orchestrator.process_query(
            user_input=last_user_message,
            messages=request.messages,
            conversation_id=request.conversation_id,
            metadata=metadata or None,
        )

        # Ensure result is a dict
        if not isinstance(result, dict):
            logger.warning(f"⚠️  Orchestrator returned non-dict: {type(result)}")
            result = {"final_response": str(result)}

        # Normalize exec_result
        exec_payload = result.get("exec_result")
        if exec_payload is not None:
            try:
                envelope = ResponseEnvelope.model_validate(exec_payload)
                result["exec_result"] = envelope.model_dump(exclude_none=True)
            except ValidationError as exc:
                logger.warning(f"⚠️  exec_result validation failed in conversation: {exc}")
                result["exec_result"] = ResponseEnvelope(ok=False, data=[]).model_dump(exclude_none=True)

        # Normalize error_info
        error_payload = result.get("error_info")
        if error_payload:
            try:
                normalized_error = ErrorInfoModel.model_validate(error_payload)
                result["error_info"] = normalized_error.model_dump(exclude_none=True)
            except ValidationError as exc:
                logger.warning(f"⚠️  error_info validation failed in conversation: {exc}")
                result["error_info"] = ErrorInfoModel(
                    type="UNKNOWN_ERROR",
                    message=str(error_payload),
                ).model_dump(exclude_none=True)

        logger.info(f"✅ Conversation processed successfully")

        # Extract the final answer from the orchestrator result (with safe fallback)
        final_response = (
            result.get("final_answer") 
            or result.get("final_response")
            or "I couldn't process your query. Please try again."
        )
        
        is_clarify = bool(result.get("clarify"))
        clarification_question = result.get("clarification_question")

        # Prepare updated messages array
        updated_messages = request.messages.copy()
        updated_messages.append({"role": "assistant", "content": final_response})

        # Ensure messages are JSON-serializable
        updated_messages = jsonable_encoder(updated_messages)

        # Return response (orchestrator handles all operations internally)
        response = ConversationResponse(
            final_response=final_response,
            operation="clarify" if is_clarify else "query",
            clarify=is_clarify,
            clarification=clarification_question,
            question=clarification_question,
            response=final_response,
            messages=updated_messages,
            status="success"
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"❌ CRITICAL: Error processing conversation: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing conversation: {str(e)}"
        )

@app.get("/debug/logs", response_model=DebugLogsResponse)
async def get_debug_logs():
    """
    Get accumulated debug logs for the current session.
    
    Returns:
        DebugLogsResponse with all buffered debug logs
    """
    global debug_logger
    
    try:
        if debug_logger is None:
            debug_logger = get_debug_logger()
        
        # Get and clear buffered logs
        logs = debug_logger.get_buffered_logs()
        
        return DebugLogsResponse(
            logs=logs,
            status="success"
        )
    except Exception as e:
        print(f"❌ Error getting debug logs: {e}")
        return DebugLogsResponse(
            logs=[],
            status="error"
        )

@app.get("/debug/logs/stream", response_model=DebugLogsResponse)
async def stream_debug_logs():
    """
    Get debug logs without clearing the buffer (for streaming).
    
    Returns:
        DebugLogsResponse with all buffered debug logs (non-destructive)
    """
    global debug_logger
    
    try:
        if debug_logger is None:
            debug_logger = get_debug_logger()
        
        # Get buffered logs without clearing
        logs = debug_logger.get_buffered_logs_no_clear()
        
        return DebugLogsResponse(
            logs=logs,
            status="success"
        )
    except Exception as e:
        print(f"❌ Error streaming debug logs: {e}")
        return DebugLogsResponse(
            logs=[],
            status="error"
        )

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "LangGraph Service",
        "version": "1.0.0",
        "description": "HTTP service wrapper for LangGraph database workflow",
        "endpoints": {
            "health": "/health",
            "process_query": "/process_query (POST)",
            "process_conversation": "/process_conversation (POST)",
            "agent_discovery": "/agent/discovery (POST)",
            "agent_join_sql": "/agent/join_sql (POST)",
            "agent_validate_sql": "/agent/validate_sql (POST)",
            "agent_exec_recovery": "/agent/exec_recovery (POST)",
            "agent_result_validator": "/agent/result_validator (POST)",
            "debug/logs": "/debug/logs (GET) - Get and clear debug logs",
            "debug/logs/stream": "/debug/logs/stream (GET) - Stream debug logs (non-destructive)",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting LangGraph Service...")
    print("📋 Make sure the following are running:")
    print("   - MCP Server (http://localhost:8000)")
    print("   - PostgreSQL database")
    print("   - OpenAI API key is set")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5001,
        log_level="info"
    )
