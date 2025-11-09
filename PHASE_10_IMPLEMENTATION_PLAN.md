# PHASE 10 Implementation Plan: Your North Star
**Status**: Master Plan | Date: November 2025

> This document is your reference when you get lost in implementation details. Return here whenever you lose context.

---

## MISSION (Reminder)

Build a **Result Validator → Discovery Fixer → Intent Enhancer** pipeline that catches garbage outputs and prevents silent failures.

**Success Metric**: System correctly identifies "0 rows = wrong discovery" vs. "0 rows = genuinely empty" and recovers appropriately.

---

## THREE-PHASE ROADMAP

### 🎯 PHASE 10a: Result Validator (THIS WEEK)
**Goal**: Catch 0-row, too-many-row, and nonsensical results before Answer agent formats them.

**Status**: ➡️ TO DO

**Scope**:
- [ ] Build `ResultValidator` node (deterministic, ~100 lines)
- [ ] Implement validation logic (0 rows, >5000 rows, unexpected schema)
- [ ] Wire into orchestrator between `ExecRecovery` and `Answer`
- [ ] Add comprehensive tests (10-15 test cases)
- [ ] Test on actual MCP with synthetic data

**Time Estimate**: 4-6 hours  
**Risk**: Low (isolated component)  
**Benefit**: Immediate (catches 20-30% of silent failures)

**Deliverables**:
- `langgraph_integration/agents/result_validator/agent.py` (new module)
- `langgraph_integration/agents/result_validator/__init__.py`
- `tests/test_result_validator_phase_10a.py`
- `langgraph_integration/agents/result_validator/README.md`
- Updated orchestrator graph

---

### 🔧 PHASE 10b: Discovery & Intent Hardening (NEXT WEEK)
**Goal**: Fix Intent Parser and Discovery Agent to reduce bad intent extraction and wrong table selection.

**Status**: ➡️ PLANNED

**Scope**:
- [ ] Add confidence check to DiscoveryAgent (early exit if < 0.5)
- [ ] Implement archive/historical table filtering
- [ ] Re-order `fetch_column_index` to happen earlier
- [ ] Add German synonym expansion to IntentParser
- [ ] Implement intent-aware re-ranking in Discovery
- [ ] Add comprehensive test coverage for German queries

**Time Estimate**: 3-4 days  
**Risk**: Medium (touches core agents)  
**Benefit**: Major (reduces discovery failures by ~30-40%)

**Deliverables**:
- Enhanced `IntentParser` with German support
- Enhanced `DiscoveryAgent` with confidence checks
- `langgraph_integration/utils/german_synonyms.py` (new utility)
- `tests/test_discovery_confidence_phase_10b.py`
- Updated prompts with German examples
- ADR-0025: Intent-Driven Discovery Refinement (new)

---

### 🎨 PHASE 11: Adaptive Recovery & Observability (FUTURE)
**Goal**: Build intelligent retry paths and visibility into what's working/failing.

**Status**: ➡️ FUTURE

**Scope**:
- [ ] Implement `RetryStrategyNode` (route failures to appropriate recovery)
- [ ] Add telemetry/metrics around discovery success rate
- [ ] Implement cache staleness detection
- [ ] Add ClarificationAgent (if needed)
- [ ] Build observability dashboard

**Time Estimate**: 1-2 weeks  
**Risk**: High (complex state management)  
**Benefit**: Long-term (system becomes self-healing)

**Deliverables**:
- `RetryStrategyNode` in orchestrator
- Metrics collection module
- ClarificationAgent (if applicable)
- Observability docs

---

## PHASE 10a DETAILED BREAKDOWN

### What is Result Validator?

A **deterministic checking node** (not an agent—no LLM) that validates execution results against intent.

```
Input: {user_query, intent, discovery_results, sql_query, exec_result}
Output: {valid: bool, issue: str, suggestion: str, retry_action: str}

Examples:
- Input: exec_result = {ok: true, rows: [], row_count: 0}
  Output: {valid: false, issue: "zero_rows", suggestion: "Maybe wrong table", retry_action: "try_next_discovery_candidate"}

- Input: exec_result = {ok: true, rows: [{...}], row_count: 1}
  Output: {valid: true, issue: null, suggestion: null, retry_action: null}

- Input: exec_result = {ok: true, rows: [{...}...], row_count: 10000, truncated: true}
  Output: {valid: false, issue: "too_many_rows", suggestion: "Need aggregation", retry_action: "replan_with_aggregation"}
```

