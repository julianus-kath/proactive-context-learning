"""
FastAPI service for the Simple SQL Agent.

Provides a clean REST API for the text-to-SQL agent.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

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

# Global agent instance
agent: Optional[SQLAgentGraph] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown."""
    global agent

    # Startup
    logger.info("Starting Simple SQL Agent service...")

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
        agent = create_sql_agent(max_iterations=max_iterations)
        logger.info(f"SQL Agent initialized successfully (max_iterations={max_iterations})")
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
        result = await agent.arun(request.user_input)

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

    # Extract the last user message from conversation
    last_user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break

    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found in conversation")

    logger.info(f"Processing conversation: {last_user_message[:100]}...")

    try:
        result = await agent.arun(last_user_message)

        answer = result.get("answer", "No answer generated")
        sql_query = result.get("sql_query")

        return ConversationResponse(
            final_response=answer,
            response=answer,
            sql_query=sql_query,
            status="success" if result.get("success", False) else "error",
        )

    except Exception as e:
        logger.error(f"Conversation processing failed: {e}", exc_info=True)

        return ConversationResponse(
            final_response=f"An error occurred: {str(e)}",
            response=f"An error occurred: {str(e)}",
            sql_query=None,
            status="error",
        )


@app.post("/stream")
async def stream_query(request: QueryRequest):
    """
    Stream agent execution in real-time.

    Returns a Server-Sent Events (SSE) stream of agent execution events.
    Each event includes the agent's thought, tool calls, results, and final answer.

    Args:
        request: QueryRequest with the user's question

    Returns:
        StreamingResponse with newline-delimited JSON events
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    logger.info(f"Starting stream for query: {request.question[:100]}...")

    async def event_generator():
        """Generate SSE events for agent execution."""
        try:
            async for event in stream_agent_execution(agent, request.question):
                import json
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            import json
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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
