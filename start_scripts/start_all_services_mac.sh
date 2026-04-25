#!/bin/bash
# Mac Machine Startup Script - Web UI + Simple SQL Agent
# =============================================================================
# This script starts the Web UI and Simple SQL Agent on Mac.
#
# MCP Server Handling:
# - If MCP_SERVER_URL points to localhost/127.0.0.1: Auto-starts local MCP server (PostgreSQL)
# - If MCP_SERVER_URL points to a remote IP: Expects MCP server already running (Windows/MSSQL)
#
# To switch databases, just change MCP_SERVER_URL in .env:
# - PostgreSQL (local): MCP_SERVER_URL=http://localhost:8000
# - MSSQL (Windows):    MCP_SERVER_URL=http://192.168.1.35:8000
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
WHITE='\033[0;37m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"

# Log file for services
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# ============================================
# HELPER FUNCTIONS (defined early)
# ============================================

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

# Function to kill process by name pattern (enhanced)
kill_by_name() {
    local pattern=$1
    local count=$(pgrep -f "$pattern" 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo -e "${YELLOW}   Killing $count process(es) matching '$pattern'${NC}"
        pkill -9 -f "$pattern" 2>/dev/null || true
        sleep 1
    fi
}

echo -e "${BLUE}"
echo "=========================================="
echo "  Mac Services Startup"
echo "  Web UI + Simple SQL Agent"
echo "=========================================="
echo -e "${NC}"

# ============================================
# AGGRESSIVE CLEANUP: Kill ALL service instances
# ============================================
echo -e "${BLUE}🔥 Aggressive Cleanup Phase...${NC}"
echo -e "${YELLOW}   Killing ALL service processes...${NC}"

# Kill by process names (most aggressive)
kill_by_name "simple_sql_agent"
kill_by_name "langchain"
kill_by_name "langgraph"

# Kill Python processes that might be our services
kill_by_name "web_app"

# Kill known ports (Web UI, LangGraph Studio, LangGraph Service, Eval Service)
kill_port 3000
kill_port 2024
kill_port 5001
kill_port 7001

# Final verification - list any remaining Python processes on our ports
echo -e "${YELLOW}   Verifying ports are clear...${NC}"
for port in 3000 2024 5001 7001; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}   ⚠️  Port $port still in use, forcing hard kill...${NC}"
        kill_port $port
        sleep 2
    else
        echo -e "${GREEN}   ✅ Port $port is clear${NC}"
    fi
done

echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

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

    # Kill all service-related processes
    kill_by_name "simple_sql_agent"
    kill_by_name "langchain"
    kill_by_name "langgraph"
    kill_by_name "web_app"
    kill_by_name "debug_langgraph_comprehensive"
    kill_by_name "eval.service"
    kill_by_name "mcp_server"

    # Kill services on known ports
    kill_port 3000  # Web UI
    kill_port 2024  # LangGraph Studio (if enabled)
    kill_port 5001  # SQL Agent
    kill_port 7001  # Evaluation & Tracking Service

    # Only kill port 8000 if we started a local MCP server
    if [ "$MCP_IS_LOCAL" = "1" ]; then
        kill_port 8000  # Local MCP Server
    fi

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
    echo "  3. Update MCP_SERVER_URL with either your Windows MCP server (e.g., http://10.255.152.48:8000) or local MCP server (e.g., http://localhost:8000)"
    echo "  4. Ensure MCP_API_KEY matches your MCP server configuration"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ .env file found${NC}"

# Load environment variables
set -a
source .env
set +a

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
# Feature toggles
# ============================================
# Enable/disable LangGraph Studio (default: off to avoid interference)
ENABLE_STUDIO="${ENABLE_STUDIO:0}"

# Enable Cloudflare tunnel for Studio (default: disabled for local-only access)
ENABLE_STUDIO_TUNNEL="${ENABLE_STUDIO_TUNNEL:0}"

# Enable/disable Evaluation & Tracking Service (default: enabled)
ENABLE_EVAL="${ENABLE_EVAL:0}"

