#!/bin/bash

# ERP Natural Language Query Assistant - Service Startup Script
# This script starts all required services for the ERP chatbot system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
cd "$PROJECT_ROOT"

# Log file for services
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo -e "${BLUE}🚀 ERP Natural Language Query Assistant Startup${NC}"
echo -e "${BLUE}===========================================${NC}"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port)
    if [ ! -z "$pid" ]; then
        echo -e "${YELLOW}⚠️  Killing existing process on port $port (PID: $pid)${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 2
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for $service_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start within $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    
    # Kill services on known ports
    kill_port 3000  # Web UI
    kill_port 5001  # LangGraph Service
    kill_port 8000  # MCP Server
    
    # Kill any remaining Python processes related to our services
    pkill -f "web_app.py" 2>/dev/null || true
    pkill -f "langgraph_service.py" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo -e "${BLUE}📋 Pre-flight checks...${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Load environment variables early to check DB_MODE
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Determine database mode
DB_MODE=${DB_MODE:-"local"}
echo -e "${BLUE}🔍 Database Mode: ${DB_MODE}${NC}"

if [ "$DB_MODE" = "proxy" ]; then
    # ============================================
    # PROXY MODE - Check Windows proxy connection
    # ============================================
    echo -e "${YELLOW}🔍 Checking Windows proxy connection...${NC}"
    
    PROXY_BASE_URL=${PROXY_BASE_URL:-""}
    PROXY_API_KEY=${PROXY_API_KEY:-""}
    
    if [ -z "$PROXY_BASE_URL" ]; then
        echo -e "${RED}❌ PROXY_BASE_URL not set in .env${NC}"
        echo -e "${YELLOW}💡 Please configure proxy settings in .env:${NC}"
        echo -e "   DB_MODE=proxy"
        echo -e "   PROXY_BASE_URL=http://your-windows-ip:5000"
        echo -e "   PROXY_API_KEY=your-api-key (or leave empty if no auth)"
        echo -e "   PROXY_DEFAULT_CONN=corp_sql_erp"
        exit 1
    fi
    
    # Parse proxy URL for connectivity test
    PROXY_HOST=$(echo $PROXY_BASE_URL | sed -e 's|^[^/]*//||' -e 's|:.*||')
    PROXY_PORT=$(echo $PROXY_BASE_URL | sed -e 's|^[^:]*:||' -e 's|/.*||' | grep -o '[0-9]*')
    PROXY_PORT=${PROXY_PORT:-5000}
    
    echo -e "${YELLOW}   Testing connection to ${PROXY_HOST}:${PROXY_PORT}...${NC}"
    
    # Test network connectivity
    if command -v nc &> /dev/null; then
        if nc -z -w 5 $PROXY_HOST $PROXY_PORT 2>/dev/null; then
            echo -e "${GREEN}✅ Proxy server is reachable${NC}"
        else
            echo -e "${RED}❌ Cannot connect to proxy server${NC}"
            echo -e "${YELLOW}💡 Please check:${NC}"
            echo -e "   1. Windows proxy is running: python vpn_config/proxy.py"
            echo -e "   2. Windows firewall allows port ${PROXY_PORT}"
            echo -e "   3. IP address is correct: ${PROXY_HOST}"
            exit 1
        fi
    else
        # Fallback to curl if nc not available
        if curl -s --connect-timeout 5 "${PROXY_BASE_URL}/health" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Proxy server is reachable${NC}"
        else
            echo -e "${YELLOW}⚠️  Cannot verify proxy connectivity (install 'nc' for better checks)${NC}"
            echo -e "${YELLOW}   Continuing anyway...${NC}"
        fi
    fi
    
    # Test proxy health endpoint
    echo -e "${YELLOW}   Testing proxy health endpoint...${NC}"
    
    if [ -n "$PROXY_API_KEY" ]; then
        HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 \
            -H "X-API-Key: ${PROXY_API_KEY}" \
            "${PROXY_BASE_URL}/health" 2>/dev/null)
    else
        HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 \
            "${PROXY_BASE_URL}/health" 2>/dev/null)
    fi
    
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Proxy health check passed${NC}"
        
        # Show proxy info if available (BSD-compatible: remove last line)
        PROXY_INFO=$(echo "$HEALTH_RESPONSE" | sed '$d')
        if echo "$PROXY_INFO" | grep -q "connections"; then
            CONN_COUNT=$(echo "$PROXY_INFO" | grep -o '"connections":\[[^]]*\]' | grep -o '{' | wc -l | tr -d ' ')
            if [ "$CONN_COUNT" -gt 0 ]; then
                echo -e "${GREEN}   Found ${CONN_COUNT} database connection(s)${NC}"
            fi
        fi
    elif [ "$HTTP_CODE" = "401" ]; then
        echo -e "${RED}❌ Proxy authentication failed${NC}"
        echo -e "${YELLOW}💡 Check PROXY_API_KEY in .env matches Windows proxy${NC}"
        exit 1
    elif [ -z "$HTTP_CODE" ]; then
        echo -e "${RED}❌ Proxy is not responding${NC}"
        echo -e "${YELLOW}💡 Please start Windows proxy: python vpn_config/proxy.py${NC}"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Proxy returned status code: ${HTTP_CODE}${NC}"
        echo -e "${YELLOW}   Continuing anyway...${NC}"
    fi
    
    echo -e "${GREEN}✅ Proxy mode configured and ready${NC}"
    
