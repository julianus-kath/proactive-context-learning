# 🎨 Orchestrator Graph Visualization Guide

**Quick Reference for LangGraph Studio Graph Display**

---

## 🔴 BEFORE (Broken) → 🟢 AFTER (Fixed)

### Visual Comparison

#### ❌ BEFORE: Broken Topology
```
┌─────────────────────────────────────────────────────────┐
│                   Graph Structure Issues                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  START                                                  │
│   ↓                                                     │
│  index_database                                         │
│   ↓                                                     │
│  parse_intent                                           │
│   ↓                                                     │
│  route_operation ──(conditional)──→ [clarify→answer]  │
│   ↓                                   [schema→?]       │
│   ↓                                   [health→answer_h]│
│  discovery                                              │
│   ├─→ join_sql ──→ exec_recovery ──→ answer ──→ END   │
│   └─→ answer_schema ──→ END  ❌ CONFLICT!              │
│                                                          │
│  ⚠️  Problem: Two unconditional edges from discovery   │
│  ⚠️  Studio can't render ambiguous routing             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### ✅ AFTER: Fixed Topology

```
┌─────────────────────────────────────────────────────────────┐
│            Corrected Graph Structure                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  START                                                      │
│   ↓                                                         │
│  index_database                                             │
│   ↓                                                         │
│  parse_intent                                               │
│   ↓                                                         │
│  route_operation ────(conditional: explicit mapping)────   │
│   ├──→ answer ────────────────────────────→ END           │
│   ├──→ discovery_for_schema ──→ answer_schema ──→ END     │
│   ├──→ answer_health ────────────────────→ END            │
│   ├──→ answer_error ─────────────────────→ END            │
│   ├──→ exec_recovery ──→ answer ─────────→ END            │
│   │                                                         │
│   └──→ discovery ──→ join_sql ──→ exec_recovery           │
│        ↓                                                    │
│        └──────────────→ answer ──────────→ END             │
│                                                              │
│  ✅ Single outgoing path per node                         │
│  ✅ Explicit conditional mapping                          │
│  ✅ Clear separation of pipelines                         │
│  ✅ Studio can render all edges                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Operation Flow Paths

### Path 1: Regular Query (Default)
```
START → index_database → parse_intent → route_operation
  ↓ (operation="query")
discovery → join_sql → exec_recovery → answer → END
```

**Use case:** "Show top 10 customers by total orders"

---

### Path 2: Schema Query
```
START → index_database → parse_intent → route_operation
  ↓ (operation="schema_query")
discovery_for_schema → answer_schema → END
```

**Use case:** "What tables are available?" or "Show me the database structure"

---

### Path 3: Clarification
```
START → index_database → parse_intent → route_operation
  ↓ (operation="clarify")
answer → END
```

**Use case:** Ambiguous queries where the system asks for clarification

---

### Path 4: Health Check
```
START → index_database → parse_intent → route_operation
  ↓ (operation="health_check")
answer_health → END
```

**Use case:** "Is the system healthy?" or "Check database connection"

---

### Path 5: Direct SQL Execution
```
START → index_database → parse_intent → route_operation
  ↓ (operation="execute_direct")
exec_recovery → answer → END
```

**Use case:** Admin operations with pre-written SQL

---

### Path 6: Error Handling
```
START → index_database → parse_intent → route_operation
  ↓ (operation="error")
answer_error → END
```

**Use case:** System errors detected during processing

---

## 🎯 How to Verify in LangGraph Studio

### Step 1: Start the Studio
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
./start_all_services_mac.sh

# Or manually:
langgraph dev --port 2024
```

### Step 2: Open in Browser
```
http://localhost:2024/docs
```

### Step 3: Look for Graph Selection Dropdown
- **Should show:** "main_orchestrator" in the graph list
- **Click it** to visualize the main orchestrator

### Step 4: Verify Edge Connections
```
✅ Checklist:

□ START node visible at top
□ START → index_database (solid blue line)
□ index_database → parse_intent (solid blue line)
□ parse_intent → route_operation (solid blue line)
□ route_operation has CONDITIONAL edges (shown as diamonds/branching)
  - Each branch should be labeled with the routing decision
□ discovery → join_sql → exec_recovery → answer → END (horizontal flow)
□ discovery_for_schema → answer_schema → END (vertical or separate flow)
□ answer_health → END (branching from route_operation)
□ answer_schema → END (branching from discovery_for_schema)
□ answer_error → END (branching from route_operation)
□ All paths clearly visible and connected
```

### Step 5: Test Interactive Execution
1. Click "Run" in Studio
2. Enter test input: `{"user_input": "Show me top 10 customers"}`
3. Watch execution flow through the graph
4. Verify nodes execute in the correct order

---

## 🧪 Command-Line Verification

### Quick Graph Check
```bash
python3 << 'EOF'
from langgraph_integration.orchestrator import build_graph
import json

