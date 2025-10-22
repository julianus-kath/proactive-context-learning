# Multi-Agent Architecture Implementation

**Status**: Phase 1 Complete (Agents & Contracts Defined)  
**Last Updated**: January 2025  
**Target**: Replace monolithic LangGraph with 4 specialized agents

---

## 🎯 Overview

The multi-agent system splits query processing into **4 specialized agents**, each with clear responsibilities:

```
User Query
    ↓
[Orchestrator Graph]
    ├→ Intent Parser (existing)
    ├→ Route by operation
    │
    ├─→ DiscoveryAgent      (find relevant tables/views)
    │   ├→ Search tables/views (MCP search_tables)
    │   ├→ Rank by relevance + role coverage + view preference
    │   ├→ Filter to ≤3 candidates
    │   ├→ Describe selected tables (MCP describe_table)
    │   └→ Build compact schema snippet
    │
    ├─→ JoinPlanAndSQLAgent (build joins & generate SQL)
    │   ├→ Check for high-coverage views (views-first)
    │   ├→ Fetch FK relationships (MCP list_relations)
    │   ├→ Build join plan (fact + dimensions, ≤3 joins)
    │   ├→ Generate MSSQL SELECT (TOP, DATEADD, fully-qualified)
    │   └→ Validate SQL syntax
    │
    ├─→ ExecAndRecoveryAgent (execute & repair)
    │   ├→ Execute query (MCP query_bounded)
    │   ├→ On error: repair SQL (LLM-based)
    │   ├→ Retry repaired query (max 2 attempts)
    │   ├→ On final failure: prepare for clarification
    │   └→ Return exec_result or error_info
    │
    └─→ AnswerAgent (format results)
        ├→ If exec_result: format as 1-2 sentence answer (NO tech jargon)
        ├→ If schema_query: explain tables briefly
        ├→ If error: provide user-friendly error + suggestion
        ├→ If clarify: ask one focused question
        └→ Return final_response

    ↓
Final Answer to User
```

---

## 📦 Repository Structure

```
langgraph_integration/
├── agents/
│   ├── __init__.py
│   ├── discovery/
│   │   ├── __init__.py
│   │   └── agent.py           # DiscoveryAgent class + subgraph
│   ├── join_sql/
│   │   ├── __init__.py
│   │   └── agent.py           # JoinPlanAndSQLAgent class + subgraph
│   ├── exec_recovery/
│   │   ├── __init__.py
│   │   └── agent.py           # ExecAndRecoveryAgent class + subgraph
│   └── answer/
│       ├── __init__.py
│       └── agent.py           # AnswerAgent class + subgraph
├── contracts/
│   ├── __init__.py
│   └── state.py               # TypedDict contracts (BaseState + per-agent)
├── prompts/
│   ├── __init__.py
│   ├── discovery.py           # TABLE_FOCUS_PROMPT, SCHEMA_VETTING_PROMPT
│   ├── join_sql.py            # JOIN_PLANNER_PROMPT, SQL_GENERATOR_PROMPT_MSSQL
│   ├── repair.py              # SQL_REPAIR_PROMPT, QUERY_SIMPLIFICATION
│   └── answer.py              # RESULT_FORMATTER_PROMPT, SCHEMA_EXPLAINER_PROMPT, etc.
├── graph_definition.py        # [NEXT] Orchestrator graph
├── mcp_client.py              # [UNCHANGED] MCP tool calls
└── prompts.py                 # [DEPRECATED] Old prompts (kept as fallback)
```

---

## 🧩 State Contracts (Strict)

All agents share `BaseState` with these key fields:

```python
class BaseState(TypedDict, total=False):
    # Conversation
    messages: List[Dict[str, Any]]
    user_input: str
    
    # Intent & routing
    intent: Dict[str, Any]  # {operation, entities, filters, ...}
    
    # Discovery outputs
    relevant_tables: List[str]                  # ["dbo.sales_orders", ...]
    schema_snippet: str                         # Compact schema ≤3 tables
    candidate_views: List[Dict[str, Any]]       # Ranked views
    
    # Join planning outputs
    join_plan: Dict[str, Any]                   # {strategy, path, fk_hints, ...}
    
    # Execution & recovery
    sql_query: str                              # Generated MSSQL
    exec_result: Dict[str, Any]                 # {ok, rows, row_count, ...}
    error_info: Dict[str, Any]                  # {type, message, context, ...}
    
    # Final output
    final_response: str                         # Natural language answer
    
    # Metadata
    retry_count: int
    session_described_tables: Optional[Dict]    # Cache
    health_status: Dict[str, Any]
```

### Per-Agent Input/Output Contracts

**DiscoveryAgent**:
- **Inputs**: `user_input`, `intent`, `session_described_tables`
- **Outputs**: `relevant_tables`, `schema_snippet`, `candidate_views`, `session_described_tables`, `error_info`

**JoinPlanAndSQLAgent**:
- **Inputs**: `intent`, `relevant_tables`, `schema_snippet`, `session_described_tables`
- **Outputs**: `join_plan`, `sql_query`, `error_info`

