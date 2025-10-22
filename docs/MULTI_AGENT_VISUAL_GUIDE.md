# Multi-Agent System — Visual Guide

Quick visual references for the multi-agent architecture.

---

## 🏗️ System Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Query                                 │
│                    "Show me top customers"                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        QueryOrchestrator                            │
│  (Composes 4 agents + routing logic)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │   Index DB   │  │Parse Intent  │  │   Route by   │
    │              │  │              │  │  Operation   │
    │ (Scout)      │  │ (operation?) │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       query  │      schema   │    health    │
         ▼    │         ▼     │      ▼      │
    ┌──────────┐    ┌──────────┐   ┌──────────┐
    │Discovery │    │Discovery │   │  Answer  │
    │ ▶ Search │    │ ▶ Search │   │ ▶ Health │
    │ ▶ Rank   │    │ ▶ Rank   │   │          │
    │ ▶ Filter │    │ ▶ Filter │   │ ▶ Format │
    │ ▶ Describe    │ ▶ Describe    │          │
    └─────┬────┘    └─────┬────┘   └─────┬────┘
          │                │              │
          ▼                ▼              │
    ┌──────────────┐   ┌──────────┐      │
    │ JoinPlanSQL  │   │ Answer   │      │
    │              │   │ ▶ Schema │      │
    │ ▶ View check │   │   explain│      │
    │ ▶ FK fetch   │   └──────────┘      │
    │ ▶ Plan joins │         ▲           │
    │ ▶ Gen SQL    │         │           │
    │ ▶ Validate   │         └─────┬─────┘
    └─────┬────────┘               │
          │                        │
          ▼                        │
    ┌──────────────────┐          │
    │ ExecRecovery     │          │
    │                  │          │
    │ ▶ Execute        │          │
    │ ▶ On error:      │          │
    │   - Repair (LLM) │          │
    │   - Retry        │          │
    │   - Simplify     │          │
    │ ▶ On success:    │          │
    │   forward result │          │
    └─────┬───────────┘           │
          │ exec_result/error_info │
          └────────────┬───────────┘
                       │
                       ▼
                ┌──────────────┐
                │   Answer     │
                │              │
                │ ▶ Format     │
                │ ▶ Explain    │
                │ ▶ Error      │
                │ ▶ Clarify    │
                │              │
                │ final_response
                └────────┬─────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   User Answer        │
              │ "Top 5 are: Acme..." │
              └──────────────────────┘
```

---

## 🧩 Agent State Contracts

```
┌─────────────────────────────────────────────────────┐
│                    BaseState                        │
│  (shared by all agents)                             │
│                                                     │
│  messages: List[Dict]           # Conversation     │
│  user_input: str                # Current query    │
│  intent: Dict                   # {operation, ...} │
│  retry_count: int               # Retry tracker    │
│                                                     │
│  ┌────────────────────────────────────────────┐   │
│  │    Discovery Inputs/Outputs                │   │
│  │                                            │   │
│  │  IN:  user_input, intent                   │   │
│  │  OUT: relevant_tables, schema_snippet      │   │
│  └────────────────────────────────────────────┘   │
│                      │                             │
│  ┌────────────────────▼────────────────────────┐   │
│  │    JoinSQL Inputs/Outputs                  │   │
│  │                                            │   │
│  │  IN:  relevant_tables, schema_snippet      │   │
│  │  OUT: join_plan, sql_query                 │   │
│  └────────────────────┬────────────────────────┘   │
│                       │                            │
│  ┌────────────────────▼────────────────────────┐   │
│  │    Exec Inputs/Outputs                     │   │
│  │                                            │   │
│  │  IN:  sql_query, retry_count               │   │
│  │  OUT: exec_result OR error_info            │   │
│  └────────────────────┬────────────────────────┘   │
│                       │                            │
│  ┌────────────────────▼────────────────────────┐   │
│  │    Answer Inputs/Outputs                   │   │
│  │                                            │   │
│  │  IN:  exec_result/error_info, intent       │   │
│  │  OUT: final_response                       │   │
│  └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 🔍 DiscoveryAgent Subgraph

