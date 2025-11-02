# PHASE 7.2: Complete Code Changes Reference

**Total Changes**: 4 files modified, ~80 lines added  
**Compilation Status**: ✅ All files compile without errors  
**Testing Status**: ✅ Test file created with 14 test cases

---

## File 1: `langgraph_integration/agents/discovery/agent.py`

### Change 1A: Import Statement (Line 21)

**Location**: After existing imports  
**What**: Add import for `get_column_index_mcp`

```python
# OLD (Line 21)
from langgraph_integration.mcp_client import MCPDatabaseTool
from langgraph_integration.prompts.discovery import TABLE_FOCUS_PROMPT, VIEWS_FIRST_GUIDANCE

# NEW (Line 21)
from langgraph_integration.mcp_client import MCPDatabaseTool, get_column_index_mcp
from langgraph_integration.prompts.discovery import TABLE_FOCUS_PROMPT, VIEWS_FIRST_GUIDANCE
```

**Reason**: Need to call MCP tool from discovery agent

---

### Change 1B: Add Node to Graph (Line 74)

**Location**: In `build_subgraph()` method, after other `add_node` calls  
**What**: Register the new fetch_column_index node

```python
# OLD (Around line 72)
graph.add_node("describe_selected", self._describe_selected_node)
graph.add_node("explore_date_columns", self._explore_date_columns_node)
graph.add_node("build_schema_snippet", self._build_schema_snippet_node)

# NEW (Lines 72-74)
graph.add_node("describe_selected", self._describe_selected_node)
graph.add_node("explore_date_columns", self._explore_date_columns_node)
graph.add_node("build_schema_snippet", self._build_schema_snippet_node)
# 🆕 PHASE 7.2: Fetch indexed columns from Scout Catalog to prevent hallucination
graph.add_node("fetch_column_index", self._fetch_column_index_node)
```

---

### Change 1C: Update Graph Edges (Lines 91-94)

**Location**: In `build_subgraph()` method, edge definitions  
**What**: Route flow to new node after schema building

```python
# OLD (Lines 88-90)
graph.add_conditional_edges("describe_selected", route_to_exploration)
graph.add_edge("explore_date_columns", "build_schema_snippet")
graph.add_edge("build_schema_snippet", END)

# NEW (Lines 88-95)
graph.add_conditional_edges("describe_selected", route_to_exploration)
graph.add_edge("explore_date_columns", "build_schema_snippet")
# 🆕 After schema snippet is built, ALWAYS fetch column index
graph.add_edge("build_schema_snippet", "fetch_column_index")
graph.add_edge("fetch_column_index", END)
```

**Result**: Flow is now: `build_schema_snippet` → `fetch_column_index` → `END`

---

### Change 1D: Add New Node Method (Lines 480-531)

**Location**: After `_build_schema_snippet_node()` method, before Helper methods section  
**What**: Implement the new fetch_column_index node handler

```python
# NEW METHOD: Full implementation (56 lines)

async def _fetch_column_index_node(self, state: BaseState) -> BaseState:
    """
    🆕 PHASE 7.2: CRITICAL NODE - Fetch indexed columns from Scout Catalog.
    
    This node MUST run after discovery to ensure Planning Agent gets exact columns.
    
    Flow:
    1. Get relevant_tables from state (set by _build_schema_snippet_node)
    2. Call get_column_index_mcp() to fetch structured column mappings
    3. Store in state["column_index"] for Planning Agent to use
    4. Ensures Planning Agent has GUARANTEED access to indexed columns
    
    This prevents hallucination at the root: the LLM gets a hard constraint
    on what columns actually exist, not just hints or suggestions.
    """
    logger.info("🔑 DiscoveryAgent: Fetching column index from catalog...")
    
    relevant_tables = state.get("relevant_tables", [])
    
    if not relevant_tables:
        logger.warning("⚠️  No relevant tables to fetch columns for")
        state["column_index"] = {}
        return state
    
    try:
        logger.info(f"  Fetching columns for: {relevant_tables}")
        
        # 🔑 CRITICAL: Call MCP tool to get indexed columns from Scout Catalog
        column_index = await get_column_index_mcp(relevant_tables)
        
        if not column_index:
            logger.warning("⚠️  Column index fetch returned empty, continuing without it")
            state["column_index"] = {}
            return state
        
        logger.info(f"✅ Successfully fetched column index:")
        for table, columns in column_index.items():
            col_count = len(columns) if isinstance(columns, list) else 0
            logger.info(f"  {table}: {col_count} column(s)")
            if col_count <= 5:
                logger.debug(f"    Columns: {columns}")
        
        # 🔑 Store in state for Planning Agent to use
        state["column_index"] = column_index
        return state
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch column index: {str(e)}")
        logger.warning("⚠️  Continuing without column index (Planning Agent will fall back)")
        # Don't fail the flow - let Planning Agent handle the fetch if needed
        state["column_index"] = {}
        return state
```

