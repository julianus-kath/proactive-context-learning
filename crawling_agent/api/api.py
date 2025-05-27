"""
API for the crawling agent.
"""
import time
import asyncio
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

from crawling_agent.api.models import NaturalLanguageQuery, QueryResult, HealthStatus
from crawling_agent.api.query_translator import QueryTranslator
from crawling_agent.api.result_processor import ResultProcessor
from crawling_agent.connectors.mcp_erp_connector import ERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import DocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import KnowledgeGraphConnector
from crawling_agent.models.task_instruction import DataSourceQuery
from crawling_agent.utils.logger import get_logger


# Create the FastAPI app
app = FastAPI(
    title="Crawling Agent API",
    description="API for the crawling agent",
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

# Initialize the logger
logger = get_logger("crawling_agent.api")

# Initialize the query translator
query_translator = QueryTranslator()

# Initialize the result processor
result_processor = ResultProcessor()

# Initialize the connectors
import os

# Get connector configuration from environment variables
erp_connector = ERPConnector(
    mock_mode=False,
    host=os.environ.get("ERP_HOST", "erp-server"),
    port=int(os.environ.get("ERP_PORT", "8001"))
)
document_storage_connector = DocumentStorageConnector(mock_mode=True)
knowledge_graph_connector = KnowledgeGraphConnector(mock_mode=True)


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
    # Check the health of each connector
    erp_health = erp_connector.check_health()
    document_storage_health = document_storage_connector.check_health()
    knowledge_graph_health = knowledge_graph_connector.check_health()
    
    # Determine overall status
    overall_status = "healthy" if all([erp_health, document_storage_health, knowledge_graph_health]) else "unhealthy"
    
    return HealthStatus(
        status=overall_status,
        components={
            "erp": "healthy" if erp_health else "unhealthy",
            "document_storage": "healthy" if document_storage_health else "unhealthy",
            "knowledge_graph": "healthy" if knowledge_graph_health else "unhealthy"
        },
        version="1.0.0"
    )


@app.post("/query", tags=["Query"], response_model=QueryResult)
async def execute_query(query: NaturalLanguageQuery = Body(...)):
    """
    Execute a natural language query.
    
    This endpoint accepts a natural language query, translates it into structured queries
    for different data sources, executes these queries, and returns the combined results.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Received natural language query: {query.query}")
        
        # Translate the query
        thought_process, structured_queries = query_translator.translate(query.query)
        
        logger.info(f"Translated query into {len(structured_queries)} structured queries")
        
        # Execute the queries
        results = []
        
        for structured_query in structured_queries:
            try:
                # Select the appropriate connector
                if structured_query.source_type == "erp":
                    connector = erp_connector
                elif structured_query.source_type == "document_storage":
                    connector = document_storage_connector
                elif structured_query.source_type == "knowledge_graph":
                    connector = knowledge_graph_connector
                else:
                    logger.warning(f"Unknown source type: {structured_query.source_type}")
                    continue
                
                # Execute the query
                logger.info(f"Executing {structured_query.query_type} query against {structured_query.source_type}")
                result = connector.execute_query(structured_query)
                
                # Add source type to the result
                result["source_type"] = structured_query.source_type
                
                # Add the result to the list
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error executing query against {structured_query.source_type}: {str(e)}")
                # Continue with other queries even if one fails
        
        # Process the results
        combined_results = result_processor.process_results(results)
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        
        # Prepare the structured queries for the response
        structured_queries_json = []
        for sq in structured_queries:
            structured_queries_json.append({
                "source_type": sq.source_type,
                "query_type": sq.query_type.value,
                "query": sq.query,
                "parameters": sq.parameters
            })
        
        # Prepare the response
        response = QueryResult(
            query_id=query.query_id,
            thought_process=thought_process,
            structured_queries=structured_queries_json,
            results=combined_results,
            execution_time_ms=execution_time,
            status="success"
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