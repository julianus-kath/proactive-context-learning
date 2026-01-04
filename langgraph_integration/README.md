# LangGraph Orchestrator – Supervisor-First Multi-Agent Flow

## Why

The Phase 9 orchestrator was hanging indefinitely due to two critical bugs:

1. **Aggressive Fallback Probing Loop** (`exec_recovery/agent.py`): When queries returned zero rows, the executor would make dozens of sequential MCP calls probing tables, views, and re-running semantic searches. This nested exception handler never escaped, causing the node to hang and never return state to downstream nodes.

2. **Cross-Boundary Windows/Mac Import** (`orchestrator.py`): The join planner imported `ViewsRanker` from `mcp_server.table_ranker`, violating the architecture principle that macOS should only communicate with Windows via the MCP client interface.

3. **Async Mismatch** (`sql_validator/agent.py`): Attempted to `await` a synchronous function `get_shared_mcp_tool()`.

These issues prevented state propagation through the complete pipeline, causing queries to fail silently or timeout.

## What

### Fixed Issues

1. **Removed Fallback Probing Loop** (lines ~273-462 in old `exec_recovery/agent.py`)
   - Deleted ~190 lines of aggressive fallback logic
   - Replaced with simple trust model: "Trust the result; let result_validator handle edge cases"
   - Node now returns immediately after query execution
   - Enables proper state propagation to downstream nodes

2. **Replaced Windows-Only Ranker** (lines ~840-880 in `orchestrator.py`)
   - Removed `from mcp_server.table_ranker import ViewsRanker` import
   - Implemented lightweight client-side heuristics using name/entity matching
   - Complex ranking remains on MCP server (Windows), accessed via proper client channels

3. **Fixed Async Initialization** (`sql_validator/agent.py` line 46)
   - Removed erroneous `await` on synchronous `get_shared_mcp_tool()` call

4. **Legacy Recursion Limit Handling** (pipeline graph)
   - The old fixed LangGraph pipeline used an `ainvoke()` wrapper with an increased
     `recursion_limit` to account for deep subgraphs and tool calls.
   - In the current supervisor-first design, recursion limits are replaced by
     explicit, testable budgets (`max_supervisor_steps`, `max_llm_calls_total`).

### Current Orchestration (React Supervisor)

The production path no longer executes the fixed LangGraph pipeline graph. Instead:

- `QueryOrchestrator.process_query()` builds an initial `BaseState` (user input,
  budgets, DB config) and delegates to the ReAct-style supervisor
  (`ReactSupervisor` in `langgraph_integration/supervisor.py`).
- The supervisor invokes capability tools (`interpret_query`, `discover_schema`,
  `plan_sql`, `validate_sql`, `execute_sql`, `evaluate_result`, `finalize_answer`)
  and owns retries, budgets, and stop conditions.
- Individual agents are single-pass tools that write well-defined fields on
  `BaseState` (`intent`, `relevant_tables`, `sql_query`, `validation_result`,
  `exec_result`, `final_response`, etc.) without implementing their own
  cross-agent loops.

The pipeline description below is kept for historical context. New integrations
should treat the supervisor path as the only supported orchestration model.

### Pipeline Architecture

The orchestrator now properly executes the complete query pipeline:

```
START
  ↓
index_database (MCP health check, Scout catalog verification)
  ↓
parse_intent (Semantic intent parsing, keyword extraction)
  ↓
route_operation (Conditional routing based on operation type)
  ├─→ query: discovery → join_sql → validate_sql → exec_recovery → result_validator → answer → END
  ├─→ schema_query: discovery_for_schema → answer_schema → END
  ├─→ health_check: answer_health → END
  ├─→ error: answer_error → END
  └─→ clarify: answer → END
```

**Key Flow for Data Queries:**

1. **Discovery**: Scout mode semantic search + semantic ranking → candidate tables/views
2. **Join & SQL**: Views-first strategy, FK analysis → MSSQL query generation
3. **Validation**: AST validation, syntax check, column existence → repair if needed
4. **Execution**: Row-capped, timeout-protected query execution via MCP
5. **Result Validation**: Check row counts, coverage, aggregation → decide retry/accept
6. **Answer**: Format results naturally, explain data provenance

## How to Run

### Quick Test

```bash
# Test single query end-to-end
python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, '.')

from langgraph_integration.orchestrator import QueryOrchestrator

async def test():
    orchestrator = QueryOrchestrator(llm_model="gpt-4o")
    
    result = await orchestrator.process_query(
        "Show me top 5 products by sales",
        messages=[],
        metadata={"eval_mode": "interactive"},
    )
    
    print(f"✅ Answer: {result.get('final_response', '')[:200]}")

asyncio.run(test())
EOF
```

### Production Usage

```python
from langgraph_integration.orchestrator import QueryOrchestrator

# Initialize once (expensive)
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    llm_temp=0.0,
    max_joins=3,
    max_retries=2,
    row_limit=1000,
    query_timeout_seconds=30
)

# High-level entrypoint used in production
result = await orchestrator.process_query(
    user_question,
    messages=conversation,
    metadata={"eval_mode": "interactive"},
)
```