**ExecAndRecoveryAgent**:
- **Inputs**: `sql_query`, `retry_count`, `join_plan`, `schema_snippet`
- **Outputs**: `exec_result`, `error_info`, `sql_query` (repaired), `retry_count`

**AnswerAgent**:
- **Inputs**: `user_input`, `exec_result` | `error_info` | `schema_snippet`, `intent`, `sql_query`
- **Outputs**: `final_response`

---

## 🚀 Agent Implementation Status

### ✅ Completed

| Agent | Subgraph | Nodes | Prompts | Tests | Status |
|-------|----------|-------|---------|-------|--------|
| **DiscoveryAgent** | ✅ | 5 nodes | 3 prompts | ✅ Mock tests pass | **READY** |
| **JoinPlanAndSQLAgent** | ✅ | 5 nodes | 3 prompts | ✅ Mock tests pass | **READY** |
| **ExecAndRecoveryAgent** | ✅ | 8 nodes | 2 prompts | ✅ Mock tests pass | **READY** |
| **AnswerAgent** | ✅ | 6 nodes | 5 prompts | ✅ Mock tests pass | **READY** |

### 📋 DiscoveryAgent Details

**Subgraph Nodes:**
1. `search_candidates` — Search tables/views by keyword (MCP search_tables)
2. `rank_candidates` — Score by relevance + role_coverage + view_bonus
3. `filter_to_limit` — Keep ≤3 candidates with score ≥ 0.30
4. `describe_selected` — Fetch detailed metadata (MCP describe_table, cached)
5. `build_schema_snippet` — Build compact schema string

**Key Features:**
- Views-first strategy (prefer views with role_coverage ≥ 0.70)
- Hybrid ranking: 0.45×text_sim + 0.25×role_coverage + 0.15×subject + 0.10×has_rows + 0.05×is_view
- Session caching of described tables
- Tool-driven (deterministic, no LLM tie-breaking for now)

**Prompts:**
- `TABLE_FOCUS_PROMPT` — [Reserved] LLM tie-breaker if multiple candidates score equally
- `SCHEMA_VETTING_PROMPT` — [Reserved] Validate schema completeness
- `VIEWS_FIRST_GUIDANCE` — Inline guidance for views-first logic

---

### 📋 JoinPlanAndSQLAgent Details

**Subgraph Nodes:**
1. `check_view_coverage` — Check if any table is high-coverage view
2. `fetch_relations` — Get FK relationships (MCP list_relations)
3. `build_join_plan` — Design join strategy (view vs. ≤3 joins)
4. `generate_sql` — Generate MSSQL SELECT statement
5. `validate_sql` — Basic syntax checks (SELECT-only, balanced quotes/parens)

**Key Features:**
- MSSQL-first: TOP N, DATEADD, GETDATE(), fully-qualified names [dbo].[table]
- Views-first: if single view covers intent with role_coverage ≥ 0.70, use it
- Max 3 joins for safety (fact table + up to 2 dimensions)
- No DML: reject INSERT/UPDATE/DELETE/DROP/CREATE
- Validation: balanced quotes/parens, FROM clause required

**Prompts:**
- `JOIN_PLANNER_PROMPT` — [Reserved] LLM guide for complex join scenarios
- `SQL_GENERATOR_PROMPT_MSSQL` — [Inline] Generation template with MSSQL rules
- `VIEWS_PREFERENCE` — [Inline] Emphasis on view selection

---

### 📋 ExecAndRecoveryAgent Details

**Subgraph Nodes:**
1. `execute_query` — Execute via MCP query_bounded (safe: row caps, timeouts, redaction)
2. `check_result` — Route: success→END, error+retries→repair, out of retries→error
3. `repair_sql` — LLM-based SQL repair (attempt 1 of 2)
4. `retry_query` — Retry repaired SQL
5. `check_retry_result` — Route: success→END, fail+retries→simplify, out→error
6. `simplify_query` — Simplify query (fewer joins, more filters, sample)
7. `final_retry` — Final retry with simplified SQL
8. `prepare_error` — Format error for answer agent

**Key Features:**
- Read-only: MCP query_bounded enforces SELECT-only
- Safety: MAX_ROWS=1000, TIMEOUT=30s, auto redaction of sensitive columns
- Auto-repair: LLM analyzes error + schema + join_plan, suggests fix
- Max 2 retry attempts (default)
- Graceful degradation: simplify query if repair fails

**Prompts:**
- `SQL_REPAIR_PROMPT` — LLM analyzes error + schema + plan → fixed SQL
- `QUERY_SIMPLIFICATION` — LLM simplifies query (reduce joins, add filters)

---

### 📋 AnswerAgent Details

**Subgraph Nodes:**
1. `route_by_intent` — Route to formatter based on operation or error
2. `format_result` — Format query results as 1-2 sentence answer (NO tech details)
3. `explain_schema` — List main tables in 1-2 sentences
4. `format_error` — Friendly error + actionable suggestion
5. `format_clarification` — Ask ONE focused question grounded in schema
6. `format_health` — Report system status + table count

