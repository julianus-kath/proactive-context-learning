#!/bin/bash

# GitHub Repository Cleanup Script
# Based on ADR-0009 and ADR-0010 final architecture
# Removes previous attempts and experimental code

echo "🧹 Starting GitHub repository cleanup..."
echo "⚠️  This will remove legacy and experimental code"
echo "✅ Keeping: chatbot_ui/, mcp_server/, langgraph_integration/, adrs/"

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

# Navigate to repo root
cd "$(dirname "$0")"

echo "🗑️  Removing legacy multi-agent system..."
rm -rf agent_system/
rm -rf fusion/

echo "🗑️  Removing experimental frontends..."
rm -rf frontend/
rm -rf chatbot-interface/

echo "🗑️  Removing N8N experiments..."
rm -rf n8n-data/
rm -rf n8n-setup/
rm -f n8n-guide.md
rm -f setup-n8n.sh stop-n8n.sh rebuild-n8n.sh

echo "🗑️  Removing crawling agent experiments..."
rm -rf crawling_agent/

echo "🗑️  Removing extended data experiments..."
rm -rf extended_data/
rm -rf scripts/

echo "🗑️  Removing build/docker experiments..."
rm -f build_*.sh
rm -f rebuild*.sh
rm -f Dockerfile
rm -f docker-compose.yml

echo "🗑️  Removing experimental scripts..."
rm -f run*.sh
rm -f setup.py setup.sh
rm -f fix_system.sh
rm -f test-sqlite.sh
rm -f build_and_run.sh
rm -f build_docstore.sh
rm -f run_mongo.sh

echo "🗑️  Removing duplicate/orphaned directories..."
rm -rf Thesis/
rm -rf docs/ 2>/dev/null
rm -rf exports/ 2>/dev/null
rm -rf 2/ 2>/dev/null

echo "🗑️  Removing legacy tests (keeping relevant ones)..."
# Keep tests that might be relevant to current system
# rm -rf tests/

echo "🗑️  Removing MCP learning materials (optional)..."
read -p "Remove mcp-crash-course/ learning materials? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf mcp-crash-course/
fi

echo "🧹 Cleanup complete!"
echo ""
echo "✅ PRODUCTION SYSTEM COMPONENTS KEPT:"
echo "   📁 chatbot_ui/          - Streamlit frontend & FastAPI service"
echo "   📁 mcp_server/          - Database access layer"
echo "   📁 langgraph_integration/ - AI workflow engine"
echo "   📁 adrs/               - Architecture documentation"
echo "   📄 requirements.txt    - Dependencies"
echo "   📄 .env.example        - Configuration template"
echo "   📄 README.md           - Project documentation"
echo "   📄 .gitignore          - Git ignore rules"
echo ""
echo "🚀 Your repository now contains only the final production system!"
echo "   Run: cd chatbot_ui && python start_services.py"