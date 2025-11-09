#!/bin/bash
# Quick test script for LangGraph Studio startup

PROJECT_ROOT="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
cd "$PROJECT_ROOT"

echo "🧪 Testing LangGraph Studio Startup"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check 1: Is langgraph command available?
echo -e "${BLUE}1️⃣  Checking langgraph command...${NC}"
if command -v langgraph &> /dev/null; then
    VERSION=$(langgraph --version)
    echo -e "${GREEN}✅ langgraph found: $VERSION${NC}"
else
    echo -e "${RED}❌ langgraph command not found${NC}"
    echo "    Installing..."
    pip3 install langgraph-cli
fi
echo ""

# Check 2: Can we access the graph?
echo -e "${BLUE}2️⃣  Checking graph_definition.py...${NC}"
if python3 -c "from langgraph_integration.graph_definition import build_graph; g = build_graph(); print('✅ Graph loaded successfully')" 2>&1; then
    echo -e "${GREEN}✅ Graph definition is valid${NC}"
else
    echo -e "${RED}❌ Failed to load graph${NC}"
    exit 1
fi
echo ""

# Check 3: Is port 2024 available?
echo -e "${BLUE}3️⃣  Checking port 2024...${NC}"
if lsof -Pi :2024 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 2024 is already in use${NC}"
    echo "    Killing existing process..."
    kill -9 $(lsof -ti:2024) 2>/dev/null || true
    sleep 2
fi
echo -e "${GREEN}✅ Port 2024 is available${NC}"
echo ""

# Check 4: Start Studio
echo -e "${BLUE}4️⃣  Starting LangGraph Studio on port 2024...${NC}"
echo "    Command: langgraph dev langgraph_integration.graph_definition:build_graph --port 2024"
echo ""

# Create logs directory
mkdir -p logs

# Start in background
nohup langgraph dev langgraph_integration.graph_definition:build_graph --port 2024 > logs/studio_test.log 2>&1 &
STUDIO_PID=$!
echo -e "${YELLOW}⏳ Waiting for Studio to start (PID: $STUDIO_PID)...${NC}"
echo ""

# Wait for startup
attempts=0
max_attempts=20
while [ $attempts -lt $max_attempts ]; do
    if curl -s http://localhost:2024 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Studio is ready!${NC}"
        echo ""
        echo -e "${BLUE}📊 LangGraph Studio is running at:${NC}"
        echo -e "${GREEN}   http://localhost:2024${NC}"
        echo ""
        echo -e "${BLUE}Graph features available:${NC}"
        echo "  • Visualize graph structure and node connections"
        echo "  • Step through execution node-by-node"
        echo "  • Inspect full state at each step"
        echo "  • Replay and debug failed runs"
        echo "  • Test graph with custom inputs"
        echo ""
        echo -e "${YELLOW}To stop: kill $STUDIO_PID${NC}"
        echo ""
        echo "Opening in browser in 2 seconds..."
        sleep 2
        open http://localhost:2024 2>/dev/null || echo "✅ Open http://localhost:2024 in your browser"
        
        # Keep running
        wait
        break
    fi
    
    attempts=$((attempts + 1))
    echo -n "."
    sleep 1
done

if [ $attempts -ge $max_attempts ]; then
    echo -e "${RED}❌ Studio failed to start${NC}"
    echo ""
    echo -e "${BLUE}📋 Last 20 lines of logs:${NC}"
    tail -20 logs/studio_test.log
    kill $STUDIO_PID 2>/dev/null || true
    exit 1
fi