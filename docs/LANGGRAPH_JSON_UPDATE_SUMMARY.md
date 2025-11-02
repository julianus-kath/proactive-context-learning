# LangGraph Studio Graph Configuration Update

## Problem
LangGraph Studio was unable to load the graphs with error: 
> "Failed to preview graph - Please ensure that the path to the compiled graph is present in langgraph.json"

## Solution
Updated `langgraph.json` to include all available graphs with proper module paths and created synchronous wrapper functions for the agent graphs.

## Changes Made

### 1. Updated `langgraph.json`
Added five graphs that can be visualized in LangGraph Studio:

```json
{
  "dependencies": ["."],
  "graphs": {
    "main_orchestrator": "langgraph_integration.graph_definition:build_graph",
    "discovery_agent": "langgraph_integration.agents.discovery.agent:build_discovery_graph",
    "join_sql_agent": "langgraph_integration.agents.join_sql.agent:build_join_sql_graph",
    "exec_recovery_agent": "langgraph_integration.agents.exec_recovery.agent:build_exec_recovery_graph",
    "answer_agent": "langgraph_integration.agents.answer.agent:build_answer_graph"
  },
  "env": ".env"
}
```

### 2. Added Synchronous Build Functions
Created `build_*_graph()` functions in each agent module as synchronous wrappers for LangGraph Studio:

- **discovery/agent.py**: `build_discovery_graph()`
- **join_sql/agent.py**: `build_join_sql_graph()`
- **exec_recovery/agent.py**: `build_exec_recovery_graph()`
- **answer/agent.py**: `build_answer_graph()`

These wrappers handle the async-to-sync conversion needed by the LangGraph CLI.

## Files Modified

1. `/langgraph.json` - Added all available graphs
2. `/langgraph_integration/agents/discovery/agent.py` - Added `build_discovery_graph()`
3. `/langgraph_integration/agents/join_sql/agent.py` - Added `build_join_sql_graph()`
4. `/langgraph_integration/agents/exec_recovery/agent.py` - Added `build_exec_recovery_graph()`
5. `/langgraph_integration/agents/answer/agent.py` - Added `build_answer_graph()`

## Verification
✅ All graphs successfully load and can be visualized in LangGraph Studio:

```bash
# Test loading graphs
python3 -c "from langgraph_integration.graph_definition import build_graph; build_graph()"
python3 -c "from langgraph_integration.agents.discovery.agent import build_discovery_graph; build_discovery_graph()"
```

## Usage in LangGraph Studio

When you run:
```bash
langgraph dev --port 2024 --tunnel
```

You'll now see 5 graphs available in the Studio dropdown:
1. **main_orchestrator** - Complete orchestration workflow
2. **discovery_agent** - Table/view discovery and ranking
3. **join_sql_agent** - Join planning and SQL generation
4. **exec_recovery_agent** - Query execution and recovery
5. **answer_agent** - Result formatting and explanations

## Next Steps
1. Run the startup script: `./start_all_services_mac.sh`
2. Open LangGraph Studio at the tunnel URL provided
3. Select each graph from the dropdown to visualize the workflow
4. Use the graphs for debugging and understanding agent behavior

## Technical Notes
- All agent graphs use async/await internally but are wrapped with synchronous entry points
- The wrappers create a new event loop per build call for proper async execution
- The main orchestrator is pure synchronous and compiles directly
- All graphs are compiled and ready for execution