### Orchestration Mode (`react_supervisor`)

The orchestrator now exposes a single supported orchestration mode:

- `react_supervisor`: a ReAct-style supervisor loop that calls the agents via
  capability tools and enforces validation/execution gates.

Any other requested mode (constructor arg, metadata, or env var) is coerced to
`react_supervisor` with a warning; the legacy `pipeline` graph has been removed.

You can configure the mode in three ways:

```python
# 1) Constructor (optional explicit mode)
orchestrator = QueryOrchestrator(orchestration_mode="react_supervisor")

# 2) Per-request metadata (still coerced to react_supervisor today)
result = await orchestrator.process_query(
    user_question,
    messages=conversation,
    metadata={"orchestration_mode": "react_supervisor"},
)

# 3) Environment variable default (used when constructor arg is None)
# export ORCHESTRATION_MODE=react_supervisor
orchestrator = QueryOrchestrator()  # picks up env default
```

Notes:
- All orchestration goes through the supervisor path; `BaseState` contracts and
  safety gates (validation before execution) are enforced by capability tools +
  supervisor policy.

### Using via FastAPI

```python
from chatbot_ui.langgraph_service import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.post('/chat', json={
    'message': 'Show me top customers',
    'conversation_history': []
})

print(response.json()['answer'])
```

## Tests

### Integration Tests (19 tests)

```bash
# All orchestrator integration tests
python3 -m pytest tests/test_orchestrator_integration.py -v

# Specific test
python3 -m pytest tests/test_orchestrator_integration.py::TestQueryOrchestrator::test_orchestrator_initialization -v
```

**Tests Cover:**
- ✅ Orchestrator initialization with all agents
- ✅ Graph node composition
- ✅ Intent parsing (query, schema_query, health_check)
- ✅ Agent composition and subgraph building
- ✅ State contract validation
- ✅ Conditional routing logic
- ✅ Factory pattern and singleton usage
- ✅ FastAPI integration

### End-to-End Tests

```bash
# Full pipeline test with MCP server
python3 tests/test_full_pipeline_e2e.py

# Or via pytest
python3 -m pytest tests/test_full_pipeline_e2e.py -v
```

**Prerequisites:**
- MCP server running (`192.168.1.35:8000`)
- Database connected and Scout catalog available
- `.env` with `MCP_SERVER_URL` and `MCP_API_KEY` configured

### MCP Connectivity Check

```bash
python3 tests/test_mcp_connectivity.py
```

Validates:
- Health endpoint responding
- TCP connectivity
- Tool call endpoint working
- Scout catalog healthy

## Configuration

### Environment Variables

```bash
# MCP Server (Windows/VPN)
MCP_SERVER_URL=http://192.168.1.35:8000
MCP_API_KEY=*** (your API key)

# LLM
OPENAI_API_KEY=sk-...

# Safety & Performance
RESULT_ROW_CAP=1000
QUERY_TIMEOUT_SECONDS=30
```

### Orchestrator Parameters

```python
QueryOrchestrator(
    llm_model="gpt-4o",           # LLM to use
    llm_temp=0.0,                 # Temperature (0=deterministic)
    max_joins=3,                  # Max joins in queries
    max_retries=2,                # Retry attempts on exec failure
    row_limit=1000,               # Default row cap
    query_timeout_seconds=30      # Query timeout
)
```

## Architecture Decisions

### Single Responsibility per Agent

Each agent handles one phase:

- **IntentParserAgent**: Extract operation type, entities, metrics, time windows
- **DiscoveryAgent**: Find relevant tables/views using Scout semantic search
- **JoinPlanAndSQLAgent**: Plan joins, generate MSSQL queries
- **SQLValidatorAgent**: Validate syntax, repair if needed
- **ExecAndRecoveryAgent**: Execute safely, handle timeouts/errors
- **ResultValidatorAgent**: Validate result quality, decide retries
- **AnswerAgent**: Format results naturally

**Simplified behavior (Phase C clean‑up):**

- **LLM‑first intent & templates**:
  - IntentParserAgent relies on LLM prompts and template classifiers for
    `operation`, entities/metrics, `keywords_for_discovery`, and
    `required_action`. Python logic only normalizes lengths and stores fields.
  - Legacy keyword/metric heuristics are no longer used to override LLM
    decisions.
- **Single‑pass discovery with light, configurable hints**:
  - DiscoveryAgent runs a single catalog search (tables + views) driven by
    `keywords_for_discovery` and optional `seed_tables` / `skip_tables`.
  - Column role and junk‑table heuristics are kept minimal and can be tuned via
    `DISCOVERY_DATE_TOKENS`, `DISCOVERY_ID_TOKENS`,
    `DISCOVERY_LABEL_TOKENS`, and `DISCOVERY_JUNK_TABLE_TOKENS`.
  - It does not run its own strategic/enrichment/fallback discovery loops;
    rediscovery decisions are left to the supervisor.
