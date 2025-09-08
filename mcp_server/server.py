"""
MCP Database Server - FastAPI implementation
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Database Server",
    description="Model Context Protocol server for database access",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key authentication
API_KEY = os.getenv("MCP_API_KEY", "supersecretapikey")

# Global database manager
db_manager = None

def verify_api_key(x_api_key: str = Header(None), authorization: str = Header(None)):
    # Check X-API-Key header first
    if x_api_key and x_api_key == API_KEY:
        return x_api_key
    
    # Check Authorization header (Bearer token)
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]  # Remove "Bearer " prefix
            if token == API_KEY:
                return token
    
    raise HTTPException(status_code=401, detail="Invalid API key")
    return None

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the database connection on startup."""
    global db_manager
    try:
        from db import DatabaseManager
        db_manager = DatabaseManager()
        await db_manager.initialize()
        logger.info("✅ MCP Database Server initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MCP Database Server: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Close the database connection on shutdown."""
    global db_manager
    if db_manager:
        await db_manager.close()
        logger.info("✅ MCP Database Server shutdown complete")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "service": "MCP Database Server",
        "database_ready": db_manager is not None and db_manager.pool is not None
    }

@app.post("/mcp")
async def mcp_endpoint(
    request: JSONRPCRequest,
    api_key: str = Depends(verify_api_key)
):
    """MCP JSON-RPC endpoint."""
    try:
        # Import tools here to avoid circular imports
        from tools import MCPTools
        
        if request.method == "tools/list":
            tools = MCPTools.get_available_tools()
            return JSONRPCResponse(
                result={"tools": [tool.dict() for tool in tools]},
                id=request.id
            )
        elif request.method == "tools/call":
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            result = await MCPTools.execute_tool(tool_name, arguments, db_manager)
            return JSONRPCResponse(result=result.dict(), id=request.id)
        else:
            return JSONRPCResponse(
                error={"code": -32601, "message": f"Method not found: {request.method}"},
                id=request.id
            )
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return JSONRPCResponse(
            error={"code": -32603, "message": str(e)},
            id=request.id
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
