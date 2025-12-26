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
from fastapi.responses import HTMLResponse
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
        # Always route via internal node handlers so we work with
        # existing orchestrator versions that don't expose invoke_agent().
        normalized = (agent_name or "").strip().lower()
        handler = None
        if normalized in ("intent_parser", "parse_intent"):
            handler = getattr(orchestrator, "_parse_intent_node", None)
        elif normalized in ("discovery",):
            handler = getattr(orchestrator, "_discovery_node", None)
        elif normalized in ("join_sql",):
            handler = getattr(orchestrator, "_join_sql_node", None)
        elif normalized in ("validate_sql", "sql_validator"):
            handler = getattr(orchestrator, "_validate_sql_node", None)
        elif normalized in ("exec_recovery", "execution"):
            handler = getattr(orchestrator, "_exec_recovery_node", None)
        elif normalized in ("result_validator",):
            # Prefer orchestrator wrapper if present, otherwise build directly.
            handler = getattr(orchestrator, "_result_validator_async", None)
            if handler is None:
                from langgraph_integration.agents.result_validator.agent import build_result_validator_node

                async def _inline_result_validator(state):
                    return build_result_validator_node(state)

                handler = _inline_result_validator

        if handler is None:
            raise ValueError(f"Unknown agent '{agent_name}'")

        # Build state payload with optional overrides
        state_payload: Dict[str, Any] = dict(request.state or {})
        options = request.options or {}
        overrides = options.get("state_overrides") if isinstance(options, dict) else None
        if isinstance(overrides, dict):
            for key, value in overrides.items():
                state_payload[key] = value

        before_state: Dict[str, Any] = dict(state_payload)
        result_state = await handler(state_payload)
        if not isinstance(result_state, dict):
            raise ValueError(f"Agent '{agent_name}' returned invalid state")

        normalized_state: Dict[str, Any] = dict(result_state)
        exec_envelope = normalized_state.get("exec_result") if isinstance(normalized_state.get("exec_result"), dict) else None
        error_info = normalized_state.get("error_info")
        if error_info is not None and not isinstance(error_info, dict):
            error_info = {"type": "UNKNOWN_ERROR", "message": str(error_info)}

        data: List[Dict[str, Any]] = []
        row_count: Optional[int] = None
        truncated = False
        exec_error: Optional[str] = None
        exec_ok = True
        if exec_envelope:
            data = exec_envelope.get("data") or []
            row_count = exec_envelope.get("row_count")
            truncated = bool(exec_envelope.get("truncated", False))
            exec_error = exec_envelope.get("error")
            exec_ok = bool(exec_envelope.get("ok", True))

        # Simple state delta for debugging
        added = {k: v for k, v in normalized_state.items() if k not in before_state}
        removed = [k for k in before_state.keys() if k not in normalized_state]
        updated = {
            k: {"before": before_state[k], "after": normalized_state[k]}
            for k in normalized_state.keys()
            if k in before_state and before_state[k] != normalized_state[k]
        }

        overall_ok = exec_ok and not bool(error_info)
        result = {
            "agent": normalized,
            "ok": overall_ok,
            "data": data,
            "row_count": row_count,
            "execution_time_ms": None,
            "truncated": truncated,
            "warnings": normalized_state.get("warnings") or [],
            "error": exec_error,
            "error_info": error_info,
            "input_state": before_state,
            "output_state": normalized_state,
            "state_delta": {
                "added": added,
                "removed": removed,
                "updated": updated,
            },
        }
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


