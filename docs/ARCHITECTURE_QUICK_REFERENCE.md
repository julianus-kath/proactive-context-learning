# Architecture Quick Reference Guide

> **Quick lookup for the production system** — Print this or bookmark it.

---

## Network & Services

```
macOS (Developer):
  🌐 Web UI ← Port 3000 (chatbot_ui/web_app.py)
  📊 LangGraph Service ← Port 5001 (langgraph_integration/)
  
Windows/VPN (Production):
  🔌 MCP Server ← Port 8000 (mcp_server/server.py)
  💾 MSSQL Database ← Port 1433 (on VPN only)
```

---

## Critical Environment Variables

### macOS (`.env`)
```bash
OPENAI_API_KEY=sk-...                       # Required
MCP_SERVER_URL=http://[WINDOWS_IP]:8000     # MCP server address
API_KEY=supersecretapikey                   # MCP authentication
```

### Windows (`.env`)
```bash
DB_DIALECT=mssql                            # Always MSSQL in production
MSSQL_SERVER=sql-server.company.local       # SQL Server hostname
MSSQL_DATABASE=ERP_Production               # Database name
MSSQL_USER=domain\svc_account               # Windows domain user
MSSQL_PASSWORD=encrypted_password           # Password
MCP_API_KEY=supersecretapikey               # Match macOS API_KEY
```

---

## Key Files (Must Know These)

| File | What It Does | Lines |
|------|-------------|-------|
| `langgraph_integration/graph_definition.py` | Workflow orchestration | 1408 |
| `langgraph_integration/prompts.py` | System prompts (8 prompts) | 400+ |
| `langgraph_integration/mcp_client.py` | MCP communication | 900+ |
| `mcp_server/server.py` | MCP API server | ~200 |
| `mcp_server/tools.py` | Tool definitions (7 tools) | ~400 |
| `mcp_server/scout_mode.py` | Semantic caching | ~300 |
| `mcp_server/db_mssql.py` | MSSQL connector | ~200 |
| `mcp_server/config.py` | Configuration | ~97 |
| `chatbot_ui/web_app.py` | Web server | ~100 |
| `chatbot_ui/index.html` | Frontend UI | ~300 |

---

## LangGraph Workflow Nodes (Execution Path)

```
START
  ↓
index_database (Load Scout catalog)
  ↓
get_schema (Retrieve schema)
  ↓
parse_intent (LLM: INTENT_PARSER_PROMPT)
  ├→ [clarify] Ask user
  ├→ [schema_query] Explain schema
  ├→ [sample_data] Show samples
  ├→ [health_check] Check status
  └→ [query] → select_tables
      ↓
      generate_sql (LLM: SQL_GENERATOR_PROMPT)
      ↓
      execute_query (MCP: query_bounded)
      ├→ retry_query (If failed)
      └→ format_results (LLM: RESULT_FORMATTER_PROMPT)
          ↓
          END
```

---

## System Prompts (All 8)

| # | Name | Purpose | Key Output |
|---|------|---------|-----------|
| 1 | INTENT_PARSER_PROMPT | Parse user intent | `{"operation": "query", "sql": "..."}` |
| 2 | SQL_GENERATOR_PROMPT | Generate safe SQL | `SELECT TOP ... FROM dbo.table` |
| 3 | RESULT_FORMATTER_PROMPT | Format results | 1-2 sentence answer |
| 4 | ERROR_HANDLER_PROMPT | Handle errors | Helpful error message |
| 5 | SCHEMA_EXPLAINER_PROMPT | Explain schema | 1-2 sentence description |
| 6 | SAMPLE_DATA_PROMPT | Show sample data | Formatted data + explanation |
| 7 | HEALTH_CHECK_PROMPT | Report status | System status + guidance |
| 8 | CLARIFICATION_PROMPT | Ask for info | One focused clarifying question |

---

## MCP Tools (7 Available)

| Tool | Purpose | Recommended? | Use When |
|------|---------|--------------|----------|
| **search_tables()** ⭐ | Find tables (ranked) | YES | Finding any table |
| list_tables() | List all tables | NO | Browse/filter by schema |
| **describe_table()** | Get columns + FKs | YES | Understand table structure |
| describe_view() | Get view details | YES | Check business views |
| list_relations() | Get foreign keys | MAYBE | Plan complex joins |
| **query_bounded()** ⭐ | Execute query | YES | Always for queries |
| health_check() | Check status | SOMETIMES | Verify connection |

**⭐ = Most commonly used**

---

## Common Query Patterns

### "How many customers?"
```
1. search_tables("customers")
2. describe_table("dbo.customers")
3. generate SQL: SELECT COUNT(*) FROM dbo.customers
4. query_bounded(sql)
5. format_results: "1250 customers"
```

