# ADR-0030: Simple SQL Agent Architecture
**Status**: Accepted
**Date**: 2026-01-07
**Author**: Julianus Kath


## Status
Accepted

## Date
2026-01-07

## Context

The existing NL-to-SQL system had a 0% success rate on benchmark queries despite its sophisticated architecture:

### Problems with the Previous System

1. **Over-engineering**: 8+ specialized agents (IntentParser, DiscoveryAgent, SQLBuilder, etc.) with a supervisor orchestrating them
2. **State explosion**: 150+ state fields making debugging nearly impossible
3. **Scout catalog dependency**: Required pre-populated semantic catalog that wasn't working correctly
4. **Intent parser failures**: Returning empty keywords, causing downstream failures
5. **Complex routing**: Multi-hop agent communication with state contract validation overhead

### Benchmark Results (Before)
- **ReAct Supervisor Branch (`react-integration`)**: 0/12 queries passed
- **Deterministic Pipeline Branch (`a-fresh-start`)**: 0/12 queries passed

## Decision

Replace the entire multi-agent system with a single ReAct agent using LangGraph's `create_react_agent` pattern with 4 simple tools.

### New Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Question                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ReAct Agent (GPT-4o)                       │
│                                                              │
│  System Prompt includes:                                     │
│  • MSSQL syntax rules (TOP, DATEADD, brackets)              │
│  • Domain concepts from concepts.json                        │
│  • KPI formulas and join hints                              │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ list_    │  │ get_     │  │ validate │  │ execute_ │
   │ tables   │  │ schema   │  │ _sql     │  │ query    │
   └──────────┘  └──────────┘  └──────────┘  └──────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (Windows)                      │
│                    HTTP JSON-RPC 2.0                         │
│                    Port 8000                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MSSQL Database                            │
│                    (On-Premise ERP)                          │
└─────────────────────────────────────────────────────────────┘
```

### Comparison

| Aspect | Before | After |
|--------|--------|-------|
| Agents | 8 specialized + supervisor | 1 ReAct agent |
| LLM calls/query | 15+ | 2-4 |
| State fields | 150+ | 10 |
| Tools | Complex MCP abstractions | 4 simple tools |
| Success rate | 0% | 58% |

## Implementation

### File Structure

```
simple_sql_agent/
├── __init__.py           # Package exports
├── agent.py              # Main ReAct agent using create_react_agent
├── state.py              # Minimal SQLAgentState (10 fields)
├── run_benchmark.py      # Benchmark runner
├── tools/
│   ├── __init__.py       # Tool exports
│   ├── db_tools.py       # list_tables, get_schema, execute_query
│   └── validation.py     # validate_sql
├── prompts/
│   ├── __init__.py
│   └── system.py         # System prompt with domain knowledge
├── db/
│   ├── __init__.py
│   └── mcp_client.py     # HTTP client for MCP server (JSON-RPC 2.0)
└── service.py            # FastAPI service (port 5002)
```

### Tools

1. **list_tables()**: Lists all available tables with row counts
2. **get_schema(table_names)**: Returns columns, types, and relationships
3. **validate_sql(sql)**: Checks MSSQL syntax before execution
4. **execute_query(sql)**: Executes SELECT queries via MCP server

### MCP Communication

The MCP client communicates with the Windows MCP server using JSON-RPC 2.0:

```python
payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "run_query",  # MCP tool name
        "arguments": {"sql": sql, "limit": 100}
    },
    "id": 1
}
response = await client.post("/mcp", json=payload)
```

### Domain Knowledge Injection

The system prompt includes domain concepts from `data/concepts.json`:
- KPI formulas (revenue, fulfillment time, etc.)
- Table relationships and join hints
- MSSQL-specific syntax rules

## Service Endpoints

### Simple SQL Agent Service (Port 5002)

```
POST /query
  Body: {"question": "Who are our top 5 customers?"}
  Returns: {"answer": "...", "sql_query": "...", "success": true}

GET /health
  Returns: {"status": "healthy", "service": "simple_sql_agent"}
```

## How to Start

### Prerequisites
1. MCP server running on Windows (port 8000)
2. `.env` file configured with:
   - `OPENAI_API_KEY`
   - `MCP_SERVER_URL` (e.g., `http://192.168.1.35:8000`)
   - `MCP_API_KEY`

### Start Command
```bash
./start_scripts/start_all_services_mac.sh
```

This starts:
- **Web UI** on port 3000
- **Simple SQL Agent** on port 5002
- **MCP Server** should already be running on Windows (port 8000)

### Port Configuration

| Service | Port | Description |
|---------|------|-------------|
| Web UI | 3000 | FastAPI web interface |
| Simple SQL Agent | 5001 | New simplified agent service (replaces old LangGraph) |
| MCP Server | 8000 | Windows database proxy |

## Benchmark Results

After implementation:
- **Pass (useful answer)**: 7/12 (58%)
- **Partial (SQL generated)**: 0/12
- **Fail/Error**: 5/12 (42%)

Note: Some failures are due to schema mismatch - benchmark queries expect Northwind schema but the production database has German ERP tables with different naming.

## Example Flow

**User**: "Who are our top 5 customers by revenue?"

1. **Agent thinks**: Need customer and order data for revenue calculation
2. **Tool call**: `list_tables()` - discovers available tables
3. **Tool call**: `get_schema(["dbo.Customers", "dbo.Orders", "dbo.[Order Details]"])`
4. **Agent writes SQL**: Uses KPI formula from concepts.json
5. **Tool call**: `validate_sql(sql)` - checks syntax
6. **Tool call**: `execute_query(sql)` - runs query
7. **Agent answers**: Natural language summary of results

**Total LLM calls: 3** (vs 15+ in the old system)

## Consequences

### Positive
- Dramatically simpler architecture (1 agent vs 8+)
- Faster response times (fewer LLM calls)
- Easier debugging (10 state fields vs 150+)
- No Scout catalog dependency
- 58% success rate (up from 0%)

### Negative
- Less specialized handling for edge cases
- Single point of failure (one agent)
- May need prompt engineering for complex queries

### Neutral
- Still depends on MCP server for database access
- Domain knowledge now embedded in prompts instead of agents

## Future Improvements

1. Create benchmark queries matching actual production schema
2. Add few-shot examples for common query patterns
3. Implement query result caching
4. Add confidence scoring to answers

## References

- LangGraph ReAct Agent: https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/
- MCP Protocol: Model Context Protocol specification
- Previous ADRs: 0018, 0023, 0029 (multi-agent architecture)
