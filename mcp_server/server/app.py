"""
MCP Database Server - FastAPI implementation
"""

import os
import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union
import uvicorn
from dotenv import load_dotenv

# MCP Server internal imports (using absolute imports for Uvicorn compatibility)
from mcp_server.database.database_adapter import DatabaseAdapter
from mcp_server.scout.mode import run_scout_mode
from mcp_server.tools import MCPTools
from mcp_server.scout.runner import ScoutRunner
from mcp_server.server.health import set_scout_runner, get_health_status, get_health_summary

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

# Global Scout Runner
scout_runner = None

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
        # Try to initialize, but with a timeout to prevent infinite loops
        logger.info("🔄 Testing database connection (timeout: 10s)...")
        try:
            # Test connection first with a short timeout
            is_healthy = await asyncio.wait_for(
                db_manager.connector.test_connection(),
                timeout=10
            )
            if not is_healthy:
                raise RuntimeError("Database connection test failed - check connectivity")
            
            logger.info("✅ Database connection verified")
            
            # Now initialize catalog (can take longer)
            await asyncio.wait_for(
                db_manager.initialize(),
                timeout=60  # 1 minute timeout for catalog
            )
            logger.info("✅ MCP Database Server initialized successfully")
        
        except asyncio.TimeoutError:
            logger.error("❌ Database initialization timed out - check VPN/network connectivity")
            raise RuntimeError("Database connection timeout - VPN may not be active")
        
        # Phase 1: Initialize Scout Runner (dialect-agnostic)
        global scout_runner
        scout_runner = None  # Initialize as None
        set_scout_runner(None)
        scout_disabled = os.getenv("SCOUT_DISABLE", "false").lower() == "true"
        setattr(db_manager, "scout_disabled", scout_disabled)
        if scout_disabled:
            setattr(db_manager, "scout_runner", None)
            logger.info("⏭️ SCOUT_DISABLE=true: using SchemaCatalog-only discovery mode")
        else:
            try:
                dialect_label = (db_manager.dialect or "unknown").upper()
                logger.info(f"🏗️ Initializing Scout Runner ({dialect_label} mode)...")
                scout_runner = ScoutRunner(
                    db_adapter=db_manager,
                    catalog_dir=os.getenv("SCOUT_CATALOG_DIR", "data/catalog"),
                    ttl_hours=int(os.getenv("SCOUT_TTL_HOURS", str(24 * 7))),  # 7 days
                    refresh_interval_hours=int(os.getenv("SCOUT_REFRESH_INTERVAL_HOURS", "24"))
                )

                # Share the runner with health + tool path so all components use the same instance
                setattr(db_manager, "scout_runner", scout_runner)
                set_scout_runner(scout_runner)

                # Start Scout Runner (non-blocking)
                await scout_runner.start()
                logger.info("✅ Scout Runner initialized and started")
            except Exception as scout_error:
                logger.warning(f"⚠️ Scout Runner initialization failed (non-blocking): {scout_error}")
                setattr(db_manager, "scout_runner", None)
                # Don't raise - Scout Mode is optional and shouldn't block startup

            # Legacy Phase 7: Run old Scout Mode as bootstrap fallback
            # Keep enabled to preserve historical behavior in both dialects.
            legacy_bootstrap_enabled = os.getenv("SCOUT_LEGACY_BOOTSTRAP", "true").lower() == "true"
            if legacy_bootstrap_enabled and (not scout_runner or not scout_runner.is_ready()):
                try:
                    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
                    scout_report = await asyncio.wait_for(
                        run_scout_mode(db_manager, cache_dir=cache_dir),
                        timeout=30
                    )
                    logger.info(f"🔍 Legacy Scout Mode Report: {scout_report}")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Legacy Scout Mode startup job timed out (non-blocking)")
                except Exception as scout_error:
                    logger.warning(f"⚠️ Legacy Scout Mode startup job failed (non-blocking): {scout_error}")

            scout_require_ready = os.getenv("SCOUT_REQUIRE_READY", "false").lower() == "true"
            if scout_require_ready:
                wait_timeout = int(os.getenv("SCOUT_REQUIRE_READY_TIMEOUT_SECONDS", "60"))
                if scout_runner:
                    start_wait = asyncio.get_event_loop().time()
                    while not scout_runner.is_ready():
                        elapsed = asyncio.get_event_loop().time() - start_wait
                        if elapsed >= wait_timeout:
                            break
                        await asyncio.sleep(0.5)

                if not scout_runner or not scout_runner.is_ready():
                    raise RuntimeError(
                        "SCOUT_REQUIRE_READY=true but Scout catalog is not ready "
                        f"after {wait_timeout}s"
                    )

        if scout_runner and scout_runner.is_ready():
            logger.info("✅ Scout catalog is ready at startup")
        else:
            logger.info("ℹ️ Scout catalog not ready at startup; discovery will temporarily fall back to SchemaCatalog")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize MCP Database Server: {e}")
        logger.error(f"   Check: VPN connection, SQL Server availability at {os.getenv('MSSQL_SERVER', 'unknown')}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Close the database connection on shutdown."""
    global db_manager
    global scout_runner
    if scout_runner:
        try:
            await scout_runner.stop()
        except Exception as e:
            logger.warning(f"⚠️ Error stopping Scout Runner: {e}")
        finally:
            scout_runner = None
    if db_manager:
        await db_manager.close()
        logger.info("✅ MCP Database Server shutdown complete")

@app.get("/health")
async def health_check():
    """
    Phase 1: Comprehensive health check with Scout Mode metrics.

    Returns comprehensive health status including:
    - Database connectivity
    - Scout catalog status and metrics
    - Build statistics and performance
    """
    try:
        health_status = await get_health_status(db_manager)
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.post("/mcp")
async def mcp_endpoint(
    request: JSONRPCRequest,
    api_key: str = Depends(verify_api_key)
):
    """MCP JSON-RPC endpoint with proper envelope & error handling."""
    try:
        # Validate request
        if not request.method or not request.params:
            raise HTTPException(status_code=400, detail="Invalid MCP request")

        # Extract method and parameters
        method = request.method
        params = request.params

        logger.info(f"MCP call: {method}")

        # Route to appropriate tool handler
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            # Route to tool handlers
            if tool_name == "search_tables":
                result = await MCPTools._search_tables(tool_args, db_manager)
            elif tool_name == "list_tables":
                result = await MCPTools._list_tables(tool_args, db_manager)
            elif tool_name == "describe_table":
                result = await MCPTools._describe_table(tool_args, db_manager)
            elif tool_name == "query":
                result = await MCPTools._query(tool_args, db_manager)
            elif tool_name == "query_bounded":
                result = await MCPTools._query_bounded(tool_args, db_manager)
            elif tool_name == "run_query":
                result = await MCPTools._run_query(tool_args, db_manager)
            elif tool_name == "get_column_index":
                result = await MCPTools._get_column_index(tool_args, db_manager)
            elif tool_name == "list_relations":
                result = await MCPTools._list_relations(tool_args, db_manager)
            elif tool_name == "list_views":
                result = await MCPTools._list_views(tool_args, db_manager)
            elif tool_name == "search_views":
                result = await MCPTools._search_views(tool_args, db_manager)
            elif tool_name == "describe_view":
                result = await MCPTools._describe_view(tool_args, db_manager)
            elif tool_name == "scout_catalog_diagnostics":
                result = await MCPTools._scout_catalog_diagnostics(tool_args, db_manager)
            elif tool_name == "scout_catalog_get":
                # New tool: expose consolidated Scout catalog over MCP
                result = await MCPTools._scout_catalog_get(tool_args, db_manager)
            elif tool_name == "scout_catalog_refresh":
                result = await MCPTools._scout_catalog_refresh(tool_args, db_manager)
            else:
                raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

            return JSONResponse(content={"result": result.content})

        else:
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")

    except HTTPException as he:
        # Preserve specific HTTP error codes like 404
        logger.error(f"MCP endpoint error: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default
    port = int(os.getenv("MCP_PORT", "8000"))

    logger.info(f"Starting MCP Database Server on port {port}")
    uvicorn.run(
        "mcp_server.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
