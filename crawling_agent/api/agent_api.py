"""
API for the crawling agent with LLM-powered agent.
"""
import os
import time
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware

from crawling_agent.api.models import NaturalLanguageQuery, QueryResult, HealthStatus
from crawling_agent.llm.provider import LLMProviderFactory
from crawling_agent.agent.agent import Agent
from crawling_agent.agent.tool import (
    ERPQueryTool,
    DocumentStorageQueryTool,
    KnowledgeGraphQueryTool,
    SchemaInformationTool,
    ToolRegistry
)
from crawling_agent.utils.logger import get_logger


# Configure logging
logger = get_logger("crawling_agent.api.agent_api")


# Create the FastAPI app
app = FastAPI(
    title="Crawling Agent API",
    description="API for the crawling agent with LLM-powered agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get the agent
async def get_agent() -> Agent:
    """
    Get the agent instance.
    
    Returns:
        Agent instance
    """
    # This would typically be cached or stored in the app state
    # For simplicity, we'll create a new instance each time
    
    # Get LLM provider configuration from environment variables
    provider_name = os.environ.get("LLM_PROVIDER", "mock")
    
    # Log the provider being used
    logger.info(f"Using LLM provider: {provider_name}")
    
    # Create the LLM provider
    llm_provider = LLMProviderFactory.create(provider_name)
    
    # Create the tool registry
    tool_registry = ToolRegistry()
    
    # Register tools
    tool_registry.register_tool(ERPQueryTool({"mock_mode": True}))
    tool_registry.register_tool(DocumentStorageQueryTool({"mock_mode": True}))
    tool_registry.register_tool(KnowledgeGraphQueryTool({"mock_mode": True}))
    tool_registry.register_tool(SchemaInformationTool({"mock_mode": True}))
    
    # Create the agent
    agent = Agent(llm_provider, tool_registry)
    
    return agent


@app.get("/", tags=["General"])
async def root():
    """Root endpoint that returns basic API information."""
    return {
        "name": "Crawling Agent API",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health", tags=["General"], response_model=HealthStatus)
async def health_check():
    """Health check endpoint."""
    # Check if we can create an agent
    try:
        agent = await get_agent()
        agent_status = "healthy"
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        agent_status = "unhealthy"
    
    # Determine overall status
    overall_status = "healthy" if agent_status == "healthy" else "unhealthy"
    
    return HealthStatus(
        status=overall_status,
        components={
            "agent": agent_status,
            "llm_provider": os.environ.get("LLM_PROVIDER", "mock")
        },
        version="1.0.0"
    )


@app.post("/query", tags=["Query"], response_model=QueryResult)
async def execute_query(
    query: NaturalLanguageQuery = Body(...),
    agent: Agent = Depends(get_agent)
):
    """
    Execute a natural language query using the LLM-powered agent.
    
    This endpoint accepts a natural language query, uses the agent to analyze it,
    select appropriate tools, generate structured queries, execute them, and
    process the results.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Received natural language query: {query.query}")
        
        # Process the query using the agent
        result = await agent.process_query(query.query)
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        
        # Prepare the response
        response = QueryResult(
            query_id=query.query_id,
            thought_process=result.get("analysis", {}).get("thought_process", ""),
            structured_queries=result.get("structured_queries", []),
            results=result.get("results", {}).get("combined_results", []),
            execution_time_ms=execution_time,
            status=result.get("status", "success"),
            error=result.get("error")
        )
        
        logger.info(f"Query executed successfully in {execution_time:.2f}ms")
        
        return response
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        
        # Prepare the error response
        response = QueryResult(
            query_id=query.query_id,
            thought_process="Error occurred during query processing.",
            structured_queries=[],
            results=[],
            execution_time_ms=execution_time,
            status="error",
            error=str(e)
        )
        
        return response


def run():
    """Run the API server."""
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="Crawling Agent API")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    run()