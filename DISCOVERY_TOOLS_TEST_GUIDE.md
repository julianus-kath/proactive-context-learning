# Discovery Tools Fix - Testing Guide

## Quick Test (5 minutes)

### 1. Start Services
```bash
# VPN must be active
./start_all_services_mac.sh

# Or manually:
python mcp_server/server.py &
python -m langgraph_integration.main &
```

### 2. Test Discovery Tools Directly
```bash
# In Python shell or test file:
import asyncio
from langgraph_integration.mcp_client import list_tables_mcp, search_tables_mcp, describe_table_mcp

# Test 1: List tables
result = asyncio.run(list_tables_mcp(page=1, page_size=10))
print("✅ list_tables_mcp result:")
print(f"  - ok: {result.get('ok')}")
print(f"  - tables found: {len(result.get('data', {}).get('tables', []))}")
print(f"  - pagination: {result.get('data', {}).get('pagination')}")

# Expected output:
# ✅ list_tables_mcp result:
#   - ok: True
#   - tables found: X (where X > 0)
#   - pagination: {'total_items': Y, 'total_pages': Z, 'page': 1, 'page_size': 10}

# Test 2: Search tables
result = asyncio.run(search_tables_mcp("product"))
print("\n✅ search_tables_mcp result:")
print(f"  - ok: {result.get('ok')}")
print(f"  - tables: {result.get('data', {}).get('results', [])[:3]}")

# Test 3: Describe table (replace with actual table name from your DB)
result = asyncio.run(describe_table_mcp("dbo.Products"))
print("\n✅ describe_table_mcp result:")
print(f"  - ok: {result.get('ok')}")
if result.get('ok'):
    data = result.get('data', {})
    print(f"  - columns: {len(data.get('columns', []))} found")
    print(f"  - row_count: {data.get('row_count')}")
```

### 3. Expected Output for Success
```
✅ list_tables_mcp result:
  - ok: True
  - tables found: 8 (example)
  - pagination: {'total_items': 50, 'total_pages': 5, 'page': 1, 'page_size': 10}

✅ search_tables_mcp result:
  - ok: True
  - tables: [{'name': 'Products', 'score': 0.95}, ...]

✅ describe_table_mcp result:
  - ok: True
  - columns: 12 found
  - row_count: 1523
```

### 4. Test Agent End-to-End
```bash
# In the agent UI or API test:

# Query 1 - Simple data query
POST /agent/query
{
  "query": "Show me top 5 products by sales"
}

# Expected: ✅ Agent responds immediately with results
# NOT: "I need more information to help you..."

# Query 2 - Schema query
POST /agent/query
{
  "query": "What tables do we have?"
}

# Expected: ✅ Agent lists available tables
# NOT: "I need more information..."

# Query 3 - Complex analysis
POST /agent/query
{
  "query": "How many customers made purchases in the last month?"
}

# Expected: ✅ Agent finds customers and sales tables, generates SQL, returns count
# NOT: Any clarification requests
```

---

## Deep Test (15 minutes)

### Test Logs for Debugging

Run the agent and check logs for these patterns:

**✅ SUCCESS PATTERN:**
```
INFO:langgraph_integration.mcp_client:✅ list_tables: page 1/5, showing 10 of 50 total tables
INFO:langgraph_integration.graph_definition:Schema overview retrieved: 10 tables shown (of 50 total)
INFO:langgraph_integration.graph_definition:Available Tables:
  - dbo.Products (1523 rows)
  - dbo.Customers (892 rows)
  ... (more tables)
```

**❌ FAILURE PATTERN (before fix):**
```
ERROR:langgraph_integration.mcp_client:Error listing tables: 0
ERROR:langgraph_integration.graph_definition:Error getting table list: 0
ERROR:langgraph_integration.graph_definition:Error generating clarification: 'NoneType' object has no attribute 'get'
```

### Detailed Trace Tests

