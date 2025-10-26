# LangGraph Studio Visualization Guide

> **Phase 8 Enhancement**: Real-time graph execution visualization and debugging.

## Overview

LangGraph Studio is a built-in web interface for visualizing and debugging LangGraph workflows. It allows you to:

- 🎨 **Visualize the graph** - See the complete DAG structure with all nodes and edges
- ⏸️ **Step through execution** - Execute one node at a time and inspect state
- 🔍 **Inspect state** - View the complete state at each step
- 🔄 **Replay runs** - Re-run the graph with the same or different inputs
- 🧪 **Test inputs** - Experiment with custom graph inputs

## Quick Start

### 1. Start Services

Run the Mac startup script:

```bash
./start_all_services_mac.sh
```

This will automatically:
- Install `langgraph-cli` (if not already installed)
- Start LangGraph Studio on **port 2024**
- Display the Studio URL in the output

### 2. Access Studio

Look for this in the startup output:

```
Service Status:
  🌐 Web UI:           http://localhost:3000
  🤖 LangGraph (Orchestrator): http://localhost:5001
  📊 LangGraph Studio: http://localhost:2024 (Graph Visualization)
```

**Open the Studio URL** in your browser:
```
http://localhost:2024
```

### 3. Interact with the Graph

#### Visualize the Graph Structure

The main canvas shows:
- **Nodes** (blue boxes): Processing steps (parse_intent, generate_sql, execute_query, etc.)
- **Edges** (arrows): Data flow between nodes
- **START/END**: Entry and exit points

#### Execute the Graph

1. Click **"Execute Graph"** button
2. Provide input state:
   ```json
   {
     "user_input": "How many customers do we have?",
     "messages": [],
     "retry_count": 0
   }
   ```
3. Click **"Run"**

#### Step Through Execution

1. After starting execution, use **Previous / Next** buttons to navigate
2. At each step, view:
   - Current node being executed
   - Complete state snapshot
   - Time taken per node
   - Any errors

#### Inspect State

At each step, the right panel shows:
- Full workflow state (JSON)
- Expandable sections for each state field
- Read-only view for debugging

#### Check Node Details

Hover over nodes to see:
- Node name and description
- Input/output types
- Current execution status

## Architecture Integration

### Graph Flow

```
START
  ↓
index_database (Scout Catalog Discovery)
  ↓
get_schema (Retrieve database schema)
  ↓
parse_intent (Extract user intent)
  ↓
[Conditional Routing based on intent]
  ├─ clarify → END
  ├─ schema_query → explain_schema → format_results → END
  ├─ query → select_tables → generate_sql → execute_query → format_results → END
  ├─ data_query → select_tables → generate_sql → execute_query → format_results → END
  └─ ... [other paths]
```

### Key Nodes

| Node | Purpose |
|------|---------|
| `index_database` | Discover and catalog all tables/views from MCP server |
| `get_schema` | Retrieve database schema for context |
| `parse_intent` | Analyze user query and route to appropriate handler |
| `select_tables` | Search for relevant tables using Scout Catalog |
| `generate_sql` | Generate MSSQL query from intent and schema |
| `execute_query` | Execute query with safety checks (row limits, timeouts) |
| `format_results` | Format results as user-friendly answer |
| `handle_error` | Handle and explain errors |

## Debugging Use Cases

### Case 1: Query Not Generating

1. Execute the graph with a test query
2. Step to `parse_intent` node
3. Check the state's `intent_analysis` field
4. If incorrect, examine the LLM prompt and schema context
5. Adjust prompts in `langgraph_integration/prompts/` if needed

### Case 2: SQL Generation Failing

1. Step to `select_tables` node
2. Check `relevant_tables` in state
3. Step to `generate_sql` node
4. If no SQL generated, check the LLM error or schema snippet
5. Verify tables exist in MCP server discovery

### Case 3: Query Execution Error

1. Step to `execute_query` node
2. Check the `sql_query` field (the generated query)
3. Check `error_info` if present
4. Test query directly in database client if needed

### Case 4: Incorrect Results

1. Verify the `sql_query` in state
2. Check the `schema_snippet` used for query generation
3. Examine the `query_results` to see raw data
4. Check the formatting in `format_results` node

## Advanced Features

### Replay a Run

1. Go to **History** (if available in your version)
2. Select a previous run
3. Click **Replay**
4. This re-executes the graph with the same inputs

### Export Graph Definition

The graph can be exported as:
- **JSON** - Complete graph definition
- **PNG** - Visualization image
- **SVG** - Scalable vector graphic

### Share Debugging Info

After a run, you can:
1. Take a screenshot of the graph visualization
2. Export the full state as JSON
3. Share with team for debugging

## Logs

Studio logs are saved to:
```
logs/langgraph_studio.log
```

View live logs:
```bash
tail -f logs/langgraph_studio.log
```

## Troubleshooting

### Studio Won't Start

Check the log file:
```bash
tail -f logs/langgraph_studio.log
```

Common issues:
- **Port 2024 in use**: `kill_port 2024` or restart
- **langgraph-cli not installed**: `pip install langgraph-cli`
- **Python version mismatch**: Ensure Python 3.11+

### Graph Not Loading

1. Verify `graph_definition.py` can be imported:
   ```bash
   python3 -c "from langgraph_integration.graph_definition import build_graph; print(build_graph())"
   ```

2. Check for import errors in the graph definition
3. Verify all dependencies are installed:
   ```bash
   pip install -r langgraph_integration/requirements.txt
   ```

### Execution Hangs

1. Check the MCP server is running (Windows machine)
2. Verify network connectivity
3. Check logs for timeout errors
4. Manually set a shorter timeout in graph if needed

## Performance Tips

- **Large State**: Studio may slow down with very large state objects
- **Long Logs**: Clear old logs periodically: `rm logs/langgraph_studio.log`
- **Multiple Tabs**: Keep only one Studio tab open for best performance

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Studio GitHub](https://github.com/langchain-ai/langgraph)
- [Project ADRs](../adrs/)

---

**Next Steps**:
1. Open Studio at `http://localhost:2024`
2. Execute a test query to see the graph in action
3. Use the visualization to understand your workflow
4. Debug issues step-by-step using the state inspector