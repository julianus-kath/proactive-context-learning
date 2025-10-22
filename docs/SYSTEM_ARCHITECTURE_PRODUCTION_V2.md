# Production System Architecture - Precise Technical Documentation

**Last Updated**: October 2025  
**Status**: Production-Grade (Phase 7 Complete)  
**Database**: Microsoft SQL Server (MSSQL) via VPN  
**Architecture Pattern**: MCP-only orchestration with Scout Mode semantic caching

---

## 1. Deployment Topology (Precise)

### Network Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ macOS Development Machine (User/Developer)                              │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ [3000] Web UI (HTML/CSS/JS)                                         │ │
│ │ ├─ index.html (served by chatbot_ui/web_app.py)                    │ │
│ │ ├─ styles.css                                                       │ │
│ │ └─ script.js (handles WebSocket & HTTP calls)                      │ │
│ └──────────────┬──────────────────────────────────────────────────────┘ │
│                │ HTTP/WebSocket                                         │
│                ▼                                                         │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ [5001] LangGraph Service (FastAPI)                                  │ │
│ │ ├─ langgraph_integration/graph_definition.py                        │ │
│ │ │  ├─ Workflow state: WorkflowState (TypedDict)                    │ │
│ │ │  ├─ Nodes: parse_intent, select_tables, generate_sql,            │ │
│ │ │  │          execute_query, format_results, handle_error, etc.   │ │
│ │ │  └─ LLM: ChatOpenAI (gpt-4o, temp=0.0)                          │ │
│ │ ├─ Uses: prompts.py for all system prompts                          │ │
│ │ └─ Communicates with MCP via mcp_client.py                         │ │
│ └──────────────┬──────────────────────────────────────────────────────┘ │
│                │ JSON-RPC over HTTP                                     │
│                │ MCP_SERVER_URL = "http://[WINDOWS_IP]:8000"           │
└────────────────┼───────────────────────────────────────────────────────┘
                 │ VPN Tunnel (via OpenVPN/corporate VPN)
                 │
┌────────────────┼───────────────────────────────────────────────────────┐
│ Windows Server (VPN Host / On-Premise Network)                         │
│ ┌──────────────▼───────────────────────────────────────────────────┐   │
│ │ [8000] MCP Server (FastAPI)                                      │   │
│ │ ├─ mcp_server/server.py (HTTP server with JSON-RPC)            │   │
│ │ ├─ mcp_server/tools.py (tool definitions)                       │   │
│ │ │  ├─ list_tables() → discovery tool                            │   │
│ │ │  ├─ search_tables() → semantic ranking (Scout Mode)           │   │
│ │ │  ├─ describe_table() → column details + role hints            │   │
│ │ │  ├─ describe_view() → business view metadata                  │   │
│ │ │  ├─ list_relations() → foreign key relationships              │   │
│ │ │  ├─ query_bounded() → safe SELECT with caps/redaction        │   │
│ │ │  └─ health_check() → system status                            │   │
│ │ ├─ mcp_server/scout_mode.py (catalog ingestion & ranking)       │   │
│ │ ├─ mcp_server/db_mssql.py (direct MSSQL connector)              │   │
│ │ └─ mcp_server/config.py (configuration management)              │   │
│ │                                                                   │   │
│ │ Authentication: X-API-Key header (MCP_API_KEY)                  │   │
│ │ Protocol: JSON-RPC 2.0 over HTTP/HTTPS                          │   │
│ │ Database Dialect: MSSQL (SQL Server)                            │   │
│ └──────────────┬────────────────────────────────────────────────┘   │
│                │ Direct ODBC connection                              │
│                │ pyodbc + ODBC Driver 17 for SQL Server             │
│                │ (VPN access only - not accessible externally)      │
│                ▼                                                     │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ SQL Server (MSSQL) ERP Database                              │   │
│ │ ├─ Schemas: dbo, webshop, (others)                           │   │
│ │ ├─ Tables: customers, orders, products, etc. (Scout indexed) │   │
│ │ ├─ Views: business views with role coverage                  │   │
│ │ └─ Scout Catalog: cache/scout_catalog.json (TTL refresh)    │   │
│ └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Connection Flow

1. **User Input** → Web UI (port 3000)
2. **Web UI** → LangGraph Service (port 5001) via HTTP
3. **LangGraph** → MCP Client (mcp_client.py) prepares request
4. **MCP Client** → MCP Server (Windows, port 8000) via JSON-RPC over HTTP
5. **MCP Server** → MSSQL Database via pyodbc (direct connection, VPN-only)
6. **Response** flows back through the same chain
7. **Final Answer** → Web UI (streaming)

---

## 2. LangGraph Integration (Precise Setup)

### Location
`/langgraph_integration/`

### Core Files

| File | Purpose |
|------|---------|
| `graph_definition.py` | LangGraph workflow orchestration (1408 lines) |
| `prompts.py` | All system prompts (400+ lines) |
| `mcp_client.py` | MCP communication client (900+ lines) |
| `debug_logger.py` | Structured logging for debugging |
| `proxy_db_client.py` | Legacy proxy interface (deprecated) |
| `hybrid_db_client.py` | Hybrid DB client (supports multiple backends) |