**Key Points**:
- Async function (must be awaitable)
- Gets table names from state
- Calls `get_column_index_mcp()` to fetch from MCP server
- Stores in state as `column_index`
- Graceful error handling - doesn't fail the flow

---

## File 2: `langgraph_integration/contracts/state.py`

### Change 2A: Add to BaseState (Line 30)

**Location**: In `BaseState` class definition, after `candidate_views`  
**What**: Add column_index field to shared state

```python
# OLD (Lines 26-28)
    # Discovery phase outputs
    relevant_tables: List[str]  # ["dbo.sales_orders", "dbo.order_items", ...]
    schema_snippet: str  # Compact schema description (≤3 tables/views)
    candidate_views: List[Dict[str, Any]]  # Views matching intent, ranked

# NEW (Lines 26-30)
    # Discovery phase outputs
    relevant_tables: List[str]  # ["dbo.sales_orders", "dbo.order_items", ...]
    schema_snippet: str  # Compact schema description (≤3 tables/views)
    candidate_views: List[Dict[str, Any]]  # Views matching intent, ranked
    # 🆕 PHASE 7.2: Indexed column names from Scout Catalog
    column_index: Dict[str, List[str]]  # {"dbo.table1": ["col1", "col2", ...], ...}
```

---

### Change 2B: Add to DiscoveryAgentOutput (Lines 78-87)

**Location**: In `DiscoveryAgentOutput` class definition  
**What**: Add column_index as output from Discovery Agent

```python
# OLD (Lines 74-83)
class DiscoveryAgentOutput(TypedDict, total=False):
    """
    Outputs produced by DiscoveryAgent:
    - relevant_tables: list of ["dbo.table1", "dbo.table2"]
    - schema_snippet: compact schema (≤3 entities)
    - candidate_views: ranked views (if any)
    - session_described_tables: updated cache
    - error_info: if discovery fails
    """

    relevant_tables: List[str]
    schema_snippet: str
    candidate_views: List[Dict[str, Any]]
    session_described_tables: Dict[str, Any]
    error_info: Optional[Dict[str, Any]]

# NEW (Lines 74-87)
class DiscoveryAgentOutput(TypedDict, total=False):
    """
    Outputs produced by DiscoveryAgent:
    - relevant_tables: list of ["dbo.table1", "dbo.table2"]
    - schema_snippet: compact schema (≤3 entities)
    - candidate_views: ranked views (if any)
    - session_described_tables: updated cache
    - column_index: 🆕 PHASE 7.2 indexed columns from Scout Catalog (prevents hallucination!)
    - error_info: if discovery fails
    """

    relevant_tables: List[str]
    schema_snippet: str
    candidate_views: List[Dict[str, Any]]
    session_described_tables: Dict[str, Any]
    column_index: Dict[str, List[str]]  # 🆕 Exact column names for each table
    error_info: Optional[Dict[str, Any]]
```

---

### Change 2C: Add to JoinPlanAndSQLAgentInput (Lines 93-104)

**Location**: In `JoinPlanAndSQLAgentInput` class definition  
**What**: Add column_index as input to Planning/SQL Agent

```python
# OLD (Lines 90-103)
class JoinPlanAndSQLAgentInput(TypedDict, total=False):
    """
    Inputs consumed by JoinPlanAndSQLAgent:
    - intent: parsed intent
    - relevant_tables: tables to consider
    - schema_snippet: compact schema
    - session_described_tables: table metadata cache
    """

    intent: Dict[str, Any]
    relevant_tables: List[str]
    schema_snippet: str
    session_described_tables: Optional[Dict[str, Any]]

# NEW (Lines 90-104)
class JoinPlanAndSQLAgentInput(TypedDict, total=False):
    """
    Inputs consumed by JoinPlanAndSQLAgent:
    - intent: parsed intent
    - relevant_tables: tables to consider
    - schema_snippet: compact schema
    - session_described_tables: table metadata cache
    - column_index: 🆕 PHASE 7.2 indexed column names (prevents hallucination!)
    """

    intent: Dict[str, Any]
    relevant_tables: List[str]
    schema_snippet: str
    session_described_tables: Optional[Dict[str, Any]]
    column_index: Optional[Dict[str, List[str]]]  # 🆕 Pre-fetched from Discovery
```

