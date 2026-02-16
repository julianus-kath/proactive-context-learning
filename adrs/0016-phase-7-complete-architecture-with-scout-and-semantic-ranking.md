# ADR-0016: Phase 7+ Complete Architecture with Scout Mode and Semantic Ranking

**Status**: Accepted
**Date**: 2025-10-20
**Author**: Julianus Kath
**Context**: Phase 7 & 7.1 - Answer-First with Scout Mode and Semantic Table Ranking
**Supersedes**: ADR-0010 (Partial), ADR-0012 (Complementary)

## Context

Phase 7 introduced the "answer-first" architecture, where the system generates and executes SQL queries autonomously before performing full schema discovery. Phase 7.1 further enhanced this with Scout Mode (semantic caching) and Semantic Table Ranking, enabling sub-second query execution.

This ADR documents the complete end-to-end architecture integrating all recent enhancements.

---

## 1. High-Level System Architecture (Phase 7+)

```mermaid
graph TB
    subgraph "User Layer"
        UI["🌐 Modern Web UI<br/>HTML/CSS/JS<br/>Port 3000"]
    end
    
    subgraph "API & Orchestration"
        WEBAPI["📡 FastAPI Server<br/>WebSocket Streaming<br/>Session Management"]
        LG["🔄 LangGraph Service<br/>Workflow Orchestration<br/>Port 5001"]
    end
    
    subgraph "Scout Mode System"
        SCOUT["🔍 Scout Mode Cache<br/>Async Startup Discovery<br/>Semantic Metadata"]
        CACHE["💾 Scout Catalog<br/>JSON File-based Cache<br/>7-day TTL"]
    end
    
    subgraph "Answer-First Pipeline"
        INTENT["📝 Intent Parser<br/>Extract entities & operations"]
        RANKER["🎯 Semantic Table Ranker<br/>Multi-dimensional scoring<br/>Cache-based ranking"]
        BLUEPRINT["📋 Query Blueprint<br/>SQL template generation"]
        EXECUTOR["⚡ Query Executor<br/>Safe SQL execution<br/>Result formatting"]
    end
    
    subgraph "Network & Data Access"
        MCP["🔌 MCP Client<br/>JSON-RPC Builder<br/>API Key Auth"]
    end
    
    subgraph "Database Layer (Windows Machine)"
        MCP_WIN["🔌 MCP Server<br/>Port 8000<br/>JSON-RPC Handler<br/>Query Executor"]
        PRODDB["🗄️ SQL Server / PostgreSQL<br/>ERP Database<br/>Read-only Access"]
    end
    
    UI -->|HTTP/WebSocket| WEBAPI
    WEBAPI --> LG
    LG --> SCOUT
    SCOUT --> CACHE
    CACHE --> RANKER
    LG --> INTENT
    INTENT --> RANKER
    RANKER --> BLUEPRINT
    BLUEPRINT --> EXECUTOR
    EXECUTOR -->|JSON-RPC<br/>API Key Auth| MCP
    MCP -->|"HTTPS<br/>Port 8000"| MCP_WIN
    MCP_WIN -->|"search_tables<br/>describe_table<br/>execute_query"| PRODDB
    
    style UI fill:#e3f2fd,stroke:#1976d2
    style WEBAPI fill:#f3e5f5,stroke:#7b1fa2
    style LG fill:#fff3e0,stroke:#f57c00
    style SCOUT fill:#e0f2f1,stroke:#00796b
    style CACHE fill:#e0f2f1,stroke:#00796b
    style INTENT fill:#fce4ec,stroke:#c2185b
    style RANKER fill:#f1f8e9,stroke:#558b2f
    style BLUEPRINT fill:#fff9c4,stroke:#f9a825
    style EXECUTOR fill:#ffe0b2,stroke:#e65100
    style MCP fill:#e8f5e9,stroke:#2e7d32
    style MCP_WIN fill:#81c784,stroke:#2e7d32,stroke-width:3px
    style PRODDB fill:#ffcdd2,stroke:#b71c1c
```

---

## 2. Scout Mode Architecture & Lifecycle