# Auto-open debugger in new terminal (default: off, shows instructions instead)
# Set to 1 to automatically open a new terminal with debugger output
AUTO_OPEN_DEBUGGER="${AUTO_OPEN_DEBUGGER:-1}"

# Debugger PID (will be set if debugger starts)
DEBUG_PID=""
EVAL_PID=""
if [ "$ENABLE_STUDIO" = "1" ]; then
    echo -e "${YELLOW}🔧 Feature toggle: LangGraph Studio is ENABLED (ENABLE_STUDIO=1)${NC}"
else
    echo -e "${YELLOW}🔧 Feature toggle: LangGraph Studio is DISABLED (set ENABLE_STUDIO=1 to enable)${NC}"
fi

if [ "$ENABLE_EVAL" = "1" ]; then
    echo -e "${YELLOW}🔧 Feature toggle: Evaluation & Tracking Service is ENABLED (ENABLE_EVAL=1)${NC}"
else
    echo -e "${YELLOW}🔧 Feature toggle: Evaluation & Tracking Service is DISABLED (set ENABLE_EVAL=1 to enable)${NC}"
fi

# ============================================
# Check MCP Server Connection (Auto-start if localhost)
# ============================================
echo ""
echo -e "${BLUE}🔍 Checking MCP Server connection...${NC}"

# Parse MCP server URL
MCP_HOST=$(echo $MCP_SERVER_URL | sed -e 's|^[^/]*//||' -e 's|:.*||')
MCP_PORT=$(echo $MCP_SERVER_URL | sed -e 's|^[^:]*:||' -e 's|/.*||' | grep -o '[0-9]*')
MCP_PORT=${MCP_PORT:-8000}

# Check if MCP server should be started locally (localhost or 127.0.0.1)
MCP_IS_LOCAL=0
if [[ "$MCP_HOST" == "localhost" ]] || [[ "$MCP_HOST" == "127.0.0.1" ]]; then
    MCP_IS_LOCAL=1
fi

# Auto-start local MCP server if needed
if [ "$MCP_IS_LOCAL" = "1" ]; then
    echo -e "${YELLOW}🏠 Local MCP server detected (${MCP_HOST}:${MCP_PORT})${NC}"

    # Check if MCP server is already running
    if lsof -Pi :$MCP_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Local MCP server is already running on port ${MCP_PORT}${NC}"
    else
        echo -e "${YELLOW}🚀 Starting local MCP server (Port ${MCP_PORT})...${NC}"

        # Verify MCP server exists
        if [ ! -f "$PROJECT_ROOT/mcp_server/server/app.py" ]; then
            echo -e "${RED}❌ MCP server not found at mcp_server/server/app.py${NC}"
            exit 1
        fi

        # Clear old logs
        > "$LOG_DIR/mcp_server.log"

        # Start MCP server
        cd "$PROJECT_ROOT"
        nohup python3 -m mcp_server.server.app > "$LOG_DIR/mcp_server.log" 2>&1 &
        MCP_SERVER_PID=$!
        echo -e "${GREEN}✅ Local MCP server started (PID: $MCP_SERVER_PID)${NC}"

        # Wait for MCP server to be ready
        echo -e "${YELLOW}⏳ Waiting for MCP server to be ready...${NC}"
        mcp_attempts=0
        while [ $mcp_attempts -lt 30 ]; do
            if curl -s "http://${MCP_HOST}:${MCP_PORT}/health" >/dev/null 2>&1; then
                echo -e "${GREEN}✅ Local MCP server is ready!${NC}"
                break
            fi
            echo -n "."
            sleep 1
            mcp_attempts=$((mcp_attempts + 1))
        done

        if [ $mcp_attempts -ge 30 ]; then
            echo -e "${RED}❌ MCP server failed to start${NC}"
            echo -e "${YELLOW}Check logs: tail -f $LOG_DIR/mcp_server.log${NC}"
            tail -20 "$LOG_DIR/mcp_server.log"
            exit 1
        fi
    fi
