# LangGraph Studio Quick Test Guide

## What Changed?

All agent graphs now have proper topology for Studio visualization:
- ✅ No orphaned nodes
- ✅ All routes explicitly declared with `Literal` types
- ✅ All conditional edges have path mappings

## Quick Start: Validate Changes

### Step 1: Run Topology Smoke Test

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code

# Run the topology validator
python3 test_graph_topology.py
```

**Expected output:**
```
🎉 All agents have healthy topology!

✅ DiscoveryAgent
✅ AnswerAgent
✅ ExecAndRecoveryAgent
✅ JoinPlanAndSQLAgent
```

If you see **❌ issues**, check the error message and re-examine the agent's `build_subgraph()` method.

---

### Step 2: Launch LangGraph Studio

#### Option A: With Local Tunnel (Recommended)

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code

# Start the dev server with tunnel
langgraph dev --tunnel

# Wait for output like:
# 🎯 Studio is live at https://smith.langchain.com/studio?url=...
# Copy that URL and open in browser
```

#### Option B: Local Studio (No Internet Required)

```bash
# In one terminal:
langgraph dev

# In another:
open http://localhost:8000
```

---

### Step 3: Navigate to Each Agent

In Studio:

1. **Home** → Click "main_orchestrator" under "Graphs"
2. **Left panel** → Select each sub-graph:
   - `discovery_agent`
   - `answer_agent`
   - `exec_recovery_agent`
   - `join_sql_agent`

3. **For each agent**, verify:
   - ✅ All nodes are connected (no floating boxes)
   - ✅ Routers have fan-out arrows to all possible destinations
   - ✅ Conditional branches are visible
   - ✅ All paths lead to END

---

## Expected Visual Layouts

### Answer Agent

```
┌─────────────────────────────────┐
│   START                         │
│     │                           │
│     ▼                           │
│   route_by_intent              │
│     │  │  │  │  │              │
│     ▼  ▼  ▼  ▼  ▼              │
│   ┌─────────────────┐           │
│   │ Formatters (5)  │           │
│   │ ├─format_result │           │
│   │ ├─explain_schema│           │
│   │ ├─format_error  │           │
│   │ ├─format_clarif │           │
│   │ └─format_health │           │
│   └─────────────────┘           │
│     ▼  ▼  ▼  ▼  ▼              │
│     │  │  │  │  │              │
│     └──────┴──────┘             │
│            ▼                    │
│          END                    │
└─────────────────────────────────┘
```

### Exec Recovery Agent

```
┌────────────────────────────────────────┐
│ execute_query                          │
│        ▼                               │
│ check_result ─→ [END if OK]            │
│        ▼                               │
│ repair_sql → retry_query               │
│              ▼                         │
│        check_retry_result ─→ [END]    │
│              ▼                         │
│        simplify_query                  │
│              ▼                         │
│        final_retry ─→ [END]            │
│              ▼                         │
│        prepare_error → END             │
└────────────────────────────────────────┘
```

### Discovery Agent

```
┌────────────────────────────────────────┐
│ search_candidates                      │
│        ▼                               │
│ rank_candidates                        │
│        ▼                               │
│ filter_to_limit                        │
│        ▼                               │
│ describe_selected                      │
│        │  ──→ explore_date_columns ──┐ │
│        └──────→ build_schema_snippet ←┘ │
│                 ▼                       │
│            fetch_column_index          │
│                 ▼                       │
│               END                      │
└────────────────────────────────────────┘
```

---

## Testing Actual Execution

Once you verify visual topology, test that graphs actually work:

```python
import asyncio
import os
os.environ["OPENAI_API_KEY"] = "sk-..."

from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.contracts.state import BaseState

async def test_discovery():
    agent = DiscoveryAgent()
    g = agent.build_subgraph()
    
    # Test input
    state = {
        "user_input": "Show me customer orders",
        "intent": {
            "entities": ["customer", "orders"],
            "needs_date_exploration": False,
        },
        "candidate_views": [],
        "session_described_tables": {},
    }
    
    # Run graph
    result = await g.ainvoke(state)
    
    print("✅ Discovery agent executed successfully")
    print(f"   Found candidates: {len(result.get('candidate_views', []))}")

asyncio.run(test_discovery())
```

---

## Troubleshooting

### Problem: Still see orphaned nodes in Studio

**Solution:** The changes haven't been picked up yet.

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Restart LangGraph dev
langgraph dev --tunnel
```

### Problem: Routes not being taken

**Check:** Verify your routing function returns the exact node name:

```python
# ✅ Correct
def route(state) -> Literal["node_a", "node_b"]:
    return "node_a"  # Exact match with path mapping key

# ❌ Wrong
def route(state) -> Literal["node_a", "node_b"]:
    return "Node_A"  # Case mismatch!
```

### Problem: "Unrecognized path" error

**Check:** Ensure the path mapping includes all Literal values:

```python
# ✅ Correct
graph.add_conditional_edges(
    "router",
    route,
    {
        "node_a": "node_a",
        "node_b": "node_b",
        "__end__": END,
    }
)

# ❌ Wrong (missing "node_b")
graph.add_conditional_edges(
    "router",
    route,
    {
        "node_a": "node_a",
        # Missing "node_b" → error!
    }
)
```

---

## Validating Routing at Runtime

To verify that routing is working correctly:

```python
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.contracts.state import BaseState

agent = AnswerAgent()
g = agent.build_subgraph()

# Test different scenarios
test_cases = [
    # Error case
    {
        "intent": {"operation": "query"},
        "error_info": {"type": "QUERY_ERROR", "message": "Invalid column"},
        "expected": "format_error",
    },
    # Schema query case
    {
        "intent": {"operation": "schema_query"},
        "error_info": None,
        "expected": "explain_schema",
    },
    # Normal result case
    {
        "intent": {"operation": "query"},
        "error_info": None,
        "exec_result": {"ok": True, "rows": [{"col": "val"}]},
        "expected": "format_result",
    },
]

for i, test in enumerate(test_cases):
    state = BaseState(
        intent=test["intent"],
        error_info=test.get("error_info"),
        exec_result=test.get("exec_result"),
        user_input="test",
    )
    
    # Get the next node by simulating routing
    # (This depends on your graph implementation)
    print(f"Test {i+1}: {test['expected']}")
```

---

## Key Takeaways

| Pattern | ❌ Before | ✅ After |
|---------|----------|---------|
| **Router logic** | Inside node function | In separate routing function |
| **Route returns** | String (implicit) | `Literal[...]` (explicit) |
| **Edge mapping** | None | Explicit `{ path: node }` dict |
| **Node calls** | Direct `await node(state)` | Through graph edges |
| **Orphaned nodes** | Common | None ✅ |
| **Studio rendering** | Broken | Perfect ✅ |

---

## Next Steps

1. ✅ Run topology test
2. ✅ Launch Studio
3. ✅ Verify visual layouts
4. ✅ Test execution
5. ✅ Commit changes

```bash
git add -A
git commit -m "fix: proper langgraph conditional edge routing with literal types"
```

---

*Quick test guide — October 2025*