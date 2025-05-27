"""
Main API for the crawling agent system.
"""
import os
import time
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from crawling_agent.llm.provider import LLMProviderFactory
from crawling_agent.tools.base import ToolRegistry
from crawling_agent.tools.sql_tool import SQLTool
from crawling_agent.tools.doc_tool import DocTool
from crawling_agent.tools.kg_tool import KGTool
from crawling_agent.agent.enhanced_mcp_agent import EnhancedMCPCrawlingAgent
from fusion.fusion_agent import FusionAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    """Model for query requests."""
    query: str = Field(..., description="The natural language query to process")
    query_id: Optional[str] = Field(None, description="Optional client-provided query ID")


class QueryResponse(BaseModel):
    """Model for query responses."""
    query_id: Optional[str] = Field(None, description="The query ID (if provided)")
    query: str = Field(..., description="The original query")
    answer: str = Field(..., description="The answer to the query")
    sources: List[Dict[str, Any]] = Field(default=[], description="Sources used to answer the query")
    confidence: float = Field(..., description="Confidence in the answer (0.0 to 1.0)")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    status: str = Field(default="success", description="Status of the query execution")
    error: Optional[str] = Field(None, description="Error message if the query failed")


class CrawlingAgentAPI:
    """
    Main API for the crawling agent system.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000
    ):
        """
        Initialize the Crawling Agent API.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.host = host
        self.port = port
        
        # Initialize the LLM provider
        llm_provider_name = os.environ.get("LLM_PROVIDER", "openai")
        llm_config = {}
        
        if llm_provider_name == "openai":
            llm_config["api_key"] = os.environ.get("OPENAI_API_KEY")
            llm_config["model"] = os.environ.get("OPENAI_MODEL", "gpt-4")
        
        self.llm_provider = LLMProviderFactory.create(llm_provider_name, llm_config)
        logger.info(f"Initialized LLM provider: {llm_provider_name}")
        
        # Initialize the tool registry
        self.tool_registry = ToolRegistry()
        
        # Register tools
        sql_config = {
            "host": os.environ.get("SQL_HOST", "localhost"),
            "port": os.environ.get("SQL_PORT", "8001")
        }
        doc_config = {
            "host": os.environ.get("DOC_HOST", "localhost"),
            "port": os.environ.get("DOC_PORT", "8002")
        }
        self.tool_registry.register_tool(SQLTool(sql_config))
        self.tool_registry.register_tool(DocTool(doc_config))
        self.tool_registry.register_tool(KGTool())
        
        # Initialize the agents
        self.crawling_agent = EnhancedMCPCrawlingAgent(self.llm_provider, self.tool_registry)
        self.fusion_agent = FusionAgent(self.llm_provider)
        
        # Create the FastAPI app
        self.app = FastAPI(
            title="Crawling Agent API",
            description="API for the crawling agent system",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
        
        logger.info(f"Initialized Crawling Agent API on {host}:{port}")
    
    def _register_routes(self):
        """Register API routes."""
        
        @self.app.get("/", tags=["General"])
        async def root():
            """Root endpoint that returns basic server information."""
            return {
                "service": "Crawling Agent API",
                "version": "1.0.0",
                "status": "online",
                "llm_provider": self.llm_provider.get_provider_name(),
                "llm_model": self.llm_provider.get_model_name()
            }
        
        @self.app.get("/health", tags=["General"])
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy"}
        
        @self.app.post("/query", tags=["Query"], response_model=QueryResponse)
        async def process_query(request: QueryRequest):
            """Process a natural language query."""
            start_time = time.time()
            
            try:
                logger.info(f"Processing query: {request.query}")
                
                # Process the query with the crawling agent
                crawling_results = await self.crawling_agent.run(request.query)
                
                # Fuse the results
                fused_answer = await self.fusion_agent.fuse(crawling_results)
                
                # Calculate execution time
                execution_time = (time.time() - start_time) * 1000  # in milliseconds
                
                # Prepare the response
                response = QueryResponse(
                    query_id=request.query_id,
                    query=request.query,
                    answer=fused_answer.answer,
                    sources=fused_answer.sources,
                    confidence=fused_answer.confidence,
                    execution_time_ms=execution_time,
                    status="success"
                )
                
                logger.info(f"Query processed successfully in {execution_time:.2f}ms")
                return response
                
            except Exception as e:
                logger.error(f"Error processing query: {str(e)}")
                
                # Calculate execution time
                execution_time = (time.time() - start_time) * 1000  # in milliseconds
                
                # Prepare the error response
                response = QueryResponse(
                    query_id=request.query_id,
                    query=request.query,
                    answer=f"Error processing query: {str(e)}",
                    sources=[],
                    confidence=0.0,
                    execution_time_ms=execution_time,
                    status="error",
                    error=str(e)
                )
                
                return response
        
        @self.app.get("/tools", tags=["Tools"])
        async def get_tools():
            """Get information about available tools."""
            return {
                "tools": self.tool_registry.get_tool_descriptions()
            }
    
    def run(self):
        """Run the Crawling Agent API."""
        logger.info(f"Starting Crawling Agent API on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)


def main():
    """Run the Crawling Agent API."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Crawling Agent API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    
    args = parser.parse_args()
    
    api = CrawlingAgentAPI(
        host=args.host,
        port=args.port
    )
    
    api.run()


if __name__ == "__main__":
    main()