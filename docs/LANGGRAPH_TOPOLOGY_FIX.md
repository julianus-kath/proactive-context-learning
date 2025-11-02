# LangGraph Topology Fix — October 2025

## Summary

Fixed **orphaned nodes** appearing in LangGraph Studio by properly configuring conditional edge routing with explicit `Literal` return types and path mappings.

### Status
✅ **All agents now have healthy topology** (no orphaned nodes)

---

## Root Cause Analysis

### Problem: Orphaned Nodes in Studio

Nodes appeared disconnected (floating boxes with no lines) due to:

1. **Missing edge mappings**: Routers returned string values but had no explicit path maps
2. **Implicit routing**: Nodes calling other nodes directly instead of using graph edges
3. **Lack of Literal typing**: Without `Literal[...]` return types, Studio couldn't infer possible route destinations

### Impact

- **Answer Agent** (WORST): Called formatters directly from `route_by_intent_node`, bypassing graph structure
- **Exec Recovery Agent**: Conditional edges lacked path mappings
- **Discovery Agent**: Routing wasn't explicit enough for Studio
- **Join SQL Agent**: ✅ Already correct

---

## Fixes Applied

### 1. Answer Agent (`langgraph_integration/agents/answer/agent.py`)

**Before:**
```python
# ❌ Anti-pattern: Router calls other nodes directly
async def _route_by_intent_node(self, state: BaseState) -> BaseState:
    if error_info:
        return await self._format_error_node(state)  # WRONG!
    ...
    return await self._format_result_node(state)
```

**After:**
```python
# ✅ Proper pattern: Router is passthrough, edges handle routing
async def _route_decision_node(self, state: BaseState) -> BaseState:
    """Passthrough node; routing is handled by conditional_edges."""
    return state

# Define routing function with explicit Literal return type
def route_by_intent(state: BaseState) -> Literal[
    "format_result", "explain_schema", "format_error", 
    "format_clarification", "format_health"
]:
    """Routing decision function."""
    if error_info and error_info.get("type"):
        return "format_error"
    elif operation == "clarify":
        return "format_clarification"
    ...

# Wire with explicit path mapping
graph.add_conditional_edges(
    "route_by_intent",
    route_by_intent,
    {
        "format_result": "format_result",
        "explain_schema": "explain_schema",
        "format_error": "format_error",
        "format_clarification": "format_clarification",
        "format_health": "format_health",
    }
)
```

**Result:**
- `route_by_intent` → all 5 formatters (fan-out routing)
- Each formatter → `__end__`
- No orphaned nodes ✅

---

### 2. Exec Recovery Agent (`langgraph_integration/agents/exec_recovery/agent.py`)

**Before:**
```python
# ❌ Missing path mappings
def route_from_check_result(state: BaseState) -> str:
    if success:
        return END
    elif can_retry:
        return "repair_sql"
    else:
        return "prepare_error"

graph.add_conditional_edges("check_result", route_from_check_result)
# ^ No path map! Studio can't see edges to repair_sql, prepare_error, END
```

**After:**
```python
# ✅ Explicit Literal type + path mapping
def route_from_check_result(state: BaseState) -> Literal[
    "repair_sql", "prepare_error", "__end__"
]:
    ...

graph.add_conditional_edges(
    "check_result",
    route_from_check_result,
    {
        "repair_sql": "repair_sql",
        "prepare_error": "prepare_error",
        "__end__": END,
    }
)
```

**Result:**
- Recovery loop properly wired: `execute_query` → `check_result` → `repair_sql` → `retry_query` → `check_retry_result` → `simplify_query` → `final_retry` → `prepare_error` → `__end__`
- All 8 nodes now have proper connectivity ✅

---

### 3. Discovery Agent (`langgraph_integration/agents/discovery/agent.py`)

**Before:**
```python
# Plain string return type (less explicit)
def route_to_exploration(state: BaseState) -> str:
    if needs_date_exploration:
        return "explore_date_columns"
    return "build_schema_snippet"

graph.add_conditional_edges("describe_selected", route_to_exploration)
# No explicit mapping
```