### Workflow State Definition

```python
class WorkflowState(TypedDict):
    messages: List[Dict[str, Any]]           # Conversation history
    user_input: str                          # Current user query
    intent_analysis: Optional[Dict]          # Parsed intent (operation, entities, requirements)
    schema: Optional[str]                    # DEPRECATED: full schema (use schema_snippet)
    schema_snippet: Optional[str]            # PHASE 5: Compact schema (≤3 tables)
    database_index: Optional[Dict]           # Catalog index with metadata
    sql_query: Optional[str]                 # Generated SQL statement
    query_results: Optional[str]             # Query execution results
    error_info: Optional[Dict]               # Error details if any
    final_response: Optional[str]            # Formatted natural language response
    retry_count: int                         # Retry attempt counter
    session_described_tables: Optional[Dict] # Cache of described tables
    relevant_tables: Optional[List[str]]     # Selected tables for current query
    is_schema_query: Optional[bool]          # True if asking about schema
```

### Workflow Nodes (Execution Order)

```
START
  ↓
index_database (Scout catalog discovery)
  ↓
get_schema (Retrieve available schema)
  ↓
parse_intent (LLM analyzes user intent)
  ├→ clarify (Ask for missing information) → END
  ├→ query (Route to table selection)
  ├→ schema_query (Route to schema explanation)
  ├→ execute_direct (Route to direct execution)
  ├→ sample_data (Route to sample data)
  ├→ health_check (Route to health check)
  └→ error (Route to error handling) → END

select_tables (Phase 1: Choose relevant tables)
  ↓
generate_sql (LLM generates SQL from blueprint)
  ├→ execute (Route to query execution)
  └→ error (Route to error handling) → END

execute_query (Execute via query_bounded)
  ├→ format (Route to result formatting)
  ├→ retry (Route to retry logic)
  └→ error (Route to error handling) → END

retry_query (Attempt repair and re-execute)
  ├→ format (Route to result formatting)
  └→ error (Route to error handling) → END

format_results (Format results as natural language)
  ↓
END

handle_error (Generate error response)
  ↓
END

explain_schema (Explain database schema)
  ↓
format_results
  ↓
END
```

### LLM Configuration

```python
llm = ChatOpenAI(
    model="gpt-4o",           # Latest GPT-4 model
    temperature=0.0,          # Deterministic (no randomness)
    api_key=OPENAI_API_KEY    # From environment
)
```

---

## 3. Prompts (Complete List)

### Location
`/langgraph_integration/prompts.py`

### All System Prompts

#### 1. **INTENT_PARSER_PROMPT**
**Purpose**: Parse user intent and decide action  
**Input**: Conversation history + Database schema  
**Output**: JSON with operation (clarify/query) + SQL if applicable  
**Key Behavior**:
- Maintains full conversation context
- Analyzes if clarification is needed
- Generates SQL when ready
- **Critical**: Always uses fully qualified table names (schema.table_name)
- **SQL Server Specific**: Uses TOP instead of LIMIT, DATEADD for date arithmetic

**Template Placeholder Variables**:
```
{messages}        → JSON array of conversation
{schema}          → All available schemas and tables
```

#### 2. **SQL_GENERATOR_PROMPT**
**Purpose**: Generate safe, efficient SQL from intent analysis  
**Input**: Schema + Intent analysis + Original user request  
**Output**: SELECT statement (MSSQL dialect)  
**Safety Constraints**:
- SELECT only (no INSERT/UPDATE/DELETE)
- Max 1000 rows via TOP clause
- Fully qualified table names
- Proper NULL handling with ISNULL/COALESCE

**Template Placeholder Variables**:
```
{schema}          → Available database schema
{operation}       → Parsed operation type
{entities}        → Identified entities/tables
{requirements}    → Additional requirements
{user_input}      → Original user query
```

**MSSQL Syntax Rules Applied**:
```sql
-- ✅ Correct:
SELECT TOP 100 * FROM dbo.customers
SELECT DATEADD(year, -1, CAST(GETDATE() AS DATE))

-- ❌ Incorrect (PostgreSQL):
SELECT * FROM customers LIMIT 100
SELECT DATE_SUB(CURDATE(), INTERVAL '1 year')
```

#### 3. **RESULT_FORMATTER_PROMPT**
**Purpose**: Convert raw query results to short natural language answers  
**Input**: User query + SQL executed + Raw results  
**Output**: 1-2 sentence answer (EXTREMELY SHORT)  
**Key Rules**:
- Maximum 1-2 sentences
- NO technical details
- Direct answer only
- NO prefix like "A:" or "Answer:"

**Template Placeholder Variables**:
```
{user_input}      → Original user question
{sql_query}       → SQL that was executed
{raw_results}     → Query results (usually JSON or CSV)
```

**Examples**:
```
Q: "How many customers?"
✅ Short: "10 customers"
❌ Long: "The database contains 10 customer records..."

Q: "Show me schema"
✅ Short: "customers, orders, products tables"
❌ Long: "The schema has the following tables..."
```

#### 4. **ERROR_HANDLER_PROMPT**
**Purpose**: Generate helpful error messages for users  
**Input**: User request + Error type + Error message + Context  
**Output**: Brief explanation + simple fix suggestion  
**Key Behavior**:
- States problem in 1-2 sentences
- Suggests actionable fix
- Keeps explanation SHORT

