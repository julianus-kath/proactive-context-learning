# Phase 10a: Result Validator Agent Implementation
**Status**: Ready to Build | Effort: 2-3 hours | Priority: HIGH

---

## WHAT WE'RE ADDING

A new agent that sits between `exec_recovery` and `answer`, validating query results before they're formatted:

```
exec_recovery 
    ↓ (exec_result + join_plan + intent)
[NEW] result_validator
    ↓ (validates result, diagnoses issues, suggests recovery)
├─→ answer (if result is valid/usable)
├─→ discovery (if we should retry with different keywords)
└─→ error (if permanently broken)
```

---

## WHY THIS AGENT IS CRITICAL

**Current Problem:**
```
Query: "How many customers?"
Discovery: Found table "BCSPjmAdressenKontakt" (wrong! This is contacts, not customers)
Join SQL: SELECT COUNT(*) FROM BCSPjmAdressenKontakt
Exec: OK, returned 0 rows
Answer: "Your query returned no data"
User: "Why? Is the system broken?"
```

**With Result Validator:**
```
Query: "How many customers?"
Discovery: Found table "BCSPjmAdressenKontakt"
Join SQL: SELECT COUNT(*) FROM BCSPjmAdressenKontakt
Exec: OK, returned 0 rows
Result Validator: "⚠️  COUNT query returned 0 - suspicious. Schema mismatch?"
                  "→ Retry discovery with keywords: ['customer', 'count']"
Discovery [RETRY]: Found better table "Customer" 
Join SQL: SELECT COUNT(*) FROM Customer
Exec: OK, returned 1253 rows ✓
Answer: "Found 1,253 customers"
```

---

## IMPLEMENTATION STEPS

### Step 1: Create Agent Class File
**File**: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/langgraph_integration/agents/result_validator/agent.py`

```python
"""
ResultValidatorAgent - Validates query results before answer formatting.

Responsibilities:
1. Check row_count matches intent (COUNT vs DETAIL query)
2. Diagnose zero-row cases (schema issue? data issue? time filter?)
3. Validate columns match join_plan
4. Route to recovery or answer

Input: exec_result, intent, join_plan, sql_query, schema_snippet
Output: result_validation, [routing decision]
"""

import logging
from typing import Any, Dict, List, Optional, Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from langgraph_integration.contracts.state import BaseState
from langgraph_integration.debug_logger import get_debug_logger

logger = logging.getLogger(__name__)
debug_logger = get_debug_logger()


