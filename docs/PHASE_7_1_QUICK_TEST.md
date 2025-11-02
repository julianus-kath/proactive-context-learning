# Phase 7.1: Quick Test Guide

## 🚀 Fast Track to Testing

### Prerequisites
- MCP server running on Windows/VPN
- LangGraph agent running on macOS
- Database with Scout Catalog initialized

---

## Test 1: Verify Tool is Available

```bash
# Check tool list from MCP
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }' | grep -i "get_column_index"
```

Expected: Should see `"name": "get_column_index"` in output

---

## Test 2: Call the Tool Directly

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_column_index",
      "arguments": {
        "table_names": ["dbo.KHKAdressen", "dbo.Orders"]
      }
    },
    "id": 2
  }' | jq .
```

Expected response:
```json
{
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"ok\":true,\"data\":{\"dbo.KHKAdressen\":[\"KdNr\",...],\"dbo.Orders\":[...]},\"execution_time_ms\":12.3}"
    }]
  }
}
```

---

## Test 3: Check Prompt Includes Column Index

```python
from langgraph_integration.prompts import format_sql_generator_prompt

column_index = {
    "dbo.KHKAdressen": ["KdNr", "Plz", "Ort", "BezeichnungKurz"],
    "dbo.Orders": ["OrderId", "CustomerId", "TotalAmount"]
}

prompt = format_sql_generator_prompt(
    schema="[schema text]",
    column_index=column_index,
    operation="query",
    entities=["customers"],
    requirements="",
    user_input="show customers"
)

# Verify column index is in prompt
assert "PHASE 7.1" in prompt
assert "KdNr" in prompt
assert "INDEXED COLUMNS" in prompt
assert "NEVER hallucinate" in prompt

print("✅ Prompt includes column index")
```

---

## Test 4: End-to-End Query

### 4a: Bad Query (Hallucination Test)

```
User: "list any 5 customers"
```

Expected behavior:
- **Before Phase 7.1**: Might generate `ORDER BY [Name]` → Error → Fallback
- **After Phase 7.1**: Only uses columns from index → Correct SQL first try

Look for logs:
```
📋 Fetching column index for 1 tables...
✅ Got column index: {'dbo.KHKAdressen': ['KdNr', 'Plz', 'Ort', ...]}
SQL generated: SELECT TOP 5 * FROM dbo.KHKAdressen
```

### 4b: Ordering Query

```
User: "show top 10 customers by name"
```

Expected behavior:
- Column index fetched
- LLM sees available columns
- If "Name" not in index, might use "BezeichnungKurz" or fallback to SELECT *
- Result returned without errors

Look for:
- No column validation errors
- No hallucination warnings
- Query executes successfully

---

## Test 5: Check Logs

### Filter for column index operations:
```bash
tail -f logs/app.log | grep -E "(📋|column index|INDEXED)"
```

### Expected log patterns:
```
📋 Fetching column index for 1 tables...
✅ Got column index: {'dbo.KHKAdressen': ['KdNr', 'Plz', 'Ort', 'BezeichnungKurz']}
execution_time_ms: 12.3ms
```

### Error patterns (if MCP tool unavailable):
```
⚠️ Column index fetch failed, continuing without it
```

---

## Test 6: Verify Backward Compatibility

```python
# Should work WITHOUT column_index parameter
from langgraph_integration.prompts import format_sql_generator_prompt

prompt = format_sql_generator_prompt(
    schema="test schema",
    operation="query",
    entities=[],
    requirements="",
    user_input="test"
    # NO column_index parameter!
)

# Should still contain SQL generation instructions
assert "MSSQL" in prompt
assert "SELECT" in prompt

print("✅ Backward compatible - works without column_index")
```

---

## Test 7: Performance Test

```python
import time
import asyncio
from langgraph_integration.mcp_client import get_column_index_mcp