**Template Placeholder Variables**:
```
{user_input}      → What user was trying to do
{error_type}      → Type of error (timeout, connection, etc.)
{error_message}   → Detailed error message
{context}         → Additional context
```

**Error Types Handled**:
- `database_indexing_error` → Catalog failed to load
- `query_timeout` → Query took too long
- `connection_error` → Cannot reach MCP/database
- `invalid_query` → SQL syntax or validation error
- `no_results` → Query returned empty

#### 5. **SCHEMA_EXPLAINER_PROMPT**
**Purpose**: Answer questions about database schema  
**Input**: Schema + User question  
**Output**: 1-2 sentence explanation  
**Key Rules**:
- EXTREMELY SHORT (1-2 sentences)
- List table names as they appear
- NO detailed explanations
- NO sample queries

**Template Placeholder Variables**:
```
{schema}          → Available database schema
{user_input}      → User's schema question
```

#### 6. **SAMPLE_DATA_PROMPT**
**Purpose**: Present sample data from a table  
**Input**: Table name + Sample data + User request  
**Output**: Formatted sample presentation  
**Key Behavior**:
- Shows data structure and types
- Explains column meanings
- Highlights patterns
- Suggests useful queries
- Maintains privacy

**Template Placeholder Variables**:
```
{table_name}      → Name of table being shown
{sample_data}     → Sample rows from table
{user_input}      → User's request
```

#### 7. **HEALTH_CHECK_PROMPT**
**Purpose**: Report system status  
**Input**: Health status + Additional info + User request  
**Output**: Status report with guidance  
**Key Information**:
- System working or not
- Any issues or limitations
- Troubleshooting guidance
- Next steps

**Template Placeholder Variables**:
```
{health_status}   → Overall system status
{additional_info} → Details (DB connected, tables count, etc.)
{user_input}      → User's status question
```

#### 8. **CLARIFICATION_PROMPT**
**Purpose**: Ask focused follow-up questions  
**Input**: Available schema + Last user message + Conversation history + Missing fields  
**Output**: One focused clarification question  
**Key Behavior**:
- Asks exactly ONE question
- Uses actual schema column names
- References conversation context
- Suggests options based on actual data

**Template Placeholder Variables**:
```
{schema}          → Available database schema
{last_user_message}  → User's most recent input
{messages}        → Full conversation history
{missing_fields}  → What information is needed
```

### Prompt Usage in Workflow

| Node | Prompt | LLM Call |
|------|--------|----------|
| `parse_intent` | INTENT_PARSER_PROMPT | `self.llm.ainvoke()` |
| `select_tables` | (uses search results) | No LLM call |
| `generate_sql` | SQL_GENERATOR_PROMPT | `self.llm.ainvoke()` |
| `execute_query` | (no prompt) | Direct MCP call |
| `format_results` | RESULT_FORMATTER_PROMPT | `self.llm.ainvoke()` |
| `handle_error` | ERROR_HANDLER_PROMPT | `self.llm.ainvoke()` |
| `explain_schema` | SCHEMA_EXPLAINER_PROMPT | `self.llm.ainvoke()` |
| `show_sample_data` | SAMPLE_DATA_PROMPT | `self.llm.ainvoke()` |
| `health_check` | HEALTH_CHECK_PROMPT | `self.llm.ainvoke()` |
| `clarify` | CLARIFICATION_PROMPT | `self.llm.ainvoke()` |

---

## 4. MCP Server (Windows/VPN - Precise Setup)

### Location
`/mcp_server/`

### Core Architecture

#### Server Implementation (`server.py`)
- **Framework**: FastAPI + Uvicorn
- **Port**: 8000 (Windows VPN host)
- **Protocol**: JSON-RPC 2.0 over HTTP
- **Authentication**: X-API-Key header required
- **CORS**: Enabled for cross-origin requests

#### Key Startup Events
```python
@app.on_event("startup")
async def startup_event():
    # 1. Initialize DatabaseAdapter (connects to MSSQL)
    db_manager = DatabaseAdapter()
    await db_manager.initialize()
    
    # 2. Run Scout Mode (builds semantic catalog)
    scout_report = await run_scout_mode(db_manager, cache_dir='cache')
```

### Available Tools (Complete Reference)

#### **1. list_tables()**
**Purpose**: List all tables (not recommended - use search_tables instead)  
**Input Parameters**:
```python
page: int = 1                    # Page number (1-indexed)
page_size: int = 25              # Items per page (max 100)
schema: Optional[str] = None     # Filter by schema (e.g., "dbo")
pattern: Optional[str] = None    # Filter by table name pattern
include_empty: bool = False      # Include tables with zero rows
min_rows: int = 1                # Minimum rows required
```

**Output**: List of tables with metadata (name, schema, estimated rows, etc.)  
**When to Use**: Browse all tables or filter by schema/pattern  
**NOT Recommended For**: Finding specific tables (use search_tables instead)