```mermaid
graph TB
    subgraph "Startup Phase"
        INIT["Server Initialization<br/>langgraph_service.py"]
        SCOUT_RUN["Scout Mode Execution<br/>Async (non-blocking)"]
        DISCOVERY["Schema Discovery<br/>Query information_schema<br/>Extract metadata"]
        SEMANTIC["Semantic Analysis<br/>Type classification<br/>FK counting<br/>Normalization"]
        SERIALIZE["Cache Serialization<br/>Write to cache/scout_catalog.json<br/>Set TTL to +7 days"]
        READY["✅ Service Ready<br/>Cache loaded in memory"]
    end
    
    subgraph "Runtime Phase"
        REQ["📝 User Query Arrives"]
        CHECK["Check Cache TTL<br/>Still valid?"]
        LOAD["⚡ Load Cache<br/>O(1) operation<br/>~50ms"]
        SERVE["Return Metadata<br/>To table ranker"]
        EXPIRED["Cache Expired<br/>Refresh Scout"]
    end
    
    subgraph "Cache Contents"
        CATALOG["Scout Catalog<br/>json"]
        ENTRY["Table Entry:<br/>- name<br/>- schema<br/>- columns (count)<br/>- numeric_columns[]<br/>- date_columns[]<br/>- text_columns[]<br/>- fk_count<br/>- estimated_rows"]
    end
    
    INIT --> SCOUT_RUN
    SCOUT_RUN --> DISCOVERY
    DISCOVERY --> SEMANTIC
    SEMANTIC --> SERIALIZE
    SERIALIZE --> READY
    
    REQ --> CHECK
    CHECK -->|Valid| LOAD
    CHECK -->|Expired| EXPIRED
    EXPIRED --> DISCOVERY
    LOAD --> SERVE
    SERVE --> CATALOG
    CATALOG --> ENTRY
    
    style INIT fill:#fff3e0,stroke:#f57c00
    style SCOUT_RUN fill:#e0f2f1,stroke:#00796b
    style DISCOVERY fill:#e0f2f1,stroke:#00796b
    style SEMANTIC fill:#e0f2f1,stroke:#00796b
    style SERIALIZE fill:#e0f2f1,stroke:#00796b
    style READY fill:#c8e6c9,stroke:#2e7d32
    style REQ fill:#fce4ec,stroke:#c2185b
    style CHECK fill:#fff9c4,stroke:#f9a825
    style LOAD fill:#f1f8e9,stroke:#558b2f
    style SERVE fill:#ffe0b2,stroke:#e65100
    style EXPIRED fill:#ffccbc,stroke:#d84315
    style CATALOG fill:#e0f2f1,stroke:#00796b
    style ENTRY fill:#e0f2f1,stroke:#00796b
```

### Scout Mode Performance Impact

```
Timeline Comparison:

Without Scout Mode (Phase 6):
  Schema Discovery: 10-50 seconds
  Full Query Pipeline: 15-70 seconds
  Problem: Discovery is bottleneck

With Scout Mode (Phase 7.1):
  Cache Load: 50ms (disk)
  Table Ranking: 50-100ms (memory)
  Full Query Pipeline: <500ms total
  Improvement: 30-140x faster
```

---

## 3. Answer-First Pipeline with Semantic Ranking

```mermaid
graph LR
    subgraph "1. Intent & Entity Extraction"
        Q["🗣️ User Query<br/>Natural Language"]
        PARSE["📝 Intent Parser<br/>LLM: Extract intent<br/>Extract entities<br/>Detect operations"]
        STATE1["📊 State:<br/>intent<br/>entities<br/>operations<br/>confidence"]
    end
    
    subgraph "2. Semantic Table Ranking"
        LOAD_CACHE["⚡ Load Scout Cache<br/>O(1) disk read"]
        SCORE["🎯 Score All Tables<br/>Entity matching<br/>Type compatibility<br/>Fuzzy matching<br/>FK connectivity<br/>Table size"]
        RANK["📈 Rank & Select<br/>Top-3 tables<br/>Confidence scores"]
        STATE2["📊 Selected Tables<br/>table_name<br/>score<br/>reasoning[]"]
    end
    
    subgraph "3. Query Blueprint"
        TEMPLATE["📋 Generate Blueprint<br/>Template SQL<br/>JOIN structure<br/>Aggregations"]
        STATE3["📊 Blueprint:<br/>sql<br/>tables<br/>confidence"]
    end
    
    subgraph "4. Safe Execution"
        EXEC["⚡ Execute Query<br/>MCP Server validates<br/>Row limit enforced<br/>Timeout applied"]
        STATE4["📊 Results:<br/>rows[]\br/>row_count<br/>duration_ms"]
    end
    
    subgraph "5. Response Formatting"
        FORMAT["✨ Format Response<br/>LLM: Natural language<br/>Context awareness<br/>Error recovery"]
        FINAL["🎯 Final Response<br/>Natural text<br/>Metadata<br/>Confidence"]
    end
    
    Q --> PARSE
    PARSE --> STATE1
    STATE1 --> LOAD_CACHE
    LOAD_CACHE --> SCORE
    SCORE --> RANK
    RANK --> STATE2
    STATE2 --> TEMPLATE
    TEMPLATE --> STATE3
    STATE3 --> EXEC
    EXEC --> STATE4
    STATE4 --> FORMAT
    FORMAT --> FINAL
    
    style Q fill:#fce4ec,stroke:#c2185b
    style PARSE fill:#f1f8e9,stroke:#558b2f
    style STATE1 fill:#fff9c4,stroke:#f9a825
    style LOAD_CACHE fill:#e0f2f1,stroke:#00796b
    style SCORE fill:#f1f8e9,stroke:#558b2f
    style RANK fill:#f1f8e9,stroke:#558b2f
    style STATE2 fill:#fff9c4,stroke:#f9a825
    style TEMPLATE fill:#fff9c4,stroke:#f9a825
    style STATE3 fill:#fff9c4,stroke:#f9a825
    style EXEC fill:#ffe0b2,stroke:#e65100
    style STATE4 fill:#fff9c4,stroke:#f9a825
    style FORMAT fill:#c8e6c9,stroke:#2e7d32
    style FINAL fill:#c8e6c9,stroke:#2e7d32
```

### Semantic Ranking Formula

