#!/bin/bash
# =============================================================================
# Mac Machine Startup Script - Web UI + LangGraph Service
# =============================================================================
# This script starts the Web UI and LangGraph service on Mac.
# It does NOT start the MCP server - that runs on Windows.
#
# Prerequisites:
# 1. Windows MCP server must be running (start_mcp_server_windows.bat)
# 2. .env file must be configured with MCP_SERVER_URL pointing to Windows
# =============================================================================

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

echo -e "${BLUE}"
echo "=========================================="
echo "  Mac Services Startup"
echo "  Web UI + LangGraph Service"
echo "=========================================="
echo -e "${NC}"

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
    local pid=$(lsof -ti:$port 2>/dev/null)
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
    
    # Kill services on known ports (NOT 8000 - that's on Windows)
    kill_port 3000  # Web UI
    kill_port 5001  # LangGraph Service
    
    # Kill any remaining Python processes related to our services
    pkill -f "web_app.py" 2>/dev/null || true
    pkill -f "langgraph_service.py" 2>/dev/null || true
    
    echo -e "${GREEN}✅ All Mac services stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo -e "${BLUE}📋 Pre-flight checks...${NC}"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3 is installed${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo ""
    echo "Please create .env file from .env.mac template:"
    echo "  1. Copy .env.mac to .env"
    echo "  2. Update OPENAI_API_KEY with your API key"
    echo "  3. Update MCP_SERVER_URL with your Windows IP (e.g., http://10.255.152.48:8000)"
    echo "  4. Ensure MCP_API_KEY matches Windows MCP server"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ .env file found${NC}"

# Load environment variables
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY is not set in .env file${NC}"
    echo -e "${YELLOW}💡 Please edit .env file and add your OpenAI API key${NC}"
    exit 1
fi

echo -e "${GREEN}✅ OPENAI_API_KEY is configured${NC}"

# Check if MCP_SERVER_URL is set
if [ -z "$MCP_SERVER_URL" ]; then
    echo -e "${RED}❌ MCP_SERVER_URL is not set in .env file${NC}"
    echo -e "${YELLOW}💡 Please edit .env file and set MCP_SERVER_URL to your Windows MCP server${NC}"
    echo -e "${YELLOW}   Example: MCP_SERVER_URL=http://10.255.152.48:8000${NC}"
    exit 1
fi

echo -e "${GREEN}✅ MCP_SERVER_URL is configured: ${MCP_SERVER_URL}${NC}"

# ============================================
# Check Windows MCP Server Connection
# ============================================
echo ""
echo -e "${BLUE}🔍 Checking Windows MCP Server connection...${NC}"

# Parse MCP server URL
MCP_HOST=$(echo $MCP_SERVER_URL | sed -e 's|^[^/]*//||' -e 's|:.*||')
MCP_PORT=$(echo $MCP_SERVER_URL | sed -e 's|^[^:]*:||' -e 's|/.*||' | grep -o '[0-9]*')
MCP_PORT=${MCP_PORT:-8000}

echo -e "${YELLOW}   Testing connection to ${MCP_HOST}:${MCP_PORT}...${NC}"

# Test network connectivity
if command -v nc &> /dev/null; then
    if nc -z -w 5 $MCP_HOST $MCP_PORT 2>/dev/null; then
        echo -e "${GREEN}✅ MCP server is reachable${NC}"
    else
        echo -e "${RED}❌ Cannot connect to MCP server${NC}"
        echo -e "${YELLOW}💡 Please check:${NC}"
        echo -e "   1. Windows MCP server is running: start_mcp_server_windows.bat"
        echo -e "   2. Windows firewall allows port ${MCP_PORT}"
        echo -e "   3. IP address is correct: ${MCP_HOST}"
        echo -e "   4. Both machines are on the same network"
        exit 1
    fi
else
    # Fallback to curl if nc not available
    if curl -s --connect-timeout 5 "${MCP_SERVER_URL}/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ MCP server is reachable${NC}"
    else
        echo -e "${RED}❌ Cannot connect to MCP server${NC}"
        echo -e "${YELLOW}💡 Please start Windows MCP server first${NC}"
        exit 1
    fi
fi

# Test MCP health endpoint
echo -e "${YELLOW}   Testing MCP health endpoint...${NC}"

if [ -n "$MCP_API_KEY" ]; then
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 \
        -H "X-API-Key: ${MCP_API_KEY}" \
        "${MCP_SERVER_URL}/health" 2>/dev/null)
else
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 \
        "${MCP_SERVER_URL}/health" 2>/dev/null)
fi

HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ MCP server health check passed${NC}"
elif [ "$HTTP_CODE" = "401" ]; then
    echo -e "${RED}❌ MCP server authentication failed${NC}"
    echo -e "${YELLOW}💡 Check MCP_API_KEY in .env matches Windows MCP server${NC}"
    exit 1
elif [ -z "$HTTP_CODE" ]; then
    echo -e "${RED}❌ MCP server is not responding${NC}"
    echo -e "${YELLOW}💡 Please start Windows MCP server: start_mcp_server_windows.bat${NC}"
    exit 1
else
    echo -e "${YELLOW}⚠️  MCP server returned status code: ${HTTP_CODE}${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
fi

echo ""
echo -e "${GREEN}✅ Windows MCP server is ready${NC}"

