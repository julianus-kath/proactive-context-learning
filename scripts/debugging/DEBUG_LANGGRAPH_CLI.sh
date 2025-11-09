#!/bin/bash
# Quick diagnostic script for LangGraph CLI issues

echo "🔍 LangGraph CLI Diagnostic"
echo ""

# Check Python version
echo "1️⃣  Python version:"
python3 --version
echo ""

# Check if pip is available
echo "2️⃣  pip availability:"
pip3 --version
echo ""

# Check if langgraph is installed
echo "3️⃣  Checking langgraph package:"
pip3 list | grep langgraph
echo ""

# Try to import langgraph
echo "4️⃣  Testing langgraph import:"
python3 -c "import langgraph; print(f'✅ langgraph imported: {langgraph.__version__}')" 2>&1 || echo "❌ Failed to import langgraph"
echo ""

# Try to run langgraph command
echo "5️⃣  Testing langgraph CLI:"
python3 -m langgraph --version 2>&1 || echo "❌ Failed to run langgraph CLI"
echo ""

# Check if graph_definition.py has build_graph function
echo "6️⃣  Checking graph_definition.py:"
grep -n "def build_graph" langgraph_integration/graph_definition.py || echo "❌ build_graph function not found"
echo ""

# Try to manually install langgraph-cli
echo "7️⃣  Installing/upgrading langgraph-cli:"
pip3 install --upgrade langgraph-cli
echo ""

# Retest after install
echo "8️⃣  Retesting langgraph CLI after install:"
python3 -m langgraph --version 2>&1 || echo "❌ Still failing"
echo ""

echo "✅ Diagnostic complete!"