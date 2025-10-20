# Proxy Connection Issue - Solution Guide

## 🔍 Problem Summary

When you tried to chat with the system, you got this error:
```
It seems there was a connection issue with the database session. Please check your network connection and ensure the database server is running.
```

## 🐛 Root Cause

The issue is that your `.env` file has `DB_MODE=proxy`, but the Windows proxy's `/query` endpoint has been **deprecated** and returns `410 Gone`. 

Looking at `/vpn_config/proxy.py` line 509-530:
```python
@app.route("/query", methods=["POST"])
def query():
    """
    DEPRECATED: This endpoint has been replaced by MCP JSON-RPC.
    
    Phase 7: Decommission Old Proxy (Cleanup)
    - This endpoint returns 410 Gone to indicate permanent deprecation
    - All database access should go through MCP server (port 8000)
    """
    return jsonify({
        "ok": False,
        "error": "This endpoint is permanently deprecated. Please use MCP JSON-RPC instead.",
        "code": "ENDPOINT_DEPRECATED",
        "status": 410
    })
```

This means:
1. The MCP server tried to connect in proxy mode
2. It called the proxy's `/query` endpoint
3. The proxy returned 410 Gone (deprecated)
4. The query failed

## ✅ Solution: Use Local PostgreSQL Mode

Since the proxy is deprecated, you should use **local PostgreSQL mode** for testing.

### Step 1: Update `.env` File

Change these lines in your `.env` file:

**FROM:**
```bash
# Database Proxy Configuration (for ERP access)
DB_MODE=proxy
PROXY_BASE_URL=http://10.255.152.48:5000
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_API_KEY=dummy-key-for-testing
```

**TO:**
```bash
# -------------------------------
# Database Configuration
# -------------------------------
# Mode: local (PostgreSQL) or proxy (Windows proxy - currently deprecated)
DB_MODE=local

# Local PostgreSQL Configuration (used when DB_MODE=local)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=juli
DB_PASSWORD=

# PostgreSQL Configuration (for MCP server direct connection)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=synthetic_erp_data
POSTGRES_USER=juli
POSTGRES_PASSWORD=

# Database Proxy Configuration (DEPRECATED - commented out)
# PROXY_BASE_URL=http://10.255.152.48:5000
# PROXY_DEFAULT_CONN=corp_sql_erp
# PROXY_API_KEY=dummy-key-for-testing
```

### Step 2: Ensure PostgreSQL is Running

```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# If not running, start it
brew services start postgresql@14

# Verify the database exists
psql -U juli -d synthetic_erp_data -c "SELECT 1;"
```

### Step 3: Restart the Services

```bash
# Stop all services
pkill -f "web_app.py"
pkill -f "langgraph_service.py"
pkill -f "uvicorn"

# Start all services again
./start_all_services.sh
```

### Step 4: Test the System

1. Open http://localhost:3000
2. Try asking: "Show me all products"
3. The system should now work with local PostgreSQL

## 🔄 Alternative: Fix the Proxy (Advanced)

If you really need to use the Windows proxy for production SQL Server access, you have two options:

### Option A: Revert the Proxy Deprecation

Edit `/vpn_config/proxy.py` and restore the `/query` endpoint functionality (remove the 410 Gone response).

### Option B: Use Direct SQL Server Connection

Instead of using the proxy, configure the MCP server to connect directly to SQL Server:

```bash
# In .env
DB_DIALECT=mssql
MSSQL_SERVER=192.168.200.16
MSSQL_PORT=1433
MSSQL_DATABASE=master
MSSQL_USER=SimonM
MSSQL_PASSWORD=your_password
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

**Note:** This requires the Mac to have network access to the SQL Server (VPN or direct connection).

## 📊 Architecture Clarification

The current architecture should be:

```
┌─────────────────────────────────────────────────────────────┐
│  Web UI (Port 3000)                                         │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Service (Port 5001)                              │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (Port 8000)                                     │
│  - Uses DatabaseAdapter                                     │
│  - Supports: local PostgreSQL, direct MSSQL, or proxy       │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Local PostgreSQL│    │  Direct MSSQL    │
│  (DB_MODE=local) │    │  (DB_DIALECT=    │
│                  │    │   mssql)         │
└──────────────────┘    └──────────────────┘
```

The Windows proxy is **no longer in the data path** after Phase 7 migration.

## 🎯 Recommended Action

**For immediate testing:** Use `DB_MODE=local` with PostgreSQL.

**For production:** Configure direct MSSQL connection with `DB_DIALECT=mssql`.

## 📝 Files Modified

I've created the following files to support proxy mode (in case you need it later):
- `/mcp_server/db_proxy.py` - Proxy connector for MCP server
- `/mcp_server/database_adapter.py` - Updated to support proxy mode
- `/test_proxy_mcp.py` - Test script for proxy connection

However, these won't work until the proxy's `/query` endpoint is restored or you use direct database connections.