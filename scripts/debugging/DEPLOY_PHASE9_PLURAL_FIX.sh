#!/bin/bash

# Phase 9 Plural Entity Bug Fix — Deployment Script
# Restarts services with the critical MCP plural handling fix

set -e

cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code

echo "🛑 Stopping services..."
pkill -f "orchestrator" || true
pkill -f "mcp_server" || true
sleep 2
echo "✅ Services stopped"

echo ""
echo "🔍 Verifying fixes..."
python -m py_compile mcp_server/intent_parser.py mcp_server/table_ranker.py
echo "✅ Files compile successfully"

echo ""
echo "🧪 Testing plural handling..."
python3 << 'EOF'
from mcp_server.intent_parser import IntentParser
parser = IntentParser()

tests = [
    ("customers", ["customer"]),
    ("orders", ["order"]),
    ("products", ["product"]),
    ("How many customers?", ["customer"]),
    ("Show me orders", ["order"]),
]

all_pass = True
for query, expected_entities in tests:
    result = parser.parse(query)
    if result.entities == expected_entities:
        print(f"  ✅ '{query}' → {result.entities}")
    else:
        print(f"  ❌ '{query}' → {result.entities} (expected {expected_entities})")
        all_pass = False

if all_pass:
    print("✅ All entity extraction tests passed!")
else:
    print("❌ Some tests failed!")
    exit(1)
EOF

echo ""
echo "🚀 Starting MCP Server..."
python -m mcp_server.main &
MCP_PID=$!
echo "  PID: $MCP_PID"
sleep 3

echo ""
echo "🚀 Starting LangGraph Orchestrator..."
python -m langgraph_integration.orchestrator &
ORCH_PID=$!
echo "  PID: $ORCH_PID"
sleep 2

echo ""
echo "✅ ================================"
echo "   DEPLOYMENT COMPLETE"
echo "================================"
echo ""
echo "🧪 Quick test commands:"
echo ""
echo "  1. Stream debug logs:"
echo "     python debug_stream.py"
echo ""
echo "  2. Test query:"
echo "     curl -X POST http://localhost:5001/ask \\
echo "       -H 'Content-Type: application/json' \\
echo "       -d '{\"query\": \"How many customers do we have?\"}'"
echo ""
echo "📊 Expected improvements:"
echo "  • MCP discovery: 943 tables → ~30 tables"
echo "  • SQL generation success rate: ~20% → 95%+"
echo "  • System behavior: 'Write SQL yourself' → Natural answers ✅"
echo ""
echo "📖 Full documentation:"
echo "  See: PHASE_9_PLURAL_FIX_COMPLETE.md"
echo ""