1. **Test list_tables() internal parsing**:
```python
from langgraph_integration.mcp_client import MCPDatabaseTool

tool = MCPDatabaseTool()
result = asyncio.run(tool.list_tables(page=1, page_size=10))

# Should be dict with these keys:
assert result.get("ok") is not None
assert "data" in result
assert "tables" in result["data"]
assert "pagination" in result["data"]
print("✅ list_tables() returns properly formatted dict")
```

2. **Test wrapper function**:
```python
from langgraph_integration.mcp_client import list_tables_mcp

result = asyncio.run(list_tables_mcp(page=1, page_size=10))

# Should be same as internal method
assert result.get("ok") is not None
assert "data" in result
print("✅ list_tables_mcp() properly passes through dict")
```

3. **Test graph workflow**:
```python
from langgraph_integration.graph_definition import LangGraphWorkflow

workflow = LangGraphWorkflow()

# Simulate workflow state
state = {
    "messages": [],
    "user_input": "Show me products",
    "intent_analysis": None,
    "schema": None,
    "schema_snippet": None,
    "database_index": None,
    "sql_query": None,
    "query_results": None,
    "error_info": None,
    "final_response": None,
    "retry_count": 0,
    "session_described_tables": None,
    "relevant_tables": None,
    "is_schema_query": None
}

# Run schema retrieval
result_state = asyncio.run(workflow._get_schema(state))

# Check if schema was populated
assert result_state["schema"] is not None
assert "Available Tables:" in result_state["schema"]
print("✅ _get_schema() successfully populates schema from discovery tools")
```

---

## Regression Tests

### Test that SQL Server syntax works
```python
from langgraph_integration.graph_definition import LangGraphWorkflow

workflow = LangGraphWorkflow()

# Test intent parsing
query = "Show me products sold today"
intent = asyncio.run(workflow._parse_intent_simple(query))

# Should identify products table
assert intent.get("operation") == "DATA_QUERY"
print("✅ Intent parsing recognizes data queries")
```

### Test that schema discovery finds multiple tables
```python
from langgraph_integration.mcp_client import list_tables_mcp

result = asyncio.run(list_tables_mcp(page=1, page_size=100))

tables = result.get("data", {}).get("tables", [])
pagination = result.get("data", {}).get("pagination", {})

# Should have multiple tables
assert len(tables) > 0, "No tables found"
assert pagination.get("total_items", 0) > 0, "Pagination broken"

print(f"✅ Found {len(tables)} tables (of {pagination.get('total_items')} total)")
```

### Test error handling
```python
from langgraph_integration.mcp_client import list_tables_mcp

# Test with invalid input (but should still handle gracefully)
result = asyncio.run(list_tables_mcp(page=999999, page_size=10))

# Should return proper error dict, not crash
assert isinstance(result, dict)
assert "ok" in result or "error" in result

print("✅ Error handling returns proper dict instead of crashing")
```

---

## Checklist for Full Verification

- [ ] VPN is connected
- [ ] MCP server starts without errors
- [ ] `list_tables_mcp()` returns `{"ok": True, "data": {...}}`
- [ ] `search_tables_mcp()` returns search results
- [ ] `describe_table_mcp()` returns table schema
- [ ] `_get_schema()` populates schema successfully
- [ ] Agent responds immediately (no "I need more info" loops)
- [ ] Agent can answer: "Show me top 5 products"
- [ ] Agent can answer: "How many customers?"
- [ ] Agent can answer: "What tables do we have?"
- [ ] Logs show "Schema overview retrieved" (not "Schema information unavailable")
- [ ] No "NoneType" errors in clarification generation
- [ ] SQL Server queries execute without "current_date" syntax errors

---

## Troubleshooting

**If tests still fail:**

1. **Check MCP server logs:**
   ```bash
   tail -f logs/mcp_server.log
   # Look for discovery tool errors
   ```

2. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Verify SQL Server connection:**
   ```bash
   python tests/test_mywebshop_connection.py
   # Should show successful connection
   ```

4. **Test discovery tools directly on MCP server:**
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Authorization: Bearer supersecretapikey" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "method": "tools/call",
       "params": {"name": "list_tables", "arguments": {"page": 1, "page_size": 10}},
       "id": 1
     }'
   ```