#### **2. search_tables()** ⭐ (RECOMMENDED)
**Purpose**: Semantic search with ranking (Scout Mode - Phase 7.1)  
**Input Parameters**:
```python
query: str                       # Search query (semantic, e.g., "customers", "sales")
page: int = 1                    # Page number
page_size: int = 25              # Items per page
```

**Output**: Top-ranked tables with relevance scores  
**Ranking Algorithm** (Scout Mode):
```
score = 0.45 * text_similarity
      + 0.25 * role_coverage (date, amount, quantity, status, id, email, fk)
      + 0.15 * subject_match
      + 0.10 * has_rows (non-empty bonus)
      + 0.05 * is_view_bonus (views get preference when roles match)
```

**When to Use**: Finding relevant tables (ALWAYS use this first)  
**Advantage**: Much faster, smarter, ranked by relevance

#### **3. describe_table()**
**Purpose**: Get detailed column information for a specific table  
**Input Parameters**:
```python
fqtn: str                        # Fully qualified table name (e.g., "dbo.customers")
```

**Output**:
```python
{
    "table_name": "customers",
    "schema": "dbo",
    "estimated_rows": 5000,
    "columns": [
        {
            "name": "customer_id",
            "type": "INT",
            "nullable": False,
            "role_hint": "id"  # id, date, amount, quantity, status, email, fk_to:TableName
        },
        ...
    ],
    "foreign_keys": [
        {
            "column": "customer_id",
            "references_table": "dbo.customer_master",
            "references_column": "id"
        }
    ]
}
```

**Role Hints**:
- `id` → Primary/unique identifier
- `date` → Date/timestamp column
- `amount` → Numeric value (money, quantity)
- `quantity` → Count/volume
- `status` → Status/category
- `email` → Email address
- `fk_to:TableName` → Foreign key to another table

#### **4. describe_view()**
**Purpose**: Get details about business views (Phase 7)  
**Input Parameters**:
```python
fqvn: str                        # Fully qualified view name (e.g., "dbo.sales_summary")
```

**Output**:
```python
{
    "view_name": "sales_summary",
    "schema": "dbo",
    "estimated_rows": 1000,
    "role_coverage": 0.85,       # How well it covers business roles
    "has_rows": True,
    "columns": [...],
    "dependencies": [             # Tables used by this view
        {"name": "orders", "schema": "dbo"},
        {"name": "customers", "schema": "dbo"}
    ],
    "definition": "SELECT ... FROM orders JOIN customers ..."  # Sanitized
}
```

**Views-First Strategy**: Prefer views when role coverage > 0.70

#### **5. list_relations()**
**Purpose**: Get foreign key relationships for a table  
**Input Parameters**:
```python
fqtn: str                        # Fully qualified table name
```

**Output**:
```python
{
    "table": "dbo.orders",
    "foreign_keys": [
        {
            "column": "customer_id",
            "references_table": "dbo.customers",
            "references_column": "id"
        }
    ],
    "referenced_by": [
        {
            "table": "dbo.order_items",
            "column": "order_id",
            "references_column": "id"
        }
    ]
}
```

**Use Cases**:
- Understanding table relationships
- Planning JOINs (max 3-hop joins per policy)

#### **6. query_bounded()** ⭐ (SAFETY CRITICAL)
**Purpose**: Execute safe SELECT queries with comprehensive guardrails  
**Input Parameters**:
```python
sql: str                         # SELECT statement (MSSQL dialect)
limit: int = 100                 # Max rows (default 100, max 1000)
enable_redaction: bool = True    # Redact sensitive columns (emails, passwords, etc.)
```

**Output**:
```python
{
    "ok": True,
    "rows": [...],               # Query results (max 1000 rows)
    "row_count": 42,             # Actual rows returned
    "execution_time_ms": 234,    # Query execution time
    "truncated": False,          # True if result was capped
    "warnings": []               # Any warnings (timeouts, redactions, etc.)
}
```

**Safety Features**:
1. **Read-Only**: Only SELECT allowed (blocks INSERT/UPDATE/DELETE)
2. **Row Cap**: Enforces TOP N in generated SQL (max 1000)
3. **Timeout**: 30-60 second query timeout (VPN-friendly)
4. **Redaction**: Removes/masks sensitive columns
5. **Validation**: SQL syntax and injection prevention

**When to Use**: Always for query execution (never direct SQL)

#### **7. health_check()**
**Purpose**: Check MCP and database connectivity  
**Input Parameters**: None  
**Output**:
```python
{
    "ok": True,
    "db_connected": True,
    "tables_count": 42,
    "views_count": 15,
    "catalog_age_s": 120,        # Scout catalog age
    "cache_hits": 1250,          # Cache hit count
    "last_query_ms": 45          # Last query execution time
}
```

### MCP Tool Selection Strategy

**For Finding Tables**:
```
1. Try search_tables(query) first → get ranked results
2. If low confidence → search_tables(query) with different query
3. Fallback to describe_table() on interesting results
4. Optional: Use list_relations() to understand joins
```

**For Data Queries**:
```
1. search_tables(user_intent) → find relevant table
2. describe_table(table) → understand columns
3. Generate SQL with fully qualified names
4. Execute with query_bounded(sql, limit=100)
```

### Database Connection Details

