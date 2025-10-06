# Database Client - Phase 7 (MCP-based)

**Status**: ✅ Active  
**Version**: 2.0 (MCP-based)  
**Phase**: 7 - Decommission Old Proxy

---

## 🎯 Overview

This directory contains the database client implementations for the Dynamic ERP Assistant project.

### Phase 7 Changes

**Before Phase 7**:
- `client.py` - Legacy Flask proxy client (deprecated)

**After Phase 7**:
- `mcp_client.py` - **NEW** MCP JSON-RPC client (recommended)
- `client.py` - Legacy client (deprecated, kept for backward compatibility)

---

## 🚀 Quick Start

### New Code (Recommended)

```python
from app.db.mcp_client import MCPDatabaseClient

# Initialize client
client = MCPDatabaseClient()

# Execute query
columns, rows = client.query(
    sql="SELECT * FROM customers WHERE region = 'US' LIMIT 10",
    limit=10
)

# Search for tables (discovery)
tables = client.search_tables(pattern="customer", limit=20)

# Describe a table
table_info = client.describe_table("customers")

# Get relationships
relations = client.list_relations("customers")

# Health check
is_healthy = client.health_check()
```

### Legacy Code (Deprecated)

```python
from app.db.client import DatabaseClient

# ⚠️ DEPRECATED: This will show warnings
client = DatabaseClient()
columns, rows = client.query(sql="SELECT * FROM customers", conn="corp_sql_erp")
```

---

## 📦 Files

### `mcp_client.py` (NEW - Phase 7)

**MCP-based database client** - Recommended for all new code.

**Features**:
- ✅ MCP JSON-RPC protocol
- ✅ Exponential backoff with Retry-After
- ✅ Discovery tools (search, describe, relations)
- ✅ Design guardrails enforcement
- ✅ Structured logging
- ✅ Rate limiting support

**Classes**:
- `MCPConfig` - Configuration dataclass
- `MCPDatabaseClient` - Main MCP client
- `DatabaseClient` - Legacy wrapper (deprecated)

**Functions**:
- `get_mcp_client()` - Get configured MCP client
- `get_database_client()` - Get legacy client (deprecated)

### `client.py` (DEPRECATED)

**Legacy Flask proxy client** - Deprecated in Phase 7.

**Status**: ⚠️ Deprecated - Use `mcp_client.py` instead

**Migration**: See `docs/MIGRATION_GUIDE_PHASE_7.md`

---

## 🔧 Configuration

### Environment Variables

```bash
# MCP Server Configuration (Phase 7)
MCP_SERVER_URL=http://localhost:8000
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_BACKOFF_FACTOR=2.0
MCP_API_KEY=your-api-key  # Optional

# Legacy Proxy Configuration (Deprecated)
PROXY_BASE_URL=http://192.168.1.35:5000  # ⚠️ Deprecated
PROXY_API_KEY=your-key                    # ⚠️ Deprecated
PROXY_DEFAULT_CONN=corp_sql_erp           # ⚠️ Deprecated
```

### Programmatic Configuration

```python
from app.db.mcp_client import MCPDatabaseClient, MCPConfig

# Custom configuration
config = MCPConfig(
    server_url="http://custom:9000",
    timeout_seconds=60,
    max_retries=5,
    backoff_factor=3.0,
    api_key="custom-key"
)

client = MCPDatabaseClient(config)
```

---

## 🎓 Design Guardrails

The MCP client enforces these design guardrails:

### 1. Never Enumerate Full Schema
```python
# ❌ Bad - Don't do this
all_tables = client.query("SELECT * FROM information_schema.tables")

# ✅ Good - Use pagination
tables = client.search_tables(pattern="", limit=20, offset=0)
```

### 2. Small, Focused Prompts (≤3 Tables)
```python
# ❌ Bad - Too many tables
for table in all_tables:
    describe_table(table)

# ✅ Good - Only relevant tables
relevant_tables = ["customers", "orders", "order_items"]
for table in relevant_tables[:3]:
    client.describe_table(table)
```

### 3. One Interface (MCP Only)
```python
# ❌ Bad - Using legacy proxy
from app.db.client import DatabaseClient

# ✅ Good - Using MCP
from app.db.mcp_client import MCPDatabaseClient
```

### 4. Caching Everywhere
```python
# ✅ Good - MCP caches automatically
tables1 = client.search_tables("customer")  # DB hit
tables2 = client.search_tables("customer")  # Cache hit (fast!)
```

### 5. Backpressure (Rate Limiting)
```python
# ✅ Good - MCP client handles Retry-After automatically
try:
    result = client.query(sql)
except RuntimeError as e:
    if "Rate limit exceeded" in str(e):
        # Client already waited for Retry-After
        # Just retry or handle gracefully
        pass
```

---

## 🧪 Testing

### Run Tests

```bash
# Run MCP client tests
pytest tests/test_mcp_client.py -v

# Run all database client tests
pytest tests/test_*client*.py -v
```

### Test Coverage

- ✅ Configuration loading
- ✅ Query execution
- ✅ Rate limiting with Retry-After
- ✅ Exponential backoff
- ✅ Discovery tools
- ✅ Health checks
- ✅ Legacy wrapper compatibility
- ✅ Design guardrails enforcement

---

## 📚 Documentation

- **Migration Guide**: `docs/MIGRATION_GUIDE_PHASE_7.md`
- **Phase 7 Plan**: `docs/PHASE_7_PLAN.md`
- **Phase 7 Summary**: `docs/PHASE_7_SUMMARY.md`
- **MCP Server**: `mcp_server/README.md`
- **ADR-0007**: MCP Database Server Implementation

---

## 🔄 Migration Path

### Step 1: Update Imports
```python
# OLD
from app.db.client import DatabaseClient

# NEW
from app.db.mcp_client import MCPDatabaseClient
```

### Step 2: Update Initialization
```python
# OLD
client = DatabaseClient()

# NEW
client = MCPDatabaseClient()
```

### Step 3: Update Query Calls
```python
# OLD
columns, rows = client.query(sql, conn="corp_sql_erp", limit=100)

# NEW
columns, rows = client.query(sql, limit=100)
```

### Step 4: Use Discovery Tools
```python
# NEW - Discovery tools available
tables = client.search_tables("customer", limit=20)
table_info = client.describe_table("customers")
relations = client.list_relations("customers")
```

**See**: `docs/MIGRATION_GUIDE_PHASE_7.md` for complete guide

---

## 🚨 Common Issues

### Issue: "MCP connection failed"
**Solution**: Check if MCP server is running
```bash
curl http://localhost:8000/health
```

### Issue: "Rate limit exceeded"
**Solution**: MCP client handles Retry-After automatically, just retry

### Issue: "conn parameter is ignored"
**Solution**: Remove `conn` parameter - MCP handles connection internally

### Issue: Import errors
**Solution**: Update imports to use `mcp_client` instead of `client`

---

## 🎉 Benefits

✅ **Single Interface**: MCP is the only SQL access layer  
✅ **Better Performance**: Catalog caching, optimized queries  
✅ **Rate Limiting**: Automatic backoff with Retry-After  
✅ **Discovery Tools**: Search, describe, relations (no manual queries)  
✅ **Safety Controls**: SELECT-only, row limits, timeouts, PII redaction  
✅ **Future-Proof**: All new features will be MCP-only  

---

**Version**: 2.0 (Phase 7)  
**Last Updated**: January 2025  
**Maintained By**: Dynamic ERP Assistant Team