#!/bin/bash

# Stop All Services Script for Dynamic ERP Assistant
# Gracefully stops all running services and frees up ports

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Dynamic ERP Assistant Services...${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to check if a process is running
check_process() {
    local process_name=$1
    local pid=$(pgrep -f "$process_name")
    if [ ! -z "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

# Function to kill process gracefully
kill_process() {
    local process_name=$1
    local display_name=$2
    
    if pid=$(check_process "$process_name"); then
        echo -e "${YELLOW}🔴 Stopping $display_name (PID: $pid)...${NC}"
        kill $pid
        sleep 2
        
        # Check if still running, force kill if necessary
        if check_process "$process_name" >/dev/null; then
            echo -e "${YELLOW}⚠️  Force stopping $display_name...${NC}"
            kill -9 $pid
        fi
        echo -e "${GREEN}✅ $display_name stopped${NC}"
    else
        echo -e "${GREEN}✅ $display_name not running${NC}"
    fi
}

# Function to free up port
free_port() {
    local port=$1
    local service_name=$2
    
    if lsof -i :$port >/dev/null 2>&1; then
        echo -e "${YELLOW}🔴 Freeing port $port ($service_name)...${NC}"
        lsof -ti :$port | xargs kill -9 2>/dev/null
        sleep 1
        
        if lsof -i :$port >/dev/null 2>&1; then
            echo -e "${RED}❌ Failed to free port $port${NC}"
        else
            echo -e "${GREEN}✅ Port $port freed${NC}"
        fi
    else
        echo -e "${GREEN}✅ Port $port already free${NC}"
    fi
}

# Stop services
echo -e "${BLUE}🔍 Checking running services...${NC}"

# Stop Streamlit
kill_process "streamlit run" "Streamlit UI"

# Stop LangGraph service
kill_process "uvicorn.*langgraph_service" "LangGraph Service"

# Stop any remaining Python processes related to our services
kill_process "langgraph_service.py" "LangGraph Service (direct)"

echo ""
echo -e "${BLUE}🔍 Checking ports...${NC}"

# Free up ports
free_port 8501 "Streamlit"
free_port 5001 "LangGraph API"

echo ""
echo -e "${BLUE}🧹 Cleaning up...${NC}"

# Clean up any remaining background processes
pkill -f "streamlit.*app.py" 2>/dev/null && echo -e "${GREEN}✅ Cleaned up Streamlit processes${NC}"
pkill -f "uvicorn.*langgraph_service" 2>/dev/null && echo -e "${GREEN}✅ Cleaned up LangGraph processes${NC}"

# Optional: Stop PostgreSQL if it was started by our script
# Uncomment the next lines if you want to stop PostgreSQL too
# echo -e "${YELLOW}⚠️  PostgreSQL is still running (database server)${NC}"
# echo -e "${YELLOW}   Use 'brew services stop postgresql@14' to stop it${NC}"

echo ""
echo -e "${GREEN}🎯 All services stopped successfully!${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ Streamlit UI: Stopped${NC}"
echo -e "${GREEN}✅ LangGraph API: Stopped${NC}"
echo -e "${GREEN}✅ Ports 8501, 5001: Free${NC}"
echo ""
echo -e "${BLUE}💡 To restart the system, run:${NC}"
echo -e "${BLUE}   ./start_all_services.sh${NC}"
echo ""