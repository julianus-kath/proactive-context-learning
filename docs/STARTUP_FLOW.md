# 🚀 Startup Script Flow Diagram

## Overview

The `start_all_services.sh` script is the universal "start button" that intelligently handles both proxy and local database modes.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  ./start_all_services.sh                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Pre-flight Checks                                       │
│     ✓ Python 3 installed?                                   │
│     ✓ Load .env file                                        │
│     ✓ Check DB_MODE (proxy or local)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    │   DB_MODE?    │
                    └───────┬───────┘
                            │
            ┌───────────────┴───────────────┐
            ↓                               ↓
┌───────────────────────┐       ┌───────────────────────┐
│   PROXY MODE          │       │   LOCAL MODE          │
└───────────────────────┘       └───────────────────────┘
            ↓                               ↓
┌───────────────────────┐       ┌───────────────────────┐
│ 2a. Proxy Checks      │       │ 2b. PostgreSQL Checks │
│                       │       │                       │
│ ✓ PROXY_BASE_URL set? │       │ ✓ PostgreSQL running? │
│ ✓ Parse host:port     │       │ ✓ Start if needed     │
│ ✓ Test connectivity   │       │ ✓ Database exists?    │
│   (nc or curl)        │       │ ✓ Create if needed    │
│ ✓ Call /health        │       │ ✓ Tables exist?       │
│ ✓ Check API key       │       │ ✓ Restore if needed   │
│ ✓ Show connections    │       │                       │
└───────────────────────┘       └───────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Install Dependencies                                    │
│     ✓ LangGraph integration requirements                    │
│     ✓ Chatbot UI requirements                               │
│     ✓ MCP Server requirements                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Environment Variables                                   │
│     ✓ Check OPENAI_API_KEY                                  │
│     ✓ Validate required config                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Cleanup Existing Processes                              │
│     ✓ Kill port 3000 (Web UI)                               │
│     ✓ Kill port 5001 (LangGraph)                            │
│     ✓ Kill port 8000 (MCP Server)                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  6. Start Services                                          │
│                                                             │
│     ┌─────────────────────────────────────────┐            │
│     │  MCP Server (Port 8000)                 │            │
│     │  - Database tools                       │            │
│     │  - Schema discovery                     │            │
│     │  - Safe query execution                 │            │
│     └─────────────────────────────────────────┘            │
│                      ↓                                      │
│     ┌─────────────────────────────────────────┐            │
│     │  LangGraph Service (Port 5001)          │            │
│     │  - AI agent backend                     │            │
│     │  - Query planning                       │            │
│     │  - Clarification handling               │            │
│     └─────────────────────────────────────────┘            │
│                      ↓                                      │
│     ┌─────────────────────────────────────────┐            │
│     │  Web UI (Port 3000)                     │            │
│     │  - Modern chatbot interface             │            │
│     │  - User interaction                     │            │
│     └─────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  7. Health Checks                                           │
│     ✓ Port 3000 listening?                                  │
│     ✓ Port 5001 listening?                                  │
│     ✓ Port 8000 listening?                                  │
│     ✓ LangGraph /health endpoint?                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  8. Display Status                                          │
│     ✅ Web UI: http://localhost:3000                        │
│     ✅ LangGraph: http://localhost:5001                     │
│     ✅ MCP Server: http://localhost:8000                    │
│     ✅ Database: [Proxy or Local PostgreSQL]                │
│                                                             │
│     📁 Logs: logs/*.log                                     │
│     ⚠️  Press Ctrl+C to stop all services                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  9. Monitor Services (Loop)                                 │
│     - Check every 10 seconds                                │
│     - Restart if service crashes                            │
│     - Exit on Ctrl+C                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Proxy Mode Details

```
┌─────────────────────────────────────────────────────────────┐
│                    PROXY MODE CHECKS                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Configuration Validation                           │
│  ✓ PROXY_BASE_URL set in .env?                              │
│  ✓ Parse host and port from URL                             │
│  ✓ PROXY_API_KEY set? (optional)                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Network Connectivity Test                          │
│                                                             │
│  Try 'nc' (netcat):                                         │
│    nc -z -w 5 192.168.1.35 5000                             │
│                                                             │
│  Fallback to 'curl':                                        │
│    curl --connect-timeout 5 http://192.168.1.35:5000/health │
│                                                             │
│  Result: ✅ Reachable or ❌ Not reachable                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Proxy Health Check                                 │
│                                                             │
│  Call: GET /health                                          │
│  Header: X-API-Key (if configured)                          │
│                                                             │
│  Expected Response:                                         │
│  {                                                          │
│    "ok": true,                                              │
│    "connections": [                                         │
│      {"name": "corp_sql_erp", "type": "sqlserver"}          │
│    ]                                                        │
│  }                                                          │
│                                                             │
│  Status Codes:                                              │
│    200 → ✅ Success                                         │
│    401 → ❌ Authentication failed                           │
│    Other → ⚠️  Warning, continue anyway                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Show Connection Info                               │
│  ✅ Found 1 database connection(s)                          │
│     - corp_sql_erp (sqlserver)                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Local Mode Details

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL MODE CHECKS                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: PostgreSQL Status                                  │
│  Command: pg_isready -h localhost -p 5432                   │
│                                                             │
│  If not running:                                            │
│    brew services start postgresql                           │
│    Wait 3 seconds                                           │
│    Verify again                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Database Existence                                 │
│  Command: psql -U juli -d synthetic_erp_data -c "SELECT 1;" │
│                                                             │
│  If not exists:                                             │
│    createdb -U juli synthetic_erp_data                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Table Existence                                    │
│  Command: psql -U juli -d synthetic_erp_data                │
│           -c "SELECT COUNT(*) FROM products;"               │
│                                                             │
│  If tables missing:                                         │
│    python3 restore_database.py                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Handling

### Proxy Mode Errors

| Error | Cause | Solution |
|-------|-------|----------|
| ❌ PROXY_BASE_URL not set | Missing config | Add to `.env` |
| ❌ Cannot connect to proxy | Network issue | Check Windows proxy running |
| ❌ Authentication failed | Wrong API key | Match keys on Windows/Mac |
| ❌ No connections found | Empty connections.yaml | Configure database on Windows |

### Local Mode Errors

| Error | Cause | Solution |
|-------|-------|----------|
| ❌ PostgreSQL not running | Service stopped | `brew services start postgresql` |
| ❌ Database doesn't exist | Not created | Script will create automatically |
| ❌ Tables missing | Not restored | Script will restore automatically |

---

## Service Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Architecture                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Web UI    │  Port 3000
│ (Streamlit) │
└──────┬──────┘
       │ HTTP
       ↓
┌─────────────┐
│  LangGraph  │  Port 5001
│   Service   │
└──────┬──────┘
       │ HTTP
       ↓
┌─────────────┐
│ MCP Server  │  Port 8000
└──────┬──────┘
       │
       ↓
┌──────┴──────┐
│ DB Client   │
└──────┬──────┘
       │
       ├─────────────┬─────────────┐
       ↓             ↓             ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Proxy Mode  │ │ Local Mode  │ │ Future...   │
│             │ │             │ │             │
│ Windows     │ │ PostgreSQL  │ │ Other DBs   │
│ Proxy       │ │ (Mac)       │ │             │
└─────────────┘ └─────────────┘ └─────────────┘
```

---

## Monitoring

The script continuously monitors services:

```bash
while true; do
    sleep 10
    
    # Check if Web UI is still running
    if ! check_port 3000; then
        echo "❌ Web UI stopped unexpectedly"
        break
    fi
    
    # Check if LangGraph is still running
    if ! check_port 5001; then
        echo "❌ LangGraph Service stopped unexpectedly"
        break
    fi
done
```

If any critical service stops, the script:
1. Logs the error
2. Stops all services
3. Exits gracefully

---

## Cleanup on Exit

When you press `Ctrl+C`:

```bash
cleanup() {
    echo "🛑 Shutting down services..."
    
    # Kill services on known ports
    kill_port 3000  # Web UI
    kill_port 5001  # LangGraph Service
    kill_port 8000  # MCP Server
    
    # Kill any remaining processes
    pkill -f "web_app.py"
    pkill -f "langgraph_service.py"
    pkill -f "uvicorn"
    
    echo "✅ All services stopped"
    exit 0
}
```

---

## Usage Examples

### Example 1: Start with Proxy Mode

```bash
# Configure .env
DB_MODE=proxy
PROXY_BASE_URL=http://192.168.1.35:5000
PROXY_API_KEY=my-secret-key
PROXY_DEFAULT_CONN=corp_sql_erp

# Start services
./start_all_services.sh

# Output:
# 🔍 Database Mode: proxy
# 🔍 Checking Windows proxy connection...
#    Testing connection to 192.168.1.35:5000...
# ✅ Proxy server is reachable
#    Testing proxy health endpoint...
# ✅ Proxy health check passed
#    Found 1 database connection(s)
# ✅ Proxy mode configured and ready
# ...
# 🎉 All services started successfully!
```

### Example 2: Start with Local Mode

```bash
# Configure .env
DB_MODE=local
DB_NAME=synthetic_erp_data
DB_USER=juli

# Start services
./start_all_services.sh

# Output:
# 🔍 Database Mode: local
# 🔍 Checking PostgreSQL...
# ✅ PostgreSQL is running
# 🔍 Checking database 'synthetic_erp_data'...
# ✅ Database exists
# 🔍 Checking database data...
# ✅ Tables exist
# ✅ Local database setup complete
# ...
# 🎉 All services started successfully!
```

---

## Architecture Compliance

This startup flow adheres to all ADR principles:

✅ **ADR-001**: Proxy-only separation (no business logic in proxy)  
✅ **ADR-002**: Database abstraction (DatabaseClient handles both modes)  
✅ **ADR-003**: Read-only queries (enforced by MCP tools)  
✅ **ADR-004**: JSON format (all APIs return JSON)  
✅ **ADR-005**: Security (API key authentication)  
✅ **ADR-006**: Modularity (clean service separation)  

---

## Next Steps

After successful startup:

1. **Access Web UI**: http://localhost:3000
2. **Test queries**: "Show me top 5 customers"
3. **Check API docs**: http://localhost:5001/docs
4. **Monitor logs**: `tail -f logs/*.log`
5. **Stop services**: Press `Ctrl+C`