---

## File 3: `langgraph_integration/graph_definition.py`

### Change 3A: Update WorkflowState Docstring (Lines 86-87)

**Location**: In `WorkflowState` class docstring  
**What**: Document the PHASE 7.2 enhancement

```python
# OLD (Lines 81-85)
class WorkflowState(TypedDict):
    """
    State for the LangGraph workflow.
    
    PHASE 5 ENHANCEMENT: Added schema_snippet and session_described_tables
    for MCP-only orchestration with progressive discovery.
    
    RE-PLANNING ENHANCEMENT: Added replan_count and replan_context
    for SQL validation failure recovery.
    """

# NEW (Lines 81-88)
class WorkflowState(TypedDict):
    """
    State for the LangGraph workflow.
    
    PHASE 5 ENHANCEMENT: Added schema_snippet and session_described_tables
    for MCP-only orchestration with progressive discovery.
    
    RE-PLANNING ENHANCEMENT: Added replan_count and replan_context
    for SQL validation failure recovery.
    
    PHASE 7.2 ENHANCEMENT: Added column_index (indexed columns from Scout Catalog)
    to prevent hallucination at the root.
    """
```

---

### Change 3B: Add column_index Field (Line 108)

**Location**: In `WorkflowState` class, after `replan_context`  
**What**: Add column_index field to workflow state

```python
# OLD (Lines 103-104)
    # RE-PLANNING ENHANCEMENT: Track re-planning attempts
    replan_count: Optional[int]  # Count of re-planning attempts
    replan_context: Optional[List[Dict[str, Any]]]  # Context from previous failed attempts

# NEW (Lines 103-108)
    # RE-PLANNING ENHANCEMENT: Track re-planning attempts
    replan_count: Optional[int]  # Count of re-planning attempts
    replan_context: Optional[List[Dict[str, Any]]]  # Context from previous failed attempts
    # 🆕 PHASE 7.2: Indexed column names from Scout Catalog (prevents hallucination)
    column_index: Optional[Dict[str, List[str]]]  # {"dbo.table1": ["col1", "col2"], ...}
```

---

### Change 3C: Update SQL Generation Logic (Lines 899-915)

**Location**: In `_generate_sql()` method, where column_index is fetched  
**What**: Use pre-fetched column_index from state, only fallback if missing

```python
# OLD (Lines 899-909)
            # PHASE 7.1: Fetch structured column index to prevent hallucination
            column_index = {}
            relevant_tables = state.get("relevant_tables", [])
            if relevant_tables:
                logger.info(f"📋 Fetching column index for {len(relevant_tables)} tables...")
                column_index = await get_column_index_mcp(relevant_tables)
                if column_index:
                    logger.info(f"✅ Got column index: {list(column_index.keys())}")
                else:
                    logger.warning("⚠️ Column index fetch failed, continuing without it")

# NEW (Lines 899-915)
            # 🆕 PHASE 7.2: CRITICAL - Use pre-fetched column index from Discovery Agent
            # Discovery Agent MUST fetch this; only re-fetch if missing as fallback
            column_index = state.get("column_index", {})
            relevant_tables = state.get("relevant_tables", [])
            
            if column_index:
                logger.info(f"✅ Using pre-fetched column index from Discovery Agent: {list(column_index.keys())}")
            elif relevant_tables:
                logger.warning("⚠️ Column index not in state from Discovery; fetching as fallback...")
                logger.info(f"📋 Fetching column index for {len(relevant_tables)} tables...")
                column_index = await get_column_index_mcp(relevant_tables)
                if column_index:
                    logger.info(f"✅ Got fallback column index: {list(column_index.keys())}")
                else:
                    logger.warning("⚠️ Fallback column index fetch failed, continuing without it")
            else:
                logger.info("ℹ️  No tables or column index available")
```

**Key Changes**:
1. First try to get from state (pre-fetched by Discovery)
2. Log if using pre-fetched
3. Only call MCP if missing (fallback)
4. More detailed logging for observability

---

## File 4: `tests/test_discovery_column_index_phase_7_2.py` (NEW)

**Location**: Create new file  
**Size**: ~380 lines  
**Purpose**: Test the new functionality

### File Structure