```
START
  │
  ▼
┌─────────────────────────────┐
│  search_candidates          │
│  • MCP search_tables        │
│  • Extract keywords         │
│  • Get 10+ candidates       │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  rank_candidates            │
│  • Score = 0.45×text_sim    │
│          + 0.25×role_cov    │
│          + 0.15×subject     │
│          + 0.10×has_rows    │
│          + 0.05×is_view     │
│  • Sort by score DESC       │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  filter_to_limit            │
│  • Keep ≤3 candidates       │
│  • Min score ≥ 0.30         │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  describe_selected          │
│  • MCP describe_table (×3)  │
│  • Get columns, FKs, rows   │
│  • Cache in session         │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  build_schema_snippet       │
│  • Combine 3 tables         │
│  • Format: tbl: col (type)  │
│  • ~200 chars total         │
└────────────┬────────────────┘
             │
             ▼
           END
  (return relevant_tables, schema_snippet)
```

---

## 📋 JoinPlanAndSQLAgent Subgraph

```
START
  │
  ▼
┌──────────────────────────────┐
│  check_view_coverage         │
│  • If table.is_view          │
│    AND role_coverage ≥ 0.70  │
│  • Use view (views-first)    │
│  • ELSE continue to joins    │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│  fetch_relations             │
│  • MCP list_relations (×3)   │
│  • Get FK hints              │
│  • Build relationship map    │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│  build_join_plan             │
│  • Primary table (fact)      │
│  • Joins via FK (≤3)         │
│  • Filters & grouping        │
│  • WHERE, GROUP BY, LIMIT    │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│  generate_sql                │
│  • MSSQL only:               │
│    - TOP N (not LIMIT)       │
│    - DATEADD, GETDATE()      │
│    - Fully-qualified names   │
│  • FROM + JOINs              │
│  • WHERE + GROUP BY + ORDER  │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│  validate_sql                │
│  • Starts with SELECT        │
│  • Has FROM clause           │
│  • No DML (INSERT/UPDATE)    │
│  • Balanced quotes/parens    │
└─────────┬────────────────────┘
          │
          ▼
        END
  (return join_plan, sql_query)
```

---

## ⚡ ExecAndRecoveryAgent Subgraph (Simplified)

```
START (sql_query, retry_count=0)
  │
  ▼
┌──────────────────────────────┐
│  execute_query (attempt 1)   │
│  • MCP query_bounded         │
│  • TOP 1000, 30s timeout     │
│  • Auto-redaction            │
└─────┬──────────────────┬─────┘
      │ success          │ error
      │                  ▼
      │            ┌──────────────────────────────┐
      │            │  repair_sql                  │
      │            │  • LLM analyzes error        │
      │            │  • Context: schema, plan     │
      │            │  • Generates fixed SQL       │
      │            └────────┬─────────────────────┘
      │                     │
      │                     ▼
      │            ┌──────────────────────────────┐
      │            │  retry_query (attempt 2)     │
      │            │  • Execute repaired SQL      │
      │            └─────┬──────────────────┬─────┘
      │                  │ success          │ error
      │                  │                  ▼
      │                  │          ┌──────────────────────────────┐
      │                  │          │  simplify_query              │
      │                  │          │  • LLM simplifies query      │
      │                  │          │  • Fewer joins, more filters │
      │                  │          └────────┬─────────────────────┘
      │                  │                   │
      │                  │                   ▼
      │                  │          ┌──────────────────────────────┐
      │                  │          │  final_retry (attempt 3)     │
      │                  │          │  • Try simplified query      │
      │                  │          └─────┬──────────────────┬─────┘
      │                  │                │ success          │ error
      │                  │                │                  ▼
      │                  │                │          ┌──────────────┐
      │                  │                │          │ prepare_error│
      │                  │                │          │              │
      │                  │                │          └────────┬─────┘
      └────────┬─────────┴────────┬───────┴──────────────────┘
               │                  │
               ▼                  ▼
        (exec_result OK)   (error_info)
               │                  │
               └────────┬─────────┘
                        │
                        ▼
                      END
  (return exec_result or error_info)
```