```
Score(table) = 
    Entity_Match(0-1.0)      [weight: 1.0]
  + Type_Compatibility(0-0.5) [weight: 0.3-0.5]
  + Fuzzy_Match(0-0.4)       [weight: 0.4]
  + FK_Connectivity(0-0.1)   [weight: 0.1]
  + Table_Size(0-0.05)       [weight: 0.05]
  
Maximum: 3.05 → capped at 1.0 (normalized confidence score)

Example:
  Query: "Show top 10 customers by orders"
  Entities: ["customers", "orders"]
  
  Table: dbo.Customers
    - Entity match: 1.0 (exact)
    - Type compatibility: 0.0 (no numeric needed)
    - Fuzzy: 0.0
    - FK bonus: 0.05 (5 FKs)
    - Size: 0.05 (150k rows)
    = Score: 1.10 → capped 1.0 ✓
  
  Table: dbo.Orders
    - Entity match: 1.0 (exact)
    - Type compatibility: 0.1 (numeric found)
    - Fuzzy: 0.0
    - FK bonus: 0.06 (3 FKs)
    - Size: 0.05 (500k rows)
    = Score: 1.21 → capped 1.0 ✓
  
  Result: Both selected (score >= 0.8)
```

---

## 4. MCP-Only Data Access Architecture

```mermaid
graph TB
    subgraph "MacBook (Orchestration Layer)"
        WF["🔄 DatabaseWorkflow<br/>LangGraph Graph"]
        STATE["📊 Workflow State<br/>All decisions tracked"]
    end
    
    subgraph "MacBook (MCP Client)"
        CLIENT["🔌 MCPClient<br/>app/db/mcp_client.py<br/>Unified Interface"]
        METHODS["📋 Public Methods:<br/>• search_tables(pattern)<br/>• describe_table(name)<br/>• execute_query(sql)"]
        CALL["🔗 _call_tool()<br/>JSON-RPC 2.0<br/>HTTPS POST<br/>X-API-Key header<br/>Error handling<br/>Retry logic"]
    end
    
    subgraph "Windows Machine (MCP Server)"
        SERVER["🖥️ FastAPI Server<br/>mcp_server/server.py<br/>Port 8000"]
        TOOLS["🛠️ Tool Handlers<br/>search_tables()<br/>describe_table()<br/>execute_query()"]
        GUARD["🛡️ Guardrails<br/>SELECT-only check<br/>Rate limiting<br/>Pagination<br/>Timeouts"]
    end
    
    subgraph "Database Layer (Windows)"
        DB["🗄️ Database Manager<br/>Connection pooling<br/>asyncpg (PostgreSQL)<br/>pyodbc (SQL Server)"]
        SCHEMA["📋 information_schema<br/>Dynamic discovery"]
    end
    
    WF --> STATE
    STATE --> CLIENT
    CLIENT --> METHODS
    CLIENT --> CALL
    CALL -->|"JSON-RPC 2.0<br/>HTTPS<br/>Port 8000"| SERVER
    SERVER --> TOOLS
    TOOLS --> GUARD
    GUARD --> DB
    DB --> SCHEMA
    
    style WF fill:#fff3e0,stroke:#f57c00
    style STATE fill:#fff9c4,stroke:#f9a825
    style CLIENT fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style METHODS fill:#e8f5e9,stroke:#2e7d32
    style CALL fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style SERVER fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style TOOLS fill:#81c784,stroke:#2e7d32
    style GUARD fill:#ffccbc,stroke:#d84315
    style DB fill:#f8bbd0,stroke:#c2185b
    style SCHEMA fill:#f8bbd0,stroke:#c2185b
```

### MCP Request/Response Example

```json
// Client Request (MCPClient._call_tool)
{
  "jsonrpc": "2.0",
  "id": "req-12345",
  "method": "search_tables",
  "params": {
    "pattern": "invoice"
  }
}

// Server Response (Tools Handler)
{
  "jsonrpc": "2.0",
  "id": "req-12345",
  "result": {
    "ok": true,
    "tables": [
      {"name": "dbo.InvoiceHeader", "row_count": 15000},
      {"name": "dbo.InvoiceLines", "row_count": 250000}
    ],
    "duration_ms": 45.2
  }
}

// Error Response
{
  "jsonrpc": "2.0",
  "id": "req-12345",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "error": "Query timeout (>30s)",
      "suggestion": "Refine search pattern"
    }
  }
}
```

---