#### Configuration File: `mcp_server/config.py`
```python
# DB_DIALECT can be: "postgres" (dev) or "mssql" (production)
db_dialect = os.getenv("DB_DIALECT", "postgres")

# MSSQL Production Configuration
MSSQL_SERVER = "your-sql-server.local"  # Windows hostname/IP
MSSQL_DATABASE = "your_erp_database"
MSSQL_USER = "domain\\username"         # Windows domain user
MSSQL_PASSWORD = "encrypted_password"
MSSQL_DRIVER = "ODBC Driver 17 for SQL Server"

# Safety Settings
MAX_QUERY_RESULTS = 1000                # Row cap per query
QUERY_TIMEOUT = 60                      # 60s for VPN connections
CATALOG_TTL_SECONDS = 3600              # Scout cache refresh (1 hour)
```

#### MSSQL Connector: `mcp_server/db_mssql.py`
```python
class MSSQLConnector:
    """
    Features:
    - pyodbc + ODBC Driver 17
    - Connection pooling
    - Statement timeouts
    - Read-only enforcement
    - Row limits
    - Automatic reconnection
    """
```

**Connection String**:
```
DRIVER={ODBC Driver 17 for SQL Server};
SERVER=tcp:server-name;
DATABASE=database;
UID=domain\user;
PWD=password;
Encrypt=yes;
TrustServerCertificate=yes;
Connection Timeout=30;
```

### Scout Mode (Semantic Caching - Phase 7)

**Location**: `mcp_server/scout_mode.py`

**Purpose**: Build intelligent schema catalog at startup

**What It Does**:
1. Queries MSSQL `sys.tables`, `sys.views`, `sys.columns`, `sys.foreign_keys`
2. Detects non-empty tables (via `sys.dm_db_partition_stats` or single SELECT probe)
3. Assigns role hints to columns (date, amount, quantity, status, id, email, fk_to:Table)
4. Computes semantic ranking scores
5. Persists catalog to `mcp_server/cache/scout_catalog.json`
6. TTL refresh every 3600 seconds (1 hour)

**Ranking Algorithm**:
```
Components:
- text_sim: Text similarity between query and table name
- role_coverage: How well table covers business roles (date, measure, keys)
- subject_match: Keyword matching on table/column names
- has_rows: Bonus for non-empty tables
- is_view_bonus: Views preferred when role coverage high

Final Score = weighted sum (0.45 text + 0.25 role + 0.15 subject + 0.10 rows + 0.05 view)
```

---

## 5. Web UI Integration (Port 3000)

### Frontend Stack
- **HTML/CSS/JS**: Vanilla JavaScript (no framework)
- **Backend**: FastAPI (`chatbot_ui/web_app.py`)
- **Communication**: HTTP + WebSocket (streaming)

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve index.html |
| `/chat` | POST | Send message to LangGraph |
| `/health` | GET | Health check |
| `/config` | GET | Frontend configuration |
| `/static/*` | GET | Serve CSS/JS/images |

### Communication Flow

**User sends query**:
```
Web UI (script.js)
  ↓ fetch("/chat", {method: "POST", body: JSON.stringify({message: "..."})})
LangGraph Service (port 5001)
  ↓ await workflow.ainvoke(state)
MCP Client (langgraph_integration/mcp_client.py)
  ↓ aiohttp.post(f"{MCP_SERVER_URL}/tool", json=params)
MCP Server (port 8000, Windows)
  ↓ tool_function(params)
MSSQL Database (via pyodbc)
  ↓ Execute query
  ↓ Return results
  ↓ Format response
Web UI (streaming via Server-Sent Events or WebSocket)
  ↓ Display answer to user
```

---

## 6. Environment Configuration

### macOS (LangGraph Development Machine)

**File**: `/langgraph_integration/.env` or project root `.env`

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...                    # Required for LLM

# MCP Server Connection
MCP_SERVER_URL=http://[WINDOWS_IP]:8000  # MCP server address
API_KEY=supersecretapikey                # MCP authentication

# LangGraph Service
LANGGRAPH_PORT=5001                      # FastAPI port
LANGGRAPH_URL=http://localhost:5001      # For local testing

# Optional: Database (if using direct connection mode - not recommended)
DB_DIALECT=mssql                         # Can be: postgres, mssql
```

### Windows (MCP Server)

**File**: `/mcp_server/.env`

```bash
# Server Configuration
MCP_API_KEY=supersecretapikey            # Same as API_KEY on macOS
MCP_HOST=0.0.0.0                         # Listen on all interfaces
MCP_PORT=8000                            # Listen port

# Database Selection
DB_DIALECT=mssql                         # MUST be mssql for production

# MSSQL Configuration (Production)
MSSQL_SERVER=sql-server.company.local    # SQL Server hostname/IP
MSSQL_DATABASE=ERP_Production            # Database name
MSSQL_USER=domain\svc_account            # Windows domain user
MSSQL_PASSWORD=encrypted_password        # User password
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

# Safety Settings
MAX_QUERY_RESULTS=1000                   # Max rows per query
QUERY_TIMEOUT=60                         # Seconds (VPN-friendly: 60s)
CATALOG_TTL_SECONDS=3600                 # Scout refresh (1 hour)

