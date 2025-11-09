# MCP Server Architecture & Integration (Complete Analysis)
**Status**: Complete Technical Analysis | Date: 2025-11-07

---

## EXECUTIVE SUMMARY

The MCP Server (running on Windows/VPN) is the **data access and discovery proxy** for the entire LangGraph orchestration system. It abstracts away database complexity behind safe, typed tools while providing semantic discovery via the **Scout Catalog**.

**Key responsibilities:**
- 🔍 **Discovery**: Find relevant tables/views via cached catalog + semantic ranking
- 🛡️ **Safe Execution**: Execute queries with row caps, timeouts, column redaction
- 📊 **Catalog Management**: Build & maintain Scout semantic index
- 🔗 **DB Abstraction**: Support both MSSQL (production) and Postgres (dev)

**Current State**: ~90% operational. Missing pieces:
- ⚠️ Weak response type validation (JSON parsing failures silent)
- ⚠️ No tool-level health probes (agents don't know when tools fail)
- ✅ Safe query execution working
- ✅ Discovery tools working (with semantic ranking)
- ✅ Catalog-backed approach preventing schema storms

---

## PART I: SYSTEM TOPOLOGY & MCP ROLE

### A. Deployment Architecture

```
┌────────────────────────────────────────────────────────┐
│ macOS (AI Tier)                                        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌─ LangGraph Orchestrator (FastAPI :5001) ────────┐  │
│  │ Agents:                                          │  │
│  │ - IntentParser                                   │  │
│  │ - Discovery                                      │  │
│  │ - JoinSQL                                        │  │
│  │ - ExecRecovery                                   │  │
│  │ - Answer                                         │  │
│  └──────────────────────┬──────────────────────────┘  │
│                         │                             │
│  ┌─ MCPDatabaseTool (HTTP Client) ───────────────────┐  │
│  │ (langgraph_integration/mcp_client.py)            │  │
│  │ - Async HTTP wrapper                            │  │
│  │ - JSON-RPC 2.0 client                           │  │
│  │ - Handles tool call marshalling                 │  │
│  │ - Parses responses + error handling             │  │
│  └──────────────────────┬──────────────────────────┘  │
│                         │                             │
│                    HTTP/JSON-RPC                      │
│                  (MCP_SERVER_URL)                     │
└────────────┬───────────────────────────────────────┬──┘
             │                                       │
             │ (over VPN/network)                   │
             │                                       │
┌────────────▼───────────────────────────────────────▼──┐
│ Windows/VPN (Data Tier - MCP Server :8000)           │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌─ FastAPI Application (server.py) ────────────────┐ │
│  │ - JSON-RPC 2.0 endpoint (/mcp/call)             │ │
│  │ - Tool router (dispatch to handlers)            │ │
│  │ - Auth (API key validation)                     │ │
│  │ - Startup: Initialize db_manager + Scout       │ │
│  └────────────────────────────────────────────────┘ │
│                                                        │
│  ┌─ Tool Handlers (tools.py) ─────────────────────┐ │
│  │ Discovery:                                      │ │
│  │  - search_tables(q, page, page_size)           │ │
│  │  - list_tables(page, page_size, schema, ...)   │ │
│  │  - describe_table(fqtn)                        │ │
│  │  - list_relations(fqtn)                        │ │
│  │  - search_views(q, page, page_size)            │ │
│  │  - describe_view(fqvn)                         │ │
│  │ Execution:                                      │ │
│  │  - query_bounded(sql, params) [SAFE]           │ │
│  │ Utility:                                        │ │
│  │  - get_column_index(fqtn)                      │ │
│  │  - /health (catalog status)                    │ │
│  └────────────────────────────────────────────────┘ │
│                                                        │
│  ┌─ Scout Catalog (scout_runner.py) ─────────────────┐ │
│  │ - TTL-based refresh (7 days)                    │ │
│  │ - In-memory cache of tables + views + columns  │ │
│  │ - Built at startup (or on-demand)              │ │
│  │ - Persisted to disk (cache/scout_catalog.json) │ │
│  │ - No live information_schema queries            │ │
│  └────────────────────────────────────────────────┘ │
│                                                        │
│  ┌─ Semantic Ranking (table_ranker.py) ────────────┐ │
│  │ - Multi-dimensional scoring [0..1]             │ │
│  │ - Entity matching + fuzzy match + type compat  │ │
│  │ - EN↔DE synonyms (Kunde↔Customer, etc.)        │ │
│  │ - View preference bonus (role coverage bonus)  │ │
│  └────────────────────────────────────────────────┘ │
│                                                        │
│  ┌─ Database Abstraction (database_adapter.py) ────┐ │
│  │ Dialect: MSSQL (via pyodbc)                    │ │
│  │  - Connection pooling                          │ │
│  │  - Timeout management (30s default)            │ │
│  │  - Row cap enforcement                         │ │
│  │  - Catalog building (sys.tables, sys.views)    │ │
│  └────────────────────────────────────────────────┘ │
│                                                        │
└────────────┬────────────────────────────────────────┬──┘
             │                                       │
             │ (ODBC / VPN Connection)              │
             │                                       │
┌────────────▼────────────────────────────────────────▼──┐
│ MSSQL Database (ERP Instance - Client VPN)           │
├────────────────────────────────────────────────────────┤
│ - Production data source (ONLY SOURCE OF TRUTH)       │
│ - System catalogs: sys.tables, sys.columns, sys.views│
│ - Foreign keys: sys.foreign_keys                      │
│ - Row estimates: sys.dm_db_partition_stats           │
└────────────────────────────────────────────────────────┘
```

### B. Data Flows

**1. Discovery Flow (Query: "How many customers?")**
```
LangGraph DiscoveryAgent
  ↓
  MCP search_tables("customers", page=0, page_size=10)
  ↓ HTTP/JSON-RPC POST :8000/mcp/call
  ↓
Server: _search_tables() handler
  ├─ Get catalog from scout_runner (in-memory)
  ├─ Extract tables + views from catalog
  ├─ Initialize TableRanker
  ├─ Score all tables against "customers" keyword
  ├─ Return top 10, ranked by score
  ↓ HTTP JSON response
  ↓
Agent receives: { ok: true, data: [RankedTable, ...], page_info: {...} }
  ├─ Parse response (extract from "Full response (JSON):" marker)
  ├─ Take top 3 candidates
  └─ Call describe_table for each
```

**2. Execution Flow (Query: "SELECT COUNT(*) FROM dbo.Customers")**
```
LangGraph ExecRecoveryAgent
  ↓
  MCP query_bounded(sql, params={})
  ↓ HTTP/JSON-RPC POST :8000/mcp/call
  ↓
Server: _query_bounded() handler
  ├─ Validate SQL (SELECT-only, single statement)
  ├─ Inject TOP 1000 (if not already limited)
  ├─ Enforce 30s timeout
  ├─ Execute via db_manager.connector
  ├─ Convert rows to JSON-serializable (Decimal→float, datetime→ISO)
  ├─ Redact sensitive columns (passwords, SSNs, etc.)
  ├─ Return QueryResponse envelope
  ↓ HTTP JSON response
  ↓
Agent receives: { ok: true, rows: [...], row_count: 5432, execution_time_ms: 145 }
  ├─ Check ok=true
  ├─ Parse rows
  └─ Pass to Answer agent
```

---

## PART II: SCOUT CATALOG & SEMANTIC DISCOVERY

### A. Catalog Architecture

**What is the Scout Catalog?**

The Scout Catalog is an **in-memory semantic index** of all tables and views in the MSSQL database. It's built once at startup and refreshed on a TTL schedule.

```
Scout Catalog Structure:
{
  "metadata": {
    "built_at": "2025-11-07T12:34:56.789Z",
    "ttl_hours": 168,  # 7 days
    "expires_at": "2025-11-14T12:34:56.789Z",
    "refresh_interval_hours": 24,
    "db_dialect": "mssql",
    "table_count": 187,
    "view_count": 42
  },
  "tables": {
    "dbo.Customers": {
      "schema": "dbo",
      "name": "Customers",
      "type": "BASE TABLE",
      "estimated_rows": 12543,
      "columns": [
        {
          "name": "CustomerID",
          "type": "int",
          "nullable": false,
          "is_primary_key": true,
          "role_hints": ["id"]
        },
        {
          "name": "CustomerName",
          "type": "nvarchar(255)",
          "nullable": false,
          "role_hints": ["name"]
        },
        {
          "name": "AnnualRevenue",
          "type": "decimal(18,2)",
          "nullable": true,
          "role_hints": ["amount", "measure"]
        }
      ],
      "foreign_keys": [
        {
          "column": "CountryID",
          "referenced_table": "Countries",
          "referenced_schema": "dbo",
          "referenced_column": "CountryID"
        }
      ],
      "primary_keys": ["CustomerID"],
      "fk_cardinality": [
        {
          "column": "CountryID",
          "referenced_table": "Countries",
          "cardinality_type": "many-to-one",
          "ratio_estimate": 0.5
        }
      ],
      "domain_metadata": {
        "domain_cluster": "Sales",
        "domain_confidence": 0.95,
        "subject_tags": ["customer", "entity", "crm"]
      }
    },
    # ... 186 more tables ...
  },
  "views": {
    "dbo.v_CustomerSalesReport": {
      "schema": "dbo",
      "name": "v_CustomerSalesReport",
      "type": "VIEW",
      "estimated_rows": 12543,
      "columns": [...],
      "view_dependencies": [
        {
          "depends_on_table": "Customers",
          "depends_on_schema": "dbo",
          "dependency_type": "table"
        }
      ],
      "is_materialized_view": false,
      "view_materialization_strategy": null
    },
    # ... 41 more views ...
  }
}
```

### B. Catalog Building Process (Startup)

**Step 1: Connection test** (10s timeout)
```
db_manager = DatabaseAdapter()
connector = MSSQLConnector(server, database, user, password)
is_healthy = await connector.test_connection()
```

**Step 2: Catalog initialization** (60s timeout)
```
await db_manager.initialize()
  ├─ Query sys.tables, sys.views
  ├─ For each table:
  │   ├─ Get columns (sys.columns)
  │   ├─ Get primary keys (sys.key_constraints)
  │   ├─ Get foreign keys (sys.foreign_keys)
  │   ├─ Get row estimate (sys.dm_db_partition_stats)
  │   └─ Enrich with role hints (ColumnRoleEnricher)
  ├─ For each view:
  │   ├─ Get columns & definition
  │   ├─ Get dependencies (sys.sql_expression_dependencies)
  │   └─ Determine if materialized
  └─ Store in SchemaCatalog
```

**Step 3: Scout Runner initialization** (async)
```
scout_runner = ScoutRunner(
  db_adapter=db_manager,
  catalog_dir="data/catalog",
  ttl_hours=7*24,
  refresh_interval_hours=24
)
await scout_runner.start()
```

### C. TTL & Refresh Strategy

**Refresh Trigger:**
- First call to Scout after TTL expires → triggers refresh in background
- Refresh runs async (doesn't block tool calls)
- New catalog swapped in atomically once ready

**Current TTL:** 7 days (604,800 seconds)

**Refresh Interval:** 24 hours

**Consequences:**
- ✅ Startup fast (catalog loaded from disk)
- ✅ No live sys.* queries after startup
- ⚠️ Schema changes not reflected until TTL expiry or manual refresh
- ⚠️ Production schema changes require manual intervention (or restart)

### D. Semantic Ranking Algorithm

**TableRanker.rank_tables()**

Scoring is multi-dimensional [0..1]:

```python
score = (
    0.45 * text_similarity        # String matching (Levenshtein distance)
    + 0.25 * role_coverage        # Do columns match query roles? (date/amount/id)
    + 0.15 * entity_match         # Exact/fuzzy keyword match
    + 0.10 * has_rows_bonus       # Prefer non-empty tables
    + 0.05 * is_view_bonus        # Views get slight preference (pre-joined)
)
```

**Language Handling (EN↔DE):**
```
Synonyms map:
- "customer" → ["kunde", "kunden", "client", "adress", "adressen"]
- "product" → ["artikel", "produkt"]
- "order" → ["auftrag", "bestellung", "beleg"]
- "inventory" → ["bestand", "lager", "lagerbestand"]
- "sales" → ["verkauf", "umsatz"]
```

**Component Matching:**
For compound German names like "BSOffeneVKLieferungen":
1. Normalize: strip prefixes (BS, VK, dbo., etc.) → "offenelieferungen"
2. Fuzzy match against query keywords
3. Bump score if query term found in component

**Example:**
```
Query: "customers"
Catalog tables:
  - dbo.Customers (exact match: 1.0)
  - dbo.CustomerOrders (substring match: 0.85)
  - dbo.BSKundenStamm (fuzzy match "kundenkunke": 0.78)

Ranked result: [Customers (1.0), CustomerOrders (0.85), BSKundenStamm (0.78)]
```

---

## PART III: TOOL CATALOG & CONTRACTS

### A. Discovery Tools

#### 1. `search_tables(q, page, page_size)`

**Purpose:** Semantic search for tables by keyword

**Request:**
```json
{
  "q": "customers",
  "page": 0,
  "page_size": 10
}
```

**Response (success):**
```json
{
  "ok": true,
  "data": [
    {
      "schema": "dbo",
      "name": "Customers",
      "full_name": "dbo.Customers",
      "type": "TABLE",
      "estimated_rows": 12543,
      "column_count": 15,
      "fk_count": 2,
      "relevance_score": 0.98,
      "ranking_reasons": [
        "Exact name match 'customers'",
        "High role coverage (id, name, date)",
        "Non-empty table (12K rows)"
      ],
      "matched_columns": ["CustomerID", "CustomerName"],
      "description": "Master table for customer entities"
    }
  ],
  "page_info": {
    "page": 0,
    "page_size": 10,
    "total_items": 187,
    "total_pages": 19,
    "has_next": true,
    "has_prev": false
  },
  "execution_time_ms": 12.5,
  "cached": true
}
```

**Response (error):**
```json
{
  "ok": false,
  "error": "Invalid query: too short",
  "error_code": "VALIDATION_FAILED",
  "execution_time_ms": 0.8
}
```

**Called by:** DiscoveryAgent._search_candidates_node()

---

#### 2. `list_tables(page, page_size, schema, pattern, include_empty, min_rows)`

**Purpose:** List all tables with optional filtering

**Request:**
```json
{
  "page": 0,
  "page_size": 20,
  "schema": "dbo",
  "include_empty": false,
  "min_rows": 1
}
```

**Response:**
```json
{
  "ok": true,
  "data": [
    {
      "schema": "dbo",
      "name": "Customers",
      "full_name": "dbo.Customers",
      "type": "TABLE",
      "estimated_rows": 12543,
      "column_count": 15,
      "has_foreign_keys": true,
      "has_primary_keys": true
    }
  ],
  "page_info": {...},
  "execution_time_ms": 8.2,
  "cached": true
}
```

**Called by:** Rarely used; fallback if search fails

---

#### 3. `describe_table(fqtn)`

**Purpose:** Get full metadata for a specific table (columns, keys, FKs, sample data info)

**Request:**
```json
{
  "fqtn": "dbo.Customers"
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "schema": "dbo",
    "name": "Customers",
    "type": "BASE TABLE",
    "estimated_rows": 12543,
    "columns": [
      {
        "name": "CustomerID",
        "type": "int",
        "nullable": false,
        "is_primary_key": true,
        "is_foreign_key": false,
        "role_hints": ["id"]
      },
      {
        "name": "CustomerName",
        "type": "nvarchar(255)",
        "nullable": false,
        "role_hints": ["name"]
      },
      {
        "name": "AnnualRevenue",
        "type": "decimal(18,2)",
        "nullable": true,
        "role_hints": ["amount", "measure"]
      }
    ],
    "primary_keys": ["CustomerID"],
    "foreign_keys": [
      {
        "column": "CountryID",
        "referenced_table": "Countries",
        "referenced_schema": "dbo",
        "referenced_column": "CountryID"
      }
    ],
    "domain_metadata": {
      "domain_cluster": "Sales",
      "subject_tags": ["customer", "entity", "crm"]
    }
  },
  "execution_time_ms": 3.1,
  "cached": true
}
```

**Called by:** DiscoveryAgent._describe_selected_node()

---

#### 4. `list_relations(fqtn)`

**Purpose:** Get FK relationships (for join planning)

**Request:**
```json
{
  "fqtn": "dbo.Orders"
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "table": "dbo.Orders",
    "foreign_keys": [
      {
        "column": "CustomerID",
        "referenced_table": "Customers",
        "referenced_schema": "dbo",
        "referenced_column": "CustomerID",
        "cardinality": "many-to-one"
      }
    ],
    "incoming_fks": [
      {
        "table": "OrderLines",
        "column": "OrderID",
        "our_column": "OrderID",
        "cardinality": "one-to-many"
      }
    ]
  },
  "execution_time_ms": 5.3,
  "cached": true
}
```

**⚠️ Known Issue:** Sometimes returns empty/malformed JSON from Windows MCP (see blind spots)

**Called by:** JoinSQLAgent for join planning

---

#### 5. `search_views(q, page, page_size)`

**Purpose:** Search for views (like search_tables but for views only)

**Request/Response:** Similar to search_tables

**Views-First Strategy:** Returned views get `is_view_bonus` in ranking, and agents should prefer views when role_coverage >= 0.70

**Called by:** DiscoveryAgent._search_candidates_node() (called BEFORE search_tables)

---

#### 6. `describe_view(fqvn)`

**Purpose:** Get full metadata for a specific view

**Request/Response:** Similar to describe_table

**Additional fields:**
- `view_dependencies`: What tables/views this depends on
- `is_materialized_view`: true if indexed/precomputed
- `role_coverage`: Which roles this view covers

**Called by:** DiscoveryAgent when view is selected

---

### B. Execution Tools

#### 1. `query_bounded(sql, params)`

**Purpose:** Execute SQL query safely (SELECT-only, row-capped, timed, redacted)

**Request:**
```json
{
  "sql": "SELECT TOP 10 CustomerID, CustomerName, AnnualRevenue FROM dbo.Customers WHERE AnnualRevenue > ?",
  "params": [100000]
}
```

**Response (success):**
```json
{
  "ok": true,
  "rows": [
    {
      "CustomerID": 1,
      "CustomerName": "ACME Corp",
      "AnnualRevenue": 5000000.50
    }
  ],
  "columns": ["CustomerID", "CustomerName", "AnnualRevenue"],
  "row_count": 10,
  "execution_time_ms": 245.3,
  "truncated": false,
  "redacted_columns": []
}
```

**Response (error):**
```json
{
  "ok": false,
  "error_code": "SYNTAX_ERROR",
  "error_message": "Syntax error in SQL",
  "execution_time_ms": 12.5
}
```

**Response (truncated):**
```json
{
  "ok": true,
  "rows": [...],  # Only 1000 rows
  "row_count": 1000,
  "truncated": true,
  "execution_time_ms": 2100.0,
  "metadata": {
    "full_result_size_estimate": 50000,
    "row_cap_applied": true
  }
}
```

**Safety Guarantees:**
- ✅ SELECT-only (no UPDATE/DELETE/INSERT)
- ✅ Single statement (no batching)
- ✅ Row cap: TOP 1000 injected if not present
- ✅ Timeout: 30s per query
- ✅ Column redaction: Passwords, SSNs, etc. removed from response
- ✅ Type conversion: Decimal→float, datetime→ISO string

**Called by:** ExecRecoveryAgent, Critic agents

---

### C. Utility Tools

#### 1. `get_column_index(fqtn)`

**Purpose:** Get list of indexed columns for a table (prevents hallucination of non-existent columns)

**Request:**
```json
{
  "fqtn": "dbo.Customers"
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "table": "dbo.Customers",
    "columns": [
      "CustomerID",
      "CustomerName",
      "AnnualRevenue",
      "CountryID",
      "CreatedDate"
    ]
  }
}
```

**Called by:** DiscoveryAgent._fetch_column_index_node() (Phase 7.2 enhancement)

---

#### 2. `/health` (GET endpoint)

**Purpose:** Health check & catalog status

**Response:**
```json
{
  "status": "healthy",
  "db_connected": true,
  "scout_status": {
    "ready": true,
    "catalog_loaded": true,
    "tables_count": 187,
    "views_count": 42,
    "catalog_age_seconds": 3600,
    "ttl_seconds": 604800,
    "expires_at": "2025-11-14T12:34:56Z",
    "cache_hits": 4521,
    "cache_misses": 89
  },
  "response_time_ms": 2.3
}
```

---

## PART IV: DATABASE ABSTRACTION LAYER

### A. Adapter Pattern

```
MCPTools
  ↓ (calls)
DatabaseAdapter
  ├─ dialect="mssql"
  ├─ connector: MSSQLConnector (pyodbc)
  └─ catalog: SchemaCatalog
```

### B. MSSQL Connector (Production)

**Class:** `MSSQLConnector` (mcp_server/db_mssql.py)

**Connection String:**
```
DRIVER={ODBC Driver 18 for SQL Server};
SERVER={server};
DATABASE={database};
UID={user};
PWD={password};
Encrypt=yes;
TrustServerCertificate=yes;
Connection Timeout=10;
```

**Features:**
- Connection pooling (prevents connection storms)
- Statement timeout (30s default, configurable)
- Row cap injection (TOP N syntax)
- Query validation (SELECT-only)
- Error categorization (syntax, timeout, permission, etc.)

**Example Query Transformation:**
```
Input:  SELECT CustomerID, CustomerName, AnnualRevenue FROM dbo.Customers
Output: SELECT TOP 1000 CustomerID, CustomerName, AnnualRevenue FROM dbo.Customers
```

### C. Postgres Connector (Dev/Testing)

**Class:** `PostgresConnector` (mcp_server/db_postgres.py)

**Connection String:**
```
postgresql://{user}:{password}@{host}:{port}/{database}
```

**Features:**
- Similar to MSSQL but with Postgres syntax
- LIMIT N instead of TOP N
- $ parameterization instead of ? placeholders

**For Development Only** (as per repo.md)

---

## PART V: DATA ACCESS PATTERNS (Agent → MCP → DB)

### A. DiscoveryAgent.\_search_candidates_node()

```python
# Agent state
state = {
  "user_input": "How many customers do we have?",
  "intent": {
    "primary_entities": ["customers"],
    "keywords_for_discovery": ["customers", "count"]
  }
}

# Step 1: Call MCP search_views first (views-first strategy)
response = await mcp.search_views(
  q="customers",
  page=0,
  page_size=10
)

# Step 2: Parse response
{
  "ok": true,
  "data": [
    { "name": "v_CustomerReport", "score": 0.92, ... }
  ]
}

# Step 3: If low confidence, search_tables
response = await mcp.search_tables(
  q="customers count",
  page=0,
  page_size=10
)

# Result: Get ranked candidates
state.update({
  "candidate_views": [...],
  "relevant_tables": [...]
})
```

### B. DiscoveryAgent.\_describe_selected_node()

```python
# For each top candidate, get full schema
for table_fqtn in state["relevant_tables"][:3]:
  response = await mcp.describe_table(fqtn=table_fqtn)
  
  schema_snippet = {
    "table": table_fqtn,
    "columns": response["data"]["columns"],  # Names + types + roles
    "foreign_keys": response["data"]["foreign_keys"],
    "primary_keys": response["data"]["primary_keys"]
  }
  
  state["schema_snippet"].append(schema_snippet)
```

### C. DiscoveryAgent.\_fetch_column_index_node()

```python
# CRITICAL: Prevent hallucination by fetching actual indexed columns
for table_fqtn in state["relevant_tables"]:
  response = await mcp.get_column_index(fqtn=table_fqtn)
  
  actual_columns = set(response["data"]["columns"])
  state["column_index"][table_fqtn] = actual_columns
  
# Later, in SQL generation, only use columns from column_index
```

### D. JoinSQLAgent.\_plan_joins_node()

```python
# Get relationships for join planning
relations = {}
for table_fqtn in state["relevant_tables"]:
  response = await mcp.list_relations(fqtn=table_fqtn)
  relations[table_fqtn] = response["data"]

# Build join graph
# ⚠️ THIS IS WHERE EMPTY JSON PARSING FAILS (Issue #2 from Phase 10 analysis)
```

### E. ExecRecoveryAgent.\_execute_node()

```python
# Execute the SQL query safely
response = await mcp.query_bounded(
  sql=state["sql_query"],
  params=state.get("query_params", {})
)

if response["ok"]:
  state["exec_result"] = {
    "rows": response["rows"],
    "row_count": response["row_count"],
    "columns": response["columns"],
    "execution_time_ms": response["execution_time_ms"],
    "truncated": response["truncated"]
  }
else:
  # Recovery: retry with repair
  state["error_info"] = {
    "error_code": response["error_code"],
    "error_message": response["error_message"]
  }
```

---

## PART VI: RESPONSE PARSING & ERROR HANDLING

### A. Client-Side Response Parsing (mcp_client.py)

**Issue:** MCP server sometimes wraps response in markdown or "Full response (JSON):" marker

```python
# Raw response from server might be:
response_text = "📊 Full response (JSON): {\"ok\": true, \"data\": [...]}"

# Or with markdown:
response_text = "```json\n{\"ok\": true, \"data\": [...]}\n```"

# Or plain JSON (sometimes):
response_text = "{\"ok\": true, \"data\": [...]}"
```

**Solution:** `_extract_json_from_text()` function

```python
def _extract_json_from_text(content: str) -> Dict[str, Any]:
    """Extract JSON from potentially wrapped response."""
    if isinstance(content, dict):
        return content
    
    content = content.strip()
    
    # Try markers first
    markers = [
        "📊 Full response (JSON):",
        "Full response (JSON):",
        "```json", "```"
    ]
    
    for marker in markers:
        if marker in content:
            content = content.split(marker, 1)[1].strip()
            break
    
    # Extract JSON object
    start = content.find("{")
    end = content.rfind("}")
    json_str = content[start:end+1]
    
    return json.loads(json_str)
```

### B. Error Categorization

**Query Execution Errors:**
```
- SYNTAX_ERROR: Invalid SQL syntax
- VALIDATION_FAILED: Query fails validation (non-SELECT, etc.)
- TIMEOUT: Query exceeded 30s limit
- PERMISSION_DENIED: User lacks permissions
- TABLE_NOT_FOUND: Referenced table doesn't exist
- COLUMN_NOT_FOUND: Referenced column doesn't exist
- CONNECTION_FAILED: Can't connect to database
```

**Discovery Errors:**
```
- VIEW_NOT_FOUND: Specific view not in catalog
- TABLE_NOT_FOUND: Specific table not in catalog
- NO_RESULTS: Search returned 0 candidates
- INVALID_PARAMETERS: Missing/invalid input
```

---

## PART VII: CURRENT BLIND SPOTS & ISSUES

### Issue 1: list_relations Returns Empty/Malformed JSON

**Symptom:**
```
JoinSQLAgent calls: mcp.list_relations(fqtn="dbo.Orders")
Server responds: (empty string or malformed JSON)
Agent logs: "Failed to parse relations result: Expecting value: line 1 column 1"
Result: Falls back to single-table query (silently degrades)
```

**Root Cause:**
- Windows MCP server returns `""` (empty string) instead of valid JSON
- `json.loads("")` raises JSONDecodeError
- Agent catches exception and continues silently

**Impact:**
- ❌ Join queries don't work (missing FK information)
- ❌ Agent generates single-table queries when multi-table needed
- ⚠️ Silent failure (no alert to user or logs)

**Fix Location:** `langgraph_integration/agents/join_sql/agent.py:1272`

---

### Issue 2: Weak Response Type Validation

**Problem:**
- Tool responses can be dicts, strings, or malformed JSON
- No schema validation at tool boundary
- Parsing errors caught but silently logged

**Example:**
```
search_tables returns: "📊 Full response (JSON): {\"data\": [...]}"
Agent tries: response["data"]  # Works if extraction succeeded
But if extraction failed: KeyError silently caught, empty list returned
```

**Impact:**
- ❌ Silent failures in discovery
- ❌ Empty candidate lists treated same as "no tables exist"

---

### Issue 3: No Tool-Level Health Probes

**Problem:**
- MCP tools don't have a "probe" version to test before production use
- Agents don't know if a tool is working
- Failures only detected during main query execution

**Consequence:**
- ⚠️ Discovery phase can fail without diagnosis
- ⚠️ No early warning of MCP/DB connectivity issues

---

### Issue 4: Catalog Staleness Not Surfaced

**Problem:**
- If MSSQL schema changes, catalog isn't updated until TTL expires
- Agent doesn't know schema is stale
- Can generate queries for non-existent tables

**Example:**
- Schema changed 1 hour ago (column renamed)
- Catalog TTL is 7 days
- Agent discovers old column name, generates query
- Execution fails: COLUMN_NOT_FOUND

---

### Issue 5: No Row Count Validation

**Problem:**
- `query_bounded` returns `row_count: 0` and sets `ok: true`
- ExecRecoveryAgent treats this as success
- No signal that the result might be wrong

**Example:**
```
Query: SELECT COUNT(*) FROM dbo.Customers
Result: row_count=0, ok=true
Answer: "No data found"
Reality: Query executed but result is wrong (wrong table or empty)
```

---

## PART VIII: DESIGN DECISIONS & TRADE-OFFS

### Decision 1: Cache-First Discovery (No Live Queries)

**Trade-off:**
- ✅ Fast startup, predictable latency
- ✅ No schema storms (millions of sys.* queries)
- ❌ Schema changes lag by up to 7 days
- ❌ Can't detect deleted tables until TTL refresh

**Rationale:** Production databases change infrequently; benefit of speed outweighs risk

---

### Decision 2: JSON-RPC over HTTP (Not Binary MCP)

**Trade-off:**
- ✅ Easy to test/debug (curl/postman)
- ✅ Works over VPN/networks
- ✅ Language-agnostic
- ❌ Slower than binary (but negligible: 5-10ms overhead)
- ❌ Larger payloads

**Rationale:** Operational clarity + network reach more valuable than speed

---

### Decision 3: Silent Fallback on Relations Parse Failure

**Trade-off:**
- ✅ Graceful degradation (single-table query instead of crash)
- ❌ User never learns about MCP issue
- ❌ Query quality degrades silently

**Rationale:** Early design; should be replaced with explicit recovery (Phase 10)

---

### Decision 4: Row Cap Injection at Query Time (Not at Planning)

**Trade-off:**
- ✅ Agents can forget about row limits (always safe)
- ✅ Prevents accidental unlimited queries
- ❌ Agents can't write queries expecting all rows (rare)
- ❌ Harder to explain why results are truncated

**Rationale:** Safety by default; agents work with bounded semantics

---

## PART IX: INTEGRATION CHECKLIST

When onboarding **new agents** to consume MCP tools:

- [ ] Agent calls tools via `get_shared_mcp_tool()` (macOS client)
- [ ] Tool calls return `MCPToolResult` with `ok`, `data`, `error_code` fields
- [ ] Agent checks `result.ok` before using result
- [ ] Agent handles `error_code` specifically (not just generic exception)
- [ ] Agent parses response with `_extract_json_from_text()` if needed
- [ ] Agent expects tool calls to succeed within 30s (timeout)
- [ ] Agent assumes query_bounded results are truncated if `truncated=true`
- [ ] Agent includes execution_time_ms in observability logging
- [ ] Agent doesn't assume anything about schema staleness (use column_index)

---

## PART X: ROADMAP & IMPROVEMENTS

### Phase 10a (Immediate)
- ✅ Result Validation Agent (validate row_count against intent)
- ⚠️ Fix list_relations JSON parsing (add strict schema validation)
- ⚠️ Implement sql_validator_node (currently stub)

### Phase 10b (Near-term)
- Tool health probes (test connectivity before queries)
- Explicit discovery recovery (retry with different keywords on no-results)
- Catalog staleness signals (warn when catalog > 24h old)

### Phase 11+ (Medium-term)
- Incremental catalog refresh (don't wait 7 days for schema changes)
- Tool response caching (avoid redundant describe_table calls)
- Query result caching (same SQL within N seconds → cached result)
- Observability dashboard (cache hit %, tool latencies, error rates)

---

## SUMMARY

| Component | Status | Issues |
|-----------|--------|--------|
| **Discovery Tools** | ✅ Working | ⚠️ list_relations JSON parsing |
| **Semantic Ranking** | ✅ Working | None (well-designed) |
| **Scout Catalog** | ✅ Working | ⚠️ TTL staleness not surfaced |
| **Query Execution** | ✅ Safe | ⚠️ No row count validation |
| **Response Parsing** | ⚠️ Fragile | Handles wrapper markers, but could fail |
| **Database Abstraction** | ✅ Clean | None |
| **Error Handling** | ⚠️ Partial | ⚠️ Silent failures in discovery |
| **Type Safety** | ⚠️ Weak | No response schema validation |

---

**Next Steps for Phase 10:**

1. **Review** this architecture document (you're reading it!)
2. **Decide** which issues to fix first (likely: result validator, then list_relations)
3. **Implement** fixes in order (small PRs, each with README + tests)
4. **Observe** improvements (cache hit %, query success rate, latency)

*End of document — ready for Phase 10 implementation planning.*