"""
ERP Chatbot Web UI - FastAPI server for the modern web interface
Serves the HTML/CSS/JS chatbot UI and provides API endpoints.
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

# Get the directory where this script is located
current_dir = Path(__file__).parent

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
        "langgraph_url": os.getenv("LANGGRAPH_URL", "http://localhost:5001"),
        "api_key_set": bool(os.getenv("API_KEY")),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    print("🚀 Starting ERP Chatbot Web UI...")
    print("📋 Make sure the following are running:")
    print("   - LangGraph Service (http://localhost:5001)")
    print("   - MCP Server (http://localhost:8000)")
    print("   - PostgreSQL database")
    print()
    print("🌐 Web UI will be available at: http://localhost:3000")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="info"
    )