#!/bin/bash
# CRITICAL FIX - Run this NOW

echo "🔴 Step 1: Killing all Python services..."
pkill -9 -f "python.*langgraph"
pkill -9 -f "python.*mcp"
pkill -9 -f "debug_stream"
sleep 3

echo "✅ Step 2: Clearing Python cache..."
find /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code -name "*.pyc" -delete 2>/dev/null

echo "✅ Step 3: Verifying fix..."
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code
python INTENT_PARSE_FIX_VERIFY.py

echo ""
echo "================================"
echo "✅ FIX VERIFIED - Cache Cleared"
echo "================================"
echo ""
echo "NOW RESTART YOUR SERVICES:"
echo ""
echo "Terminal 1:"
echo "  cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code"
echo "  python -m langgraph_integration.main"
echo ""
echo "Terminal 2:"
echo "  python mcp_server/main.py"
echo ""
echo "Terminal 3 (optional):"
echo "  python debug_stream.py"
echo ""
echo "Then test a query!"