**Key Features:**
- 1-2 sentences ONLY (no verbose explanations)
- NO technical jargon (no "denormalized star schema", just "tables")
- Clarification questions use real column/table names from schema
- Error suggestions: "Try filtering by date" (if TIMEOUT), "Try reformulating" (if no results)

**Prompts:**
- `RESULT_FORMATTER_PROMPT` — LLM formats results as 1-2 sentence answer
- `SCHEMA_EXPLAINER_PROMPT` — LLM explains schema briefly
- `CLARIFICATION_PROMPT` — LLM asks ONE question grounded in real column names
- `ERROR_RESPONSE_PROMPT` — LLM creates user-friendly error + fix
- `HEALTH_CHECK_RESPONSE` — LLM formats system status

---

## 🔄 Orchestrator Graph (Next Phase)

The **Orchestrator** (in `graph_definition.py`) will:

1. Load Scout catalog (existing `index_database` node)
2. Parse intent (existing `parse_intent` node)
3. **Route by operation**:
   - `clarify` → AnswerAgent(clarify) → END
   - `schema_query` → DiscoveryAgent(schema) → AnswerAgent(schema_explain) → END
   - `health_check` → AnswerAgent(health) → END
   - `query` → DiscoveryAgent → JoinPlanAndSQLAgent → ExecAndRecoveryAgent → AnswerAgent → END
   - `execute_direct` (if parser gave SQL) → ExecAndRecoveryAgent → AnswerAgent → END
   - `sample_data` → (fetch sample, format, answer) → END

4. Compose agent subgraphs via `graph.add_node()` and `invoke()` or call directly

---

## 🧪 Testing Status

### ✅ Mock Tests (No MCP Required)

All 5 mock tests **PASS**:
- `test_mock_discovery_flow` — Keyword extraction, scoring, ranking
- `test_mock_join_planning` — Join plan building
- `test_mock_sql_generation` — SQL generation
- `test_mock_sql_validation` — SQL validation (SELECT-only, balanced quotes)
- `test_mock_answer_formatting` — Result & schema formatting

### 📝 Integration Tests (Require MCP)

Created but skipped (MCP not running):
- `test_discovery_agent_search_candidates` — Real MCP search
- `test_discovery_agent_full_flow` — End-to-end discovery
- `test_mcp_health_check` — MCP server connectivity

**To enable**: Set `MCP_SERVER_URL` and `API_KEY`, ensure Windows MCP server is running

---

## 🛠️ MSSQL Dialect Enforcement

All agents enforce MSSQL syntax:

| Feature | Correct | Incorrect |
|---------|---------|-----------|
| Row limit | `TOP 100` | `LIMIT 100` |
| Date math | `DATEADD(year, -1, GETDATE())` | `DATE_SUB(CURDATE(), INTERVAL...)` |
| Current time | `GETDATE()` | `NOW()` |
| Identifiers | `[Order Date]` or `dbo.table` | backticks, unqualified names |
| NULL handling | `ISNULL(col, 0)` | `COALESCE(col, 0)` ✅ both OK |
| Aggregates | `SELECT TOP 10 COUNT(*)` | `SELECT COUNT(*) LIMIT 10` |

Validation happens in:
- **JoinPlanAndSQLAgent**: `_validate_sql_node()` rejects non-SELECT
- **ExecAndRecoveryAgent**: Repair prompts emphasize MSSQL syntax
- **Prompts**: All SQL generation prompts include MSSQL-specific rules

---

## 📊 Safety & Performance

### Row Caps
- Default: `TOP 1000`
- Configurable per agent (ExecAndRecoveryAgent `row_limit` param)
- MCP query_bounded enforces at server level

### Timeouts
- Default: `30 seconds`
- Configurable per agent (ExecAndRecoveryAgent `query_timeout_seconds` param)
- Monitored by MCP query_bounded

### Redaction
- Handled by MCP query_bounded server-side
- Sensitive columns (password, email, ssn) auto-redacted
- Agents don't need to implement redaction

### Retry Strategy
- **Max retries**: 2 (default, configurable)
- **Attempt 1**: LLM repair (analyze error + schema + plan)
- **Attempt 2**: Query simplification (fewer joins, more filters)
- **Failure**: Ask user for clarification or suggest reformulation

---

## 🚀 Next Steps

1. **Refactor Orchestrator** (`graph_definition.py`)
   - Replace monolithic flow with agent composition
   - Implement operation routing
   - Invoke agent subgraphs

2. **Integration Testing**
   - Start Windows MCP server
   - Run full end-to-end tests
   - Validate views-first, joins-fallback, repair/retry

3. **Performance Tuning**
   - Benchmark agent latencies
   - Optimize caching (session_described_tables)
   - Profile LLM calls

4. **Production Readiness**
   - Error handling & logging
   - Observability (debug_logger integration)
   - Documentation for operators

---

## 📚 References

- **ADR-0012**: MCP-Only Architecture Migration
- **ADR-0014**: Scout Mode Semantic Caching
- **ADR-0016**: Phase 7 Orchestration & Multi-Agent System
- **repo.md**: Deployment topology & tool specifications
- **SYSTEM_ARCHITECTURE_PRODUCTION_V2.md**: Complete system diagram

---

*End of document. Ready for Orchestrator refactoring!*