## 5. Complete Query Execution Flow

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant WebUI as 🌐 Web UI
    participant LG as 🔄 LangGraph<br/>(MacBook)
    participant MCP_Client as 🔌 MCP Client
    participant MCP_Server as 🔌 MCP Server<br/>(Windows:8000)
    participant DB as 🗄️ Database
    
    User->>WebUI: "Show recent invoices"
    WebUI->>LG: HTTP: /chat
    
    Note over LG: 1. Parse Intent
    LG->>LG: Extract: entity="invoices"<br/>intent=QUERY
    
    Note over LG: 2. Load Scout Cache
    LG->>LG: Cache hit (~50ms)<br/>Found 943 tables
    
    Note over LG: 3. Rank Tables
    LG->>LG: Score: dbo.InvoiceHeader=1.0<br/>dbo.InvoiceLines=0.95
    
    Note over LG: 4. Generate Blueprint
    LG->>LG: Generate SQL template
    
    Note over LG: 5. Describe Tables
    LG->>MCP_Client: MCPClient.describe_table()
    MCP_Client->>MCP_Server: JSON-RPC: describe_table<br/>+ API Key header
    MCP_Server->>DB: SELECT FROM information_schema
    DB-->>MCP_Server: Schema columns
    MCP_Server-->>MCP_Client: { ok: true, columns: [...] }
    MCP_Client-->>LG: Result
    
    Note over LG: 6. Generate Final SQL
    LG->>LG: GPT-4: Convert to concrete SQL<br/>SELECT TOP 10 FROM dbo.InvoiceHeader
    
    Note over LG: 7. Execute Query
    LG->>MCP_Client: MCPClient.execute_query(sql)
    MCP_Client->>MCP_Server: JSON-RPC: execute_query<br/>+ API Key header
    MCP_Server->>MCP_Server: Validate: SELECT only ✓
    MCP_Server->>MCP_Server: Apply: Row limit ✓
    MCP_Server->>DB: Execute query
    DB-->>MCP_Server: Results (150 rows)
    MCP_Server->>MCP_Server: Paginate: Top 10 rows
    MCP_Server-->>MCP_Client: { ok: true, rows: [...] }
    MCP_Client-->>LG: Result
    
    Note over LG: 8. Format Response
    LG->>LG: GPT-4: Natural language<br/>response
    
    LG-->>WebUI: Response + Metadata
    WebUI-->>User: "Here are the 10 most<br/>recent invoices..."
    
    rect rgb(200, 255, 200)
    Note over LG,DB: Total Time: <500ms
    Note over LG,DB: Scout Cache: 50ms
    Note over LG,DB: Table Scoring: 50ms
    Note over LG,DB: Query Execution: 150ms
    Note over LG,DB: Response Format: 100ms
    end
```

---

## 6. Windows MCP Server Architecture

```mermaid
graph TB
    subgraph "MacBook (Orchestration)"
        LG["🔄 LangGraph Service<br/>Port 5001"]
        MCHP["🔌 MCP Client<br/>JSON-RPC Builder"]
    end
    
    subgraph "Network Communication"
        HTTPS["🔒 HTTPS/TLS<br/>Port 8000<br/>API Key Auth<br/>Encrypted"]
    end
    
    subgraph "Windows Machine"
        SERVER["🪟 MCP Server<br/>FastAPI<br/>Port 8000<br/>JSON-RPC Handler"]
        AUTH["🔐 Authentication<br/>X-API-Key validation<br/>Request logging<br/>Rate limiting"]
        GUARD["🛡️ Query Guards<br/>SELECT-only enforcement<br/>Row/time limits<br/>Parameterization<br/>SQL injection prevention"]
    end
    
    subgraph "Database Layer"
        DB["📦 SQL Server / PostgreSQL<br/>ERP Database<br/>Port 1433 / 5432"]
    end
    
    LG -->|"MCPClient calls<br/>search_tables()<br/>describe_table()<br/>execute_query()"| MCHP
    
    MCHP -->|"JSON-RPC 2.0<br/>POST /chat<br/>X-API-Key header"| HTTPS
    
    HTTPS --> AUTH
    AUTH --> SERVER
    SERVER --> GUARD
    
    GUARD -->|"Validated<br/>SELECT sql"| DB
    
    DB -->|"Results<br/>JSON"| GUARD
    
    GUARD --> SERVER
    SERVER -->|"Response<br/>JSON"| HTTPS
    HTTPS -->|"Result<br/>Streaming"| MCHP
    MCHP -->|"Return to<br/>LangGraph state"| LG
    
    style LG fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style MCHP fill:#e8f5e9,stroke:#2e7d32
    style HTTPS fill:#ffccbc,stroke:#d84315,stroke-width:3px
    style SERVER fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style AUTH fill:#ffccbc,stroke:#d84315
    style GUARD fill:#ffccbc,stroke:#d84315
    style DB fill:#ffcdd2,stroke:#b71c1c
```

### MCP Server Request Handling

```
Request arrives at Windows MCP Server (Port 8000):
  ├─ Step 1: HTTPS/TLS
  │   ├─ TLS 1.3 required
  │   ├─ Certificate validation
  │   └─ Encrypted channel established
  │
  ├─ Step 2: Authentication
  │   ├─ Extract header: X-API-Key
  │   ├─ Validate against environment variable
  │   ├─ Log access: IP, timestamp, user, action
  │   └─ Reject (401) if invalid
  │
  ├─ Step 3: Parse Request
  │   ├─ Expect: JSON-RPC 2.0 POST
  │   ├─ Extract: method (search_tables, describe_table, execute_query)
  │   ├─ Extract: params (table name, SQL, pattern)
  │   └─ Validate format or return (400)
  │
  ├─ Step 4: Security Guards
  │   ├─ Guard 1: SELECT-only (reject INSERT/UPDATE/DELETE)
  │   ├─ Guard 2: No dangerous keywords (DROP, TRUNCATE, EXEC)
  │   ├─ Guard 3: Parameterized queries (prevent SQL injection)
  │   └─ Guard 4: Row limit (MAX 10000 rows)
  │
  ├─ Step 5: Rate Limiting (per API Key)
  │   ├─ Check: Requests per minute (limit: 60)
  │   ├─ Check: Concurrent queries (limit: 5)
  │   └─ Return (429) if exceeded
  │
  ├─ Step 6: Execute
  │   ├─ Set timeout: 30 seconds
  │   ├─ Connection pooling via asyncpg/pyodbc
  │   ├─ Execute on target database
  │   └─ Stream results as JSON
  │
  └─ Step 7: Response
      ├─ Format: { ok: true, data: [...], duration_ms: X }
      ├─ Or: { ok: false, error: "...", code: "..." }
      ├─ Redact sensitive columns (passwords, tokens, SSN)
      └─ Send back over HTTPS