# ============================================
# Install Dependencies
# ============================================
echo ""
echo -e "${BLUE}📦 Installing dependencies...${NC}"

# Install LangGraph integration dependencies
if [ -f "langgraph_integration/requirements.txt" ]; then
    echo -e "${YELLOW}   Installing LangGraph integration dependencies...${NC}"
    pip3 install -q -r langgraph_integration/requirements.txt || {
        echo -e "${RED}❌ Failed to install LangGraph dependencies${NC}"
        exit 1
    }
fi

# Install chatbot UI dependencies
if [ -f "chatbot_ui/requirements.txt" ]; then
    echo -e "${YELLOW}   Installing Chatbot UI dependencies...${NC}"
    pip3 install -q -r chatbot_ui/requirements.txt || {
        echo -e "${RED}❌ Failed to install Chatbot UI dependencies${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"

# ============================================
# Clean up existing processes
# ============================================
echo ""
echo -e "${BLUE}🧹 Cleaning up existing processes...${NC}"
kill_port 3000
kill_port 5001

# ============================================
# Start Services
# ============================================
echo ""
echo -e "${BLUE}🚀 Starting Mac services...${NC}"
echo ""

# Start LangGraph Service with Multi-Agent Orchestrator
echo -e "${YELLOW}🔧 Starting LangGraph Service (Port 5001) - Multi-Agent Orchestrator...${NC}"
cd "$PROJECT_ROOT/chatbot_ui"

if [ ! -f "langgraph_service.py" ]; then
    echo -e "${RED}❌ langgraph_service.py not found${NC}"
    exit 1
fi

# Verify orchestrator exists
if [ ! -f "$PROJECT_ROOT/langgraph_integration/orchestrator.py" ]; then
    echo -e "${RED}❌ Multi-Agent Orchestrator not found${NC}"
    echo -e "${YELLOW}   Expected: langgraph_integration/orchestrator.py${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Multi-Agent Orchestrator found${NC}"

# Clear old logs
> "$LOG_DIR/langgraph.log"

nohup python3 langgraph_service.py > "$LOG_DIR/langgraph.log" 2>&1 &
LANGGRAPH_PID=$!
echo -e "${GREEN}✅ LangGraph Service started (PID: $LANGGRAPH_PID)${NC}"
echo -e "${YELLOW}📋 LangGraph Startup Logs:${NC}"

# Stream logs until service is ready or timeout
timeout 30 tail -f "$LOG_DIR/langgraph.log" 2>/dev/null | while IFS= read -r line; do
    echo -e "${BLUE}  $line${NC}"
    # Check if service is ready
    if [[ $line == *"Uvicorn running on"* ]] || [[ $line == *"Application startup complete"* ]] || [[ $line == *"orchestrator"* ]]; then
        echo -e "${GREEN}✅ LangGraph Service is ready!${NC}"
        break
    fi
done &

# Wait for LangGraph to be ready
wait_for_service "http://localhost:5001/health" "LangGraph Service" || {
    echo -e "${RED}❌ LangGraph Service failed to start${NC}"
    echo -e "${YELLOW}Check full logs: tail -f $LOG_DIR/langgraph.log${NC}"
    cleanup
}

# Start Web UI
echo ""
echo -e "${YELLOW}🌐 Starting Web UI (Port 3000)...${NC}"
cd "$PROJECT_ROOT/chatbot_ui"

if [ ! -f "web_app.py" ]; then
    echo -e "${RED}❌ web_app.py not found${NC}"
    cleanup
fi

nohup python3 web_app.py > "$LOG_DIR/web_ui.log" 2>&1 &
WEB_UI_PID=$!
echo -e "${GREEN}✅ Web UI started (PID: $WEB_UI_PID)${NC}"

# Wait for Web UI to be ready
wait_for_service "http://localhost:3000" "Web UI" || {
    echo -e "${RED}❌ Web UI failed to start${NC}"
    echo -e "${YELLOW}Check logs: tail -f $LOG_DIR/web_ui.log${NC}"
    cleanup
}

# ============================================
# All services started successfully
# ============================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ All Mac services started successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${BLUE}🎯 System Architecture:${NC}"
echo -e "  Multi-Agent Orchestrator (4 specialized agents)"
echo -e "  ├─ Discovery Agent (table/view search & ranking)"
echo -e "  ├─ JoinSQL Agent (join planning & MSSQL generation)"
echo -e "  ├─ Exec Agent (query execution & auto-repair)"
echo -e "  └─ Answer Agent (result formatting & explanations)"
echo ""
echo -e "${BLUE}Service Status:${NC}"
echo -e "  🌐 Web UI:           http://localhost:3000"
echo -e "  🤖 LangGraph (Orchestrator): http://localhost:5001"
echo -e "  🗄️  MCP Server:       ${MCP_SERVER_URL} (Windows)"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  Web UI:      tail -f $LOG_DIR/web_ui.log"
echo -e "  LangGraph:   tail -f $LOG_DIR/langgraph.log"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo -e "  📖 Architecture:     docs/MULTI_AGENT_ARCHITECTURE.md"
echo -e "  🚀 Quick Start:      docs/MULTI_AGENT_QUICK_START.md"
echo -e "  🎨 Visual Guide:     docs/MULTI_AGENT_VISUAL_GUIDE.md"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for user interrupt
wait