### "Show me top 5 products by sales"
```
1. search_tables("products sales")
2. describe_table("dbo.products"), describe_table("dbo.order_items")
3. generate SQL: SELECT TOP 5 p.name, SUM(oi.qty) FROM dbo.products p
                 LEFT JOIN dbo.order_items oi ON ...
4. query_bounded(sql)
5. format_results: [table with 5 rows]
```

### "What tables do we have?"
```
1. parse_intent() → operation="schema_query"
2. Route to explain_schema()
3. Call list_tables() or search_tables()
4. format_results: "customers, orders, products, suppliers, inventory"
```

---

## MSSQL Syntax Rules (CRITICAL)

| PostgreSQL | SQL Server (MSSQL) | Issue |
|-----------|-------------------|-------|
| `LIMIT 100` | `TOP 100` | Query cap syntax |
| `DATE_SUB(NOW(), INTERVAL '1 year')` | `DATEADD(year, -1, CAST(GETDATE() AS DATE))` | Date arithmetic |
| `NOW()` | `GETDATE()` | Current timestamp |
| `CURDATE()` | `CAST(GETDATE() AS DATE)` | Current date only |
| `"column"` (double quotes) | `[column]` (brackets) | Identifiers |
| `'string'` | `'string'` | String literals (same) |
| `schema.table` | `schema.table` (fully qualified) | Table names (same) |

**ALWAYS use fully qualified table names**: `dbo.customers`, `webshop.orders`, etc.

---

## Safety Guardrails

| Guardrail | Limit | Where Enforced |
|-----------|-------|-----------------|
| **Max Rows** | 1000 | query_bounded() adds TOP 1000 |
| **Query Timeout** | 60 seconds | MCP server configuration |
| **Read-Only** | SELECT only | query_bounded() validation |
| **Sensitive Data** | Redacted | query_bounded() with enable_redaction=true |
| **Page Size** | 100 items | Discovery tools pagination |
| **Max Describes** | 3 tables | LangGraph planning |
| **Max Joins** | 3 hops | MCP config (JOIN_MAX_HOPS) |

---

## Performance Numbers (Typical)

| Operation | Time | Notes |
|-----------|------|-------|
| Scout catalog build | 5-10 min | One-time at MCP startup |
| Table search | 10-50 ms | From Scout catalog (fast) |
| describe_table() | 20-100 ms | From catalog or database |
| Simple query | 50-200 ms | e.g., COUNT(*) |
| Complex query | 200-1000 ms | With JOINs, GROUP BY |
| Result formatting | 50-200 ms | LLM call |
| **Total end-to-end** | **500-2000 ms** | From user input to response |

---

## Testing Checklist

### Quick Tests (< 5 min)
```bash
# 1. Check MCP connectivity
curl -H "X-API-Key: supersecretapikey" http://[WINDOWS_IP]:8000/health

# 2. Check MSSQL connectivity from Windows
sqlcmd -S [SERVER] -U [USER] -P [PASS] -Q "SELECT COUNT(*) FROM sys.tables"

# 3. Check LangGraph startup
python tests/test_mcp_connectivity.py

# 4. Test simple query
python langgraph_integration/test_flow.py
```

### Full Tests (< 30 min)
```bash
# Run complete test suite
pytest tests/test_mcp_client.py -v
pytest tests/test_complete_system.py -v
```

---

## Error Codes & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused: [WINDOWS_IP]:8000` | MCP not running | `python -m uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000` |
| `MSSQL connection failed` | Bad credentials | Check MSSQL_USER, MSSQL_PASSWORD in .env |
| `Query timeout after 60s` | VPN slow or query complex | Increase QUERY_TIMEOUT or optimize SQL |
| `TABLE_NOT_FOUND` | Table doesn't exist | Use search_tables() to find correct name |
| `OpenAI API key invalid` | Bad key | Check OPENAI_API_KEY in .env |
| `API key invalid (401)` | Wrong MCP key | Check API_KEY matches MCP_API_KEY |

---

## Startup Order (Critical!)

### 1. Windows (MCP Server)
```bash
# Verify .env has MSSQL credentials
cat mcp_server/.env

# Start MCP server
python -m uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000

# Verify startup
# Should see: "✅ MCP Database Server initialized successfully"
# Should see: "🔍 Scout Mode Report: ..."
```

### 2. macOS (LangGraph)
```bash
# Verify .env has MCP_SERVER_URL pointing to Windows
cat .env | grep MCP_SERVER_URL

# Start LangGraph service & Web UI
python chatbot_ui/start_system.py

# Or separately:
# Terminal 1: python langgraph_integration/test_flow.py
# Terminal 2: python chatbot_ui/web_app.py
```