async def test_performance():
    tables = ["dbo.KHKAdressen", "dbo.Orders", "dbo.Customers"]
    
    start = time.time()
    column_index = await get_column_index_mcp(tables)
    elapsed = (time.time() - start) * 1000
    
    print(f"✅ Fetched {len(column_index)} tables in {elapsed:.1f}ms")
    assert elapsed < 100, f"Too slow: {elapsed}ms (should be <100ms)"

asyncio.run(test_performance())
```

Expected: ~10-30ms for 2-3 tables

---

## Test 8: Error Handling

### What if MCP server is down?

```python
import asyncio
from langgraph_integration.mcp_client import get_column_index_mcp

async def test_mcp_down():
    # MCP server not running
    result = await get_column_index_mcp(["dbo.Table"])
    
    # Should gracefully degrade
    if not result:
        print("✅ Graceful degradation: returned empty dict")
    else:
        print("⚠️ Unexpected result:", result)

asyncio.run(test_mcp_down())
```

Expected behavior:
- Returns empty dict `{}`
- Agent continues with old validation logic
- No crash

---

## Test 9: Multiple Tables

```
User: "show customers with their orders"
```

Expected:
- Fetch column index for BOTH tables
- Pass both to prompt: `{"dbo.KHKAdressen": [...], "dbo.Orders": [...]}`
- LLM can use columns from either table
- SQL is correct for JOIN

---

## Debugging Checklist

If column index isn't working:

- [ ] MCP server is running
- [ ] `get_column_index` tool appears in `/tools/list`
- [ ] Scout Catalog is initialized (`catalog_age_s` in health check)
- [ ] LangGraph agent has updated code
- [ ] Logs show `📋 Fetching column index`
- [ ] Response includes column names

Check logs:
```bash
# MCP server logs
grep -i "get_column_index" mcp_server.log

# LangGraph logs  
grep -i "column index" langgraph.log
```

---

## Success Criteria

✅ **Phase 7.1 is working when:**

1. Tool `get_column_index` appears in MCP tools list
2. Calling tool returns structured column data
3. Prompt formatting includes `{column_index_json}`
4. Logs show "Fetching column index" messages
5. Query results are correct without hallucination errors
6. Old validation still works as fallback
7. Performance is <50ms for typical queries

---

## Before & After Comparison

### Before Phase 7.1
```
User: "list 5 customers"
SQL: SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [Name]
Error: Ungültiger Spaltenname 'Name'
Fallback: SELECT TOP 100 * FROM dbo.KHKAdressen
⏱️ Takes longer (includes error & fallback)
```

### After Phase 7.1
```
User: "list 5 customers"
📋 Fetching column index for 1 tables...
✅ Got column index: {'dbo.KHKAdressen': ['KdNr', 'Plz', ...]}
SQL: SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [KdNr]
✅ Correct immediately
⏱️ Faster (no fallback needed)
```

---

## Quick Test Script

```bash
#!/bin/bash

echo "=== Phase 7.1 Quick Test ==="

echo ""
echo "1. Check MCP server health..."
curl -s http://localhost:8000/health | jq '.ok'

echo ""
echo "2. Check column index tool available..."
curl -s -X POST http://localhost:8000/mcp \
  -H "X-API-Key: supersecretapikey" \
  -d '{"method":"tools/list"}' | grep -q "get_column_index" && echo "✅ Tool available" || echo "❌ Tool not found"

echo ""
echo "3. Test column index fetch..."
curl -s -X POST http://localhost:8000/mcp \
  -H "X-API-Key: supersecretapikey" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_column_index",
      "arguments": {"table_names": ["dbo.KHKAdressen"]}
    }
  }' | grep -q "KdNr" && echo "✅ Column index working" || echo "❌ Column index failed"

echo ""
echo "=== All checks complete ==="
```

---

## Support

If issues arise, check:
1. **Syntax errors**: `python3 -m py_compile` on modified files
2. **Import errors**: Check PYTHONPATH includes repo root
3. **MCP issues**: Test tool directly with curl
4. **Performance**: Check catalog size and network latency
5. **Logs**: Search for "column_index" or "7.1"

---

*Happy testing! 🧪*