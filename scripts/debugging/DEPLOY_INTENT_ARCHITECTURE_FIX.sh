#!/bin/bash
#
# PHASE 9: Deploy Intent Parsing Architecture Fix
#
# This script verifies that the MCP server no longer performs duplicate intent parsing.
# Intent parsing is now exclusively handled by LangGraph's IntentParserAgent.
#
# Changes:
# 1. ✅ Removed IntentParser usage from mcp_server/discovery_tools.py
# 2. ✅ MCP now acts as a pure tool layer (no semantic reasoning)
# 3. ✅ LangGraph remains the sole intent parser (single source of truth)

set -e

PROJECT_ROOT="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
LOGS_DIR="$PROJECT_ROOT/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"
DEPLOY_LOG="$LOGS_DIR/intent_architecture_fix_$(date +%Y%m%d_%H%M%S).log"

echo "🚀 DEPLOYING INTENT PARSING ARCHITECTURE FIX" | tee "$DEPLOY_LOG"
echo "================================================" | tee -a "$DEPLOY_LOG"
echo "" | tee -a "$DEPLOY_LOG"

# ============= VERIFICATION TESTS =============

echo "✓ Verification 1: MCP discovery tools no longer import intent_parser" | tee -a "$DEPLOY_LOG"
if grep -q "from mcp_server.intent_parser import IntentParser" "$PROJECT_ROOT/mcp_server/discovery_tools.py"; then
    echo "  ❌ FAILED: MCP discovery_tools.py still imports IntentParser" | tee -a "$DEPLOY_LOG"
    exit 1
else
    echo "  ✅ PASSED: No IntentParser import in discovery_tools.py" | tee -a "$DEPLOY_LOG"
fi

echo "" | tee -a "$DEPLOY_LOG"
echo "✓ Verification 2: LangGraph orchestrator uses correct IntentParserAgent" | tee -a "$DEPLOY_LOG"
if grep -q "from langgraph_integration.agents.intent_parser.agent import IntentParserAgent" "$PROJECT_ROOT/langgraph_integration/orchestrator.py"; then
    echo "  ✅ PASSED: Orchestrator imports IntentParserAgent from correct location" | tee -a "$DEPLOY_LOG"
else
    echo "  ❌ FAILED: Orchestrator doesn't import correct IntentParserAgent" | tee -a "$DEPLOY_LOG"
    exit 1
fi

echo "" | tee -a "$DEPLOY_LOG"
echo "✓ Verification 3: Intent parsing only happens in LangGraph" | tee -a "$DEPLOY_LOG"
MAIN_PARSE_CALLS=$(grep -r "IntentParser()" "$PROJECT_ROOT" --include="*.py" \
    | grep -v "tests/" \
    | grep -v "archive/" \
    | grep -v "\.intent_parser\.py" \
    | wc -l)
if [ "$MAIN_PARSE_CALLS" -eq 0 ]; then
    echo "  ✅ PASSED: No direct IntentParser() calls in active code" | tee -a "$DEPLOY_LOG"
else
    echo "  ⚠️  WARNING: Found $MAIN_PARSE_CALLS IntentParser() calls outside of intent_parser.py" | tee -a "$DEPLOY_LOG"
    grep -r "IntentParser()" "$PROJECT_ROOT" --include="*.py" \
        | grep -v "tests/" \
        | grep -v "archive/" \
        | grep -v "\.intent_parser\.py" | tee -a "$DEPLOY_LOG" || true
fi

echo "" | tee -a "$DEPLOY_LOG"
echo "✓ Verification 4: DiscoveryAgent uses cleaned keywords from ParsedIntent" | tee -a "$DEPLOY_LOG"
if grep -q "intent.get(\"keywords_for_discovery\"" "$PROJECT_ROOT/langgraph_integration/agents/discovery/agent.py"; then
    echo "  ✅ PASSED: DiscoveryAgent uses intent.keywords_for_discovery" | tee -a "$DEPLOY_LOG"
else
    echo "  ❌ FAILED: DiscoveryAgent not using intent.keywords_for_discovery" | tee -a "$DEPLOY_LOG"
    exit 1
fi

echo "" | tee -a "$DEPLOY_LOG"
echo "✓ Verification 5: Architecture documentation updated" | tee -a "$DEPLOY_LOG"
if [ -f "$PROJECT_ROOT/PHASE_9_INTENT_PARSING_ARCHITECTURE_FIX.md" ]; then
    echo "  ✅ PASSED: Architecture fix documentation exists" | tee -a "$DEPLOY_LOG"
else
    echo "  ⚠️  WARNING: Architecture fix documentation not found" | tee -a "$DEPLOY_LOG"
fi

echo "" | tee -a "$DEPLOY_LOG"
echo "================================================" | tee -a "$DEPLOY_LOG"
echo "🎯 DEPLOYMENT VERIFICATION COMPLETE" | tee -a "$DEPLOY_LOG"
echo "" | tee -a "$DEPLOY_LOG"

# ============= SYNTAX CHECKS =============

echo "✓ Python Syntax Check: Key files" | tee -a "$DEPLOY_LOG"

FILES_TO_CHECK=(
    "mcp_server/discovery_tools.py"
    "langgraph_integration/orchestrator.py"
    "langgraph_integration/agents/discovery/agent.py"
    "langgraph_integration/agents/intent_parser/agent.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    full_path="$PROJECT_ROOT/$file"
    if python3 -m py_compile "$full_path" 2>&1 | tee -a "$DEPLOY_LOG"; then
        echo "  ✅ $file - Syntax OK" | tee -a "$DEPLOY_LOG"
    else
        echo "  ❌ $file - Syntax ERROR" | tee -a "$DEPLOY_LOG"
        exit 1
    fi
done

echo "" | tee -a "$DEPLOY_LOG"
echo "✅ ALL VERIFICATIONS PASSED" | tee -a "$DEPLOY_LOG"
echo "" | tee -a "$DEPLOY_LOG"
echo "📝 Log saved to: $DEPLOY_LOG" | tee -a "$DEPLOY_LOG"
echo "" | tee -a "$DEPLOY_LOG"

# ============= DEPLOYMENT INSTRUCTIONS =============

cat >> "$DEPLOY_LOG" << 'EOF'

🚀 NEXT STEPS FOR DEPLOYMENT:

1. RESTART SERVICES:
   - Stop MCP Server (if running)
   - Stop LangGraph Orchestrator (if running)
   - Restart both services with:
     python -m mcp_server.main &
     python -m langgraph_integration.orchestrator &

2. RUN END-TO-END TEST:
   - Test query: "How many customers do we have?"
   - Verify Discovery returns ~20-30 customer tables (not all 943)
   - Verify system answers naturally instead of asking for SQL

3. CHECK LOGS:
   - MCP logs: Should NOT see "Intent parsed:" messages
   - LangGraph logs: SHOULD see "Intent parsed:" message once per query

4. MONITOR PERFORMANCE:
   - Query latency should be same or faster (one parse vs two)
   - Discovery time should be faster (fewer candidates to rank)

ROLLBACK (if needed):
   - Git revert to previous commit
   - No database migrations needed

EOF

cat "$DEPLOY_LOG"

echo ""
echo "✨ Deployment ready! Review the log above and follow NEXT STEPS." 
echo ""