# Phase 7 Migration Guide: Legacy Proxy → MCP

**Status**: Active  
**Version**: 1.0  
**Last Updated**: January 2025

---

## 🎯 Overview

Phase 7 decommissions the legacy Flask `/query` endpoint and enforces **MCP as the single interface** for SQL database access. This guide helps you migrate existing code to the new MCP-based client.

### Why Migrate?

1. **Single Interface**: No more dual paths (Flask + MCP) - reduces complexity
2. **Better Performance**: MCP has catalog caching, rate limiting, and optimized discovery
3. **Design Guardrails**: Enforces best practices (pagination, small prompts, backpressure)
4. **Future-Proof**: All new features will be MCP-only

---

## 🚨 Breaking Changes

### 1. Flask `/query` Endpoint Returns 410 Gone

**Before** (Legacy):
```bash
curl -X POST http://localhost:5000/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM customers", "conn": "corp_sql_erp"}'
```

**After** (Phase 7):
```json
{
  "ok": false,
  "error": "This endpoint is permanently deprecated. Please use MCP JSON-RPC instead.",
  "code": "ENDPOINT_DEPRECATED",
  "status": 410,
  "migration_guide": { ... }
}
```

### 2. `app/db/client.py` DatabaseClient is Deprecated

**Before** (Legacy):
```python
from app.db.client import DatabaseClient

client = DatabaseClient()
columns, rows = client.query(
    sql="SELECT * FROM customers",
    conn="corp_sql_erp",
    limit=100
)
```

**After** (Phase 7):
```python
from app.db.mcp_client import MCPDatabaseClient

client = MCPDatabaseClient()
columns, rows = client.query(
    sql="SELECT * FROM customers",
    limit=100
)
```

---

## 📋 Migration Checklist

### Step 1: Update Imports

**Find and Replace**:
```python
# OLD
from app.db.client import DatabaseClient, get_database_client

# NEW
from app.db.mcp_client import MCPDatabaseClient, get_mcp_client
```

### Step 2: Update Client Initialization

**OLD**:
```python
client = DatabaseClient()
# or
client = get_database_client()
```

**NEW**:
```python
client = MCPDatabaseClient()
# or
client = get_mcp_client()
```

### Step 3: Update Query Calls

**OLD**:
```python
columns, rows = client.query(
    sql="SELECT * FROM customers WHERE region = 'US'",
    conn="corp_sql_erp",        # ❌ Removed
    params={"region": "US"},    # ❌ Removed (use SQL params instead)
    timeout_s=30,               # ❌ Removed (configured in MCP)
    limit=100
)
```

**NEW**:
```python
columns, rows = client.query(
    sql="SELECT * FROM customers WHERE region = 'US'",
    limit=100,                  # ✅ Optional (default: 100)
    enable_redaction=True       # ✅ Optional (default: True)
)
```

### Step 4: Use Discovery Tools (New Feature!)

**OLD** (Manual schema queries):
```python
# Had to query information_schema manually
columns, rows = client.query(
    sql="SELECT table_name FROM information_schema.tables",
    conn="corp_sql_erp"
)
```

**NEW** (Discovery tools with pagination):
```python
# Search for tables (never enumerate full schema)
tables = client.search_tables(
    pattern="customer",
    limit=20,
    offset=0
)

# Describe a specific table
table_info = client.describe_table("customers")

# Get relationships
relations = client.list_relations("customers")
```

### Step 5: Update Environment Variables

**Remove** (Legacy proxy config):
```bash
PROXY_BASE_URL=http://192.168.1.35:5000
PROXY_API_KEY=your-key
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_TIMEOUT=30
```

**Add** (MCP config):
```bash
MCP_SERVER_URL=http://localhost:8000
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_BACKOFF_FACTOR=2.0
MCP_API_KEY=your-key  # Optional
```

---

## 🔄 Code Examples

### Example 1: Simple Query Migration

**Before**:
```python
from app.db.client import DatabaseClient

def get_customers():
    client = DatabaseClient()
    columns, rows = client.query(
        sql="SELECT customer_id, name, email FROM customers LIMIT 10",
        conn="corp_sql_erp"
    )
    return columns, rows
```

**After**:
```python
from app.db.mcp_client import MCPDatabaseClient

def get_customers():
    client = MCPDatabaseClient()
    columns, rows = client.query(
        sql="SELECT customer_id, name, email FROM customers LIMIT 10",
        limit=10
    )
    return columns, rows
```

### Example 2: Schema Discovery Migration

**Before** (Manual queries):
```python
from app.db.client import DatabaseClient

def find_customer_tables():
    client = DatabaseClient()
    
    # Query information_schema
    columns, rows = client.query(
        sql="""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_name LIKE '%customer%'
        """,
        conn="corp_sql_erp"
    )
    
    return [row[0] for row in rows]
```

**After** (Discovery tools):
```python
from app.db.mcp_client import MCPDatabaseClient

def find_customer_tables():
    client = MCPDatabaseClient()
    
    # Use search_tables (catalog-backed, no DB hit)
    tables = client.search_tables(
        pattern="customer",
        limit=50
    )
    
    return [table["name"] for table in tables]
```

### Example 3: Error Handling Migration

**Before**:
```python
from app.db.client import DatabaseClient

def safe_query(sql):
    client = DatabaseClient()
    try:
        columns, rows = client.query(sql, conn="corp_sql_erp")
        return {"ok": True, "columns": columns, "rows": rows}
    except RuntimeError as e:
        if "Proxy connection failed" in str(e):
            return {"ok": False, "error": "Database unavailable"}
        raise
```