else
    # Remote MCP server - just check connectivity
    echo -e "${YELLOW}🌐 Remote MCP server detected (${MCP_HOST}:${MCP_PORT})${NC}"
    echo -e "${YELLOW}   Testing connection to ${MCP_HOST}:${MCP_PORT}...${NC}"

    # Test network connectivity
    if command -v nc &> /dev/null; then
        if nc -z -w 5 $MCP_HOST $MCP_PORT 2>/dev/null; then
            echo -e "${GREEN}✅ MCP server is reachable${NC}"
        else
            echo -e "${RED}❌ Cannot connect to MCP server${NC}"
            echo -e "${YELLOW}💡 Please check:${NC}"
            echo -e "   1. MCP server is running on Windows"
            echo -e "   2. Firewall allows port ${MCP_PORT}"
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
            echo -e "${YELLOW}💡 Please ensure your MCP server is running on Windows${NC}"
            exit 1
        fi
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
    echo -e "${YELLOW}💡 Check MCP_API_KEY in .env matches your MCP server configuration${NC}"
    exit 1
elif [ -z "$HTTP_CODE" ]; then
    echo -e "${RED}❌ MCP server is not responding${NC}"
    echo -e "${YELLOW}💡 Please ensure your MCP server is running and reachable${NC}"
    exit 1
else
    echo -e "${YELLOW}⚠️  MCP server returned status code: ${HTTP_CODE}${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
fi

echo ""
echo -e "${GREEN}✅ MCP server is ready${NC}"

# ============================================
# Install Dependencies
# ============================================
echo ""
echo -e "${BLUE}📦 Installing dependencies...${NC}"

# Upgrade build tooling for reliable wheel builds
echo -e "${YELLOW}   Upgrading pip/setuptools/wheel...${NC}"
python3 -m pip install --upgrade pip setuptools wheel || {
    echo -e "${RED}❌ Failed to upgrade pip/setuptools/wheel${NC}"
    exit 1
}

# Install Simple SQL Agent dependencies
if [ -f "simple_sql_agent/requirements.txt" ]; then
    echo -e "${YELLOW}   Installing Simple SQL Agent dependencies...${NC}"
    pip3 install -r simple_sql_agent/requirements.txt || {
        echo -e "${RED}❌ Failed to install Simple SQL Agent dependencies${NC}"
        exit 1
    }
fi

