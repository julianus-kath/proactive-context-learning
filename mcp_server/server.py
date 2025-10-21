"""
MCP Database Server - FastAPI implementation
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union
import uvicorn
from dotenv import load_dotenv

# MCP Server internal imports (must be at module level for package context)
from .database_adapter import DatabaseAdapter
from .scout_mode import run_scout_mode
from .discovery_tools import DiscoveryTools
from .observability import get_metrics_summary
from .tools import MCPTools

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
    """Initialize the database connection and run Scout Mode on startup."""
    global db_manager
    try:
        db_manager = DatabaseAdapter()
        await db_manager.initialize()
        logger.info("✅ MCP Database Server initialized successfully")
        
        # Phase 7: Run Scout Mode (async, doesn't block startup)
        try:
            cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
            scout_report = await run_scout_mode(db_manager, cache_dir=cache_dir)
            logger.info(f"🔍 Scout Mode Report: {scout_report}")
        except Exception as scout_error:
            logger.warning(f"⚠️ Scout Mode startup job failed (non-blocking): {scout_error}")
            # Don't raise - Scout Mode is optional and shouldn't block startup
        
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
    Phase 7.1 (Scout Mode): Comprehensive health check with catalog metrics.
    
    Returns:
    - ok: Overall health status
    - service: Service name and version
    - db_connected: Database connection status
    - catalog: Scout catalog metrics (tables_count, catalog_age_s, cache_hits)
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
        "phase": "7.1 - Scout Mode & Semantic Caching",
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
        
        # Phase 7.1: Scout catalog metrics (from SchemaCatalog or SemanticCatalogBuilder)
        health_data["catalog"] = {
            "tables_count": 0,
            "catalog_age_s": None,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_ratio": 0.0,
            "warmup_complete": False
        }
        
        if hasattr(db_manager, 'catalog') and db_manager.catalog:
            catalog = db_manager.catalog
            
            # Get metrics from SchemaCatalog
            if hasattr(catalog, '_metrics'):
                metrics = catalog._metrics
                health_data["catalog"]["tables_count"] = metrics.table_count
                health_data["catalog"]["cache_hits"] = metrics.cache_hits
                health_data["catalog"]["cache_misses"] = metrics.cache_misses
                health_data["catalog"]["hit_ratio"] = metrics.hit_ratio()
                health_data["catalog"]["warmup_complete"] = catalog._warmup_complete
                
                # Calculate age from last refresh
                if metrics.last_refresh_time:
                    health_data["catalog"]["catalog_age_s"] = time.time() - metrics.last_refresh_time
            
            # Alternative: Get from db_manager.get_cache_stats()
            elif hasattr(db_manager, 'get_cache_stats'):
                catalog_metrics = db_manager.get_cache_stats()
                health_data["catalog"]["tables_count"] = catalog_metrics.get("table_count", 0)
                health_data["catalog"]["cache_hits"] = catalog_metrics.get("cache_hits", 0)
                health_data["catalog"]["cache_misses"] = catalog_metrics.get("cache_misses", 0)
                health_data["catalog"]["hit_ratio"] = catalog_metrics.get("hit_ratio", 0.0)
                health_data["catalog"]["catalog_age_s"] = catalog_metrics.get("catalog_age_s")
                health_data["catalog"]["warmup_complete"] = catalog_metrics.get("warmup_complete", False)
        
        # Phase 4: Discovery tools metrics
        try:
            if hasattr(DiscoveryTools, 'get_cache_stats'):
                discovery_stats = DiscoveryTools.get_cache_stats()
                health_data["discovery_tools"] = discovery_stats
        except Exception as e:
            logger.warning(f"Failed to get discovery tools stats: {e}")
        
        # Phase 6: Connection pool statistics
        try:
            if hasattr(db_manager, 'get_pool_stats'):
                pool_stats = db_manager.get_pool_stats()
                health_data["pool_stats"] = pool_stats
        except Exception as e:
            logger.warning(f"Failed to get pool stats: {e}")
            health_data["pool_stats"] = {"error": str(e)}
        
        # Phase 6: Observability metrics
        try:
            metrics_summary = get_metrics_summary()
            health_data["observability"] = metrics_summary
        except Exception as e:
            logger.warning(f"Failed to get observability metrics: {e}")
        
        # Phase 6: Last database error
        try:
            if hasattr(db_manager, 'get_last_error'):
                last_error = db_manager.get_last_error()
                if last_error:
                    health_data["last_db_error"] = last_error
        except Exception as e:
            logger.warning(f"Failed to get last error: {e}")
        
        # Test a simple query if connected
        if db_connected:
            try:
                if hasattr(db_manager, 'fetch'):
                    test_result = await db_manager.fetch("SELECT 1 as test", limit=1)
                    health_data["query_test"] = "passed"
            except Exception as e:
                health_data["query_test"] = "failed"
                health_data["query_error"] = str(e)
                health_data["ok"] = False
        
    except Exception as e:
        health_data["ok"] = False
        health_data["error"] = str(e)
        logger.error(f"Health check error: {e}")
    
    return health_data

@app.post("/mcp")
async def mcp_endpoint(
    request: JSONRPCRequest,
    api_key: str = Depends(verify_api_key)
):
    """MCP JSON-RPC endpoint with proper envelope & error handling."""
    try:
        import json as json_module
        
        response_data = None
        
        if request.method == "tools/list":
            tools = MCPTools.get_available_tools()
            response_data = JSONRPCResponse(
                result={"tools": [tool.dict() for tool in tools]},
                id=request.id
            )
        elif request.method == "tools/call":
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            # Execute tool with error boundary
            try:
                result = await MCPTools.execute_tool(tool_name, arguments, db_manager)
                # Ensure result is properly JSON-serializable
                result_dict = result.dict() if hasattr(result, 'dict') else result
                
                # Validate content structure
                if isinstance(result_dict, dict) and 'content' in result_dict:
                    # Ensure content is a list of dicts with proper structure
                    if not isinstance(result_dict['content'], list):
                        result_dict['content'] = []
                    
                    # Ensure each content item is JSON-serializable
                    valid_content = []
                    for item in result_dict.get('content', []):
                        if isinstance(item, dict):
                            valid_content.append(item)
                        else:
                            valid_content.append({"type": "text", "text": str(item)})
                    result_dict['content'] = valid_content
                
                logger.info(f"✅ Tool '{tool_name}' executed successfully")
                response_data = JSONRPCResponse(result=result_dict, id=request.id)
                
            except Exception as tool_error:
                logger.error(f"❌ Tool execution failed for '{tool_name}': {tool_error}")
                response_data = JSONRPCResponse(
                    error={
                        "code": -32603,
                        "message": f"Tool execution error: {str(tool_error)}",
                        "data": {"tool": tool_name, "error_type": type(tool_error).__name__}
                    },
                    id=request.id
                )
        else:
            response_data = JSONRPCResponse(
                error={"code": -32601, "message": f"Method not found: {request.method}"},
                id=request.id
            )
        
        # Return with proper JSON content-type header
        return JSONResponse(
            content=response_data.dict(exclude_none=True),
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "X-MCP-Version": "2.0"
            }
        )
        
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        error_response = JSONRPCResponse(
            error={"code": -32603, "message": str(e)},
            id=getattr(request, 'id', None)
        )
        return JSONResponse(
            content=error_response.dict(exclude_none=True),
            status_code=500,
            headers={
                "Content-Type": "application/json",
                "X-MCP-Version": "2.0"
            }
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