**After**:
```python
from app.db.mcp_client import MCPDatabaseClient

def safe_query(sql):
    client = MCPDatabaseClient()
    try:
        columns, rows = client.query(sql)
        return {"ok": True, "columns": columns, "rows": rows}
    except RuntimeError as e:
        if "MCP connection failed" in str(e):
            return {"ok": False, "error": "Database unavailable"}
        elif "Rate limit exceeded" in str(e):
            return {"ok": False, "error": "Too many requests, retry later"}
        raise
```

### Example 4: Health Check Migration

**Before**:
```python
from app.db.client import DatabaseClient

def check_database():
    client = DatabaseClient()
    if client.health_check():
        return {"status": "healthy"}
    return {"status": "unhealthy"}
```

**After** (Same API!):
```python
from app.db.mcp_client import MCPDatabaseClient

def check_database():
    client = MCPDatabaseClient()
    if client.health_check():
        return {"status": "healthy"}
    return {"status": "unhealthy"}
```

---

## 🎓 Design Guardrails (Enforced)

### 1. Never Enumerate Full Schema

**❌ Bad** (Legacy pattern):
```python
# Don't do this - loads entire schema
columns, rows = client.query("SELECT * FROM information_schema.tables")
```

**✅ Good** (Phase 7 pattern):
```python
# Use pagination - only load what you need
tables = client.search_tables(pattern="", limit=20, offset=0)
```

### 2. Small, Focused Prompts (≤3 Tables)

**❌ Bad**:
```python
# Don't describe 10 tables at once
for table in all_tables:
    describe_table(table)  # Causes rate limiting
```

**✅ Good**:
```python
# Describe only relevant tables (≤3)
relevant_tables = ["customers", "orders", "order_items"]
for table in relevant_tables[:3]:
    describe_table(table)
```

### 3. Use Caching

**✅ Good**:
```python
# MCP caches catalog automatically
# Repeated searches are fast
tables1 = client.search_tables("customer")  # DB hit
tables2 = client.search_tables("customer")  # Cache hit (fast!)
```

### 4. Handle Rate Limiting

**✅ Good**:
```python
import time

def query_with_backoff(client, sql, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.query(sql)
        except RuntimeError as e:
            if "Rate limit exceeded" in str(e):
                # MCP client handles Retry-After automatically
                # But you can add additional logic here
                time.sleep(2 ** attempt)
            else:
                raise
    raise RuntimeError("Max retries exceeded")
```

---

## 🧪 Testing Your Migration

### Unit Tests

```python
import pytest
from unittest.mock import patch, Mock
from app.db.mcp_client import MCPDatabaseClient

def test_query_migration():
    """Test that migrated code works with MCP client."""
    with patch('app.db.mcp_client.requests.post') as mock_post:
        # Mock MCP response
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "columns": ["id", "name"],
                    "rows": [[1, "Test"]]
                }
            }
        )
        
        client = MCPDatabaseClient()
        columns, rows = client.query("SELECT * FROM test")
        
        assert columns == ["id", "name"]
        assert rows == [[1, "Test"]]
```

### Integration Tests

```bash
# Start MCP server
cd mcp_server
python start_server.py &

# Run integration tests
pytest tests/test_mcp_client.py -v

# Verify no legacy /query calls
grep -r "POST /query" tests/ --include="*.py"
# Should return no results (or only deprecated tests)
```

---

## 🚨 Common Issues & Solutions

### Issue 1: "MCP connection failed"

**Cause**: MCP server not running or wrong URL

**Solution**:
```bash
# Check if MCP server is running
curl http://localhost:8000/health

# Start MCP server if needed
cd mcp_server
python start_server.py
```

### Issue 2: "Rate limit exceeded"

**Cause**: Too many requests in short time

**Solution**:
```python
# MCP client handles Retry-After automatically
# Just retry the request - it will backoff correctly
try:
    result = client.query(sql)
except RuntimeError as e:
    if "Rate limit exceeded" in str(e):
        # Wait and retry (client already waited for Retry-After)
        time.sleep(1)
        result = client.query(sql)
```

### Issue 3: "conn parameter is ignored"

**Cause**: Using legacy DatabaseClient API

**Solution**:
```python
# Remove conn parameter - MCP handles connection internally
# OLD
client.query(sql, conn="corp_sql_erp")

# NEW
client.query(sql)  # Connection configured in MCP server
```

### Issue 4: Import errors

**Cause**: Old import paths

**Solution**:
```python
# Update imports
# OLD
from app.db.client import DatabaseClient

# NEW
from app.db.mcp_client import MCPDatabaseClient
```

---

## 📚 Additional Resources

- **Phase 7 Plan**: `docs/PHASE_7_PLAN.md`
- **Phase 6 Features**: `docs/PHASE_6_COMPLETE.md`
- **MCP Server Docs**: `mcp_server/README.md`
- **ADR-0007**: MCP Database Server Implementation
- **ADR-0010**: Complete System Architecture

---

## 🎉 Benefits After Migration

✅ **Simpler Architecture**: One interface, no drift  
✅ **Better Performance**: Catalog caching, optimized queries  
✅ **Rate Limiting**: Automatic backoff with Retry-After  
✅ **Discovery Tools**: Search, describe, relations (no manual queries)  
✅ **Safety Controls**: SELECT-only, row limits, timeouts, PII redaction  
✅ **Future-Proof**: All new features will be MCP-only  

---

## 🤝 Need Help?

- **Documentation**: See `docs/PHASE_7_PLAN.md`
- **Examples**: See `tests/test_mcp_client.py`
- **Issues**: Check logs in `mcp_server/logs/`

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Maintained By**: Dynamic ERP Assistant Team