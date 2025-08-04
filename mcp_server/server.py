"""
MCP Server implementation using FastAPI with JSON-RPC 2.0 protocol.
"""

import logging
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from dotenv import load_dotenv

from models import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCError,
    MCPInitializeParams, MCPInitializeResult, MCPCallToolParams
)
from tools import MCPTools
from db import db_manager

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="MCP Database Server",
    description="Model Context Protocol server for PostgreSQL database access",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key validation
API_KEY = os.getenv("API_KEY", "supersecretapikey")

def validate_api_key(authorization: Optional[str] = Header(None)):
    """Validate API key from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.split(" ")[1]
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return token

# MCP Protocol Implementation
class MCPServer:
    """MCP Server implementation."""
    
    def __init__(self):
        self.initialized = False
        self.client_capabilities = {}
    
    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle MCP JSON-RPC requests."""
        try:
            if request.method == "initialize":
                return await self._handle_initialize(request)
            elif request.method == "list_tools":
                return await self._handle_list_tools(request)
            elif request.method == "call_tool":
                return await self._handle_call_tool(request)
            else:
                return JSONRPCResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32601,
                        message="Method not found",
                        data={"method": request.method}
                    ).__dict__
                )
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32603,
                    message="Internal error",
                    data={"error": str(e)}
                ).__dict__
            )
    
    async def _handle_initialize(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle MCP initialize method."""
        try:
            params = MCPInitializeParams(**request.params) if request.params else None
            
            if params:
                self.client_capabilities = params.capabilities
            
            self.initialized = True
            
            result = MCPInitializeResult(
                protocolVersion="2024-11-05",
                capabilities={
                    "tools": {}
                },
                serverInfo={
                    "name": "mcp-database-server",
                    "version": "1.0.0"
                }
            )
            
            return JSONRPCResponse(id=request.id, result=result.__dict__)
            
        except Exception as e:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32602,
                    message="Invalid params",
                    data={"error": str(e)}
                ).__dict__
            )
    
    async def _handle_list_tools(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle MCP list_tools method."""
        if not self.initialized:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32002,
                    message="Server not initialized"
                ).__dict__
            )
        
        tools = MCPTools.get_available_tools()
        tools_dict = [tool.__dict__ for tool in tools]
        
        return JSONRPCResponse(
            id=request.id,
            result={"tools": tools_dict}
        )
    
    async def _handle_call_tool(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle MCP call_tool method."""
        if not self.initialized:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32002,
                    message="Server not initialized"
                ).__dict__
            )
        
        try:
            params = MCPCallToolParams(**request.params) if request.params else None
            
            if not params:
                return JSONRPCResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32602,
                        message="Invalid params"
                    ).__dict__
                )
            
            result = await MCPTools.execute_tool(params.name, params.arguments or {})
            
            return JSONRPCResponse(
                id=request.id,
                result=result.__dict__
            )
            
        except Exception as e:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32603,
                    message="Internal error",
                    data={"error": str(e)}
                ).__dict__
            )

# Global MCP server instance
mcp_server = MCPServer()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    await db_manager.initialize()
    logger.info("MCP Database Server started")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    await db_manager.close()
    logger.info("MCP Database Server stopped")

@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "MCP Database Server",
        "version": "1.0.0",
        "protocol": "MCP JSON-RPC 2.0",
        "description": "Model Context Protocol server for PostgreSQL database access"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        await db_manager.fetch("SELECT 1", limit=1)
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@app.post("/mcp")
async def mcp_endpoint(
    request: JSONRPCRequest,
    api_key: str = Depends(validate_api_key)
):
    """Main MCP JSON-RPC endpoint."""
    response = await mcp_server.handle_request(request)
    return response

@app.get("/events")
async def events_endpoint(api_key: str = Depends(validate_api_key)):
    """Server-Sent Events endpoint for streaming (optional for future use)."""
    async def event_stream():
        while True:
            # For now, just send a heartbeat every 30 seconds
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
            await asyncio.sleep(30)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )