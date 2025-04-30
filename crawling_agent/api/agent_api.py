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
    
    # Register tools with real data sources
    tool_registry.register_tool(ERPQueryTool({
        "mock_mode": False,
        "host": os.environ.get("ERP_HOST", "erp-server"),
        "port": int(os.environ.get("ERP_PORT", "8001"))
    }))
    tool_registry.register_tool(DocumentStorageQueryTool({
        "mock_mode": False,
        "host": os.environ.get("DOCUMENT_STORAGE_HOST", "document-storage-server"),
        "port": int(os.environ.get("DOCUMENT_STORAGE_PORT", "8002"))
    }))
    tool_registry.register_tool(KnowledgeGraphQueryTool({
        "mock_mode": False,
        "host": os.environ.get("KNOWLEDGE_GRAPH_HOST", "knowledge-graph-server"),
        "port": int(os.environ.get("KNOWLEDGE_GRAPH_PORT", "8003"))
    }))
    tool_registry.register_tool(SchemaInformationTool({
        "mock_mode": False,
        "erp_host": os.environ.get("ERP_HOST", "erp-server"),
        "erp_port": int(os.environ.get("ERP_PORT", "8001")),
        "document_storage_host": os.environ.get("DOCUMENT_STORAGE_HOST", "document-storage-server"),
        "document_storage_port": int(os.environ.get("DOCUMENT_STORAGE_PORT", "8002")),
        "knowledge_graph_host": os.environ.get("KNOWLEDGE_GRAPH_HOST", "knowledge-graph-server"),
        "knowledge_graph_port": int(os.environ.get("KNOWLEDGE_GRAPH_PORT", "8003"))
    }))
    
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
    query_id = getattr(query, "query_id", f"query-{int(time.time())}")
    query_text = getattr(query, "query", str(query))
    
    try:
        logger.info(f"Received natural language query: {query_text}")
        
        # Process the query using the agent
        result = await agent.process_query(query_text)
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        
        # Use the complete thought process if available, otherwise build it
        if "complete_thought_process" in result:
            thought_process = result["complete_thought_process"]
        else:
            # Fallback to building the thought process (for backward compatibility)
            thought_process = result.get("analysis", {}).get("thought_process", "")
            
            # Add tool selection thought process if available
            if "structured_queries" in result and result["structured_queries"]:
                for i, sq in enumerate(result["structured_queries"]):
                    if "thought_process" in sq:
                        thought_process += f"\n\nTool {i+1} ({sq.get('tool_name', 'unknown')}) reasoning:\n"
                        thought_process += sq["thought_process"]
            
            # Add results processing thought process if available
            if "results" in result and isinstance(result["results"], dict) and "thought_process" in result["results"]:
                thought_process += f"\n\nResults processing:\n"
                thought_process += result["results"]["thought_process"]
        
        # Add summary and answer to thought process if not already included
        summary = None
        
        # Try to extract summary from different places
        if "results" in result and isinstance(result["results"], dict) and "summary" in result["results"]:
            summary = result["results"]["summary"]
        elif "summary" in result:
            summary = result["summary"]
            
        # Add summary to thought process if not already included
        if summary and "Summary:" not in thought_process:
            thought_process += f"\n\nSummary: {summary}"
        
        # Extract the answer and error from the result
        answer = None
        error = None
        
        # Check for errors first
        if "error" in result:
            error = result["error"]
            # If there's an error, use it as the answer too
            answer = f"Error: {error}"
        
        # If no error, proceed with normal answer extraction
        if not error:
            # First check if there's a direct answer field at the top level
            if "answer" in result:
                answer = result["answer"]
            # Then check if there's an answer in the results dictionary
            elif "results" in result and isinstance(result["results"], dict):
                if "answer" in result["results"]:
                    answer = result["results"]["answer"]
                elif "summary" in result["results"]:
                    answer = result["results"]["summary"]
            # Finally, use the summary as a fallback
            elif "summary" in result:
                answer = result["summary"]
                
        response = QueryResult(
            query_id=query_id,
            thought_process=thought_process,
            structured_queries=result.get("structured_queries", []),
            results=result.get("results", {}).get("combined_results", []),
            execution_time_ms=execution_time,
            status="error" if error else result.get("status", "success"),
            error=error or result.get("error"),
            answer=answer
        )
        
        logger.info(f"Query executed successfully in {execution_time:.2f}ms")
        
        return response
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        
        # Prepare the error response
        response = QueryResult(
            query_id=query_id,
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