"""
ERP Chatbot Web UI - FastAPI server for the modern web interface
Serves the HTML/CSS/JS chatbot UI and provides API endpoints.
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Resolve current directory and load environment variables from local .env
current_dir = Path(__file__).parent
load_dotenv(current_dir / ".env", override=True)

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:5001").rstrip("/")
API_KEY = os.getenv("API_KEY")

# Database configuration (for UI status only – read directly from .env)
raw_dialect = (os.getenv("DB_DIALECT") or "").strip()
DB_DIALECT = raw_dialect.lower()
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE")

DB_DATABASE = None
if DB_DIALECT.startswith("mssql"):
    DB_DATABASE = MSSQL_DATABASE
elif DB_DIALECT.startswith("postgres"):
    DB_DATABASE = POSTGRES_DATABASE
else:
    # Fallback: try either explicit database vars or legacy DB_NAME
    DB_DATABASE = POSTGRES_DATABASE or MSSQL_DATABASE or os.getenv("DB_NAME")

# Create FastAPI app
app = FastAPI(
    title="ERP Chatbot Web UI",
    description="Modern web interface for the ERP Chatbot",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=current_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main HTML page."""
    index_path = current_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Index file not found")
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return HTMLResponse(content=content)

@app.get("/styles.css")
async def serve_styles():
    """Serve the CSS file."""
    css_path = current_dir / "styles.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS file not found")
    
    return FileResponse(css_path, media_type="text/css")

@app.get("/script.js")
async def serve_script():
    """Serve the JavaScript file."""
    js_path = current_dir / "script.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript file not found")
    
    return FileResponse(js_path, media_type="application/javascript")

@app.get("/health")
async def health_check():
    """Health check endpoint for the web UI."""
    return {
        "status": "healthy",
        "service": "ERP Chatbot Web UI",
        "version": "2.0.0"
    }

@app.get("/config")
async def get_config():
    """Get configuration for the frontend."""
    return {
        "langgraph_url": LANGGRAPH_URL,
        "api_key_set": bool(API_KEY),
        "version": "2.0.0",
        "db_dialect": DB_DIALECT,
        "db_database": DB_DATABASE,
    }


@app.get("/backend_health")
async def backend_health():
    """Health check endpoint for the backend LangGraph/agent service."""
    target_url = f"{LANGGRAPH_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(target_url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Backend health check failed: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    try:
        payload = resp.json() if "application/json" in content_type else {"raw": resp.text}
    except ValueError:
        payload = {"raw": resp.text}

    return {
        "status": "online" if resp.status_code == 200 else "degraded",
        "backend_status_code": resp.status_code,
        "backend_response": payload,
    }


@app.post("/process_conversation")
async def proxy_process_conversation(request: Request):
    """
    Proxy /process_conversation requests to the LangGraph/agent service.

    The API key is attached server-side so it never lives in the browser.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request payload")

    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    forward_body = dict(body)
    if API_KEY:
        forward_body["api_key"] = API_KEY

    target_url = f"{LANGGRAPH_URL}/process_conversation"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(target_url, json=forward_body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Error contacting backend service: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    try:
        data = resp.json() if "application/json" in content_type else {"error": resp.text}
    except ValueError:
        data = {"error": resp.text}

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data)

    return data

if __name__ == "__main__":
    print("Starting ERP Chatbot Web UI...")
    print("Make sure the following are running:")
    print("   - LangGraph Service (http://localhost:5001)")
    print("   - MCP Server (http://localhost:8000)")
    print("   - PostgreSQL database")
    print()
    print("Web UI will be available at: http://localhost:3000")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="info"
    )