else
    # ============================================
    # LOCAL MODE - Check PostgreSQL
    # ============================================
    echo -e "${YELLOW}🔍 Checking PostgreSQL...${NC}"
    
    if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  PostgreSQL is not running. Starting it...${NC}"
        
        # Try to start PostgreSQL using Homebrew
        if command -v brew &> /dev/null; then
            brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || {
                echo -e "${RED}❌ Failed to start PostgreSQL with Homebrew${NC}"
                echo -e "${YELLOW}💡 Please start PostgreSQL manually:${NC}"
                echo -e "   brew services start postgresql"
                echo -e "   or"
                echo -e "   sudo systemctl start postgresql"
                exit 1
            }
            sleep 3
        else
            echo -e "${RED}❌ PostgreSQL is not running and Homebrew is not available${NC}"
            echo -e "${YELLOW}💡 Please start PostgreSQL manually${NC}"
            exit 1
        fi
    fi
    
    # Verify PostgreSQL is now running
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is running${NC}"
    else
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        exit 1
    fi
    
    # Check if the database exists
    DB_NAME=${DB_NAME:-"synthetic_erp_data"}
    DB_USER=${DB_USER:-"juli"}
    
    echo -e "${YELLOW}🔍 Checking database '${DB_NAME}'...${NC}"
    if ! psql -h localhost -p 5432 -U $DB_USER -d $DB_NAME -c "SELECT 1;" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Database '${DB_NAME}' not found. Creating it...${NC}"
        createdb -h localhost -p 5432 -U $DB_USER $DB_NAME 2>/dev/null || {
            echo -e "${RED}❌ Failed to create database${NC}"
            echo -e "${YELLOW}💡 Please create the database manually:${NC}"
            echo -e "   createdb -U $DB_USER $DB_NAME"
            exit 1
        }
    fi
    
    # Check and restore database data if needed
    echo -e "${YELLOW}🔍 Checking database data...${NC}"
    if ! psql -h localhost -p 5432 -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM products;" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Database tables missing. Restoring...${NC}"
        if [ -f "restore_database.py" ]; then
            python3 restore_database.py
        else
            echo -e "${YELLOW}⚠️  restore_database.py not found, skipping...${NC}"
        fi
    fi
    
    echo -e "${GREEN}✅ Local database setup complete${NC}"
fi

# Check and install dependencies
echo -e "${YELLOW}🔍 Checking Python dependencies...${NC}"

# Install LangGraph integration dependencies
if [ -f "langgraph_integration/requirements.txt" ]; then
    echo -e "${YELLOW}📦 Installing LangGraph integration dependencies...${NC}"
    pip3 install -r langgraph_integration/requirements.txt >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to install LangGraph dependencies${NC}"
        echo -e "${YELLOW}💡 Try running manually: pip3 install -r langgraph_integration/requirements.txt${NC}"
        exit 1
    }
fi

# Install chatbot UI dependencies
if [ -f "chatbot_ui/requirements.txt" ]; then
    echo -e "${YELLOW}📦 Installing Chatbot UI dependencies...${NC}"
    pip3 install -r chatbot_ui/requirements.txt >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to install Chatbot UI dependencies${NC}"
        exit 1
    }
fi

# Skip synthetic data service dependencies (using direct database setup instead)

