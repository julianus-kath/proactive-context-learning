#!/bin/bash
# =============================================================================
# Windows MCP Server Startup Script (Git Bash / WSL)
# =============================================================================
# This script starts the MCP server on Windows with VPN access to SQL Server.
# Use this if you're running Git Bash or WSL on Windows.
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "========================================"
echo "  MCP Server Startup (Windows)"
echo "========================================"
echo -e "${NC}"

# Get project root (parent of vpn_config)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${BLUE}Project Root: ${PROJECT_ROOT}${NC}"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}[ERROR] Python is not installed or not in PATH${NC}"
    echo "Please install Python 3.11+ and add it to PATH"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo -e "${GREEN}[OK] Python is installed${NC}"
echo ""

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}[WARNING] .env file not found${NC}"
    echo ""
    echo "Please create .env file from .env.windows template:"
    echo "  1. Copy .env.windows to .env"
    echo "  2. Update MSSQL_PASSWORD with your actual password"
    echo "  3. Update MCP_API_KEY if needed"
    echo "  4. Verify MSSQL_SERVER IP address"
    echo ""
    exit 1
fi

echo -e "${GREEN}[OK] .env file found${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}Installing MCP server dependencies...${NC}"
$PYTHON_CMD -m pip install -r "$PROJECT_ROOT/mcp_server/requirements.txt" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to install dependencies${NC}"
    echo "Please run manually: pip install -r mcp_server/requirements.txt"
    exit 1
fi

echo -e "${GREEN}[OK] Dependencies installed${NC}"
echo ""

# Check if port 8000 is in use
if netstat -ano 2>/dev/null | grep -q ":8000.*LISTENING" || lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}[WARNING] Port 8000 is already in use${NC}"
    echo ""
    read -p "Kill existing process on port 8000? (y/n): " KILL_PORT
    if [ "$KILL_PORT" = "y" ] || [ "$KILL_PORT" = "Y" ]; then
        # Try Windows netstat first
        if command -v netstat &> /dev/null; then
            PID=$(netstat -ano 2>/dev/null | grep ":8000.*LISTENING" | awk '{print $5}' | head -1)
            if [ ! -z "$PID" ]; then
                taskkill //F //PID $PID 2>/dev/null || kill -9 $PID 2>/dev/null
            fi
        fi
        # Try Unix lsof
        if command -v lsof &> /dev/null; then
            PID=$(lsof -ti:8000)
            if [ ! -z "$PID" ]; then
                kill -9 $PID 2>/dev/null
            fi
        fi
        sleep 2
    else
        echo "Please stop the existing process manually"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Starting MCP Server on port 8000${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "The MCP server will:"
echo "  - Connect to SQL Server via VPN"
echo "  - Listen on 0.0.0.0:8000 (accessible from Mac)"
echo "  - Provide database access via MCP JSON-RPC"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the MCP server
cd "$PROJECT_ROOT/mcp_server"
$PYTHON_CMD -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload