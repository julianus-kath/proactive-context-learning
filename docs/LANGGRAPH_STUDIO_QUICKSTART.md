# LangGraph Studio - Quick Start Guide

## Before You Begin
Make sure you have:
- `.env` file with `OPENAI_API_KEY` and `MCP_API_KEY` set
- LangGraph CLI installed: `pip install -U langgraph-cli`
- All fixes applied (see `LANGGRAPH_STUDIO_FIX_COMPLETE.md`)

---

## Step 1: Start the Dev Server

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code
langgraph dev --tunnel
```

**Expected output:**
```
Resolved graph paths for graphs in /Users/juli/Desktop/.../code/langgraph.json

Found 5 graphs:
  • main_orchestrator
  • discovery_agent
  • join_sql_agent
  • exec_recovery_agent
  • answer_agent

LangGraph Studio running at:
https://dev-XXXX.langchain.run/?baseUrl=https://dev-XXXX.langchain.run
```

---

## Step 2: Verify Graphs Are Available

In another terminal, test the graphs endpoint:

```bash
curl http://localhost:8000/graphs
```

**Expected response:**
```json
["main_orchestrator","discovery_agent","join_sql_agent","exec_recovery_agent","answer_agent"]
```

---

## Step 3: Open LangGraph Studio

Click the URL from Step 1 or navigate to:
```
https://dev-XXXX.langchain.run/?baseUrl=https://dev-XXXX.langchain.run
```

---

## Step 4: Select and Preview a Graph

1. Click the **dropdown** at the top of the left panel
2. Select a graph (e.g., `discovery_agent`)
3. Click **"Preview Graph"**

**Expected result:** Graph visualization appears (no "Failed to fetch" error)

---

## Step 5: Test the Graph

1. At the bottom, click **"Chat"** tab
2. Type a test input:
   ```
   Show me all customers in the database
   ```
3. Click **"Send"** or press Enter
4. Watch the graph execute step-by-step in the graph view
5. See the result in the chat panel

---

## Troubleshooting

### ❌ Error: "Failed to preview graph"
- Check: Are all builders synchronous? (Run `pytest tests/test_langgraph_studio_builders.py`)
- Check: Do all builders return `CompiledStateGraph`?
- Check: Are environment variables set correctly?

### ❌ Error: "This event loop is already running"
- This is the bug that was fixed. If you see it, the builders still have asyncio loop management.
- Verify fixes were applied to all 4 agent files.
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +` (ignore errors)

### ❌ Error: "OPENAI_API_KEY not found"
- Ensure `.env` file exists in the project root
- Ensure it contains: `OPENAI_API_KEY=sk-...`

### ❌ Error: "MCP connection failed"
- Ensure MCP server is running (if required for your setup)
- Check: `MCP_API_KEY` is set in `.env`

---

## Testing Each Graph

### Main Orchestrator
**Entry point:** The overall query processing workflow
**Test:** Any natural language query
```
How many products do we have?
```

### Discovery Agent
**Entry point:** Table/view search and ranking
**Test:** Keywords from your schema
```
Find tables related to sales
```

### Join SQL Agent
**Entry point:** Join planning and SQL generation
**Test:** Multi-table queries
```
Combine customer and order data
```

### Exec Recovery Agent
**Entry point:** Query execution with retry logic
**Test:** SQL execution scenarios
```
Execute a sales report query
```

### Answer Agent
**Entry point:** Result formatting and response generation
**Test:** Answer formatting
```
Format the results in natural language
```

---

## Debug: View Full Graph Definition

In Studio:
1. Select a graph from dropdown
2. Click **"Show Code"** (if available)
3. View the graph structure: nodes, edges, conditional routing

Or in Python:
```python
from langgraph_integration.agents.discovery.agent import build_discovery_graph

graph = build_discovery_graph()
print(graph.get_graph().draw_ascii())
```

---

## Next: Advanced Usage

Once graphs are working in Studio:

1. **Edit graphs:** Modify node logic and see changes instantly in Studio
2. **Debug execution:** Use Studio's step-by-step view to trace execution
3. **Export:** Studio can export graph definitions for deployment
4. **Monitor:** Watch tool calls, errors, and state transitions

---

## Environment Variables Reference

For LangGraph dev server to work:

```env
# OpenAI
OPENAI_API_KEY=sk-...

# MCP Server (if using MCP tools)
MCP_HOST=localhost
MCP_PORT=8000
MCP_API_KEY=...

# Optional: LangSmith tracing
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=false  # Set to false if no tracing needed
```

---

## Quick Check: All Builders Working?

```bash
python3 << 'PY'
from langgraph_integration.graph_definition import build_graph
from langgraph_integration.agents.discovery.agent import build_discovery_graph
from langgraph_integration.agents.join_sql.agent import build_join_sql_graph
from langgraph_integration.agents.exec_recovery.agent import build_exec_recovery_graph
from langgraph_integration.agents.answer.agent import build_answer_graph

for name, fn in [
    ("main_orchestrator", build_graph),
    ("discovery_agent", build_discovery_graph),
    ("join_sql_agent", build_join_sql_graph),
    ("exec_recovery_agent", build_exec_recovery_graph),
    ("answer_agent", build_answer_graph),
]:
    try:
        g = fn()
        print(f"✅ {name}: {type(g).__name__}")
    except Exception as e:
        print(f"❌ {name}: {e}")
PY
```

---

## Status Checklist
- [ ] All 5 graphs compile without errors (run quick check above)
- [ ] `langgraph dev --tunnel` starts successfully
- [ ] `/graphs` endpoint returns all 5 graph names
- [ ] Studio opens without errors
- [ ] Can preview at least one graph
- [ ] Can send a test message and see execution

✅ When all checks pass, LangGraph Studio is ready to use!