@app.post("/agent/intent_parser", response_model=AgentInvokeResponse)
async def invoke_intent_parser_agent(
    request: AgentInvokeRequest = Body(...),
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Invoke the IntentParserAgent subgraph via the parse_intent node.

    Typical usage:
    - Provide user_input (and optionally messages for multi-turn)
    - Inspect intent.operation, keywords_for_discovery, filters, time_window, etc.
    """
    return await _invoke_named_agent("parse_intent", request, api_key_header)


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


@app.get("/agent/docs", response_class=HTMLResponse)
async def agent_docs():
    """
    Lightweight HTML documentation for the /agent/* endpoints so you
    can inspect and exercise individual agents locally in a browser.
    """
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>LangGraph Agent Endpoints</title>
        <style>
            body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }
            h1, h2 { color: #222; }
            code { background: #f4f4f4; padding: 0.1rem 0.25rem; border-radius: 3px; }
            pre { background: #f4f4f4; padding: 0.75rem; border-radius: 4px; overflow-x: auto; }
            .endpoint { margin-bottom: 2rem; }
            .method { font-weight: bold; color: #0b7285; }
        </style>
    </head>
    <body>
        <h1>LangGraph Agent Endpoints</h1>
        <p>
            These endpoints let you invoke individual LangGraph agents with partial state
            for targeted debugging and analysis, without running the full orchestration pipeline.
        </p>

        <h2>Common Request Envelope</h2>
        <p><span class="method">POST</span> <code>/agent/&lt;name&gt;</code></p>
        <pre>{
  "state": { /* partial LangGraph state visible to the agent */ },
  "options": {
    // optional; if present, "state_overrides" is merged into state
    "state_overrides": { "some_key": "some_value" }
  },
  "api_key": "supersecretapikey"
}</pre>

        <h2>Common Response Envelope</h2>
        <pre>{
  "ok": true,
  "agent": "discovery",
  "data": [ /* convenience view of rows, mainly for exec_recovery */ ],
  "row_count": 42,
  "execution_time_ms": 15,
  "truncated": false,
  "warnings": [],
  "error": null,
  "error_info": null,
  "output_state": { /* full LangGraph state after the agent */ },
  "state_delta": {
    "added": { /* keys added */ },
    "removed": [ /* keys removed */ ],
    "updated": { /* keys whose values changed */ }
  }
}</pre>

        <h2>Authentication</h2>
        <ul>
            <li>Header: <code>X-API-Key: supersecretapikey</code> <strong>or</strong></li>
            <li>Body field: <code>"api_key": "supersecretapikey"</code></li>
        </ul>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/discovery</code></h2>
            <p>Runs the <strong>DiscoveryAgent</strong> ("scout + schema linking") to find relevant tables and schema context.</p>
            <p><strong>Required state (typical):</strong></p>
            <pre>{
  "user_input": "Show me customers",
  "intent": {
    "operation": "query",
    "keywords_for_discovery": ["customers"]
  }
}</pre>
            <p><strong>Key outputs in <code>output_state</code>:</strong></p>
            <ul>
                <li><code>relevant_tables</code> – list of candidate tables/views.</li>
                <li><code>schema_snippet</code> – compact SQL-style schema description.</li>
                <li><code>column_index</code> – mapping of table → list of columns.</li>
            </ul>
        </div>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/intent_parser</code></h2>
            <p>Runs the <strong>IntentParserAgent</strong> subgraph via the <code>parse_intent</code> node.</p>
            <p><strong>Required state:</strong></p>
            <pre>{
  "user_input": "How many customers placed orders last month?"
}</pre>
            <p><strong>Key outputs in <code>output_state</code>:</strong></p>
            <ul>
                <li><code>intent.operation</code> – e.g. <code>query</code>, <code>schema_query</code>, <code>health_check</code>, <code>clarify</code>.</li>
                <li><code>intent.primary_entities</code>, <code>metrics</code>, <code>filters</code>, <code>time_window</code>.</li>
                <li><code>intent.keywords_for_discovery</code> – canonical tokens used by Discovery.</li>
                <li><code>intent.needs_clarification</code> and <code>intent.clarification_question</code> when the query is ambiguous.</li>
            </ul>
        </div>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/join_sql</code></h2>
            <p>Runs the <strong>JoinPlanAndSQLAgent</strong> to build a join plan and generate SQL.</p>
            <p><strong>Required state (typical):</strong></p>
            <pre>{
  "intent": {
    "operation": "query"
  },
  "relevant_tables": [
    { "name": "dbo.Customers" }
  ]
}</pre>
            <p><strong>Key outputs in <code>output_state</code>:</strong></p>
            <ul>
                <li><code>sql_query</code> – generated SQL statement.</li>
                <li><code>join_plan</code> – structured description of primary table and joins.</li>
            </ul>
        </div>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/validate_sql</code></h2>
            <p>Runs the <strong>SQLValidatorAgent</strong> to validate and optionally repair a SQL string.</p>
            <p><strong>Required state:</strong></p>
            <pre>{
  "sql_query": "SELECT TOP 10 * FROM dbo.Customers"
}</pre>
            <p><strong>Key outputs in <code>output_state</code>:</strong></p>
            <ul>
                <li><code>validation_result.is_valid</code> – whether the SQL passed validation.</li>
                <li><code>validation_result.error_type</code>, <code>error_message</code> – if invalid.</li>
                <li>Possibly updated <code>sql_query</code> if a repair was applied.</li>
            </ul>
        </div>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/exec_recovery</code></h2>
            <p>Runs the <strong>ExecAndRecoveryAgent</strong> to execute SQL against the database with safety and retry logic.</p>
            <p><strong>Required state:</strong></p>
            <pre>{
  "sql_query": "SELECT TOP 10 * FROM dbo.Customers"
}</pre>
            <p><strong>Key outputs:</strong></p>
            <ul>
                <li>Top-level <code>data</code>, <code>row_count</code>, <code>truncated</code> – convenience summary.</li>
                <li><code>output_state.exec_result</code> – full execution envelope (ok, data, row_count, error, error_info).</li>
            </ul>
        </div>

        <div class="endpoint">
            <h2><span class="method">POST</span> <code>/agent/result_validator</code></h2>
            <p>Runs the <strong>result validator</strong> node to assess result quality and surface warnings.</p>
            <p><strong>Required state (typical):</strong></p>
            <pre>{
  "exec_result": {
    "ok": true,
    "data": [],
    "row_count": 0
  }
}</pre>
            <p><strong>Key outputs in <code>output_state</code>:</strong></p>
            <ul>
                <li><code>validation_result</code> – semantic status of the result set.</li>
                <li><code>warnings</code> – any issues discovered during validation.</li>
            </ul>
        </div>

        <h2>Example Debugging Flows</h2>
        <ol>
            <li>Call <code>/agent/discovery</code> to see which tables/views a question maps to.</li>
            <li>Feed that state into <code>/agent/join_sql</code> to inspect the generated SQL.</li>
            <li>Validate that SQL with <code>/agent/validate_sql</code>.</li>
            <li>Execute it with <code>/agent/exec_recovery</code> if valid.</li>
            <li>Optionally, run <code>/agent/result_validator</code> to check result quality.</li>
        </ol>

        <p>For OpenAPI/Swagger documentation of all endpoints, visit <code>/docs</code>.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)

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
            "agent_docs": "/agent/docs (GET)",
            "agent_intent_parser": "/agent/intent_parser (POST)",
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