---

## ✨ AnswerAgent Subgraph

```
START
  │
  ▼
┌──────────────────────────────┐
│  route_by_intent             │
│  • Check intent.operation    │
│  • Check error_info          │
│  • Choose formatter          │
└─────┬────────────────────────┘
      │
      ├─── query + exec_result ──► format_result
      │        (1-2 sentences)
      │
      ├─── schema_query ──────────► explain_schema
      │        (list tables)
      │
      ├─── health_check ──────────► format_health
      │        (status + count)
      │
      ├─── error_info ────────────► format_error
      │        (problem + fix)
      │
      └─── operation=clarify ────► format_clarify
               (ONE question)

All formatters:
  • Call LLM for formatting
  • Set final_response
  • Return state

         │
         ├─ format_result ────────┐
         ├─ explain_schema ───────┤
         ├─ format_health ────────┤
         ├─ format_error ─────────┤
         └─ format_clarify ───────┤
                                   │
                                   ▼
                                 END
         (return final_response)
```

---

## 🔄 Data Flow Example: "Show top 3 customers"

```
┌─ User Input ────────────────────────────────────────────┐
│  "Show top 3 customers"                                 │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ Index Database ────────────────────────────────────────┐
│  ✓ MCP healthy                                          │
│  relevant_tables = []                                   │
│  schema_snippet = ""                                    │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ Parse Intent ──────────────────────────────────────────┐
│  operation: "query"                                     │
│  entities: ["customers"]                                │
│  filters: {}                                            │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ DiscoveryAgent ────────────────────────────────────────┐
│  1. Search: "customers" → [dbo.customers, ...]          │
│  2. Rank: dbo.customers (score=0.92)                    │
│  3. Filter: [dbo.customers]                             │
│  4. Describe: columns, FKs, rows                        │
│  5. Build schema:                                       │
│     "dbo.customers: id (int), name (varchar),           │
│      email (varchar), created_at (date)"                │
│  ───────────────────────────────────────────────────── │
│  OUTPUT:                                                │
│    relevant_tables = ["dbo.customers"]                  │
│    schema_snippet = "..."                               │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ JoinPlanAndSQLAgent ───────────────────────────────────┐
│  1. Check: is_view? NO                                  │
│  2. Fetch: list_relations → no FKs to join              │
│  3. Build plan:                                         │
│     strategy="joins" (single table, no joins)           │
│     primary="dbo.customers"                             │
│  4. Generate SQL:                                       │
│     "SELECT TOP 3 * FROM dbo.customers                  │
│      ORDER BY name"                                     │
│  5. Validate: ✓ SELECT, ✓ FROM, ✓ balanced             │
│  ───────────────────────────────────────────────────── │
│  OUTPUT:                                                │
│    join_plan = {...}                                    │
│    sql_query = "SELECT TOP 3 ..."                       │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ ExecAndRecoveryAgent ──────────────────────────────────┐
│  1. Execute: MCP query_bounded → ✓ OK                   │
│  ───────────────────────────────────────────────────── │
│  OUTPUT:                                                │
│    exec_result = {                                      │
│      "ok": true,                                        │
│      "rows": [                                          │
│        {"id": 1, "name": "Acme Corp", ...},             │
│        {"id": 2, "name": "Widget Inc", ...},            │
│        {"id": 3, "name": "Tech Ltd", ...}               │
│      ],                                                 │
│      "row_count": 3,                                    │
│      "execution_time_ms": 125                           │
│    }                                                    │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ AnswerAgent ───────────────────────────────────────────┐
│  1. Route: exec_result + query → format_result          │
│  2. LLM formats:                                        │
│     Input: "Top 3 customers", results (3 rows)          │
│     Output: "The top 3 customers are: Acme Corp,        │
│               Widget Inc, and Tech Ltd."                │
│  ───────────────────────────────────────────────────── │
│  OUTPUT:                                                │
│    final_response = "The top 3 customers are:           │
│                      Acme Corp, Widget Inc, Tech Ltd"   │
└─────────────┬──────────────────────────────────────────┘
              │
              ▼
┌─ User Gets Answer ──────────────────────────────────────┐
│  "The top 3 customers are: Acme Corp, Widget Inc,       │
│   Tech Ltd"                                             │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ MSSQL Dialect Comparison

```
┌────────────────────────────┬──────────────────┬──────────────────┐
│ Concept                    │ MSSQL (Correct)  │ PostgreSQL (❌)   │
├────────────────────────────┼──────────────────┼──────────────────┤
│ Row limit                  │ TOP 10           │ LIMIT 10         │
│ Date subtract              │ DATEADD(y, -1,   │ DATE_SUB(         │
│                            │ GETDATE())       │ CURDATE(),       │
│                            │                  │ INTERVAL '1 yr') │
│ Current timestamp          │ GETDATE()        │ NOW()            │
│ Identifiers with spaces    │ [Order Date]     │ "order date"     │
│ Fully qualified name       │ dbo.customers    │ public.customers │
│ Integer division           │ CAST(5 AS FLOAT)│ 5::float         │
│                            │ / 2              │ / 2              │
│ Check if NULL              │ ISNULL(col, 0)  │ COALESCE(col, 0) │
│ String concatenation       │ CONCAT(a, b)    │ a || b           │
│                            │ or a + b         │                  │
│ String length              │ LEN(col)         │ LENGTH(col)      │
│ Cast                       │ CAST(x AS INT)   │ x::int           │
│ Date format conversion     │ CONVERT(DATE,    │ TO_DATE(x,       │
│                            │ x, 120)          │ 'YYYY-MM-DD')    │
└────────────────────────────┴──────────────────┴──────────────────┘