```

---

### Deprecated: Windows Proxy Mode (Optional)

> **Status**: Deprecated but available as optional fallback
> 
> The legacy proxy.py (Python Flask on Port 5000) is no longer the primary connection method. However, it remains available as an optional fallback if direct MCP communication is unavailable. To enable proxy mode, update the environment variable `MCP_SERVER_URL` to point to the proxy endpoint instead of the MCP server.
> 
> **Why deprecated**: MCP server is more efficient (single architecture), has built-in JSON-RPC support, and eliminates the dual-code-path maintenance burden.

---

## 7. Component Responsibilities

```mermaid
graph TB
    subgraph "Presentation Layer"
        UI["🌐 Web UI<br/>Responsibilities:<br/>• Real-time streaming<br/>• Chat rendering<br/>• Session management<br/>Files: index.html, styles.css, script.js"]
    end
    
    subgraph "API Layer"
        API["📡 FastAPI Web Server<br/>Responsibilities:<br/>• HTTP endpoints<br/>• WebSocket streaming<br/>• CORS headers<br/>• Auth middleware<br/>Files: chatbot_ui/web_app.py"]
    end
    
    subgraph "Orchestration Layer"
        LG["🔄 LangGraph Service<br/>Responsibilities:<br/>• Workflow state machine<br/>• Component sequencing<br/>• Error recovery<br/>• Observability hooks<br/>Files: langgraph_service.py<br/>graph_definition.py"]
    end
    
    subgraph "Processing Layer"
        SCOUT["🔍 Scout Mode<br/>Responsibilities:<br/>• Async discovery<br/>• Metadata caching<br/>• TTL management<br/>Files: langgraph_integration/<br/>scout_mode.py"]
        
        PARSER["📝 Intent Parser<br/>Responsibilities:<br/>• Extract entities<br/>• Classify intent<br/>• Compute confidence<br/>Files: langgraph_integration/<br/>intent_parser.py"]
        
        RANKER["🎯 Table Ranker<br/>Responsibilities:<br/>• Load Scout cache<br/>• Multi-dim scoring<br/>• Rank tables<br/>Files: langgraph_integration/<br/>semantic_ranker.py"]
        
        BLUEPRINT["📋 Blueprint Gen<br/>Responsibilities:<br/>• Template SQL<br/>• JOIN structure<br/>Files: langgraph_integration/<br/>query_blueprint.py"]
    end
    
    subgraph "Data Access Layer"
        MCP["🔌 MCP Server<br/>Responsibilities:<br/>• JSON-RPC handler<br/>• Schema discovery<br/>• Query execution<br/>• Safety guards<br/>• Rate limiting<br/>Files: mcp_server/<br/>server.py, tools.py, db.py"]
    end
    
    subgraph "Database Layer"
        DB["🗄️ Database Manager<br/>Responsibilities:<br/>• Connection pooling<br/>• Query execution<br/>• Error handling<br/>• Result streaming<br/>Files: mcp_server/db.py"]
    end
    
    subgraph "Infrastructure"
        CACHE["💾 Cache System<br/>Responsibilities:<br/>• TTL management<br/>• Serialization<br/>Files: cache/scout_catalog.json"]
        
        LOG["📋 Observability<br/>Responsibilities:<br/>• Query logging<br/>• Performance metrics<br/>• Error tracking<br/>Files: logs/, debug_logger.py"]
    end
    
    UI --> API
    API --> LG
    LG --> SCOUT
    LG --> PARSER
    PARSER --> RANKER
    RANKER --> BLUEPRINT
    BLUEPRINT --> MCP
    MCP --> DB
    SCOUT --> CACHE
    LG --> LOG
    MCP --> LOG
    
    style UI fill:#e3f2fd,stroke:#1976d2
    style API fill:#f3e5f5,stroke:#7b1fa2
    style LG fill:#fff3e0,stroke:#f57c00
    style SCOUT fill:#e0f2f1,stroke:#00796b
    style PARSER fill:#fce4ec,stroke:#c2185b
    style RANKER fill:#f1f8e9,stroke:#558b2f
    style BLUEPRINT fill:#fff9c4,stroke:#f9a825
    style MCP fill:#e8f5e9,stroke:#2e7d32
    style DB fill:#f8bbd0,stroke:#c2185b
    style CACHE fill:#e0f2f1,stroke:#00796b
    style LOG fill:#ede7f6,stroke:#512da8