# Views + Ranking
RANKER_VIEW_PRIORITY_BONUS=0.15          # View preference bonus
VIEW_ROLE_COVERAGE_THRESHOLD=0.70        # Prefer views if coverage > 70%
INCLUDE_EMPTY_BY_DEFAULT=false           # Only show non-empty tables
JOIN_MAX_HOPS=3                          # Max joins in query planning
```

---

## 7. Data Flow Examples

### Example 1: Simple Query

```
User Input: "How many customers?"

1. Web UI sends to LangGraph (port 5001)
   POST /chat
   {"message": "How many customers?"}

2. LangGraph workflow executes:
   - parse_intent() → operation="query", entities=["customer"]
   - select_tables() → relevant_tables=["dbo.customers"]
   - generate_sql() → SQL="SELECT COUNT(*) as total FROM dbo.customers"
   - execute_query() → calls query_bounded(sql, limit=100)

3. MCP Client makes JSON-RPC call to MCP Server (port 8000)
   POST /tool
   {
     "jsonrpc": "2.0",
     "method": "query_bounded",
     "params": {
       "sql": "SELECT COUNT(*) as total FROM dbo.customers",
       "limit": 100,
       "enable_redaction": true
     },
     "id": 1
   }

4. MCP Server executes:
   - Validates SQL (SELECT only)
   - Connects to MSSQL via pyodbc
   - Executes query with timeout
   - Returns results: {"ok": true, "rows": [{"total": 1250}], "row_count": 1}

5. LangGraph format_results():
   - Uses RESULT_FORMATTER_PROMPT
   - LLM generates: "1250 customers"

6. Web UI displays answer:
   "1250 customers"
```

### Example 2: Complex Query with Discovery

```
User Input: "Show me the top 5 products by sales"

1. parse_intent() → operation="query", entities=["product"], requirements="top 5 by sales"

2. select_tables() → uses search_tables("products sales")
   ├─ search_tables() calls MCP server
   ├─ MCP returns ranked:
   │  1. dbo.products (score: 0.92)
   │  2. dbo.order_items (score: 0.85)
   │  3. dbo.sales_summary (view, score: 0.88)
   └─ LangGraph selects top 3 for planning

3. generate_sql():
   - Calls describe_table() for each selected table
   - Gets columns: products.id, products.name, order_items.quantity
   - Generates SQL:
     SELECT TOP 5 p.name, SUM(oi.quantity) as total_sales
     FROM dbo.products p
     LEFT JOIN dbo.order_items oi ON p.id = oi.product_id
     GROUP BY p.name
     ORDER BY total_sales DESC

4. execute_query() → query_bounded(sql, limit=5)

5. MCP Server:
   - Validates SQL (SELECT, fully qualified names, TOP 5)
   - Executes with 60s timeout
   - Returns 5 rows with sales data
   - Optionally redacts sensitive columns

6. format_results() → LLM creates natural answer

7. Web UI displays results as table + explanation
```

### Example 3: Schema Discovery

```
User Input: "What tables do we have?"

1. parse_intent() → operation="schema_query"

2. Route to explain_schema()

3. explain_schema():
   - Calls search_tables("tables schema") or list_tables()
   - Formats available tables
   - Uses SCHEMA_EXPLAINER_PROMPT

4. LLM generates 1-2 sentence answer:
   "customers, orders, products, suppliers, inventory tables"

5. Web UI displays: "customers, orders, products, suppliers, inventory tables"
```

---

## 8. Critical Parameters & Thresholds

### Safety Limits

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Max Query Results | 1000 rows | Prevent large data transfers |
| Query Timeout | 60 seconds | VPN-friendly timeout |
| Page Size | 100 items | Pagination for discovery |
| Max Table Description | 3 tables | Keep schema snippets compact |
| Role Coverage Threshold | 0.70 (70%) | Prefer views if coverage high |
| Catalog TTL | 3600 seconds | Scout cache refresh interval |
| Max Join Hops | 3 | Limit query complexity |

### LLM Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Model | gpt-4o | Latest GPT-4 |
| Temperature | 0.0 | Deterministic (no randomness) |
| Max Tokens | (default) | No token limit specified |
| API Timeout | (default) | Use OpenAI defaults |

### Ranking Weights (Scout Mode)

| Component | Weight | Description |
|-----------|--------|-------------|
| Text Similarity | 0.45 (45%) | Match between query and table name |
| Role Coverage | 0.25 (25%) | Business roles present (date, amount, etc.) |
| Subject Match | 0.15 (15%) | Keyword matching on columns |
| Has Rows | 0.10 (10%) | Non-empty table bonus |
| View Bonus | 0.05 (5%) | Business view preference |

---

## 9. Error Handling & Logging

### Error Types & Codes

| Error Type | Code | HTTP Status | Handler |
|-----------|------|-------------|---------|
| Database Indexing Error | 500 | 500 | error_handler |
| Table Not Found | 404 | 404 | handle_error → suggest alternatives |
| View Not Found | 404 | 404 | handle_error → suggest tables |
| Query Timeout | 504 | 504 | handle_error → suggest optimization |
| Connection Error | 503 | 503 | handle_error → troubleshoot connection |
| Invalid Query | 400 | 400 | handle_error → explain issue |
| No Results | 200 | 200 | format_results → "No matching records" |
| Validation Failed | 400 | 400 | handle_error → explain validation issue |

### Logging Strategy

**Structured Logging** via debug_logger:
```python
debug_logger.tool_call("search_tables", {"query": "customers", "page": 1})
debug_logger.tool_result("search_tables", {"count": 3, "top_match": "dbo.customers"})
debug_logger.tool_result("search_tables", None, error="Connection timeout")
```

**Log Levels**:
- `INFO`: Main workflow progress
- `WARNING`: Non-blocking issues (Scout Mode optional failures)
- `ERROR`: Critical failures (database connection, missing config)
- `DEBUG`: Detailed execution traces (not enabled by production default)

---

## 10. Deployment Checklist

### Windows Server (MCP Server Setup)

- [ ] SQL Server 2019+ installed
- [ ] ODBC Driver 17 for SQL Server installed
- [ ] Python 3.10+ installed
- [ ] Clone repository to `C:\ERP\mcp_server\`
- [ ] Create `.env` file with MSSQL credentials
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Test connection: `python quick_test.py`
- [ ] Run Scout Mode: `python mcp_server/scout_mode.py`
- [ ] Start MCP Server: `python -m uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000`
- [ ] Verify health check: `curl http://localhost:8000/health`
- [ ] Configure Windows Firewall: Allow port 8000 from macOS IP
- [ ] Test VPN connectivity from macOS

