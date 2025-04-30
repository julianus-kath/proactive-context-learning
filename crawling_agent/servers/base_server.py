"""
Base MCP Server implementation.
Provides common functionality for all MCP servers.
"""
import os
import yaml
import json
import uuid
from typing import Dict, Any, Optional, List, Union
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
import uvicorn

from crawling_agent.utils.logger import get_logger


class QueryRequest(BaseModel):
    """Model for query requests."""
    query: str = Field(..., description="The query string to execute")
    query_type: str = Field(..., description="The type of query (SQL, MONGODB, SPARQL)")
    parameters: Dict[str, Any] = Field(default={}, description="Query parameters")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request ID")


class QueryResponse(BaseModel):
    """Model for query responses."""
    request_id: str = Field(..., description="The request ID this response is for")
    data: List[Dict[str, Any]] = Field(default=[], description="The query results as a list of records")
    metadata: Dict[str, Any] = Field(default={}, description="Metadata about the query execution")
    status: str = Field(default="success", description="Status of the query execution")
    error: Optional[str] = Field(default=None, description="Error message if the query failed")


class ServerInfo(BaseModel):
    """Model for server information."""
    server_type: str = Field(..., description="Type of the server (ERP, DOCUMENT_STORAGE, KNOWLEDGE_GRAPH)")
    version: str = Field(..., description="Server version")
    capabilities: List[str] = Field(default=[], description="List of server capabilities")
    query_types: List[str] = Field(default=[], description="List of supported query types")
    status: str = Field(default="online", description="Server status")


class BaseMCPServer:
    """
    Base class for all MCP servers.
    Provides common functionality and API endpoints.
    """
    
    def __init__(
        self, 
        server_type: str,
        version: str = "1.0.0",
        host: str = "localhost",
        port: int = 8000,
        config_path: Optional[str] = None
    ):
        """
        Initialize the base MCP server.
        
        Args:
            server_type: Type of the server (ERP, DOCUMENT_STORAGE, KNOWLEDGE_GRAPH)
            version: Server version
            host: Host to bind the server to
            port: Port to bind the server to
            config_path: Path to the configuration file
        """
        self.logger = get_logger(f"mcp_server.{server_type.lower()}")
        self.server_type = server_type
        self.version = version
        self.host = host
        self.port = port
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config = self._load_config(config_path)
        
        # Create FastAPI app
        self.app = FastAPI(
            title=f"MCP {server_type} Server",
            description=f"MCP Server for {server_type} data source",
            version=version,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        # Register routes
        self._register_routes()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from the YAML file with environment variable substitution.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dictionary containing the configuration
        """
        try:
            with open(config_path, 'r') as f:
                # Load the YAML content
                config_str = f.read()
                
                # Replace environment variables
                for env_var in os.environ:
                    placeholder = f"${{{env_var}}}"
                    if placeholder in config_str:
                        config_str = config_str.replace(placeholder, os.environ[env_var])
                
                # Handle default values in format ${VAR:default}
                import re
                pattern = r'\${([^{}]+):([^{}]*)}'
                
                def replace_with_default(match):
                    env_var, default = match.groups()
                    return os.environ.get(env_var, default)
                
                config_str = re.sub(pattern, replace_with_default, config_str)
                
                # Parse the modified YAML
                config = yaml.safe_load(config_str)
                
                return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return {}
    
    def _register_routes(self):
        """Register API routes."""
        
        @self.app.get("/", tags=["General"])
        async def root():
            """Root endpoint that returns basic server information."""
            return {
                "server": f"MCP {self.server_type} Server",
                "version": self.version,
                "status": "online"
            }
        
        @self.app.get("/info", tags=["General"], response_model=ServerInfo)
        async def get_info():
            """Get detailed server information."""
            return self.get_server_info()
        
        @self.app.post("/query", tags=["Query"], response_model=QueryResponse)
        async def execute_query(request_data: dict = Body(...)):
            """Execute a query against the data source."""
            try:
                # Log the received request data
                self.logger.debug(f"Received request data: {json.dumps(request_data)}")
                
                # Validate and convert to QueryRequest
                try:
                    # Ensure required fields are present
                    if "query" not in request_data:
                        raise ValueError("Missing required field: 'query'")
                    if "query_type" not in request_data:
                        raise ValueError("Missing required field: 'query_type'")
                    
                    # Create QueryRequest object
                    request = QueryRequest(
                        query=request_data["query"],
                        query_type=request_data["query_type"],
                        parameters=request_data.get("parameters", {}),
                        request_id=request_data.get("request_id")
                    )
                    
                    self.logger.debug(f"Converted to QueryRequest: {request}")
                    
                except Exception as e:
                    self.logger.error(f"Error validating request data: {str(e)}")
                    raise HTTPException(status_code=422, detail=f"Invalid request data: {str(e)}")
                
                # Execute the query and await the result
                # Execute the query and await the result
                result = await self.execute_query(request)
                return result
                return result
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health", tags=["General"])
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy"}
    
    def get_server_info(self) -> ServerInfo:
        """
        Get server information.
        
        Returns:
            ServerInfo object with server details
        """
        return ServerInfo(
            server_type=self.server_type,
            version=self.version,
            capabilities=self.get_capabilities(),
            query_types=self.get_query_types(),
            status="online"
        )
    
    def get_capabilities(self) -> List[str]:
        """
        Get server capabilities.
        
        Returns:
            List of capability strings
        """
        return ["query"]
    
    def get_query_types(self) -> List[str]:
        """
        Get supported query types.
        
        Returns:
            List of supported query type strings
        """
        return []
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a query against the data source.
        
        Args:
            request: The query request
            
        Returns:
            Query response with results
        """
        raise NotImplementedError("Subclasses must implement execute_query")
    
    def run(self):
        """Run the server."""
        self.logger.info(f"Starting MCP {self.server_type} Server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)