```

---

## 8. Scout Mode Cache Lifecycle

```mermaid
graph TB
    subgraph "Cache States"
        INIT["🔄 INITIALIZING<br/>Server starting<br/>No cache loaded"]
        
        READY["✅ READY<br/>Cache valid<br/>Serving requests"]
        
        EXPIRED["⏱️ EXPIRED<br/>TTL exceeded (7 days)<br/>Refresh needed"]
        
        ERROR["❌ ERROR<br/>Metadata corruption<br/>Fallback mode"]
    end
    
    subgraph "Cache Operations"
        STARTUP["1️⃣ On Startup<br/>• Check if cache exists<br/>• Read cache file<br/>• Check TTL<br/>• Load to memory"]
        
        REFRESH["2️⃣ Refresh TTL<br/>• Query information_schema<br/>• Update all tables<br/>• Re-compute metadata<br/>• Write new cache"]
        
        ACCESS["3️⃣ Runtime Access<br/>• Memory lookup O(1)<br/>• No DB queries<br/>• Return metadata<br/>• ~1ms response"]
        
        VALIDATE["4️⃣ Validation<br/>• Check file integrity<br/>• Verify JSON format<br/>• Count tables<br/>• Audit metadata"]
    end
    
    subgraph "Cache Contents"
        FILE["📄 scout_catalog.json<br/>• version: '1.0'<br/>• generated_at: timestamp<br/>• ttl_days: 7<br/>• tables: { ... }"]
        
        TABLE["📋 Per-Table:<br/>• name<br/>• schema<br/>• full_name<br/>• type<br/>• estimated_rows<br/>• column_count<br/>• numeric_columns[]<br/>• date_columns[]<br/>• text_columns[]<br/>• fk_count<br/>• primary_keys[]<br/>• foreign_keys[]"]
    end
    
    INIT --> STARTUP
    STARTUP -->|"Cache valid"| READY
    STARTUP -->|"Cache missing"| REFRESH
    STARTUP -->|"TTL expired"| EXPIRED
    STARTUP -->|"Corrupt file"| ERROR
    
    READY --> ACCESS
    READY -->|"7 days pass"| EXPIRED
    
    EXPIRED --> REFRESH
    REFRESH --> READY
    
    ERROR -->|"Manual refresh"| REFRESH
    ERROR -->|"Fallback"| READY
    
    REFRESH --> VALIDATE
    VALIDATE --> FILE
    FILE --> TABLE
    
    style INIT fill:#fff9c4,stroke:#f9a825
    style READY fill:#c8e6c9,stroke:#2e7d32
    style EXPIRED fill:#ffccbc,stroke:#d84315
    style ERROR fill:#ffcdd2,stroke:#b71c1c
    style STARTUP fill:#e0f2f1,stroke:#00796b
    style REFRESH fill:#e0f2f1,stroke:#00796b
    style ACCESS fill:#f1f8e9,stroke:#558b2f
    style VALIDATE fill:#f1f8e9,stroke:#558b2f
    style FILE fill:#e0f2f1,stroke:#00796b
    style TABLE fill:#e0f2f1,stroke:#00796b
```

---

## 9. Performance Characteristics

```mermaid
graph LR
    subgraph "Phase 6 (Interactive)"
        P6_START["Start"]
        P6_DISCOVERY["Schema Discovery<br/>10-50s"]
        P6_LLM["LLM Processing<br/>5-10s"]
        P6_EXECUTE["Execute + Format<br/>2-5s"]
        P6_END["End: 17-65s"]
    end
    
    subgraph "Phase 7 (Answer-First)"
        P7_START["Start"]
        P7_PARSE["Parse Intent<br/>1-2s"]
        P7_DISCOVERY["Discover (DB)<br/>10-50s"]
        P7_LLM["LLM + SQL Gen<br/>3-5s"]
        P7_EXECUTE["Execute + Format<br/>2-5s"]
        P7_END["End: 16-62s"]
    end
    
    subgraph "Phase 7.1 (Scout Mode)"
        P71_START["Start"]
        P71_CACHE["Load Cache<br/>50ms"]
        P71_RANK["Rank Tables<br/>50-100ms"]
        P71_LLM["LLM + SQL Gen<br/>2-3s"]
        P71_EXECUTE["Execute + Format<br/>1-2s"]
        P71_END["End: <500ms"]
    end
    
    P6_START --> P6_DISCOVERY
    P6_DISCOVERY --> P6_LLM
    P6_LLM --> P6_EXECUTE
    P6_EXECUTE --> P6_END
    
    P7_START --> P7_PARSE
    P7_PARSE --> P7_DISCOVERY
    P7_DISCOVERY --> P7_LLM
    P7_LLM --> P7_EXECUTE
    P7_EXECUTE --> P7_END
    
    P71_START --> P71_CACHE
    P71_CACHE --> P71_RANK
    P71_RANK --> P71_LLM
    P71_LLM --> P71_EXECUTE
    P71_EXECUTE --> P71_END
    
    style P6_DISCOVERY fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style P7_DISCOVERY fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style P71_CACHE fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style P71_RANK fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style P6_END fill:#ffcdd2,stroke:#b71c1c,stroke-width:2px
    style P7_END fill:#ffcdd2,stroke:#b71c1c,stroke-width:2px
    style P71_END fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

### Performance Metrics Table

| Operation | Phase 6 | Phase 7 | Phase 7.1 | Improvement |
|-----------|---------|---------|-----------|-------------|
| **Schema Discovery** | 10-50s | 10-50s | 50ms | **200-1000x** |
| **Entity Ranking** | N/A | 2-5s | 50-100ms | **20-100x** |
| **LLM Processing** | 5-10s | 3-5s | 2-3s | 1.5-3x |
| **Query Execution** | 2-5s | 2-5s | 1-2s | 1.5-2.5x |
| **Total Time** | 17-65s | 16-62s | **<500ms** | **40-130x** |
| **User Experience** | Interactive | Interactive | **Real-time** | Near-instant |

---

## 10. Error Handling & Recovery

