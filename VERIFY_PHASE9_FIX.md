# ✅ PHASE 9 FIX VERIFICATION CHECKLIST

## Pre-Deployment Verification

- [ ] **Code Review**
  - [ ] Reviewed `mcp_server/discovery_tools.py` changes (lines 487-520)
  - [ ] Confirmed: No `IntentParser` import in discovery_tools
  - [ ] Confirmed: `IntentParserAgent` is used in LangGraph

- [ ] **Syntax Check**
  ```bash
  python -m py_compile mcp_server/discovery_tools.py
  # Should return: No errors ✅
  ```

- [ ] **Verification Script**
  ```bash
  bash DEPLOY_INTENT_ARCHITECTURE_FIX.sh
  # Should show: ✅ ALL VERIFICATIONS PASSED
  ```

---

## Deployment Steps

- [ ] **Stop Services**
  ```bash
  pkill -f "mcp_server"
  pkill -f "orchestrator"
  sleep 2
  ```

- [ ] **Start MCP Server**
  ```bash
  python -m mcp_server.main &
  sleep 3
  ```

- [ ] **Start LangGraph**
  ```bash
  python -m langgraph_integration.orchestrator &
  sleep 2
  ```

- [ ] **Services Are Running**
  ```bash
  ps aux | grep -E "mcp_server|orchestrator"
  # Should show both running ✅
  ```

---

## Functional Testing

- [ ] **Test 1: Query with Plural**
  ```
  Query: "How many customers do we have?"
  
  Expected:
  ✅ System answers naturally (e.g., "We have 12,543 customers")
  ✅ NOT asking: "Please write the SQL yourself"
  ❌ WRONG: All 943 tables returned
  ```

- [ ] **Test 2: Different Entity**
  ```
  Query: "Show me orders"
  
  Expected:
  ✅ Returns ~20-30 order-related tables
  ❌ WRONG: Returns all 943 tables
  ```

- [ ] **Test 3: Join Query**
  ```
  Query: "Show orders with customer details"
  
  Expected:
  ✅ Returns both orders and customer tables
  ✅ System can generate JOIN query
  ❌ WRONG: Fails to find relevant tables
  ```

---

## Log Verification

- [ ] **Check LangGraph Logs**
  ```bash
  # Look for this (EXACTLY ONCE per query):
  "Intent parsed: operation=query, entities=[...], keywords=[...]"
  
  ✅ Should appear: ONCE
  ❌ Should NOT appear: Multiple times
  ```

- [ ] **Check MCP Logs**
  ```bash
  # Look for "Intent parsed:" in MCP logs
  
  ✅ Should appear: NEVER (0 times)
  ❌ Should NOT appear in MCP: "Intent parsed:"
  ```

- [ ] **Check Discovery Logs**
  ```bash
  # Look for this in MCP discovery_tools:
  "Ranked X tables in Y ms for query"
  
  ✅ Should show: ~30-50 tables (semantic ranking)
  ❌ Should NOT show: 943 tables
  ```

---

## Code Quality Checks

- [ ] **No Regressions**
  ```bash
  # Verify no new imports of mcp_server.intent_parser
  grep -r "from mcp_server.intent_parser" . --include="*.py" \
    | grep -v "tests/" \
    | grep -v "archive/" \
    | grep -v ".intent_parser.py"
  
  # Should show: (empty - no results) ✅
  ```

- [ ] **Architecture Compliance**
  ```bash
  # Count intent parsing locations in active code:
  grep -r "IntentParser()" . --include="*.py" \
    | grep -v "tests/" \
    | grep -v "archive/" \
    | wc -l
  
  # Should be: 0 (only in intent_parser.py itself)
  ```

- [ ] **LangGraph Uses Correct Parser**
  ```bash
  grep "IntentParserAgent" langgraph_integration/orchestrator.py
  
  # Should show: ✅ Import exists
  ```

---

## End-to-End Test Scenario

**Scenario:** "How many customers placed orders in the last 30 days?"

**Step by step:**

1. [ ] **Parsing Phase**
   - LangGraph IntentParserAgent parses once ✅
   - Produces: `keywords_for_discovery: ["customer", "order"]`
   - Produces: `time_window: {period: "last_30_days"}`

2. [ ] **Discovery Phase**
   - DiscoveryAgent calls MCP with: `search_tables("customer")`
   - MCP returns: ~15 customer tables
   - DiscoveryAgent calls MCP with: `search_tables("order")`
   - MCP returns: ~20 order tables
   - Total candidates: ~35 tables (NOT 943!) ✅

3. [ ] **Planning Phase**
   - JoinSQL identifies key join: `customers.id = orders.customer_id`
   - Generates SQL with date filter ✅

4. [ ] **Execution Phase**
   - Executes with row cap + timeout ✅
   - Gets results safely ✅

5. [ ] **Answer Phase**
   - System says: "12,543 customers placed orders in the last 30 days" ✅
   - NOT: "Please write the SQL yourself" ❌

---

## Rollback Plan (If Needed)

- [ ] **Stop Services**
  ```bash
  pkill -f "mcp_server|orchestrator"
  ```

- [ ] **Revert Code**
  ```bash
  git revert HEAD  # or git checkout HEAD~1
  ```

- [ ] **Restart Services**
  ```bash
  python -m mcp_server.main &
  sleep 3
  python -m langgraph_integration.orchestrator &
  ```

---

## Sign-Off

- [ ] **Code Review:** Approved
- [ ] **Tests:** All passing
- [ ] **Functional Test:** Plural queries work
- [ ] **Logs:** Correct (1 parse in LangGraph, 0 in MCP)
- [ ] **Architecture:** Aligned with repo.md
- [ ] **Ready for Production:** ✅ **YES**

**Deployer Name:** ___________________
**Date:** ___________________
**Notes:** ___________________

---

## Quick Debug Commands

```bash
# Check if services are running
ps aux | grep -E "python.*mcp_server|python.*orchestrator"

# View recent logs
tail -f /path/to/logs/mcp_server.log
tail -f /path/to/logs/langgraph.log

# Kill and restart all
pkill -f "mcp_server|orchestrator"
sleep 2
python -m mcp_server.main & python -m langgraph_integration.orchestrator &

# Check for double parsing
grep -i "intent" /path/to/logs/*.log | wc -l
# Should be low (not huge numbers)

# Verify discovery quality
grep "Ranked.*tables" /path/to/logs/mcp_server.log
# Should show: ~30-50 tables, NOT 943
```

---

**Status:** Ready to verify ✅
**Risk Level:** LOW
**Estimated Time:** 15-20 minutes