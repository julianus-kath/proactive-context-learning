# Multi-Agent System — Quick Start Guide

**Ready to use!** This guide shows how to use the new multi-agent system for query processing.

---

## 📦 Installation & Setup

### 1. Prerequisites
- Python 3.11+
- LangChain + LangGraph installed
- MCP server running (Windows, port 8000)
- Environment variables set:
  ```bash
  export MCP_SERVER_URL="http://192.168.1.35:8000"  # Windows host IP
  export API_KEY="your-mcp-api-key"
  export OPENAI_API_KEY="your-openai-key"
  ```

### 2. Files Location
All new code is in:
```
langgraph_integration/
├── agents/              # 4 agent modules
├── contracts/           # State contracts
├── prompts/             # Agent-specific prompts
└── orchestrator.py      # Main orchestrator
```

---

## 🚀 Quick Start (5 minutes)

### Step 1: Import and Initialize
```python
from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState

# Create orchestrator (all agents initialized)
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    max_joins=3,
    max_retries=2
)

# Build the graph
graph = orchestrator.build_graph()
```

### Step 2: Create Input State
```python
initial_state = BaseState(
    user_input="Show me top 5 customers by total orders",
    messages=[],                      # Conversation history (optional)
    session_described_tables={},      # Cache (auto-populated)
    retry_count=0
)
```

### Step 3: Run the Query
```python
# Invoke the graph
result = graph.invoke(initial_state)

# Get the final answer
answer = result["final_response"]
print(answer)
# Output: "The top 5 customers are: Acme Corp ($50k), Widget Inc ($45k), ..."
```

---

## 📋 Common Use Cases

### Query Execution
```python
state = BaseState(
    user_input="How many orders were placed last month?",
    messages=[],
    session_described_tables={},
    retry_count=0
)

result = graph.invoke(state)
print(result["final_response"])
# Output: "150 orders were placed last month."
```

### Schema Explanation
```python
state = BaseState(
    user_input="What tables are available?",
    messages=[],
    session_described_tables={},
    retry_count=0
)

result = graph.invoke(state)
print(result["final_response"])
# Output: "Main tables: customers, orders, products, and invoices."
```

### Health Check
```python
state = BaseState(
    user_input="Is the system working?",
    messages=[],
    session_described_tables={},
    retry_count=0
)

result = graph.invoke(state)
print(result["final_response"])
# Output: "System is running. Database connected with 150 tables."
```

---

## 🔍 Understanding the Flow

### What Happens Inside
```
Your Query: "Show me top 5 customers"
    ↓
[QueryOrchestrator]
    ├─ index_database: Load Scout catalog
    ├─ parse_intent: Identify "query" operation
    ├─ route_operation: Route to agent flow
    │
    ├─ DiscoveryAgent:
    │   ├─ Search for "customers" tables (MCP search_tables)
    │   ├─ Rank candidates by relevance + role_coverage
    │   ├─ Filter to ≤3 (usually 1-2 best matches)
    │   ├─ Describe selected tables (get columns, FKs)
    │   └─ Build compact schema snippet
    │
    ├─ JoinPlanAndSQLAgent:
    │   ├─ Check for high-coverage views (views-first)
    │   ├─ Fetch FK relationships
    │   ├─ Plan joins (fact + dimensions, ≤3 joins)
    │   ├─ Generate MSSQL: "SELECT TOP 5 ... ORDER BY total DESC"
    │   └─ Validate SQL syntax
    │
    ├─ ExecAndRecoveryAgent:
    │   ├─ Execute query via MCP (safe: row caps, timeouts)
    │   ├─ On success: return results
    │   ├─ On error: repair SQL + retry (max 2 attempts)
    │   └─ Return exec_result or error_info
    │
    └─ AnswerAgent:
        ├─ Format results as 1-2 sentence answer
        └─ Return: "The top 5 customers are: Acme ($50k), Widget Inc ($45k), ..."
    ↓
Final Answer
```

### State at Each Stage
```python
# After Discovery
state["relevant_tables"] = ["dbo.customers", "dbo.orders"]
state["schema_snippet"] = "dbo.customers: id (int), name (varchar), ...
                           dbo.orders: id (int), customer_id (int FK), total (decimal)"

# After JoinSQL
state["join_plan"] = {
    "strategy": "joins",
    "primary_table": "dbo.customers",
    "joins": [{"table": "dbo.orders", "on": "customers.id = orders.customer_id"}]
}
state["sql_query"] = "SELECT TOP 5 c.name, SUM(o.total) as total FROM dbo.customers c
                      INNER JOIN dbo.orders o ON c.id = o.customer_id
                      GROUP BY c.name ORDER BY total DESC"

# After Execution
state["exec_result"] = {
    "ok": True,
    "rows": [
        {"name": "Acme Corp", "total": 50000},
        {"name": "Widget Inc", "total": 45000},
        ...
    ],
    "row_count": 5,
    "execution_time_ms": 234
}

# After Answer
state["final_response"] = "The top 5 customers are: Acme Corp ($50k), Widget Inc ($45k), ..."
```

---

## ⚙️ Configuration Options

### Adjust Join Complexity
```python
# For simpler queries (fewer joins)
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    max_joins=2            # Fewer joins allowed
)

# For complex queries (more joins)
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    max_joins=4            # More joins allowed
)
```

### Adjust Retry Attempts
```python
# More aggressive retry
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    max_retries=3          # More retry attempts
)

# Fast fail
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    max_retries=1          # Only 1 attempt
)
```

