# Architecture Diagram - Mac + Windows Deployment

## Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MAC MACHINE                                   │
│                         (No VPN Access)                                 │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                        WEB UI (Port 3000)                        │  │
│  │  - Streamlit chatbot interface                                  │  │
│  │  - User asks questions                                          │  │
│  │  - Displays responses                                           │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │                                        │
│                               │ HTTP POST /chat                        │
│                               ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   LANGGRAPH SERVICE (Port 5001)                  │  │
│  │  - Intent mapping                                               │  │
│  │  - Query planning                                               │  │
│  │  - Clarification handling                                       │  │
│  │  - Response generation                                          │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │                                        │
│                               │ MCP JSON-RPC over HTTP                 │
│                               │ (Schema discovery, query execution)    │
└───────────────────────────────┼────────────────────────────────────────┘
                                │
                                │ Network: http://10.255.152.48:8000
                                │ Auth: X-API-Key header
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        WINDOWS MACHINE                                  │
│                      (VPN Access to SQL Server)                         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    MCP SERVER (Port 8000)                        │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────┐    │  │
│  │  │  MCP Tools (JSON-RPC)                                  │    │  │
│  │  │  ────────────────────────                              │    │  │
│  │  │  • list_databases()      - Discover available DBs      │    │  │
│  │  │  • list_tables()         - Get tables in database      │    │  │
│  │  │  • describe_table()      - Get table schema            │    │  │
│  │  │  • execute_query()       - Run safe SELECT queries     │    │  │
│  │  │  • search_schema()       - Find tables by keyword      │    │  │
│  │  └────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────┐    │  │
│  │  │  Safety & Performance Layer                            │    │  │
│  │  │  ──────────────────────────                            │    │  │
│  │  │  • Read-only enforcement (SELECT only)                 │    │  │
│  │  │  • Query timeout (30s)                                 │    │  │
│  │  │  • Row limit (1000 max)                                │    │  │
│  │  │  • SQL injection prevention                            │    │  │
│  │  │  • Rate limiting                                       │    │  │
│  │  └────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────┐    │  │
│  │  │  Schema Catalog (Phase 3)                              │    │  │
│  │  │  ────────────────────────                              │    │  │
│  │  │  • Schema caching (1 hour TTL)                         │    │  │
│  │  │  • Disk persistence                                    │    │  │
│  │  │  • Automatic warmup                                    │    │  │
│  │  │  • Metrics tracking                                    │    │  │
│  │  └────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  │  ┌────────────────────────────────────────────────────────┐    │  │
│  │  │  Database Adapter                                      │    │  │
│  │  │  ────────────────                                      │    │  │
│  │  │  • Connection pooling (1-10 connections)               │    │  │
│  │  │  • Automatic reconnection                              │    │  │
│  │  │  • Health monitoring                                   │    │  │
│  │  └────────────────────────────────────────────────────────┘    │  │
│  │                                                                  │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │                                        │
│                               │ pyodbc (ODBC Driver 17)                │
│                               │ Direct SQL connection                  │
│                               ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              SQL SERVER DATABASE (Production ERP)                │  │
│  │              192.168.200.16:1433                                 │  │
│  │                                                                  │  │
│  │  • Hundreds of tables (customers, orders, products, etc.)       │  │
│  │  • Production data                                              │  │
│  │  • Accessible only via VPN                                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: User Question → Database → Response

```
1. USER ASKS QUESTION
   ↓
   "What were our top selling products last month?"
   ↓
   
2. WEB UI (Mac:3000)
   ↓
   POST /chat → LangGraph Service
   ↓
   
3. LANGGRAPH (Mac:5001)
   ↓
   • Intent: "sales_analysis"
   • Needs: product sales data
   ↓
   MCP Tool Call: list_tables(database="master")
   ↓
   
4. MCP SERVER (Windows:8000)
   ↓
   • Receives JSON-RPC request
   • Checks schema catalog (cache hit!)
   • Returns: ["products", "orders", "order_items", ...]
   ↓
   
5. LANGGRAPH (Mac:5001)
   ↓
   • Plans query
   • Needs: orders + order_items + products
   ↓
   MCP Tool Call: execute_query(sql="SELECT p.name, SUM(oi.quantity) ...")
   ↓
   
6. MCP SERVER (Windows:8000)
   ↓
   • Validates query (read-only, safe)
   • Applies row limit (1000)
   • Sets timeout (30s)
   ↓
   
7. SQL SERVER (Windows VPN:1433)
   ↓
   • Executes query
   • Returns results
   ↓
   
8. MCP SERVER (Windows:8000)
   ↓
   • Formats results as JSON
   • Returns to LangGraph
   ↓
   
9. LANGGRAPH (Mac:5001)
   ↓
   • Analyzes results
   • Generates natural language response
   ↓
   
10. WEB UI (Mac:3000)
    ↓
    Displays: "Last month's top products were:
               1. Widget A (1,234 units)
               2. Gadget B (987 units)
               3. Doohickey C (765 units)"
```