class ResultValidatorAgent:
    """
    Validates query execution results and diagnoses issues.
    
    Input contract: {exec_result, intent, join_plan, sql_query, schema_snippet, relevant_tables}
    Output contract: {result_validation, validation_routing_decision}
    """
    
    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        """
        Initialize ResultValidatorAgent.
        
        Args:
            llm_model: LLM for diagnostic analysis (if LLM-based diagnostics needed)
            llm_temp: Temperature for LLM
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
    
    def build_subgraph(self) -> StateGraph:
        """
        Build the result validation subgraph.
        
        Nodes:
        1. validate_result: Check structure & row counts
        2. diagnose_zero_rows: If empty, figure out why
        3. validate_columns: Check expected columns present
        4. decide_routing: Should we retry, escalate, or proceed?
        """
        graph = StateGraph(BaseState)
        
        # Add validation nodes
        graph.add_node("validate_result", self._validate_result_node)
        graph.add_node("diagnose_zero_rows", self._diagnose_zero_rows_node)
        graph.add_node("validate_columns", self._validate_columns_node)
        graph.add_node("decide_routing", self._decide_routing_node)
        
        # Wire them up
        graph.add_edge(START, "validate_result")
        graph.add_edge("validate_result", "validate_columns")
        graph.add_edge("validate_columns", "diagnose_zero_rows")
        graph.add_edge("diagnose_zero_rows", "decide_routing")
        graph.add_edge("decide_routing", END)
        
        return graph.compile()
    
    async def _validate_result_node(self, state: BaseState) -> BaseState:
        """
        Check if exec_result has expected structure.
        """
        logger.info("🔍 [RESULT_VALIDATOR] validate_result: Checking result structure...")
        
        exec_result = state.get("exec_result", {})
        intent = state.get("intent", {})
        
        # Result must be a dict with {ok, rows, row_count, ...}
        if not isinstance(exec_result, dict):
            logger.error(f"🔍 [RESULT_VALIDATOR] ❌ exec_result is not dict: {type(exec_result)}")
            state["result_validation"] = {
                "valid": False,
                "severity": "error",
                "diagnosis": "Invalid result structure from execution",
                "suggestions": ["Check MCP server logs"]
            }
            state["validation_routing"] = "error"
            return state
        
        if not exec_result.get("ok"):
            logger.warning(f"🔍 [RESULT_VALIDATOR] ⚠️  Execution failed: {exec_result.get('error')}")
            state["result_validation"] = {
                "valid": False,
                "severity": "error",
                "diagnosis": f"Query execution failed: {exec_result.get('error')}",
                "suggestions": ["Check query syntax", "Reduce time window"]
            }
            state["validation_routing"] = "error"
            return state
        
        row_count = exec_result.get("row_count", 0)
        logger.info(f"🔍 [RESULT_VALIDATOR] ✅ Structure OK, row_count: {row_count}")
        
        state["_validation_row_count"] = row_count  # Store for downstream
        return state
    
    async def _diagnose_zero_rows_node(self, state: BaseState) -> BaseState:
        """
        If query returned 0 rows, figure out why.
        """
        exec_result = state.get("exec_result", {})
        row_count = exec_result.get("row_count", 0)
        
        if row_count > 0:
            logger.info(f"🔍 [RESULT_VALIDATOR] Row count > 0, no diagnosis needed")
            state["result_diagnosis"] = None
            return state
        
        logger.warning(f"🔍 [RESULT_VALIDATOR] ⚠️  ZERO ROWS - Diagnosing...")
        
        intent = state.get("intent", {})
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        is_count = "count" in metrics
        
        join_plan = state.get("join_plan", {})
        sql_query = state.get("sql_query", "")
        
        diagnosis = {
            "is_count_query": is_count,
            "likely_causes": [],
            "recovery_suggestion": None
        }
        
        # Check 1: COUNT queries should return exactly 1 row
        if is_count:
            logger.error(f"🔍 [RESULT_VALIDATOR] ❌ COUNT query returned 0 rows (expected 1)")
            diagnosis["likely_causes"].append("Schema mismatch (wrong table discovered)")
            diagnosis["likely_causes"].append("Table filter excluded all data")
            diagnosis["recovery_suggestion"] = "retry_discovery"
        else:
            # DETAIL query returning 0 rows is more acceptable
            diagnosis["likely_causes"].append("No matching records (genuine empty result)")
            diagnosis["likely_causes"].append("Time filter too restrictive")
            diagnosis["likely_causes"].append("Schema issue (wrong table)")
        
        # Check 2: Analyze join_plan for FK failures
        if join_plan.get("fk_resolution") == "failed":
            diagnosis["likely_causes"].append("Join relationships not found (MCP error)")
        
        # Check 3: Look for obvious filters in SQL
        if "WHERE" in sql_query.upper():
            diagnosis["likely_causes"].append("WHERE clause may be too restrictive")
        
        state["result_diagnosis"] = diagnosis
        logger.info(f"🔍 [RESULT_VALIDATOR] Diagnosis: {diagnosis['likely_causes']}")
        
        return state
    
    async def _validate_columns_node(self, state: BaseState) -> BaseState:
        """
        Check that returned columns match what we expected.
        """
        logger.info("🔍 [RESULT_VALIDATOR] validate_columns: Checking columns...")
        
        exec_result = state.get("exec_result", {})
        join_plan = state.get("join_plan", {})
        column_index = state.get("column_index", {})
        
        rows = exec_result.get("rows", [])
        if not rows or not isinstance(rows, list):
            logger.info("🔍 [RESULT_VALIDATOR] No rows to validate columns")
            state["column_validation"] = {"valid": True, "issue": None}
            return state
        
        first_row = rows[0]
        if not isinstance(first_row, dict):
            logger.warning(f"🔍 [RESULT_VALIDATOR] ⚠️  First row is not dict: {type(first_row)}")
            state["column_validation"] = {"valid": False, "issue": "Row format unexpected"}
            return state
        
        actual_columns = set(first_row.keys())
        logger.info(f"🔍 [RESULT_VALIDATOR] Actual columns: {actual_columns}")
        
        # Check if we have expected columns (from schema_snippet or join_plan)
        expected = set()
        if join_plan:
            # Extract columns from join_plan if available
            pass  # TODO: implement based on join_plan structure
        
        logger.info(f"🔍 [RESULT_VALIDATOR] ✅ Column validation OK")
        state["column_validation"] = {"valid": True, "actual": list(actual_columns)}
        return state
    
    async def _decide_routing_node(self, state: BaseState) -> BaseState:
        """
        Determine next step: answer, retry_discovery, error, etc.
        """
        logger.info("🔍 [RESULT_VALIDATOR] decide_routing: Determining next action...")
        
        exec_result = state.get("exec_result", {})
        diagnosis = state.get("result_diagnosis")
        intent = state.get("intent", {})
        
        row_count = exec_result.get("row_count", 0)
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        is_count = "count" in metrics
        
        # Decision 1: If execution failed, route to error
        if not exec_result.get("ok"):
            logger.info("🔍 [RESULT_VALIDATOR] → Route to ERROR (execution failed)")
            state["validation_routing"] = "error"
            return state
        
        # Decision 2: If COUNT query returned 0, retry discovery
        if is_count and row_count == 0:
            logger.warning("🔍 [RESULT_VALIDATOR] → Route to DISCOVERY (COUNT=0, suspicious)")
            state["validation_routing"] = "discovery_retry"
            state["retry_discovery_reason"] = "COUNT query returned 0 rows"
            state["retry_discovery_keywords"] = self._enhance_keywords(
                intent.get("keywords_for_discovery", []),
                intent.get("primary_entities", [])
            )
            return state
        
        # Decision 3: If result looks valid, route to answer
        logger.info("🔍 [RESULT_VALIDATOR] → Route to ANSWER (result valid)")
        state["validation_routing"] = "answer"
        
        # Attach validation metadata for answer to use
        state["result_validation"] = {
            "valid": True,
            "severity": "warning" if row_count == 0 else "ok",
            "diagnosis": diagnosis or "Result OK",
            "suggestions": self._get_suggestions(state)
        }
        
        return state
    
    def _enhance_keywords(self, current: List[str], entities: List[str]) -> List[str]:
        """
        Enhance keywords for retry discovery.
        
        Example: ["customer"] → ["customer", "count", "total"]
        """
        enhanced = list(current)
        
        # Add aggregation keywords if they're missing
        agg_keywords = ["count", "total", "sum", "average"]
        for kw in agg_keywords:
            if kw not in enhanced:
                enhanced.append(kw)
        
        # Add entity keywords
        for entity in entities:
            if entity not in enhanced:
                enhanced.append(entity)
        
        return enhanced[:5]  # Limit to top 5
    
    def _get_suggestions(self, state: BaseState) -> List[str]:
        """
        Generate suggestions based on result quality.
        """
        exec_result = state.get("exec_result", {})
        row_count = exec_result.get("row_count", 0)
        
        suggestions = []
        
        if row_count == 0:
            suggestions = [
                "The query returned no data. This could mean:",
                "1. The selected table doesn't contain matching records",
                "2. The time filter excluded all data",
                "3. The table name differs in the ERP system"
            ]
        elif row_count > 1000:
            suggestions = [
                f"The query returned {row_count} rows (capped at 1000 displayed)",
                "Consider adding filters to narrow the result set"
            ]
        
        return suggestions


# Factory function for lazy initialization
def create_result_validator_agent() -> ResultValidatorAgent:
    """Factory to create ResultValidatorAgent."""
    return ResultValidatorAgent()
```

### Step 2: Create __init__.py
**File**: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/langgraph_integration/agents/result_validator/__init__.py`

```python
"""Result validator agent - validates query results before answer formatting."""

from langgraph_integration.agents.result_validator.agent import (
    ResultValidatorAgent,
    create_result_validator_agent
)

__all__ = ["ResultValidatorAgent", "create_result_validator_agent"]
```

### Step 3: Update State Contract
**File**: `langgraph_integration/contracts/state.py` (ADD to BaseState)

```python
# ADD these fields to BaseState TypedDict:

class BaseState(TypedDict, total=False):
    # ... existing fields ...
    
    # Result validation (NEW)
    result_validation: Dict[str, Any]  # {valid, severity, diagnosis, suggestions}
    result_diagnosis: Optional[Dict[str, Any]]  # {is_count_query, likely_causes, recovery_suggestion}
    validation_routing: Literal["answer", "discovery_retry", "error"]  # Where to route after validation
    retry_discovery_keywords: Optional[List[str]]  # Enhanced keywords if retrying discovery
    retry_discovery_reason: Optional[str]  # Why we're retrying
```

### Step 4: Integrate into Orchestrator
**File**: `langgraph_integration/orchestrator.py`

**BEFORE (around line 38):**
```python
from langgraph_integration.agents.answer.agent import AnswerAgent
```

**AFTER:**
```python
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.agents.result_validator.agent import ResultValidatorAgent  # NEW
```

**AROUND line 130 (in __init__):**
```python
self.answer_agent = AnswerAgent(llm_model=llm_model, llm_temp=llm_temp)
logger.info("✅ AnswerAgent initialized (Result formatting)")
self.interpret_agent = InterpretationAgent(llm_model=llm_model, llm_temp=llm_temp)
logger.info("✅ InterpretationAgent initialized (Follow-up over prior results)")

# NEW: Initialize Result Validator
self.result_validator_agent = ResultValidatorAgent(llm_model=llm_model, llm_temp=llm_temp)
logger.info("✅ ResultValidatorAgent initialized (Result validation & diagnosis)")
```

**AROUND line 174 (add node):**
```python
graph.add_node("validate_sql", self._validate_sql_node)
graph.add_node("exec_recovery", self._exec_recovery_node)
graph.add_node("result_validator", self._result_validator_node)  # NEW
graph.add_node("answer", self._answer_node)
```

**AROUND line 276 (update edges):**
```python
# Standard query flow
graph.add_edge("discovery", "join_sql")
graph.add_edge("join_sql", "validate_sql")
graph.add_edge("validate_sql", "exec_recovery")
graph.add_edge("exec_recovery", "result_validator")  # CHANGED from → "answer"
# Conditional routing from result_validator added below
```

**ADD routing from result_validator (around line 270):**
```python
# Add conditional routing from result_validator
def route_after_validation(state: BaseState) -> str:
    """Route based on validation result."""
    routing = state.get("validation_routing", "answer")
    logger.info(f"🔍 [ROUTE_AFTER_VALIDATION] → {routing}")
    return routing

graph.add_conditional_edges(
    "result_validator",
    route_after_validation,
    {
        "answer": "answer",
        "discovery_retry": "discovery",  # Loop back with enhanced keywords
        "error": "answer_error"           # Escalate to error handler
    }
)
```

**ADD implementation of _result_validator_node (around line 1078, before _answer_node):**
```python
async def _result_validator_node(self, state: BaseState) -> BaseState:
    """
    Validate query result before answer formatting.
    
    This node checks if the result makes sense given the intent,
    diagnoses issues, and routes accordingly.
    """
    debug_logger.agent_entry("result_validator", dict(state))
    before_state = dict(state)
    
    logger.info("🔍 [RESULT_VALIDATOR] ════════════════════════════════════════")
    logger.info("🔍 [RESULT_VALIDATOR] VALIDATING QUERY RESULT")
    logger.info("🔍 [RESULT_VALIDATOR] ════════════════════════════════════════")
    
    try:
        # Build and invoke validator subgraph
        validator_graph = self.result_validator_agent.build_subgraph()
        result = await validator_graph.ainvoke(state)
        
        # Extract validation results
        validation_routing = result.get("validation_routing", "answer")
        result_validation = result.get("result_validation")
        
        logger.info(f"🔍 [RESULT_VALIDATOR] ✅ Validation complete")
        logger.info(f"🔍 [RESULT_VALIDATOR] Routing: {validation_routing}")
        if result_validation:
            logger.info(f"🔍 [RESULT_VALIDATOR] Severity: {result_validation.get('severity')}")
            logger.info(f"🔍 [RESULT_VALIDATOR] Diagnosis: {result_validation.get('diagnosis')}")
        
        # Update state with validation results
        state["validation_routing"] = validation_routing
        state["result_validation"] = result_validation
        if result.get("retry_discovery_keywords"):
            state["retry_discovery_keywords"] = result["retry_discovery_keywords"]
            state["retry_discovery_reason"] = result.get("retry_discovery_reason")
        
        debug_logger.agent_exit("result_validator", before_state, dict(state))
        return state
        
    except Exception as e:
        logger.error(f"🔍 [RESULT_VALIDATOR] ❌ Validation failed: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        error = {
            "type": "VALIDATION_ERROR",
            "message": f"Result validation failed: {str(e)}",
            "error": str(e)
        }
        
        result_state = {**state, "error_info": error, "validation_routing": "error"}
        debug_logger.agent_exit("result_validator", before_state, dict(result_state))
        return result_state
```

### Step 5: Add Debug Logging
**File**: `langgraph_integration/debug_logger.py` (ADD method)

```python
def result_validation_complete(validation_result: Dict[str, Any], routing: str):
    """Log result validation completion."""
    self.logger.info(f"🔍 RESULT VALIDATION COMPLETE")
    self.logger.info(f"   Valid: {validation_result.get('valid')}")
    self.logger.info(f"   Severity: {validation_result.get('severity')}")
    self.logger.info(f"   Routing: {routing}")
    self.logger.info(f"   Diagnosis: {validation_result.get('diagnosis')}")
```

---

## TESTING CHECKLIST

- [ ] **Unit test**: Direct call to ResultValidatorAgent with mock state
- [ ] **Integration test**: Full orchestrator flow with result validation
- [ ] **Edge case**: Zero-row COUNT query triggers discovery retry
- [ ] **Edge case**: Zero-row DETAIL query proceeds to answer with warning
- [ ] **Edge case**: Large result (>1000) shows suggestion
- [ ] **Logging**: Validation decisions appear in LangGraph Studio trace

---

## QUICK TEST

After implementing, run:

```python
import asyncio
from langgraph_integration.agents.result_validator.agent import ResultValidatorAgent
from langgraph_integration.contracts.state import BaseState

# Create test state
state: BaseState = {
    "user_input": "How many customers?",
    "intent": {
        "operation": "query",
        "metrics": ["count"],
        "keywords_for_discovery": ["customer"],
        "primary_entities": ["customer"]
    },
    "exec_result": {
        "ok": True,
        "row_count": 0,
        "rows": [],
        "execution_time_ms": 45
    },
    "join_plan": {"strategy": "single", "primary_table": "Customer"},
    "sql_query": "SELECT COUNT(*) FROM Customer"
}

# Run validator
validator = ResultValidatorAgent()
graph = validator.build_subgraph()
result = asyncio.run(graph.ainvoke(state))

# Check routing
print(f"Routing: {result.get('validation_routing')}")
print(f"Diagnosis: {result.get('result_diagnosis')}")
```

Expected output:
```
Routing: discovery_retry
Diagnosis: {'is_count_query': True, 'likely_causes': [...], 'recovery_suggestion': 'retry_discovery'}
```

---

## NEXT STEPS AFTER PHASE 10a

1. **Phase 10b**: Fix `_validate_sql_node` (actually validate SQL syntax)
2. **Phase 10c**: Fix MCP JSON parsing errors
3. **Phase 10d**: Test end-to-end with "empty result → retry → success" flow
4. **Phase 10e**: Add observability & metrics collection

---

**Status**: Ready to implement. Questions? Ask now before we start coding.