### Implementation Strategy

**File**: `langgraph_integration/agents/result_validator/agent.py`

```python
from typing import TypedDict, Literal, Optional, Dict, Any

class ValidationResult(TypedDict, total=False):
    valid: bool
    issue: Literal[
        "zero_rows",
        "too_many_rows", 
        "schema_mismatch",
        "all_nulls",
        "suspicious_values"
    ] or None
    issue_severity: Literal["warning", "error"] or None
    suggestion: str or None
    retry_action: Literal[
        "accept",
        "ask_user",
        "try_next_candidate",
        "replan_with_aggregation",
        "replan_with_filter"
    ] or None

class ResultValidator:
    """Deterministic validation of execution results."""
    
    def validate(
        self,
        user_query: str,
        intent: Dict[str, Any],
        discovery_results: List[str],
        sql_query: str,
        exec_result: Dict[str, Any],
        config: Dict[str, Any] = None
    ) -> ValidationResult:
        """
        Validate execution result against intent.
        
        Returns:
        - {valid: true} → pass to Answer agent
        - {valid: false, retry_action: "try_next_candidate"} → pass to Discovery for retry
        - {valid: false, retry_action: "replan_with_aggregation"} → pass back to JoinSQL
        - {valid: false, retry_action: "ask_user"} → pass to Answer with clarification
        """
```

### Validation Checks

#### Check 1: Zero Rows Detection
```python
if exec_result.get("row_count", 0) == 0:
    # Is zero rows expected?
    metrics = intent.get("metrics", [])
    
    if "count" in metrics:
        # count(customers) = 0 could be real or wrong table
        # Check discovery confidence
        intent_confidence = intent.get("confidence", 1.0)
        if intent_confidence < 0.7:
            return {
                "valid": False,
                "issue": "zero_rows",
                "issue_severity": "error",
                "suggestion": "Low intent confidence + 0 rows = likely wrong table",
                "retry_action": "try_next_candidate"
            }
        else:
            return {
                "valid": True,  # Accept it
                "issue": "zero_rows",
                "issue_severity": "warning",
                "suggestion": "Query returned 0 rows (might be empty)"
            }
    elif "sum" in metrics or "total" in metrics:
        # sum(amount) = 0 is suspicious
        return {
            "valid": False,
            "issue": "zero_rows",
            "suggestion": "Sum query returned 0 (likely wrong table or filter too strict)",
            "retry_action": "try_next_candidate"
        }
```

#### Check 2: Too Many Rows Detection
```python
if exec_result.get("truncated", False) or exec_result.get("row_count", 0) >= 5000:
    metrics = intent.get("metrics", [])
    
    if "count" in metrics:
        # User asked for count, got many rows? That's an error
        return {
            "valid": False,
            "issue": "too_many_rows",
            "suggestion": "Expected aggregated count, got many rows",
            "retry_action": "replan_with_aggregation"
        }
    else:
        # User asked for details, got truncated result
        return {
            "valid": False,
            "issue": "too_many_rows",
            "suggestion": "Result truncated (>5000 rows). Need filter or aggregation",
            "retry_action": "replan_with_filter"
        }
```

#### Check 3: Schema Mismatch
```python
# Check if result columns match expected columns
expected_columns = self._extract_expected_columns(intent, sql_query)
actual_columns = list(exec_result.get("rows", [{}])[0].keys()) if exec_result.get("rows") else []

if expected_columns and actual_columns:
    if not any(col in actual_columns for col in expected_columns):
        return {
            "valid": False,
            "issue": "schema_mismatch",
            "suggestion": f"Expected columns like {expected_columns}, got {actual_columns}",
            "retry_action": "try_next_candidate"
        }
```

#### Check 4: All Nulls
```python
if exec_result.get("rows"):
    first_row = exec_result["rows"][0]
    all_nulls = all(v is None for v in first_row.values())
    
    if all_nulls:
        return {
            "valid": False,
            "issue": "all_nulls",
            "suggestion": "Result contains only NULLs (likely wrong join or column)",
            "retry_action": "try_next_candidate"
        }
```

### Orchestrator Integration

**Current Flow**:
```
IntentParser → DiscoveryAgent → JoinSQL → SQLValidator → ExecRecovery → Answer
```