**After:**
```python
# Explicit Literal type + path mapping
def route_to_exploration(state: BaseState) -> Literal[
    "explore_date_columns", "build_schema_snippet"
]:
    ...

graph.add_conditional_edges(
    "describe_selected",
    route_to_exploration,
    {
        "explore_date_columns": "explore_date_columns",
        "build_schema_snippet": "build_schema_snippet",
    }
)
```

**Result:**
- Linear pipeline: `search_candidates` → `rank_candidates` → `filter_to_limit` → `describe_selected` → [optional: `explore_date_columns`] → `build_schema_snippet` → `fetch_column_index` → `__end__`
- All 7 nodes properly connected ✅

---

### 4. Join SQL Agent

✅ **Already correct** — no changes needed. Linear pipeline works as intended.

---

## Verification: Smoke Test Results

```
🎉 All agents have healthy topology!

✅ DiscoveryAgent
   - 7 nodes, 9 edges
   - No orphaned nodes
   - Conditional routing explicit

✅ AnswerAgent
   - 6 nodes, 11 edges
   - Router fans out to 5 formatters
   - All paths defined

✅ ExecAndRecoveryAgent
   - 8 nodes, 14 edges
   - Recovery loop fully wired
   - No orphaned nodes

✅ JoinPlanAndSQLAgent
   - 5 nodes, 6 edges
   - Linear pipeline
   - No orphaned nodes
```

Run verification:
```bash
python3 /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code/test_graph_topology.py
```

---

## Testing in LangGraph Studio

Now graphs will display properly without orphaned nodes:

```bash
langgraph dev --tunnel
# Open the printed URL
# Visit /agents/main_orchestrator
# Visualize each sub-graph
```

Expected layout (Answer Agent):
```
  START
    ↓
route_by_intent
  ↙ ↓ ↓ ↓ ↘
 5 formatter nodes (all connected to END)
    ↓ ↓ ↓ ↓
   END (all converge)
```

Expected layout (Exec Recovery Agent):
```
execute_query
  ↓
check_result ──→ END (if ok)
  ↓
repair_sql → retry_query → check_retry_result ──→ END (if ok)
                             ↓
                          simplify_query → final_retry ──→ END (if ok)
                                             ↓
                                         prepare_error → END
```

---

## Code Standards Applied

✅ **Explicit routing with Literal types**
- All routers return `Literal["destination1", "destination2", ...]`
- Studio can infer all possible destinations

✅ **Path mappings for conditional edges**
- Every `add_conditional_edges()` includes a dictionary mapping
- Format: `{ return_value: target_node, ... }`

✅ **Separation of concerns**
- Router nodes are now passthrough (no business logic)
- Routing function contains decision logic
- Graph edges orchestrate flow

✅ **No orphaned nodes**
- Every user-defined node has at least one incoming and one outgoing edge (or connects to `START`/`END`)

✅ **Type safety**
- All routing functions are properly typed
- LangGraph can validate routes at compile time

---

## Files Modified

1. `langgraph_integration/agents/answer/agent.py` — Fixed router to use conditional_edges
2. `langgraph_integration/agents/exec_recovery/agent.py` — Added path mappings to all conditional_edges
3. `langgraph_integration/agents/discovery/agent.py` — Added explicit Literal types + path mapping
4. `test_graph_topology.py` — Created smoke test for topology validation

---

## Next Steps

1. **Test in Studio**: Run `langgraph dev --tunnel` and verify visual layout
2. **Run integration tests**: Ensure all agents still execute correctly
3. **Monitor logs**: Watch for any routing errors (fallback logic will activate)
4. **Document patterns**: These fixes are now the standard for all new agents

---

## Reference: LangGraph Conditional Edges Best Practice

```python
from typing import Literal
from langgraph.graph import StateGraph, END

# ✅ DO THIS:
def router(state) -> Literal["path_a", "path_b", "__end__"]:
    if condition:
        return "path_a"
    elif other_condition:
        return "path_b"
    else:
        return "__end__"

graph.add_conditional_edges(
    "router_node",
    router,
    {
        "path_a": "node_a",
        "path_b": "node_b",
        "__end__": END,
    }
)

# ❌ DON'T DO THIS:
async def bad_router(state):
    if condition:
        return await node_a(state)  # Wrong! Calls node directly
    ...
```

---

*Document updated: October 2025*  
*All LangGraph agents now display properly in Studio without orphaned nodes.*