- **Bounded execution recovery**:
  - ExecAndRecoveryAgent executes a validated `sql_query` via MCP and may
    perform at most one LLM repair + retry and one LLM simplification + final
    retry (`max_retries <= 2` enforced in code).
  - It never rewrites queries based on local business heuristics; it only
    returns `exec_result` / `error_info` for the supervisor and ResultValidator.
- **Result‑driven routing**:
  - ResultValidator remains a deterministic checker that maps `exec_result`
    plus intent to a small `retry_action` enum
    (`accept`, `ask_user`, `try_next_candidate`, `replan_with_aggregation`,
    `replan_with_filter`).
  - The ReactSupervisor interprets these hints and owns all rediscovery,
    re‑planning, and clarification loops.

At the orchestration level, the **ReactSupervisor** acts as a project
manager for these agents:

- Maintains a world view over `BaseState` (intent, schema context,
  SQL, validation/execution results, and budgets).
- Decides which capability tool to call next based on
  `progress_signal`, `retry_action`, and `suggested_next_actions`.
- Owns all cross-agent loops (rediscovery, replan, revalidate,
  re-execute, fallback to clarification), so individual agents remain
  single-pass and stateless aside from their edits to `BaseState`.

### Trust Model for Execution

- Execute once, trust the result
- Don't probe the database for every zero-row response
- Let result_validator decide if retry/replan needed
- Keeps execution fast and state flowing properly

### Views-First Strategy

- Check business views first (pre-joined, curated data)
- Fall back to raw tables only if views don't cover intent
- Reduces join complexity and improves query quality

### Recursion / Budget Handling

- The supervisor loop is bounded by explicit budgets:
  - `max_supervisor_steps` – maximum tool invocations per query
  - `max_llm_calls` / `max_llm_calls_total` – global LLM call caps
- `process_query()` seeds safe defaults; callers can override per request via
  `metadata` (for example `{"max_supervisor_steps": 20}`) when needed.

## Observability

### Structured Logging

All logs include:
- Agent entry/exit markers (`🚀 AGENT ENTRY`, `✅ AGENT EXIT`)
- Operation status (✅ success, ❌ error, ⚠️ warning)
- Timing (duration_ms)
- Tool call traces (tool name, arguments, results)

Example:
```
INFO:langgraph_integration.orchestrator:🚦 [ROUTE] operation='query'
INFO:langgraph_integration.orchestrator:🔍 [DISCOVERY] ✅ Discovery subgraph completed
INFO:langgraph_integration.agents.exec_recovery.agent:✅ Query executed: 5 rows, 45ms
INFO:langgraph_integration.agents.result_validator.agent:✅ [RESULT_VALIDATOR] Valid=True, Action=accept
```

### Debug Logger

Enable detailed tracing:
```python
from langgraph_integration.debug_logger import get_debug_logger

debug_logger = get_debug_logger()
debug_logger.agent_entry("my_agent", state)
debug_logger.intent_parsed(intent, method="llm")
debug_logger.tool_called("search_tables", args, duration_ms)
```

Debug verbosity is controlled via environment variables:

- `LANGGRAPH_DEBUG_VERBOSE=1` – include full before/after state
  snapshots in `agent_entry`/`agent_exit` JSONL logs for deep
  debugging.
- Default / `LANGGRAPH_DEBUG_VERBOSE=0` – keep concise, high-value
  logs (agent names, changed keys, supervisor decisions, tool calls)
  without dumping entire state payloads.

## Notes

### Limitations

- Queries limited to ≤3 table joins (configurable via `max_joins`)
- Results capped at `RESULT_ROW_CAP` rows (default 1000, configurable)
- Queries timeout at `QUERY_TIMEOUT_SECONDS` (default 30s, configurable)
- No support for complex stored procedures (read-only SELECT only)
- Column name hallucinations prevented by column_index validation

### Known Constraints

- **Supervisor Budgets**: For very deep/complex queries, you may need to increase
  `max_supervisor_steps` and/or LLM budgets via `metadata` on `process_query`.
- **Cold Start**: First query ~2-3s (LLM models loading), subsequent queries ~1s
- **MCP Availability**: System depends on Windows MCP server being reachable over network

### Future Improvements

- Blueprint memory (cache successful plans)
- Router for domain-specific workspaces
- Graph/RAG integration for docs and lineage
- User study (UTAUT2) evaluation
- Query cost estimation
- Incremental result streaming

## References

- **ADR-0023**: Multi-Agent Orchestration Architecture
- **ADR-0024**: Comprehensive ERP Assistant Architecture
- **ADR-0012**: MCP-Only Architecture Migration
- **ADR-0014**: Scout Mode Semantic Caching
- **ADR-0015**: Semantic Table Ranking
- **Repo Overview**: `.zencoder/rules/repo.md`