**New Flow (Phase 10a)**:
```
IntentParser → DiscoveryAgent → JoinSQL → SQLValidator → ExecRecovery 
  ↓
[NEW] ResultValidator
  ├─ valid=true → Answer
  ├─ retry_action="try_next_candidate" → DiscoveryAgent (with state.failed_candidates)
  ├─ retry_action="replan_with_aggregation" → JoinSQL (with instruction)
  └─ retry_action="ask_user" → Answer (with clarification prompt)
```

**Code Changes**:
```python
# In orchestrator.py or graph_definition.py

from langgraph_integration.agents.result_validator import ResultValidator

# Add node
def result_validator_node(state: BaseState) -> BaseState:
    validator = ResultValidator()
    
    validation = validator.validate(
        user_query=state.get("user_input", ""),
        intent=state.get("intent", {}),
        discovery_results=state.get("relevant_tables", []),
        sql_query=state.get("sql_query", ""),
        exec_result=state.get("exec_result", {})
    )
    
    state["validation_result"] = validation
    return state

graph.add_node("result_validator", result_validator_node)

# Add conditional edges
def route_after_validation(state: BaseState) -> Literal["answer", "discovery", "join_sql", "ask_clarification"]:
    validation = state.get("validation_result", {})
    
    if validation.get("valid", True):
        return "answer"
    
    retry_action = validation.get("retry_action", "ask_user")
    
    if retry_action == "try_next_candidate":
        return "discovery"  # Go back to discovery
    elif retry_action == "replan_with_aggregation":
        return "join_sql"  # Go back to join planning
    elif retry_action in ["ask_user", "accept"]:
        return "answer"
    
    return "answer"  # Default safe path

graph.add_conditional_edges(
    "exec_recovery",
    route_after_validation,
    {
        "answer": "answer",
        "discovery": "discovery",
        "join_sql": "join_sql",
        "ask_clarification": "answer"
    }
)

# Update edges
graph.add_edge("exec_recovery", "result_validator")
graph.add_edge("result_validator", route_after_validation)
```

### Testing Strategy

**Test File**: `tests/test_result_validator_phase_10a.py`

```python
@pytest.mark.asyncio
class TestResultValidator:
    def test_zero_rows_with_low_confidence(self):
        """0 rows + low confidence = try_next_candidate"""
        
    def test_zero_rows_with_high_confidence(self):
        """0 rows + high confidence = accept it"""
        
    def test_count_returns_too_many(self):
        """User asked for count, got 10k rows = replan_with_aggregation"""
        
    def test_schema_mismatch(self):
        """Returned columns don't match expected = try_next_candidate"""
        
    def test_all_nulls(self):
        """All NULL values = try_next_candidate"""
        
    def test_valid_result(self):
        """Normal result with rows = accept"""
```

### Success Criteria (Phase 10a)

✅ Result Validator correctly identifies:
- [ ] Zero rows (with confidence checks)
- [ ] Too many rows
- [ ] Schema mismatches
- [ ] All NULL results

✅ Orchestrator correctly routes:
- [ ] Valid results to Answer
- [ ] Invalid results with right retry action
- [ ] Doesn't infinite loop on retry

✅ Tests pass:
- [ ] All 15+ test cases pass
- [ ] Integration test with synthetic MCP data
- [ ] No regressions in existing tests

---

## PHASE 10b AT A GLANCE

### Intent Parser Hardening
- [ ] Add German entity synonym list (Kunde, Artikel, Umsatz, etc.)
- [ ] Add German query examples to LLM prompts
- [ ] Lower confidence threshold from 0.6 to 0.5 (trigger clarification earlier)
- [ ] Fix double-extraction bug in `_extract_keywords`

### Discovery Agent Hardening
- [ ] Check intent.confidence before searching MCP
- [ ] Filter out archive/historical tables
- [ ] Move `fetch_column_index` earlier (before schema building)
- [ ] Implement intent-aware re-ranking
- [ ] Add tests for German queries

### Test Coverage
- [ ] German intent parsing (10+ test cases)
- [ ] Discovery with low confidence (5+ test cases)
- [ ] Archive table filtering (3+ test cases)
- [ ] End-to-end flow tests (5+ test cases)

---

## PHASE 11 AT A GLANCE