### 3. Access Web UI
```
http://localhost:3000
```

---

## Scout Mode (Caching Strategy)

**What**: Semantic schema catalog built at MCP startup  
**How**: Ingests MSSQL sys.* tables + assigns role hints  
**Where**: `mcp_server/cache/scout_catalog.json`  
**When**: Refreshed every 3600 seconds (1 hour)  
**Why**: Fast table discovery without querying information_schema live  

**Ranking Formula** (for search_tables):
```
score = 0.45 * text_similarity
      + 0.25 * role_coverage      (date, amount, quantity, status, id, email, fk)
      + 0.15 * subject_match
      + 0.10 * has_rows          (non-empty bonus)
      + 0.05 * is_view_bonus     (views preferred when roles match)
```

---

## Views-First Strategy

**Principle**: Prefer business views when available  
**Implementation**: `search_tables()` ranks views higher if:
- role_coverage > 0.70 (70%)
- Table has rows
- Semantic match high

**Example**:
```
Search: "customer sales summary"
Results (ranked):
1. vw_customer_sales_summary (view, score: 0.92) ← PREFERRED
2. dbo.customers (table, score: 0.80)
3. dbo.order_items (table, score: 0.75)
```

---

## Fallback to Joins Strategy

**When**: No suitable view found  
**Max Joins**: 3 tables (configurable: JOIN_MAX_HOPS)  
**How**: 
1. Describe all 3 selected tables
2. Generate SQL with INNER/LEFT JOINs
3. Execute with query_bounded()

**Example**:
```sql
SELECT TOP 100 
  c.name,
  COUNT(o.id) as order_count,
  SUM(oi.quantity) as total_items
FROM dbo.customers c
LEFT JOIN dbo.orders o ON c.id = o.customer_id
LEFT JOIN dbo.order_items oi ON o.id = oi.order_id
GROUP BY c.name
ORDER BY order_count DESC
```

---

## Configuration Hierarchy

```
1. .env file (environment variables)
   ↓
2. mcp_server/config.py (loads .env)
   ↓
3. MCPServerConfig dataclass (provides defaults)
   ↓
4. Used by all components

Example:
  MCP_API_KEY in .env
  → read by config.py
  → stored in config.mcp_api_key
  → used in server.py verify_api_key()
```

---

## Ports Reference

| Port | Service | Protocol | Host |
|------|---------|----------|------|
| 3000 | Web UI | HTTP | localhost (macOS) |
| 5001 | LangGraph | HTTP | localhost (macOS) |
| 8000 | MCP Server | JSON-RPC over HTTP | 0.0.0.0 (Windows/VPN) |
| 1433 | MSSQL | Native SQL | Windows/VPN (not directly accessible) |

---

## Key Decisions (Why This Design?)

**Q: Why MCP-only (not direct DB access)?**
A: Single interface, centralized safety, no drift between paths

**Q: Why Scout Mode caching?**
A: Avoid schema discovery storms, enable semantic ranking, one-time build cost

**Q: Why views-first?**
A: Business semantics already encapsulated, simpler planning, fallback to joins

**Q: Why MSSQL only?**
A: Production requirement, no Postgres/SQLite in production

**Q: Why LangGraph?**
A: State machine with proper error handling, fallback paths, flexible routing

**Q: Why separate macOS + Windows?**
A: VPN-required access to production DB, isolation of concerns

---

## Debugging Techniques

### 1. Check Tool Call Output
```python
# In graph_definition.py, tools get logged:
debug_logger.tool_call("search_tables", {"query": "customers"})
debug_logger.tool_result("search_tables", result_dict)
```

### 2. Inspect Scout Catalog
```bash
# View what Scout Mode built:
python -c "import json; print(json.dumps(json.load(open('mcp_server/cache/scout_catalog.json')), indent=2)[:1000])"
```

### 3. Test MCP Tool Directly
```bash
# Call MCP tool via curl:
curl -X POST http://localhost:8000/tool \
  -H "X-API-Key: supersecretapikey" \
  -H "Content-Type: application/json" \
  -d '{"method": "search_tables", "params": {"query": "customers"}}'
```

### 4. Enable Debug Logging
```bash
# In langgraph_integration/ .env:
DEBUG=1
LOG_LEVEL=DEBUG
```

### 5. Trace Full Workflow
```python
# In test_flow.py:
async def test_full_flow():
    workflow = DatabaseWorkflow()
    state = await workflow.invoke({
        "user_input": "How many customers?",
        "messages": [...]
    })
    # Inspect state.final_response
```

---

**Last Updated**: October 2025  
**Status**: ✅ Production-Grade  
**Version**: 1.0.0