### Adjust Row Limits & Timeouts
```python
orchestrator = QueryOrchestrator(
    llm_model="gpt-4o",
    row_limit=500,                    # Smaller results
    query_timeout_seconds=15          # Shorter timeout
)
```

---

## 🧪 Testing

### Run Mock Tests (No MCP Required)
```bash
# Test core agent logic
pytest tests/test_multi_agent_system.py -k "mock" -v -s

# Test orchestrator
pytest tests/test_orchestrator.py -v -s
```

### Run Integration Tests (Requires MCP)
```bash
# Test with real MCP server
pytest tests/test_discovery_agent.py -v -s
pytest tests/test_multi_agent_system.py -v -s
```

### Manual Testing
```python
from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState

# Create and test
orchestrator = QueryOrchestrator()
graph = orchestrator.build_graph()

# Test different query types
test_queries = [
    "Show me top 10 products by sales",
    "What tables exist?",
    "Is the system healthy?",
]

for query in test_queries:
    state = BaseState(
        user_input=query,
        messages=[],
        session_described_tables={},
        retry_count=0
    )
    result = graph.invoke(state)
    print(f"Q: {query}")
    print(f"A: {result['final_response']}")
    print()
```

---

## 🐛 Troubleshooting

### Error: "MCP server is not responding"
- **Check**: Windows MCP server is running (port 8000)
- **Check**: `MCP_SERVER_URL` is correct
- **Check**: Network connectivity to Windows host
- **Fix**: Start MCP server, verify environment variables

### Error: "No tables found for keywords"
- **Cause**: Query keywords don't match database table names
- **Fix**: Try more specific keywords (e.g., "customer" instead of "people")
- **Check**: Tables exist in database (use "What tables exist?" query)

### Error: "Query timed out"
- **Cause**: Query is too complex (many joins, large result set)
- **Fix**: Add more specific filters (e.g., "last 30 days")
- **Fix**: Increase timeout: `query_timeout_seconds=60`
- **Fix**: Reduce row limit: `row_limit=500`

### Error: "SQL validation failed"
- **Cause**: Generated SQL has syntax error
- **Check**: LLM repair is working (check logs for "repair attempt")
- **Fix**: Clarify intent (use simpler query)
- **Fix**: Provide more context ("Q4 2024 sales" instead of just "sales")

### Error: "All retry attempts failed"
- **Cause**: Query cannot be fixed by repair/simplification
- **Action**: System will ask user for clarification
- **Fix**: Reformulate question more clearly
- **Check**: Required tables exist in database

---

## 📊 Performance Tips

### Speed Up Queries
1. **Be specific**: "Top 5 customers" (faster) vs "All customers with any orders" (slower)
2. **Use time filters**: "Sales this quarter" (faster) vs "All sales" (slower)
3. **Limit results**: "Top 10" (faster) vs "Top 1000" (slower)

### Avoid Timeouts
1. **Pre-filter data**: Use specific date ranges
2. **Reduce joins**: System auto-limits to ≤3 joins
3. **Increase timeout** (if needed): `query_timeout_seconds=60`

### Leverage Caching
1. **Session reuse**: Use same `orchestrator` instance for multiple queries
2. **Cache tables**: `session_described_tables` is populated after first query
3. **Batch queries**: Process similar queries together

---

## 🔐 Security Considerations

### Data Privacy
- ✅ Read-only queries only (SELECT)
- ✅ Row limits enforced (default 1000)
- ✅ Sensitive columns redacted (password, email, SSN)
- ✅ MCP server validates all queries

### Access Control
- ✅ API key required (MCP_API_KEY)
- ✅ VPN access only (MSSQL on Windows host)
- ✅ Audit logs available (debug_logger)

### Query Safety
- ✅ No SQL injection (parameterized via MCP)
- ✅ Syntax validation (SELECT-only, balanced quotes/parens)
- ✅ Timeout protection (30s default, configurable)

---

## 📚 Additional Resources

### Architecture
- `docs/MULTI_AGENT_ARCHITECTURE.md` — Full architecture spec
- `docs/SYSTEM_ARCHITECTURE_PRODUCTION_V2.md` — Deployment topology

### Code Examples
- `tests/test_multi_agent_system.py` — Agent usage examples
- `tests/test_orchestrator.py` — Orchestrator usage examples

### Implementation Details
- `langgraph_integration/agents/discovery/agent.py` — Discovery logic
- `langgraph_integration/agents/join_sql/agent.py` — Join planning
- `langgraph_integration/agents/exec_recovery/agent.py` — Execution & repair
- `langgraph_integration/agents/answer/agent.py` — Result formatting

---

## ✅ Next Steps

1. **Test locally** with mock tests (no MCP needed)
   ```bash
   pytest tests/test_multi_agent_system.py -k "mock" -v -s
   ```

2. **Start MCP server** on Windows (port 8000)

3. **Run integration tests** with real database
   ```bash
   pytest tests/test_discovery_agent.py -v -s
   ```

4. **Integrate into web UI** (use `orchestrator.build_graph()` in FastAPI)

5. **Monitor in production** (check logs, metrics, errors)

---

## 📞 Support

- **Architecture questions**: See `docs/MULTI_AGENT_ARCHITECTURE.md`
- **Test failures**: Check `tests/` for examples
- **Performance issues**: See "Performance Tips" section
- **Bugs/Issues**: File issue with query example + logs

---

*Quick Start Guide — January 2025*