---

## Network Communication

### Mac → Windows (MCP JSON-RPC)

```http
POST http://10.255.152.48:8000/tools/execute_query
Headers:
  X-API-Key: supersecretapikey
  Content-Type: application/json

Body:
{
  "sql": "SELECT TOP 10 * FROM products",
  "limit": 100,
  "timeout": 30
}

Response:
{
  "ok": true,
  "columns": ["id", "name", "price"],
  "rows": [
    [1, "Widget A", 19.99],
    [2, "Gadget B", 29.99]
  ],
  "row_count": 2,
  "execution_time_ms": 45
}
```

---

## Component Responsibilities

### Mac Machine

| Component | Port | Responsibility |
|-----------|------|----------------|
| Web UI | 3000 | User interface, chat display |
| LangGraph | 5001 | Intent mapping, query planning, orchestration |

**Does NOT:**
- ❌ Connect to SQL Server directly
- ❌ Run MCP server
- ❌ Need VPN access
- ❌ Store database credentials

### Windows Machine

| Component | Port | Responsibility |
|-----------|------|----------------|
| MCP Server | 8000 | Database access layer, safety controls |
| SQL Server | 1433 | Production ERP database |

**Does NOT:**
- ❌ Run Web UI
- ❌ Run LangGraph
- ❌ Handle user interactions
- ❌ Generate responses

---

## Security Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Network Security                             │
│  • VPN required for SQL Server access                  │
│  • Firewall on Windows (port 8000 only)                │
│  • Private network only                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: API Authentication                           │
│  • MCP_API_KEY required (X-API-Key header)             │
│  • Key must match on both machines                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Query Safety                                 │
│  • Read-only (SELECT only)                             │
│  • SQL injection prevention                            │
│  • Parameterized queries                               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Resource Limits                              │
│  • Query timeout (30s)                                 │
│  • Row limit (1000 max)                                │
│  • Connection pooling (max 10)                         │
│  • Rate limiting                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Development vs Production

### Development (Local Mac)

```
Mac Machine:
├── Web UI (3000)
├── LangGraph (5001)
├── MCP Server (8000) ← Runs locally
└── PostgreSQL (5432) ← Local test database
```

**Configuration:**
```bash
# .env on Mac
DB_DIALECT=postgres
POSTGRES_HOST=localhost
MCP_SERVER_URL=http://localhost:8000
```

### Production (Mac + Windows)

```
Mac Machine:                Windows Machine:
├── Web UI (3000)          ├── MCP Server (8000)
└── LangGraph (5001) ────► └── SQL Server (1433)
```

**Configuration:**
```bash
# .env on Mac
MCP_SERVER_URL=http://10.255.152.48:8000

# .env on Windows
DB_DIALECT=mssql
MSSQL_SERVER=192.168.200.16
```

---

## Why This Architecture?

### ✅ Advantages

1. **VPN Isolation**
   - Only Windows needs VPN access
   - Mac can be on any network

2. **Separation of Concerns**
   - Mac: UI/orchestration (stateless)
   - Windows: Data access (stateful)

3. **Security**
   - Database credentials only on Windows
   - Multiple security layers
   - Read-only enforcement

4. **Scalability**
   - Can add more Mac clients
   - Can add more Windows MCP servers
   - Load balancing possible

5. **Testability**
   - Can run locally with PostgreSQL
   - No VPN needed for development

### ❌ Trade-offs

1. **Network Dependency**
   - Mac needs network access to Windows
   - Latency added (minimal for LAN)

2. **Two Machines Required**
   - Can't run production on Mac alone
   - Need to manage two environments

3. **Firewall Configuration**
   - Windows firewall must allow port 8000
   - Network must allow Mac → Windows traffic

---

## Comparison to Old Proxy Architecture

### Old (Deprecated)

```
Mac → Windows Proxy → SQL Server
      (Simple /query endpoint)
      ❌ No rate limiting
      ❌ No schema caching
      ❌ No safety controls
      ❌ No connection pooling
```

### New (Current)

```
Mac → Windows MCP Server → SQL Server
      (Intelligent database layer)
      ✅ Rate limiting
      ✅ Schema caching
      ✅ Safety controls
      ✅ Connection pooling
      ✅ Metrics & monitoring
```

---

**This architecture provides a clean, secure, and scalable foundation for the ERP chatbot system!**