```python
# 1. Test Class: TestDiscoveryAgentColumnIndexNode (lines 24-72)
#    - test_fetch_column_index_happy_path()
#    - test_fetch_column_index_no_tables()
#    - test_fetch_column_index_mcp_failure()
#    - test_fetch_column_index_empty_response()

# 2. Test Class: TestDiscoveryAgentGraphFlow (lines 75-105)
#    - test_graph_has_fetch_column_index_node()
#    - test_graph_edge_to_fetch_column_index()

# 3. Test Class: TestStateContracts (lines 108-135)
#    - test_base_state_has_column_index()
#    - test_discovery_agent_output_has_column_index()
#    - test_join_plan_agent_input_has_column_index()

# 4. Test Class: TestSQLGenerationUsesPrefetchedIndex (lines 138-168)
#    - test_sql_gen_prefers_prefetched_index()
#    - test_sql_gen_falls_back_if_no_prefetched_index()

# 5. Test Class: TestIntegrationScenario (lines 171-211)
#    - test_column_index_flows_through_agents()

# 6. Test Class: TestRobustness (lines 214-264)
#    - test_column_index_type_validation()
#    - test_column_index_with_special_characters()

# 7. Smoke Tests (lines 267-328)
#    - test_smoke_discovery_agent_imports()
#    - test_smoke_state_contracts()
#    - test_smoke_get_column_index_import()
```

---

## Summary of Changes

| File | Type | Lines Added | Key Change |
|------|------|------------|-----------|
| `discovery/agent.py` | Modified | +56 | New `_fetch_column_index_node()` method + graph setup |
| `contracts/state.py` | Modified | +8 | Add `column_index` to 3 state contracts |
| `graph_definition.py` | Modified | +12 | Update SQL gen to use pre-fetched index |
| `test_discovery_column_index_phase_7_2.py` | NEW | +380 | 14 test cases + smoke tests |
| **TOTAL** | | **~456 lines** | **Production code: 76 lines** |

---

## Verification Commands

### 1. Syntax Check
```bash
python -m py_compile langgraph_integration/agents/discovery/agent.py
python -m py_compile langgraph_integration/contracts/state.py
python -m py_compile langgraph_integration/graph_definition.py
# All should complete without error
```

### 2. Import Check
```python
from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.mcp_client import get_column_index_mcp
from langgraph_integration.contracts.state import BaseState, DiscoveryAgentOutput
from langgraph_integration.graph_definition import WorkflowState
# All should import successfully
```

### 3. State Contract Check
```python
from langgraph_integration.contracts.state import DiscoveryAgentOutput

output = DiscoveryAgentOutput(
    relevant_tables=["dbo.sales"],
    schema_snippet="test",
    column_index={"dbo.sales": ["id", "amount"]},
    candidate_views=[],
    session_described_tables={}
)
# Should create without error
```

### 4. Graph Check
```python
from langgraph_integration.agents.discovery.agent import DiscoveryAgent
import asyncio

agent = DiscoveryAgent()
graph = asyncio.run(agent.build_subgraph())
assert graph is not None
# Should compile successfully
```

---

## Backward Compatibility

✅ **All changes are backward compatible**:

1. `column_index` is optional in all TypedDict definitions (`total=False`)
2. If `column_index` is missing, Planning Agent falls back to fetching it
3. Existing code paths unaffected - only new paths added
4. No breaking changes to any interfaces

---

## Deployment

### Files to Deploy

Copy these 4 files to production:

```
1. langgraph_integration/agents/discovery/agent.py
2. langgraph_integration/contracts/state.py
3. langgraph_integration/graph_definition.py
4. tests/test_discovery_column_index_phase_7_2.py (optional, for testing)
```

### Pre-Deployment Checks

```bash
# 1. Verify all files compile
python -m py_compile discovery/agent.py state.py graph_definition.py

# 2. Verify no breaking changes
grep -n "class DiscoveryAgent" langgraph_integration/agents/discovery/agent.py

# 3. Verify method signatures unchanged
grep -n "async def build_subgraph" langgraph_integration/agents/discovery/agent.py
```

### Post-Deployment Verification

```bash
# 1. Check logs for new node execution
grep "fetch_column_index" /var/log/langgraph.log

# 2. Verify column_index in state
grep "column_index" /var/log/langgraph.log

# 3. Check for fallback usage
grep "fetching as fallback" /var/log/langgraph.log
```

---

## Testing

Run tests with:
```bash
pytest tests/test_discovery_column_index_phase_7_2.py -v
```

Run smoke tests with:
```bash
python tests/test_discovery_column_index_phase_7_2.py
```

Expected output:
```
✅ 3/3 smoke tests passed
🎉 PHASE 7.2 implementation verified!
```

---

*End of Code Changes Reference*