### Adaptive Recovery
- [ ] Build `RetryStrategyNode` to intelligently route failures
- [ ] Track retry attempts per query type
- [ ] Implement exponential backoff for repeated failures
- [ ] Add metrics around success/failure rates

### Observability
- [ ] Instrument Discovery with metrics (time, candidates, selection)
- [ ] Track validation failures (what types, how often)
- [ ] Build dashboard showing system health
- [ ] Alert on anomalies (unexpected zero rows, slow queries)

---

## HOW TO USE THIS DOCUMENT

### When You Start Phase 10a
1. Read "Phase 10a Detailed Breakdown" above
2. Implement following the "Implementation Strategy" section
3. Test using "Testing Strategy" section
4. Verify against "Success Criteria" checklist

### When You Get Lost
1. Return to "Three-Phase Roadmap" to confirm what phase you're in
2. Check "Success Criteria" to verify progress
3. Re-read "Mission" at top to remember the goal

### When You Want Context
1. Read "INTENT_PARSER_DEEP_DIVE.md" for background on Intent Parser issues
2. Read "DISCOVERY_AGENT_DEEP_DIVE.md" for background on Discovery Agent issues
3. Read "MCP_SERVER_ARCHITECTURE.md" for MCP context

### When You Want to Handoff
Copy the relevant section (e.g., "Phase 10a Detailed Breakdown") and give it to whoever takes over.

---

## KEY PRINCIPLES (Non-Negotiable)

1. **Small, reversible changes**: Phase 10a is <400 lines of new code
2. **Isolated components**: Result Validator is deterministic, no LLM calls
3. **Comprehensive tests**: Every edge case covered before deploying
4. **No silent failures**: If something goes wrong, log it explicitly
5. **Maintain compatibility**: Don't break existing agents
6. **Document as you go**: Each module gets a README

---

## RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Orchestrator graph breaks | Low | High | Write 10+ graph routing tests first |
| Infinite retry loop | Medium | High | Add retry count limit (max 3) |
| Result Validator rejects valid results | Medium | Medium | Conservative thresholds; manual review of edge cases |
| Phase 10b doesn't fix German queries | Medium | Medium | Test early with German data; iterate on synonym list |
| Performance regression | Low | Medium | Measure baseline; validate latency before merge |

---

## DEPENDENCIES

**Phase 10a depends on**:
- [ ] Existing orchestrator working
- [ ] MCP returning results
- [ ] ExecRecovery returning execution results

**Phase 10b depends on**:
- [ ] Phase 10a complete
- [ ] German synonym list built
- [ ] LLM prompts updated

**Phase 11 depends on**:
- [ ] Phase 10a + 10b complete
- [ ] Metrics instrumentation in place
- [ ] Dashboard tool available

---

## DELIVERABLES CHECKLIST

### Phase 10a
- [ ] `agents/result_validator/agent.py` (new)
- [ ] `agents/result_validator/__init__.py` (new)
- [ ] `agents/result_validator/README.md` (new)
- [ ] `tests/test_result_validator_phase_10a.py` (new)
- [ ] Updated orchestrator with validation node
- [ ] Updated state contracts (if needed)
- [ ] All tests passing

### Phase 10b
- [ ] Enhanced `IntentParserAgent`
- [ ] Enhanced `DiscoveryAgent`
- [ ] German synonym utility
- [ ] German prompt examples
- [ ] `tests/test_discovery_confidence_phase_10b.py`
- [ ] ADR-0025 (if architectural change)
- [ ] All tests passing

### Phase 11
- [ ] `RetryStrategyNode` implementation
- [ ] Metrics collection module
- [ ] Observability dashboard
- [ ] Updated orchestrator
- [ ] Documentation

---

## SUCCESS METRICS

### Phase 10a Success
- System correctly identifies 0-row vs. empty result in **90%+ of cases**
- **0 infinite retry loops** on 1000+ synthetic queries
- **<100ms** additional latency per query

### Phase 10b Success
- German query success rate: **>80%** (up from ~60%)
- Intent confidence < 0.5 triggers clarification **100%** of the time
- Archive table filtering works in **95%+** of cases

### Phase 11 Success
- System self-recovers from failed discoveries **50%+** of the time
- Dashboard shows **>95%** query success rate
- **Zero** silent failures (all issues logged)

---

*End of Phase 10 Implementation Plan. This is your North Star. Return to this when lost.*