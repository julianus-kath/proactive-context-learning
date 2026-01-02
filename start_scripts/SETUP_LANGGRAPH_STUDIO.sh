#!/bin/bash
# Quick setup script for LangGraph Studio
# Run this after running start_all_services_mac.sh to ensure everything is installed

echo "🔧 LangGraph Studio Setup Check"
echo ""

PROJECT_ROOT="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
cd "$PROJECT_ROOT"

# Check Python version
echo "📋 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python: $PYTHON_VERSION"

# Check if langgraph-cli is installed
echo ""
echo "📦 Checking dependencies..."
if python3 -m langgraph --version >/dev/null 2>&1; then
    LANGGRAPH_VERSION=$(python3 -m langgraph --version 2>&1)
    echo "   ✅ LangGraph CLI: $LANGGRAPH_VERSION"
else
    echo "   ❌ LangGraph CLI not found. Installing..."
    pip3 install langgraph-cli
fi

# Check if graph can be imported
echo ""
echo "🧪 Testing graph import..."
if python3 -c "from langgraph_integration.graph_definition import build_graph; print('Graph imported successfully')" 2>/dev/null; then
    echo "   ✅ Graph definition is valid"
else
    echo "   ❌ Graph definition has errors. Check langgraph_integration/graph_definition.py"
    exit 1
fi

# Show how to start Studio
echo ""
echo "🚀 Ready to start LangGraph Studio!"
echo ""
echo "Option 1: Start all services (recommended)"
echo "  ./start_all_services_mac.sh"
echo ""
echo "Option 2: Start Studio only"
echo "  python3 -m langgraph dev langgraph_integration.graph_definition:build_graph --port 2024"
echo ""
echo "Option 3: Start on different port"
echo "  python3 -m langgraph dev langgraph_integration.graph_definition:build_graph --port 3001"
echo ""
echo "After starting, open: http://localhost:2024"
echo ""