```mermaid
graph TB
    subgraph "Failure Modes"
        NO_CACHE["❌ Scout Cache<br/>Unavailable"]
        NO_MATCH["❌ No Tables<br/>Match Query"]
        TIMEOUT["❌ Query<br/>Timeout"]
        CORRUPT["❌ Cache<br/>Corrupted"]
        PROXY_DOWN["❌ Proxy<br/>Offline"]
    end
    
    subgraph "Detection"
        DET1["Detect: Cache file<br/>missing or unreadable"]
        DET2["Detect: Ranking<br/>score all < 0.3"]
        DET3["Detect: Query runs<br/>>30 seconds"]
        DET4["Detect: JSON<br/>parse error"]
        DET5["Detect: HTTP 503<br/>on proxy"]
    end
    
    subgraph "Recovery Strategy"
        REC1["Fallback: Query<br/>information_schema<br/>Slower but works"]
        REC2["Recovery: Return<br/>all tables with<br/>low confidence"]
        REC3["Recovery: Cancel<br/>query, suggest<br/>refinement"]
        REC4["Recovery: Rebuild<br/>cache from DB"]
        REC5["Recovery: Return<br/>cached results<br/>or error msg"]
    end
    
    subgraph "User Experience"
        UX1["Tell user:<br/>'Slower first query'"]
        UX2["Tell user:<br/>'Refine keywords'"]
        UX3["Tell user:<br/>'Query too complex'"]
        UX4["Tell user:<br/>'System refreshing'"]
        UX5["Tell user:<br/>'Database offline'"]
    end
    
    NO_CACHE --> DET1 --> REC1 --> UX1
    NO_MATCH --> DET2 --> REC2 --> UX2
    TIMEOUT --> DET3 --> REC3 --> UX3
    CORRUPT --> DET4 --> REC4 --> UX4
    PROXY_DOWN --> DET5 --> REC5 --> UX5
    
    style NO_CACHE fill:#ffcdd2,stroke:#b71c1c
    style NO_MATCH fill:#ffcdd2,stroke:#b71c1c
    style TIMEOUT fill:#ffcdd2,stroke:#b71c1c
    style CORRUPT fill:#ffcdd2,stroke:#b71c1c
    style PROXY_DOWN fill:#ffcdd2,stroke:#b71c1c
    style REC1 fill:#fff9c4,stroke:#f9a825
    style REC2 fill:#fff9c4,stroke:#f9a825
    style REC3 fill:#fff9c4,stroke:#f9a825
    style REC4 fill:#fff9c4,stroke:#f9a825
    style REC5 fill:#fff9c4,stroke:#f9a825
    style UX1 fill:#c8e6c9,stroke:#2e7d32
    style UX2 fill:#c8e6c9,stroke:#2e7d32
    style UX3 fill:#c8e6c9,stroke:#2e7d32
    style UX4 fill:#c8e6c9,stroke:#2e7d32
    style UX5 fill:#c8e6c9,stroke:#2e7d32
```

---

## 11. Observability & Debug Logging

```mermaid
graph TB
    subgraph "Log Collection Points"
        SCOUT_LOG["🔍 Scout Mode Logs<br/>• Discovery start/end<br/>• Tables found<br/>• Cache write<br/>• Duration"]
        
        INTENT_LOG["📝 Intent Parsing<br/>• Extracted entities<br/>• Confidence scores<br/>• Operations detected"]
        
        RANK_LOG["🎯 Ranking Logs<br/>• All table scores<br/>• Top 3 selected<br/>• Reasoning per table"]
        
        SQL_LOG["📋 SQL Generation<br/>• Template used<br/>• Final SQL<br/>• Bindings applied"]
        
        EXEC_LOG["⚡ Query Execution<br/>• SQL executed<br/>• Rows returned<br/>• Duration"]
        
        ERROR_LOG["❌ Error Logs<br/>• Error type<br/>• Stack trace<br/>• Recovery action"]
    end
    
    subgraph "Log Structure"
        STRUCT["Each Log Entry:<br/>• timestamp (ISO 8601)<br/>• component (source)<br/>• level (DEBUG/INFO/WARN/ERROR)<br/>• message<br/>• duration_ms<br/>• context (user_id, session_id)<br/>• metadata (JSON)"]
    end
    
    subgraph "Log Storage"
        FILE_LOG["📄 File Logs<br/>logs/langgraph_debug.log<br/>Rotated daily"]
        
        MEMORY_LOG["💾 Memory Buffer<br/>Thread-safe buffer<br/>For WebSocket streaming<br/>Last 100 entries"]
    end
    
    subgraph "Log Streaming"
        FRONTEND["🌐 Frontend<br/>Real-time log viewer<br/>WebSocket connection<br/>Color-coded levels"]
    end
    
    SCOUT_LOG --> STRUCT
    INTENT_LOG --> STRUCT
    RANK_LOG --> STRUCT
    SQL_LOG --> STRUCT
    EXEC_LOG --> STRUCT
    ERROR_LOG --> STRUCT
    
    STRUCT --> FILE_LOG
    STRUCT --> MEMORY_LOG
    
    MEMORY_LOG --> FRONTEND
    
    style STRUCT fill:#ede7f6,stroke:#512da8
    style FILE_LOG fill:#ede7f6,stroke:#512da8
    style MEMORY_LOG fill:#ede7f6,stroke:#512da8
    style FRONTEND fill:#e3f2fd,stroke:#1976d2
```

### Debug Log Example