# Build the graph
graph = build_graph()

# Check nodes
print("📊 Graph Nodes:")
print(f"  Total: {len(graph.nodes)}")
for node in sorted(graph.nodes.keys()):
    print(f"    - {node}")

# Verify critical nodes exist
critical = ['index_database', 'parse_intent', 'route_operation', 
            'discovery', 'discovery_for_schema', 'join_sql', 
            'exec_recovery', 'answer', 'answer_schema', 
            'answer_health', 'answer_error']

missing = [n for n in critical if n not in graph.nodes]
if missing:
    print(f"\n❌ Missing nodes: {missing}")
else:
    print(f"\n✅ All {len(critical)} critical nodes present!")

EOF
```

### Expected Output
```
📊 Graph Nodes:
  Total: 12
    - __start__
    - index_database
    - parse_intent
    - route_operation
    - discovery
    - discovery_for_schema
    - join_sql
    - exec_recovery
    - answer
    - answer_schema
    - answer_health
    - answer_error

✅ All 12 critical nodes present!
```

---

## 🐛 Troubleshooting

### Issue: Edges still appear disconnected in Studio

**Possible causes:**
1. **Studio cache issue**
   - Clear browser cache: Cmd+Shift+Delete
   - Restart Studio: `pkill -f "langgraph dev"` then restart

2. **Stale Python modules**
   - Restart Python: `pkill -f "python"`
   - Reimport: `python3 -c "from langgraph_integration.orchestrator import build_graph; build_graph()"`

3. **Graph not reloaded**
   - Studio watches file changes; if not reloading, restart: `pkill -f "langgraph dev"`

### Issue: "No graphs available" in Studio

**Solution:**
1. Verify `langgraph.json` exists in project root:
   ```bash
   cat /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/langgraph.json
   ```

2. Check graph key matches:
   ```json
   {
     "graphs": {
       "main_orchestrator": "langgraph_integration.orchestrator:build_graph"
     }
   }
   ```

3. Verify `build_graph()` function exists:
   ```bash
   python3 -c "from langgraph_integration.orchestrator import build_graph; print('✅ build_graph() found')"
   ```

### Issue: "Graph compilation error"

**Check:**
```bash
python3 -c "
from langgraph_integration.orchestrator import build_graph
try:
    g = build_graph()
    print('✅ Graph compiles successfully')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
"
```

---

## 📈 Understanding Conditional Edge Visualization

### What You'll See in Studio

**Conditional edges appear as:**
- 🔷 **Diamond/Decision nodes** at the routing point
- Multiple outgoing arrows with labels
- Each arrow labeled with the decision value

**Example: route_operation conditional edges**
```
┌──────────────────────┐
│   route_operation    │
└──────────────────────┘
         │
    ┌────┼────┬─────┬────────┐
    │    │    │     │        │
  ["clarify"]                │
    │                        │
   answer              ["schema_query"]
    │                        │
   END                discovery_for_schema
                             │
                       answer_schema
                             │
                            END
```

---

## 🎓 Graph Architecture Highlights

### Key Design Decisions

1. **Single Route Point:** All operations go through `route_operation` for consistency
2. **Explicit Mapping:** Every possible routing decision is mapped to a target node
3. **Pipeline Separation:** Query and schema pipelines are explicit (not overlapping)
4. **Stateless Routing:** Routing function only depends on `intent.operation`

### Why This Design Works

- ✅ **Debuggable:** Easy to trace execution in Studio
- ✅ **Maintainable:** Adding new operations just means adding new conditional branch
- ✅ **Scalable:** Multiple pipelines don't conflict
- ✅ **Type-safe:** LangGraph validates all routing decisions at compile time

---

## 📝 Node Responsibilities

| Node | Responsibility | Output |
|------|-----------------|--------|
| `index_database` | Load Scout catalog, verify MCP | Schema metadata |
| `parse_intent` | Parse user query → operation type | Intent dict |
| `route_operation` | Route based on operation | Target node name |
| `discovery` | Find relevant tables/views | Table list, schema snippet |
| `discovery_for_schema` | Same as discovery (schema queries) | Table list, schema snippet |
| `join_sql` | Plan joins, generate MSSQL | SQL query |
| `exec_recovery` | Execute safely, repair on error | Query results |
| `answer` | Format results as natural language | Final response |
| `answer_schema` | Explain discovered schema | Schema explanation |
| `answer_health` | Report system health | Health status |
| `answer_error` | Handle errors gracefully | Error message |

---

## 🚀 Next Steps

1. **Verify** the fix in your environment:
   ```bash
   python3 /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/tests/test_orchestrator_graph.py
   ```

2. **Monitor** Studio visualization for completeness

3. **Test** all six operation types to verify routing works

4. **Document** any new operations added in the future

---

**For more details, see:** `docs/ORCHESTRATOR_GRAPH_FIX_DEEP_DIVE.md`