All generated SQL MUST use MSSQL syntax (left column)!
```

---

## 📊 Performance Timeline

```
User Query (t=0)
    │
    ├─ Index Database ────────────── 1-2s (MCP health check)
    │
    ├─ Parse Intent ────────────────── <1s (simple parsing)
    │
    ├─ DiscoveryAgent ─────────────── 2-3s
    │  ├─ Search: 1s (MCP search_tables)
    │  ├─ Describe ×3: 1-2s (MCP describe_table)
    │  └─ Build schema: <1s
    │
    ├─ JoinPlanAndSQLAgent ────────── 1-2s
    │  ├─ Fetch relations: <1s (MCP list_relations)
    │  ├─ LLM SQL generation: 1-2s
    │  └─ Validation: <1s
    │
    ├─ ExecAndRecoveryAgent ────────── 5-30s (VARIABLE)
    │  ├─ Execute (attempt 1): 1-30s (MCP query_bounded)
    │  ├─ If error + repair: +2-3s (LLM repair + retry)
    │  └─ If final retry: +5-15s (simplified query)
    │
    └─ AnswerAgent ────────────────── 1-2s
       └─ LLM format results: 1-2s

    ───────────────────────────────────────────
    TOTAL: ~10-40s (simple queries)
           ~15-60s (queries with errors + repair)

    ✓ Most time spent on query execution (MCP query_bounded)
    ✓ LLM calls are fast (2-3s total)
    ✓ MCP discovery is cached (fast on second query)
```

---

## 🎯 Operation Routing Map

```
User Input Analysis
    │
    ├─ "What tables..." ────────────► operation: "schema_query"
    │  "Show schema..."
    │  "List tables..."
    │  "Database structure..."
    │
    ├─ "Is system..." ──────────────► operation: "health_check"
    │  "Status..."
    │  "Working..."
    │
    ├─ "How many..." ───────────────► operation: "query"
    │  "Show me..."
    │  "Top 5..."
    │  "Total..."
    │
    ├─ (empty input) ───────────────► operation: "error"
    │  (parser failed)
    │
    └─ (everything else) ──────────► operation: "query"
       (default safe routing)

                  ▼

            ┌─ schema_query ─────► Discovery + Answer(schema)
            │
    Route ──┼─ health_check ─────► Answer(health)
            │
            ├─ query ───────────► Discovery → JoinSQL → Exec → Answer
            │
            └─ error ───────────► Answer(error)
```

---

*Visual Guide — January 2025*