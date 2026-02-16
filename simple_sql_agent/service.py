"""
FastAPI service for the Simple SQL Agent.

Provides a clean REST API for the text-to-SQL agent.
"""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from simple_sql_agent.agent import create_sql_agent, SQLAgentGraph
from simple_sql_agent.db.mcp_client import get_mcp_client
from simple_sql_agent.debug_stream import stream_agent_execution, DebugStreamFormatter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConversationLogger:
    """
    File-based conversation logger.

    Saves each conversation turn to a JSON file for analysis and debugging.
    Conversations are stored in logs/conversations/ with one file per session.
    """

    def __init__(self, log_dir: Optional[str] = None):
        """Initialize the conversation logger."""
        if log_dir is None:
            # Default to logs/conversations relative to project root
            project_root = Path(__file__).parent.parent
            self.log_dir = project_root / "logs" / "conversations"
        else:
            self.log_dir = Path(log_dir)

        # Ensure directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Conversation logger initialized: {self.log_dir}")

    def _get_session_file(self, conversation_id: str) -> Path:
        """Get the file path for a conversation session."""
        # Use date prefix for easier organization
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"{date_prefix}_{conversation_id}.json"

    def _load_session(self, conversation_id: str) -> Dict[str, Any]:
        """Load existing session data or create new."""
        file_path = self._get_session_file(conversation_id)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Create new session
        return {
            "conversation_id": conversation_id,
            "created_at": datetime.now().isoformat(),
            "turns": []
        }

    def _save_session(self, conversation_id: str, session_data: Dict[str, Any]):
        """Save session data to file."""
        file_path = self._get_session_file(conversation_id)
        session_data["updated_at"] = datetime.now().isoformat()

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save conversation log: {e}")

    def log_turn(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        response: str,
        sql_query: Optional[str] = None,
        success: bool = True,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None
    ):
        """
        Log a conversation turn.

        Args:
            conversation_id: Unique ID for the conversation session
            messages: Full message history sent to the agent
            response: Agent's response
            sql_query: SQL query executed (if any)
            success: Whether the query was successful
            latency_ms: Response latency in milliseconds
            error: Error message (if any)
        """
        session = self._load_session(conversation_id)

        # Extract the last user message
        last_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        turn = {
            "turn_number": len(session["turns"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "user_message": last_user_message,
            "full_context_length": len(messages),
            "assistant_response": response,
            "sql_query": sql_query,
            "success": success,
            "latency_ms": latency_ms,
            "error": error
        }

        session["turns"].append(turn)
        self._save_session(conversation_id, session)

        logger.info(f"Logged conversation turn {turn['turn_number']} for session {conversation_id[:8]}...")


# Global instances
agent: Optional[SQLAgentGraph] = None
conversation_logger: Optional[ConversationLogger] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown."""
    global agent, conversation_logger

    # Startup
    logger.info("Starting Simple SQL Agent service...")

    # Initialize conversation logger
    conversation_logger = ConversationLogger()

    # Check MCP connectivity
    mcp = get_mcp_client()
    is_healthy = await mcp.health_check()
    if is_healthy:
        logger.info("MCP server is healthy")
    else:
        logger.warning("MCP server health check failed - queries may fail")

    # Initialize agent
    try:
        max_iterations = int(os.getenv("SQL_AGENT_MAX_ITERATIONS", "25"))
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        agent = create_sql_agent(model_name=model_name, max_iterations=max_iterations)
        logger.info(
            "SQL Agent initialized successfully (model=%s, max_iterations=%s)",
            model_name,
            max_iterations,
        )
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Simple SQL Agent service...")
    await mcp.close()


# Create FastAPI app
app = FastAPI(
    title="Simple SQL Agent",
    description="A minimal text-to-SQL agent for ERP systems",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    question: str
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    answer: str
    sql_query: Optional[str] = None
    success: bool
    latency_ms: int
    error: Optional[str] = None


class ConversationRequest(BaseModel):
    """Request model for process_conversation endpoint (frontend compatibility)."""
    messages: list
    conversation_id: Optional[str] = None
    api_key: Optional[str] = None


class StreamConversationRequest(BaseModel):
    """Request model for streaming conversation endpoint."""
    messages: list
    api_key: Optional[str] = None
    conversation_id: Optional[str] = None


class ConversationResponse(BaseModel):
    """Response model for process_conversation endpoint (frontend compatibility)."""
    final_response: Optional[str] = None
    response: Optional[str] = None
    sql_query: Optional[str] = None
    status: str = "success"


class BenchmarkQueryRequest(BaseModel):
    """Request model for benchmark /process_query endpoint."""
    user_input: str
    api_key: Optional[str] = None
    query_contract: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response model for health endpoint."""
    status: str
    mcp_healthy: bool
    agent_ready: bool


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    mcp = get_mcp_client()
    mcp_healthy = await mcp.health_check()

    return HealthResponse(
        status="healthy" if (mcp_healthy and agent is not None) else "degraded",
        mcp_healthy=mcp_healthy,
        agent_ready=agent is not None,
    )


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a natural language query.

    Args:
        request: QueryRequest with the user's question

    Returns:
        QueryResponse with the answer and metadata
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    logger.info(f"Processing query: {request.question[:100]}...")
    start_time = time.time()

    try:
        result = await agent.arun(request.question)

        latency_ms = int((time.time() - start_time) * 1000)

        return QueryResponse(
            answer=result.get("answer", "No answer generated"),
            sql_query=result.get("sql_query"),
            success=result.get("success", False),
            latency_ms=latency_ms,
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        latency_ms = int((time.time() - start_time) * 1000)

        return QueryResponse(
            answer=f"An error occurred: {str(e)}",
            sql_query=None,
            success=False,
            latency_ms=latency_ms,
            error=str(e),
        )


@app.post("/process_query")
async def process_query_benchmark(request: BenchmarkQueryRequest):
    """
    Process a query (benchmark compatibility endpoint).

    This endpoint is compatible with the eval/run_benchmark.py harness.
    It returns a response format expected by the benchmark scoring.

    Args:
        request: BenchmarkQueryRequest with user_input and optional query_contract

    Returns:
        Dict with final_response, sql_query, exec_result, sources, etc.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not request.user_input or not request.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input is required")

    logger.info(f"Processing benchmark query: {request.user_input[:100]}...")
    start_time = time.time()

    try:
        result = await agent.arun(
            request.user_input,
            query_contract=request.query_contract,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        answer = result.get("answer", "No answer generated")
        sql_query = result.get("sql_query")
        success = result.get("success", False)
        agent_exec_result = result.get("exec_result") or {}

        # Build exec_result from agent's parsed result
        exec_result = {
            "data": agent_exec_result.get("data", []),
            "rows": agent_exec_result.get("rows", []),
            "row_count": agent_exec_result.get("row_count"),
            "columns": agent_exec_result.get("columns", []),
            "ok": agent_exec_result.get("ok", True),
            "tables_used": [],
        }

        # Extract table names from SQL
        tables = []
        if sql_query:
            import re
            table_pattern = r'(?:FROM|JOIN)\s+(\[?(?:dbo|public)\]?\.\[?\w+\]?|\[?\w+\]?\.?\[?\w+\]?)'
            tables = re.findall(table_pattern, sql_query, re.IGNORECASE)
            # Clean up table names
            tables = [t.replace('[', '').replace(']', '').replace('"', '') for t in tables]
            exec_result["tables_used"] = tables

        # Build response compatible with benchmark expectations
        response = {
            "final_response": answer,
            "sql_query": sql_query,
            "exec_result": exec_result,
            "sources": tables,
            "relevant_tables": tables,
            "latency_ms": latency_ms,
            "success": success,
            "llm_usage": result.get("llm_usage"),
            "node_entry_counts": result.get("node_entry_counts"),
            "loop_events": result.get("loop_events"),
            "total_llm_calls": result.get("total_llm_calls"),
            "total_graph_cycles": result.get("total_graph_cycles"),
            "retrieval_log": result.get("retrieval_log", []),
            "retrieved_tables_topk": result.get("retrieved_tables_topk", []),
            "model_name": result.get("model_name", os.getenv("OPENAI_MODEL", "gpt-4o")),
        }

        return response

    except Exception as e:
        logger.error(f"Benchmark query processing failed: {e}", exc_info=True)
        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "final_response": f"An error occurred: {str(e)}",
            "sql_query": None,
            "exec_result": None,
            "sources": [],
            "relevant_tables": [],
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
        }


@app.post("/process_conversation", response_model=ConversationResponse)
async def process_conversation(request: ConversationRequest):
    """
    Process a conversation (frontend compatibility endpoint).

    This endpoint is compatible with the existing chatbot UI.

    Args:
        request: ConversationRequest with messages and api_key

    Returns:
        ConversationResponse with the final_response
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Validate API key
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate input
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    # Check that there's at least one user message
    has_user_message = any(msg.get("role") == "user" for msg in request.messages)
    if not has_user_message:
        raise HTTPException(status_code=400, detail="No user message found in conversation")

    # Extract last user message for logging
    last_user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break

    logger.info(f"Processing conversation: {last_user_message[:100]}...")

    # Generate or use existing conversation ID
    conv_id = request.conversation_id or str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        # Pass full conversation history to agent (not just last message)
        result = await agent.arun(request.messages)

        answer = result.get("answer", "No answer generated")
        sql_query = result.get("sql_query")
        success = result.get("success", False)
        latency_ms = int((time.time() - start_time) * 1000)

        # Log the conversation turn
        if conversation_logger:
            conversation_logger.log_turn(
                conversation_id=conv_id,
                messages=request.messages,
                response=answer,
                sql_query=sql_query,
                success=success,
                latency_ms=latency_ms
            )

        return ConversationResponse(
            final_response=answer,
            response=answer,
            sql_query=sql_query,
            status="success" if success else "error",
        )

    except Exception as e:
        logger.error(f"Conversation processing failed: {e}", exc_info=True)
        latency_ms = int((time.time() - start_time) * 1000)

        error_response = f"An error occurred: {str(e)}"

        # Log the failed conversation turn
        if conversation_logger:
            conversation_logger.log_turn(
                conversation_id=conv_id,
                messages=request.messages,
                response=error_response,
                sql_query=None,
                success=False,
                latency_ms=latency_ms,
                error=str(e)
            )

        return ConversationResponse(
            final_response=error_response,
            response=error_response,
            sql_query=None,
            status="error",
        )


@app.post("/stream")
async def stream_query(request: StreamConversationRequest):
    """
    Stream agent execution in real-time.

    Returns a Server-Sent Events (SSE) stream of agent execution events.
    Each event includes the agent's thought, tool calls, results, and final answer.

    Accepts either:
    - messages: list of conversation messages (for multi-turn conversations)

    Args:
        request: StreamConversationRequest with messages array

    Returns:
        StreamingResponse with newline-delimited JSON events
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Validate API key if provided
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key and request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate messages
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    # Check that there's at least one user message
    has_user_message = any(msg.get("role") == "user" for msg in request.messages)
    if not has_user_message:
        raise HTTPException(status_code=400, detail="No user message found in conversation")

    # Extract last user message for logging
    last_user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break

    # Generate or use existing conversation ID
    conv_id = request.conversation_id or str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"Starting stream for conversation {conv_id}: {last_user_message[:100]}...")

    async def event_generator():
        """Generate SSE events for agent execution."""
        final_response = ""
        sql_query = None
        success = True
        error_msg = None

        try:
            async for event in stream_agent_execution(agent, request.messages):
                # Track final response and SQL from events
                if event.get("type") == "llm_response":
                    final_response = event.get("content", "")
                elif event.get("type") == "complete":
                    sql_query = event.get("sql_query")
                elif event.get("type") == "error":
                    success = False
                    error_msg = event.get("error")

                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            success = False
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        finally:
            # Log the conversation turn after streaming completes
            latency_ms = int((time.time() - start_time) * 1000)
            if conversation_logger:
                try:
                    conversation_logger.log_turn(
                        conversation_id=conv_id,
                        messages=request.messages,
                        response=final_response or "[No response captured]",
                        sql_query=sql_query,
                        success=success,
                        latency_ms=latency_ms,
                        error=error_msg
                    )
                except Exception as log_err:
                    logger.error(f"Failed to log conversation: {log_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Simple SQL Agent",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/query": "Process natural language query (POST)",
            "/process_query": "Process query - benchmark compatible (POST)",
            "/process_conversation": "Process conversation - frontend compatible (POST)",
            "/stream": "Stream agent execution in real-time (POST)",
        }
    }


# CLI entry point
def main():
    """Run the service using uvicorn."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))  # Default to 5001 for frontend compatibility

    logger.info(f"Starting service on {host}:{port}")

    uvicorn.run(
        "simple_sql_agent.service:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