```
[2025-01-15T14:23:45.123Z] 🔍 SCOUT_MODE | INFO
  Operation: cache_load_on_startup
  Duration: 250ms
  Tables in cache: 943
  Cache age: 2 days
  Next refresh: 2025-01-22

[2025-01-15T14:23:46.456Z] 📝 INTENT_PARSE | INFO
  Query: "Show recent invoices"
  Extracted entities: ["invoices"]
  Detected intent: QUERY
  Confidence: 0.92
  Operations: ["list"]

[2025-01-15T14:23:46.512Z] 🎯 TABLE_RANKING | INFO
  Tables evaluated: 943
  Tables scored positive: 8
  Top table: dbo.InvoiceHeader (score: 1.0)
  Top 3 selected: [dbo.InvoiceHeader, dbo.InvoiceLines, dbo.InvoiceStatus]
  Ranking duration: 85ms

[2025-01-15T14:23:47.234Z] 📋 SQL_GENERATION | INFO
  Template: PAGINATED_QUERY
  SQL: SELECT TOP 10 FROM dbo.InvoiceHeader ORDER BY created_at DESC
  Joins: 1 (InvoiceLines)
  Where clauses: 1

[2025-01-15T14:23:47.890Z] ⚡ QUERY_EXECUTION | INFO
  Status: SUCCESS
  Rows returned: 10
  Duration: 150ms
  Query timeout: 30s

Total Pipeline: 2.1 seconds
```

---

## 12. Deployment Architecture

```mermaid
graph TB
    subgraph "Development Environment (Mac)"
        DEV_UI["🌐 Dev Web UI<br/>localhost:3000"]
        DEV_LG["🔄 LangGraph Service<br/>localhost:5001"]
        DEV_MCP["🔌 MCP Server<br/>localhost:8000"]
        DEV_DB["📊 PostgreSQL Dev<br/>localhost:5432"]
    end
    
    subgraph "Production Environment (Docker)"
        PROD_UI["🌐 Web UI Container<br/>Port 3000<br/>nginx reverse proxy"]
        PROD_LG["🔄 LangGraph Container<br/>Port 5001<br/>Auto-restart"]
        PROD_MCP["🔌 MCP Container<br/>Port 8000<br/>Health checks"]
        PROD_VOL["💾 Volumes<br/>logs/\ncache/\nconfig/"]
    end
    
    subgraph "Data Sources"
        PG_PROD["📊 PostgreSQL<br/>(Test Data)"]
        PROXY_PROD["🪟 Windows Proxy<br/>(Production ERP)"]
    end
    
    DEV_UI --> DEV_LG
    DEV_LG --> DEV_MCP
    DEV_MCP --> DEV_DB
    
    PROD_UI --> PROD_LG
    PROD_LG --> PROD_MCP
    PROD_MCP --> PROD_VOL
    PROD_MCP --> PG_PROD
    PROD_MCP --> PROXY_PROD
    
    style DEV_UI fill:#e3f2fd,stroke:#1976d2
    style DEV_LG fill:#fff3e0,stroke:#f57c00
    style DEV_MCP fill:#e8f5e9,stroke:#2e7d32
    style DEV_DB fill:#f8bbd0,stroke:#c2185b
    style PROD_UI fill:#e3f2fd,stroke:#1976d2
    style PROD_LG fill:#fff3e0,stroke:#f57c00
    style PROD_MCP fill:#e8f5e9,stroke:#2e7d32
    style PROD_VOL fill:#e0f2f1,stroke:#00796b
```

---

## Design Decisions Summary

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| **Scout Mode** | 200-1000x faster than runtime discovery | ML-based ranking (more complex), graph-based (expensive) |
| **MCP-Only** | Single unified interface eliminates code drift | Keep dual interfaces (maintenance burden) |
| **Multi-Dimensional Scoring** | More accurate than single heuristic | Binary decisions (less accurate) |
| **Cache-First Architecture** | O(1) lookup, no I/O during query | Query DB on demand (slower) |
| **7-Day TTL** | Balances freshness vs. cache hits | 1-day (more refreshes), 30-day (stale data) |
| **File-Based Cache** | Simple, portable, version-controllable | Redis (external dependency), in-memory only |
| **Answer-First Pipeline** | Autonomous query execution before confirmation | Interactive clarification (slower) |

---

## Future Enhancements

### Phase 8 Roadmap
- **User-Specific Weights** - Different scoring per role/team
- **Query History** - Boost tables from recent successful queries
- **Semantic Embeddings** - Use embeddings for deeper entity understanding
- **Schema Change Detection** - Auto-invalidate cache on DDL
- **ML-Based Learning** - Train weights from interaction data
- **Multi-Language Support** - German/other language normalization

### Long-Term Considerations
- **Distributed Caching** - Redis for multi-instance Scout Mode
- **GraphQL Layer** - Alternative to JSON-RPC
- **Real-Time Streaming** - WebSocket-based result streaming
- **Federated Schema** - Multiple databases with cross-DB joins
- **Privacy-Preserving Mode** - PII masking, differential privacy

---

## References

- **ADR-0012**: MCP-Only Architecture Migration
- **ADR-0014**: Scout Mode Semantic Caching
- **ADR-0015**: Semantic Table Ranking for Autonomous Query Execution
- **Phase 7 Documentation**: Answer-First Pipeline Implementation
- **Phase 7.1 Documentation**: Scout Mode Integration

---

**Generated**: 2025-01-15  
**Status**: Active Architecture (Phase 7+)  
**Maintenance**: System Architecture Team