# Install MCP server dependencies
if [ -f "mcp_server/requirements.txt" ]; then
    echo -e "${YELLOW}📦 Installing MCP Server dependencies...${NC}"
    pip3 install -r mcp_server/requirements.txt >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to install MCP Server dependencies${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Check environment variables
echo -e "${YELLOW}🔍 Checking environment variables...${NC}"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Creating .env file...${NC}"
    cat > .env << EOF
# OpenAI API Key (required for LangGraph)
OPENAI_API_KEY=your_openai_api_key_here

# LangGraph Service Configuration
LANGGRAPH_URL=http://localhost:5001
API_KEY=supersecretapikey

# Database Configuration Mode
# Options: "local" (PostgreSQL on Mac) or "proxy" (Windows proxy server)
DB_MODE=local

# Local PostgreSQL Configuration (used when DB_MODE=local)
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=juli
DB_PASSWORD=

# Proxy Configuration (used when DB_MODE=proxy)
# Uncomment and configure these if using Windows proxy:
# PROXY_BASE_URL=http://192.168.1.35:5000
# PROXY_API_KEY=your-api-key-here
# PROXY_DEFAULT_CONN=corp_sql_erp
# PROXY_TLS_VERIFY=false

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
MCP_API_KEY=supersecretapikey
EOF
    echo -e "${YELLOW}⚠️  Please edit .env file and add your OPENAI_API_KEY${NC}"
    echo -e "${YELLOW}⚠️  Configure DB_MODE (local or proxy) based on your setup${NC}"
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY is not set in .env file${NC}"
    echo -e "${YELLOW}💡 Please edit .env file and add your OpenAI API key${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment variables configured${NC}"

# Clean up any existing processes
echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
kill_port 3000
kill_port 5001
kill_port 8000

echo -e "${BLUE}🚀 Starting services...${NC}"

# Start MCP Server (if we have the files)
if [ -f "mcp_server/tools.py" ]; then
    echo -e "${YELLOW}🔧 Starting MCP Server...${NC}"
    cd "$PROJECT_ROOT/mcp_server"
    
    # Create a simple server.py if it doesn't exist
    if [ ! -f "server.py" ]; then
        echo -e "${YELLOW}⚠️  Creating MCP server.py...${NC}"
        cat > server.py << 'EOF'
"""
MCP Database Server - FastAPI implementation
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
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

def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "MCP Database Server"}

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
            
            result = await MCPTools.call_tool(tool_name, arguments)
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
EOF
    fi
    
    # Start MCP server in background
    python3 server.py > "$LOG_DIR/mcp_server.log" 2>&1 &
    MCP_PID=$!
    echo -e "${GREEN}✅ MCP Server started (PID: $MCP_PID)${NC}"
    cd "$PROJECT_ROOT"
else
    echo -e "${YELLOW}⚠️  MCP Server files not found, skipping...${NC}"
fi

# Start LangGraph Service
echo -e "${YELLOW}🔧 Starting LangGraph Service...${NC}"
cd "$PROJECT_ROOT/chatbot_ui"
# Use uvicorn directly with nohup for reliable background execution
nohup python3 -m uvicorn langgraph_service:app --host 0.0.0.0 --port 5001 > "$LOG_DIR/langgraph_service.log" 2>&1 &
LANGGRAPH_PID=$!
echo -e "${GREEN}✅ LangGraph Service started (PID: $LANGGRAPH_PID)${NC}"

# Wait for LangGraph service to be ready
sleep 8

# Start Web UI
echo -e "${YELLOW}🔧 Starting Modern Web UI...${NC}"
# Use uvicorn directly with nohup for reliable background execution
nohup python3 -m uvicorn web_app:app --host 0.0.0.0 --port 3000 > "$LOG_DIR/web_ui.log" 2>&1 &
WEB_UI_PID=$!
echo -e "${GREEN}✅ Modern Web UI started (PID: $WEB_UI_PID)${NC}"

cd "$PROJECT_ROOT"

# Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
sleep 15

# Check service status
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "${BLUE}==================${NC}"

# Check Web UI
if check_port 3000; then
    echo -e "${GREEN}✅ Modern Web UI: http://localhost:3000${NC}"
else
    echo -e "${RED}❌ Modern Web UI: Failed to start${NC}"
fi

# Check LangGraph Service
if check_port 5001; then
    # Additional health check
    if curl -s http://localhost:5001/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ LangGraph Service: http://localhost:5001 (Healthy)${NC}"
    else
        echo -e "${YELLOW}⚠️  LangGraph Service: http://localhost:5001 (Starting...)${NC}"
    fi
else
    echo -e "${RED}❌ LangGraph Service: Failed to start${NC}"
fi

# Check MCP Server
if check_port 8000; then
    echo -e "${GREEN}✅ MCP Server: http://localhost:8000${NC}"
else
    echo -e "${YELLOW}⚠️  MCP Server: Not running${NC}"
fi

# Check Database Backend
if [ "$DB_MODE" = "proxy" ]; then
    echo -e "${GREEN}✅ Database: Proxy mode (${PROXY_BASE_URL})${NC}"
else
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Database: Local PostgreSQL on port 5432${NC}"
    else
        echo -e "${RED}❌ Database: PostgreSQL not running${NC}"
    fi
fi

echo -e "\n${BLUE}📋 Quick Access URLs:${NC}"
echo -e "${BLUE}=====================${NC}"
echo -e "🌐 Modern Web UI:     http://localhost:3000"
echo -e "🔧 LangGraph Service: http://localhost:5001"
echo -e "📊 API Docs:          http://localhost:5001/docs"
echo -e "🗄️  MCP Server:        http://localhost:8000"
echo -e "📖 MCP Docs:          http://localhost:8000/docs"

echo -e "\n${BLUE}📁 Log Files:${NC}"
echo -e "${BLUE}==============${NC}"
echo -e "📄 Web UI:            $LOG_DIR/web_ui.log"
echo -e "📄 LangGraph:         $LOG_DIR/langgraph_service.log"
echo -e "📄 MCP Server:        $LOG_DIR/mcp_server.log"

echo -e "\n${GREEN}🎉 All services started successfully!${NC}"
echo -e "${YELLOW}⚠️  Press Ctrl+C to stop all services${NC}"

# Keep the script running and monitor services
while true; do
    sleep 10
    
    # Check if critical services are still running
    if ! check_port 3000; then
        echo -e "${RED}❌ Web UI stopped unexpectedly${NC}"
        break
    fi
    
    if ! check_port 5001; then
        echo -e "${RED}❌ LangGraph Service stopped unexpectedly${NC}"
        break
    fi
done

# If we get here, something went wrong
cleanup