### macOS (Development Machine)

- [ ] Python 3.10+ installed
- [ ] Clone repository to `~/code/`
- [ ] Create `.env` file with OpenAI API key + MCP server URL
- [ ] Install dependencies: `pip install -r langgraph_integration/requirements.txt`
- [ ] Test MCP connectivity: `python tests/test_mcp_connectivity.py`
- [ ] Start LangGraph Service: `python chatbot_ui/start_system.py`
- [ ] Start Web UI: `python chatbot_ui/web_app.py`
- [ ] Access UI: `http://localhost:3000`
- [ ] Run test suite: `pytest tests/test_mcp_client.py -v`

---

## 11. Production Considerations

### Security

- ✅ **MSSQL on VPN Only**: Database not exposed externally
- ✅ **MCP API Key**: X-API-Key header authentication
- ✅ **Read-Only Queries**: No INSERT/UPDATE/DELETE allowed
- ✅ **Query Timeouts**: 60-second limit prevents DoS
- ✅ **Row Caps**: Max 1000 rows per query
- ✅ **Sensitive Column Redaction**: Emails, passwords automatically masked

### Performance

- ✅ **Scout Mode Caching**: 1-hour TTL for schema discovery
- ✅ **Connection Pooling**: Reuse MSSQL connections
- ✅ **Pagination**: Limit results to prevent memory bloat
- ✅ **Semantic Ranking**: Find relevant tables quickly
- ✅ **Execution Times**: Typical 50-250ms for queries

### Monitoring

- ✅ **Health Endpoints**: `/health` available on all services
- ✅ **Structured Logging**: Tool calls, results, errors logged
- ✅ **Metrics**: Cache hits, query times, table counts
- ✅ **Observability**: Complete audit trail for compliance

---

## 12. File Directory Structure

```
/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/
│
├── langgraph_integration/           # LangGraph orchestration (macOS)
│   ├── graph_definition.py          # Main workflow (1408 lines)
│   ├── prompts.py                   # System prompts (400+ lines)
│   ├── mcp_client.py                # MCP communication (900+ lines)
│   ├── debug_logger.py              # Structured logging
│   ├── proxy_db_client.py           # Legacy proxy (deprecated)
│   ├── hybrid_db_client.py          # Multi-backend support
│   ├── test_flow.py                 # Local testing
│   ├── requirements.txt             # Dependencies
│   ├── README.md                    # Documentation
│   └── .env.example                 # Example config
│
├── mcp_server/                      # MCP Server (Windows/VPN)
│   ├── server.py                    # FastAPI server (port 8000)
│   ├── tools.py                     # Tool definitions
│   ├── scout_mode.py                # Semantic caching
│   ├── db_mssql.py                  # MSSQL connector
│   ├── db_postgres.py               # PostgreSQL connector (dev)
│   ├── config.py                    # Configuration management
│   ├── database_adapter.py           # DB abstraction layer
│   ├── discovery_tools.py            # search_tables implementation
│   ├── bounded_query.py              # query_bounded implementation
│   ├── models.py                    # Pydantic models
│   ├── cache/                       # Scout catalog cache
│   │   └── scout_catalog.json       # Cached schema metadata
│   ├── requirements.txt             # Dependencies
│   ├── Dockerfile                   # Docker image
│   ├── .env.example                 # Example config
│   └── README.md                    # Documentation
│
├── chatbot_ui/                      # Web UI (port 3000 + 5001)
│   ├── web_app.py                   # FastAPI server (port 3000)
│   ├── index.html                   # HTML frontend
│   ├── styles.css                   # CSS styles
│   ├── script.js                    # JavaScript client
│   ├── app.py                       # Alternative server
│   ├── start_web_ui.py              # Startup script
│   ├── requirements.txt             # Dependencies
│   └── .env.example                 # Example config
│
├── app/db/                          # App layer database access
│   ├── mcp_client.py                # App-level MCP client
│   ├── adapter.py                   # LangGraph adapter
│   └── client.py                    # Legacy wrapper
│
├── tests/                           # Test suite
│   ├── test_mcp_client.py           # MCP client tests (15 tests)
│   ├── test_mcp_connectivity.py      # Connectivity check
│   ├── test_mcp_views.sh            # View tool tests (bash)
│   ├── test_answer_first.py         # Answer-first flow tests
│   ├── test_complete_system.py      # End-to-end tests
│   └── [many more test files]
│
├── docs/                            # Documentation
│   ├── SYSTEM_OVERVIEW.md           # General overview
│   ├── SYSTEM_ARCHITECTURE_PRODUCTION_V2.md  # This file
│   ├── ARCHITECTURE_OVERVIEW.md     # Detailed architecture (800 lines)
│   ├── PHASE_7_COMPLETE.md          # Phase 7 summary
│   ├── SCOUT_MODE_ARCHITECTURE.md   # Scout Mode details
│   ├── MIGRATION_GUIDE_PHASE_7.md   # Migration instructions
│   └── [many more documentation files]
│
├── adrs/                            # Architecture Decision Records
│   ├── 0012-mcp-only-architecture-migration.md
│   ├── 0014-scout-mode-semantic-caching.md
│   ├── 0015-semantic-table-ranking.md
│   ├── 0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md
│   └── [other ADRs]
│
├── vpn_config/                      # VPN/proxy configuration
│   ├── start_mcp_server_windows.bat  # Windows batch script
│   └── start_mcp_server_windows.sh   # Windows bash script
│
└── .env                             # Root environment file
    # OPENAI_API_KEY=...
    # MCP_SERVER_URL=http://[WINDOWS_IP]:8000
    # API_KEY=supersecretapikey
```

