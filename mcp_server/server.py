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
        from database_adapter import DatabaseAdapter
        db_manager = DatabaseAdapter()
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
    """
    Phase 6: Comprehensive health check endpoint.
    
    Returns:
    - ok: Overall health status
    - service: Service name and version
    - db_connected: Database connection status
    - catalog_stats: Catalog metrics (age, hits, table count)
    - pool_stats: Connection pool statistics
    - discovery_tools: Discovery tools cache stats
    - observability: Recent tool call metrics
    - last_db_error: Last database error (if any)
    """
    import time
    
    # Basic health status
    health_data = {
        "ok": True,
        "service": "MCP Database Server",
        "version": "1.0.0",
        "phase": "6 - Observability & Guardrails",
        "timestamp": time.time()
    }
    
    # Database connectivity
    if db_manager is None:
        health_data["ok"] = False
        health_data["db_connected"] = False
        health_data["error"] = "Database manager not initialized"
        return health_data
    
    try:
        # Check if database is connected
        db_connected = db_manager.pool is not None
        health_data["db_connected"] = db_connected
        
        # Get database dialect/mode
        if hasattr(db_manager, 'dialect'):
            health_data["dialects"] = [db_manager.dialect]
            health_data["db_mode"] = db_manager.dialect
        elif hasattr(db_manager, 'client'):
            health_data["dialects"] = [db_manager.client.mode]
            health_data["db_mode"] = db_manager.client.mode
        else:
            health_data["dialects"] = ["unknown"]
        
        # Phase 3: Catalog metrics
        if hasattr(db_manager, 'catalog') and db_manager.catalog:
            catalog_metrics = db_manager.get_cache_stats()
            health_data["catalog_stats"] = {
                "age_s": catalog_metrics.get("catalog_age_s"),
                "cache_hits": catalog_metrics.get("cache_hits", 0),
                "cache_misses": catalog_metrics.get("cache_misses", 0),
                "hit_ratio": catalog_metrics.get("hit_ratio", 0.0),
                "table_count": catalog_metrics.get("table_count", 0),
                "warmup_complete": catalog_metrics.get("warmup_complete", False)
            }
            
            # Phase 4: Discovery tools metrics
            try:
                from discovery_tools import DiscoveryTools
                discovery_stats = DiscoveryTools.get_cache_stats()
                health_data["discovery_tools"] = discovery_stats
            except Exception as e:
                logger.warning(f"Failed to get discovery tools stats: {e}")
        # Legacy cache information (backward compatibility)
        elif hasattr(db_manager, '_schema_cache'):
            cache = db_manager._schema_cache
            health_data["catalog_stats"] = {
                "cached": cache.get("data") is not None,
                "age_s": int(time.time() - cache["timestamp"]) if cache.get("timestamp") else None,
                "cache_hits": cache.get("hits", 0)
            }
        else:
            health_data["catalog_stats"] = {
                "cached": False,
                "age_s": None,
                "cache_hits": 0
            }
        
        # Phase 6: Connection pool statistics
        try:
            pool_stats = db_manager.get_pool_stats()
            health_data["pool_stats"] = pool_stats
        except Exception as e:
            logger.warning(f"Failed to get pool stats: {e}")
            health_data["pool_stats"] = {"error": str(e)}
        
        # Phase 6: Observability metrics
        try:
            from observability import get_metrics_summary
            metrics_summary = get_metrics_summary()
            health_data["observability"] = metrics_summary
        except Exception as e:
            logger.warning(f"Failed to get observability metrics: {e}")
            health_data["observability"] = {"error": str(e)}
        
        # Phase 6: Last database error
        try:
            last_error = db_manager.get_last_error()
            if last_error:
                health_data["last_db_error"] = last_error
        except Exception as e:
            logger.warning(f"Failed to get last error: {e}")
        
        # Test a simple query if connected
        if db_connected:
            try:
                test_result = await db_manager.fetch("SELECT 1 as test", limit=1)
                health_data["query_test"] = "passed"
            except Exception as e:
                health_data["query_test"] = "failed"
                health_data["query_error"] = str(e)
                health_data["ok"] = False
        
    except Exception as e:
        health_data["ok"] = False
        health_data["error"] = str(e)
    
    return health_data

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
