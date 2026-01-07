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
from pydantic import BaseModel
from dotenv import load_dotenv

from simple_sql_agent.agent import create_sql_agent, SQLAgentGraph
from simple_sql_agent.db.mcp_client import get_mcp_client

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
        agent = create_sql_agent()
        logger.info("SQL Agent initialized successfully")
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


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Simple SQL Agent",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/query": "Process natural language query (POST)",
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