---

## 13. Key Insights & Decisions

### Why MCP-Only Architecture?
- **Single Interface**: No drift between multiple access paths
- **Clear Responsibility**: MCP Server owns all database access
- **Safety**: Centralized query validation and guardrails
- **Consistency**: All requests follow same path (no legacy endpoints)

### Why Scout Mode?
- **Fast Discovery**: Catalog built once at startup, TTL refresh
- **Smart Ranking**: Semantic scoring finds relevant tables
- **No Live Queries**: Avoids schema discovery storm on database
- **Flexible Caching**: JSON-based, can be versioned/distributed

### Why Views-First?
- **Business Semantics**: Views encapsulate domain logic
- **Simplified Joins**: Reduce query planning complexity
- **Role Coverage**: Tables already aggregated by business roles
- **Fallback Strategy**: If no suitable view, fall back to table joins

### MSSQL-Only (Production)
- **Client Requirement**: Production DB is SQL Server (on VPN)
- **No Postgres in Production**: Earlier Postgres was synthetic demo only
- **Dialect-Specific SQL**: All prompts generate MSSQL syntax (TOP, DATEADD, etc.)
- **VPN-Required Access**: Never exposed directly; always through MCP

---

## 14. Troubleshooting Quick Reference

### "MCP Server Connection Failed"
```
1. Verify Windows IP: Can macOS reach Windows VPN?
   ping [WINDOWS_IP]
2. Check MCP is running: curl http://[WINDOWS_IP]:8000/health
3. Verify MCP_SERVER_URL in .env: echo $MCP_SERVER_URL
4. Check firewall: Windows Firewall allowing port 8000?
```

### "MSSQL Connection Error"
```
1. Check MSSQL credentials in mcp_server/.env
2. Verify ODBC driver: odbcinst -j
3. Test connection: sqlcmd -S server -U user -P password
4. Check firewall on Windows: Port 1433 accessible?
```

### "No Tables Found in Search"
```
1. Run Scout Mode manually: python mcp_server/scout_mode.py
2. Check cache: cat mcp_server/cache/scout_catalog.json | head -20
3. Verify database has tables: SELECT COUNT(*) FROM sys.tables
4. Check catalog TTL hasn't expired
```

### "Query Timeout"
```
1. Increase timeout in mcp_server/.env:
   QUERY_TIMEOUT=120  (or higher for slow network)
2. Check VPN latency: ping [WINDOWS_IP] multiple times
3. Check SQL Server load: Query sys.dm_exec_requests
4. Optimize query: Add WHERE clauses, reduce JOIN complexity
```

---

## 15. Summary Table

| Component | Technology | Port | Location | Protocol |
|-----------|-----------|------|----------|----------|
| **Web UI** | FastAPI | 3000 | macOS | HTTP/WebSocket |
| **LangGraph Service** | FastAPI + LangGraph | 5001 | macOS | HTTP |
| **MCP Server** | FastAPI | 8000 | Windows/VPN | JSON-RPC over HTTP |
| **MSSQL Database** | Microsoft SQL Server | 1433 | Windows/VPN | Native SQL Server |
| **LLM** | GPT-4o | N/A | OpenAI Cloud | HTTPS API |

---

**Document Status**: ✅ Complete  
**Last Verified**: October 2025  
**Accuracy**: Production-Grade (Matches current codebase v1.0.0)