# Install chatbot UI dependencies
if [ -f "chatbot_ui/requirements.txt" ]; then
    echo -e "${YELLOW}   Installing Chatbot UI dependencies...${NC}"
    pip3 install -r chatbot_ui/requirements.txt || {
        echo -e "${RED}❌ Failed to install Chatbot UI dependencies${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"

# ============================================
# Note: Aggressive cleanup already performed above
# ============================================

# ============================================
# Start Services
# ============================================
echo ""
echo -e "${BLUE}🚀 Starting Mac services...${NC}"
echo ""

if [ "$ENABLE_STUDIO" = "1" ]; then
    # ============================================
    # Start LangGraph Studio (Visualization)
    # ============================================
    echo -e "${YELLOW}📊 Starting LangGraph Studio (Port 2024) - Graph Visualization & Debugging...${NC}"
    cd "$PROJECT_ROOT"

    # Ensure langgraph-cli (with in-memory API) is installed
    echo -e "${YELLOW}   Checking langgraph-cli installation...${NC}"
    if ! command -v langgraph &> /dev/null; then
        echo -e "${YELLOW}   Installing langgraph-cli[inmem] (this may take a moment)...${NC}"
        python3 -m pip install -U "langgraph-cli[inmem]" || true
    fi

    # Verify both CLI and API are available
    if command -v langgraph &> /dev/null; then
        LANGGRAPH_CLI_VERSION=$(langgraph --version 2>&1 | head -1)
        echo -e "${GREEN}   ✅ langgraph-cli found: ${LANGGRAPH_CLI_VERSION}${NC}"
    else
        echo -e "${YELLOW}⚠️  langgraph CLI not found after install attempt${NC}"
    fi

    python3 - << 'PY' 2>/dev/null || export LANGGRAPH_API_MISSING=1
try:
    import langgraph_api  # type: ignore
    print("langgraph_api: ok")
except Exception as e:
    raise SystemExit(1)
PY

    if [ "$LANGGRAPH_API_MISSING" = "1" ]; then
        echo -e "${YELLOW}   Installing missing langgraph-api via langgraph-cli[inmem]...${NC}"
        python3 -m pip install -U "langgraph-cli[inmem]" || true
    fi

    # Start LangGraph Studio in the background (if CLI is available)
    if command -v langgraph &> /dev/null; then
        # Clear old logs
        > "$LOG_DIR/langgraph_studio.log"

        # Start langgraph dev server (uses langgraph.json config for build_graph reference)
        cd "$PROJECT_ROOT"
        STUDIO_ARGS="--port 2024 --no-reload"
        if [ "$ENABLE_STUDIO_TUNNEL" = "1" ]; then
            STUDIO_ARGS="$STUDIO_ARGS --tunnel"
        else
            STUDIO_ARGS="$STUDIO_ARGS --host 127.0.0.1"
        fi
        nohup langgraph dev $STUDIO_ARGS > "$LOG_DIR/langgraph_studio.log" 2>&1 &
        STUDIO_PID=$!
        echo -e "${GREEN}✅ LangGraph Studio started (PID: $STUDIO_PID)${NC}"

        # Wait for Studio to be ready
        studio_attempts=0
        while [ $studio_attempts -lt 15 ]; do
            if curl -s "http://localhost:2024" >/dev/null 2>&1; then
                echo -e "${GREEN}✅ LangGraph Studio is ready!${NC}"
                STUDIO_URL="http://localhost:2024"
                break
            fi
            echo -n "."
            sleep 1
            studio_attempts=$((studio_attempts + 1))
        done

        if [ $studio_attempts -ge 15 ]; then
            echo -e "${YELLOW}⚠️  LangGraph Studio is taking longer to start (this can happen on first run)${NC}"
            echo -e "${YELLOW}   Showing recent Studio logs for diagnosis...${NC}"
            tail -n 80 "$LOG_DIR/langgraph_studio.log" 2>/dev/null || true
        fi

        if [ "$ENABLE_STUDIO_TUNNEL" = "1" ]; then
            # Extract tunnel URL from logs
            sleep 3  # Give it a moment to write the tunnel info to logs
            TUNNEL_URL=$(grep "Studio UI:" "$LOG_DIR/langgraph_studio.log" 2>/dev/null | sed 's/.*\[\[0-9;]*m//g' | sed 's/\[\[0-9;]*m.*//g' | grep -o 'https://[^ ]*')

            if [ -n "$TUNNEL_URL" ]; then
                STUDIO_URL="$TUNNEL_URL"
                echo -e "${GREEN}✅ LangGraph Studio tunnel URL: ${STUDIO_URL}${NC}"
            else
                STUDIO_URL="http://localhost:2024"
                echo -e "${YELLOW}⚠️  Could not extract tunnel URL, using localhost${NC}"
            fi
        else
            STUDIO_URL="http://localhost:2024"
            echo -e "${GREEN}ℹ️  LangGraph Studio running locally at ${STUDIO_URL}${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  LangGraph CLI not available, skipping Studio${NC}"
        STUDIO_URL=""
    fi
else
    echo -e "${YELLOW}📊 LangGraph Studio is DISABLED (ENABLE_STUDIO=0). Skipping Studio startup.${NC}"
    STUDIO_URL=""
fi

echo ""

# Start Simple SQL Agent — single ReAct agent over MCP tools.
echo -e "${YELLOW}🔧 Starting Simple SQL Agent (Port 5001) - ReAct Text-to-SQL Engine...${NC}"
cd "$PROJECT_ROOT"

# Verify simple_sql_agent exists
if [ ! -f "$PROJECT_ROOT/simple_sql_agent/service.py" ]; then
    echo -e "${RED}❌ Simple SQL Agent not found${NC}"
    echo -e "${YELLOW}   Expected: simple_sql_agent/service.py${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Simple SQL Agent found${NC}"

# Clear old logs
> "$LOG_DIR/sql_agent.log"

nohup python3 -m simple_sql_agent.service > "$LOG_DIR/sql_agent.log" 2>&1 &
SQL_AGENT_PID=$!
echo -e "${GREEN}✅ Simple SQL Agent started (PID: $SQL_AGENT_PID)${NC}"
echo -e "${YELLOW}📋 SQL Agent Startup Logs:${NC}"

# Stream logs until service is ready or timeout
timeout 30 tail -f "$LOG_DIR/sql_agent.log" 2>/dev/null | while IFS= read -r line; do
    echo -e "${BLUE}  $line${NC}"
    # Check if service is ready
    if [[ $line == *"Uvicorn running on"* ]] || [[ $line == *"Application startup complete"* ]] || [[ $line == *"SQL Agent initialized"* ]]; then
        echo -e "${GREEN}✅ Simple SQL Agent is ready!${NC}"
        break
    fi
done &

# Wait for SQL Agent to be ready
wait_for_service "http://localhost:5001/health" "Simple SQL Agent" || {
    echo -e "${RED}❌ Simple SQL Agent failed to start${NC}"
    echo -e "${YELLOW}Check full logs: tail -f $LOG_DIR/sql_agent.log${NC}"
    cleanup
}

# Start LangGraph Debugger (Real-time agent reasoning monitor)
echo ""
echo -e "${YELLOW}🔬 Starting LangGraph Debugger (Real-time agent reasoning monitor)...${NC}"
cd "$PROJECT_ROOT"

if [ ! -f "debug_langgraph_comprehensive.py" ]; then
    echo -e "${YELLOW}⚠️  debug_langgraph_comprehensive.py not found, skipping debugger${NC}"
    DEBUG_PID=""
else
    > "$LOG_DIR/langgraph_debugger.log"
    # Use default API key if not set (debug script defaults to supersecretapikey)
    DEBUG_API_KEY="${API_KEY:-supersecretapikey}"
    nohup python3 debug_langgraph_comprehensive.py --url "http://localhost:5001" --api-key "$DEBUG_API_KEY" > "$LOG_DIR/langgraph_debugger.log" 2>&1 &
    DEBUG_PID=$!
    echo -e "${GREEN}✅ LangGraph Debugger started (PID: $DEBUG_PID)${NC}"
    echo -e "${YELLOW}   Debugger output: tail -f $LOG_DIR/langgraph_debugger.log${NC}"
    echo -e "${YELLOW}   Or view directly in terminal${NC}"
fi

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

# Start Evaluation & Tracking Service (Optional)
if [ "$ENABLE_EVAL" = "1" ]; then
    echo ""
    echo -e "${YELLOW}📊 Starting Evaluation & Tracking Service (Port 7001) - Benchmark & Artifact Tracking...${NC}"
    cd "$PROJECT_ROOT"

    if [ ! -f "eval/service.py" ]; then
        echo -e "${YELLOW}⚠️  eval/service.py not found, skipping evaluation service${NC}"
        EVAL_PID=""
    else
        # Clear old logs
        > "$LOG_DIR/eval_service.log"

        nohup python3 -m eval.service > "$LOG_DIR/eval_service.log" 2>&1 &
        EVAL_PID=$!
        echo -e "${GREEN}✅ Evaluation & Tracking Service started (PID: $EVAL_PID)${NC}"

        # Wait for Eval Service to be ready
        wait_for_service "http://localhost:7001/health" "Evaluation Service" || {
            echo -e "${YELLOW}⚠️  Evaluation Service failed to start (non-critical)${NC}"
            EVAL_PID=""
        }
    fi
else
    echo ""
    echo -e "${YELLOW}📊 Evaluation & Tracking Service is DISABLED (ENABLE_EVAL=0). Skipping Eval Service startup.${NC}"
    EVAL_PID=""
fi

# ============================================
# All services started successfully
# ============================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ All Mac services started successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${BLUE}🎯 System Architecture:${NC}"
echo -e "  Simple SQL Agent (ReAct Pattern)"
echo -e "  ├─ Single ReAct Agent (GPT-4o)"
echo -e "  ├─ 4 Tools: list_tables, get_schema, validate_sql, execute_query"
echo -e "  ├─ Domain Knowledge from concepts.json"
echo -e "  └─ MCP Server for MSSQL access"
echo ""
echo -e "${BLUE}Service Status:${NC}"
echo -e "  🌐 Web UI:           http://localhost:3000"
echo -e "  🤖 SQL Agent:        http://localhost:5001"
if [ -n "$STUDIO_URL" ]; then
    echo -e "  📊 LangGraph Studio: ${STUDIO_URL} (Graph Visualization)"
fi
if [ -n "$EVAL_PID" ]; then
    echo -e "  📊 Eval Service:     http://localhost:7001 (Benchmark & Artifact Tracking)"
fi
if [ "$MCP_IS_LOCAL" = "1" ]; then
    echo -e "  🗄️  MCP Server:       ${MCP_SERVER_URL} (Local - PostgreSQL)"
else
    echo -e "  🗄️  MCP Server:       ${MCP_SERVER_URL} (Remote - Windows/MSSQL)"
fi
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  Web UI:             tail -f $LOG_DIR/web_ui.log"
echo -e "  SQL Agent:          tail -f $LOG_DIR/sql_agent.log"
if [ "$MCP_IS_LOCAL" = "1" ]; then
    echo -e "  MCP Server:         tail -f $LOG_DIR/mcp_server.log"
fi
if [ -n "$STUDIO_URL" ]; then
    echo -e "  LangGraph Studio:   tail -f $LOG_DIR/langgraph_studio.log"
fi
if [ -n "$EVAL_PID" ]; then
    echo -e "  Eval Service:       tail -f $LOG_DIR/eval_service.log"
fi
if [ -n "$DEBUG_PID" ]; then
    echo -e "  LangGraph Debugger: tail -f $LOG_DIR/langgraph_debugger.log"
    echo -e "                    (Shows real-time agent reasoning steps)"
fi
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo -e "  📖 Architecture:     adrs/0030-simple-sql-agent-architecture.md"
if [ -n "$STUDIO_URL" ]; then
    echo ""
    echo -e "${GREEN}🎯 LangGraph Studio Features:${NC}"
    echo -e "  • Visualize the complete graph structure and node connections"
    echo -e "  • Step through graph execution node-by-node"
    echo -e "  • Inspect full state at each step"
    echo -e "  • Replay and debug failed runs"
    echo -e "  • Test graph with custom inputs"
fi
if [ -n "$DEBUG_PID" ]; then
    echo ""
    echo -e "${CYAN}${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║  🔬 WATCH REAL-TIME AGENT REASONING (Recommended!)          ║${NC}"
    echo -e "${CYAN}${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"

    # Auto-open debugger in new terminal if enabled
    if [ "$AUTO_OPEN_DEBUGGER" = "1" ]; then
        echo -e "${GREEN}✅ Auto-opening debugger in new terminal window...${NC}"
        # macOS Terminal.app - open new window with tail command
        osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && tail -f logs/langgraph_debugger.log\"" 2>/dev/null || {
            echo -e "${YELLOW}⚠️  Could not auto-open terminal. Please run manually:${NC}"
            echo -e "    ${GREEN}${BOLD}tail -f logs/langgraph_debugger.log${NC}"
        }
    else
        echo -e "${WHITE}Open a ${BOLD}NEW TERMINAL${NC}${WHITE} and run:${NC}"
        echo -e ""
        echo -e "    ${GREEN}${BOLD}tail -f logs/langgraph_debugger.log${NC}"
    fi

    echo -e ""
    echo -e "${WHITE}This shows:${NC}"
    echo -e "  ${CYAN}✓${NC} Agent entries/exits with state snapshots"
    echo -e "  ${CYAN}✓${NC} Intent parsing (keywords, confidence, operation)"
    echo -e "  ${CYAN}✓${NC} Discovery results (tables found)"
    echo -e "  ${CYAN}✓${NC} SQL generation and execution"
    echo -e "  ${CYAN}✓${NC} Routing decisions and error propagation"
    echo -e ""
    echo -e "${YELLOW}💡 This is the best way to debug 'missing info' responses!${NC}"

    if [ "$AUTO_OPEN_DEBUGGER" != "1" ]; then
        echo -e "${DIM}   (To auto-open debugger, set AUTO_OPEN_DEBUGGER=1 in startup script)${NC}"
    fi
fi
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for user interrupt
wait