# Fix Plan: Three Production Failures

## Root Causes Identified

### Failure 1: Wrong Data (Payroll instead of Sales)
**Problem:** Scout ranking returns payroll tables instead of product/sales tables.

**Root Cause:** Intent entities don't include "sales"/"umsatz", so the product+sales composite boost (line 439-448 in scout_runner.py) never fires.

**Fix:** Add fallback to text-based entity detection in Scout when LLM extraction fails.

### Failure 2: SQL Generation Gap (Temporal Queries)
**Problem:** "How have our sales improved from September to October?" fails with "couldn't generate SQL".

**Root Cause:** Multiple possible:
1. LLM isn't extracting metrics correctly (no "sum"/"total" metric)
2. Intent routing isn't classifying as `sum_with_period`
3. Exception in _generate_sum_with_period_sql() being swallowed

**Fix:** Add robust logging + fallback logic in _derive_action_hints to handle keyword-based classification.

### Failure 3: 500 Errors (Two Specific Queries)
**Problem:** "What table did you get that from?" and "When do we have to order..." crash with 500.

**Root Cause:** Unhandled exceptions in agent nodes, or null-check failures.

**Fix:** Add comprehensive error handling and null-checks in orchestrator nodes.

---

## Implementation Plan

### Change 1: Scout Ranking - Fallback Entity Detection
**File:** `mcp_server/scout_runner.py`

Add keywords-based entity detection when intent_entities is empty or insufficient:

```python
# Around line 400 in search_tables()
# Extract fallback entities from query text itself if intent.entities is empty
intent_entities = intent.get("entities", []) or []
if not intent_entities:
    # Fallback: extract common entities from query text
    query_lower = query.lower()
    fallback_entities = []
    entity_keywords = {
        "product": ["product", "products", "artikel", "sku", "item", "items"],
        "customer": ["customer", "customers", "kunde", "kunden", "client"],
        "sales": ["sales", "verkauf", "revenue", "umsatz", "rechnung", "invoice"],
        "order": ["order", "orders", "bestellung", "bestellungen"]
    }
    for entity_type, keywords in entity_keywords.items():
        if any(kw in query_lower for kw in keywords):
            fallback_entities.append(entity_type)
    intent_entities = fallback_entities
```

### Change 2: Intent Parser - Robust Action Classification
**File:** `langgraph_integration/agents/intent_parser/agent.py`

Add keyword-based fallback in _derive_action_hints when metrics are empty:

```python
# After line 558, add:
# Fallback: extract metrics from raw text if LLM extraction empty
if not metrics:
    text = (user_input or "").lower()
    if any(k in text for k in ["sum", "total", "umsatz", "verkauf", "revenue"]):
        metrics.append("sum")
    if any(k in text for k in ["count", "how many", "wie viele"]):
        metrics.append("count")
```

And add explicit temporal query detection:

```python
# After line 605, add:
# Fallback: explicit temporal query detection
elif any(k in text for k in ["improved", "changed", "growth", "increased", "since", "from", "to"]) and \
     any(m in text for m in ["october", "oktober", "september", "januar", "februar"]):
    required_action = "sum_with_period"  # Prioritize temporal even without metrics
```

### Change 3: Orchestrator - Error Handling Hardening
**File:** `langgraph_integration/orchestrator.py`

Wrap all agent nodes with comprehensive try/catch and null-checks:

```python
# In _discovery_node (around line 633)
try:
    discovery_graph = self.discovery_agent.build_subgraph()
    if not discovery_graph:
        raise ValueError("Discovery graph is None")
    result = await discovery_graph.ainvoke(state)
    if not isinstance(result, dict):
        raise TypeError(f"Discovery result must be dict, got {type(result)}")
    ...

# In _join_sql_node (around line 750)
try:
    if not join_plan:
        error = {"type": "NO_JOIN_PLAN", "message": "Join plan is empty"}
        return {**state, "error_info": error, "sql_query": ""}
    join_graph = self.join_sql_agent.build_subgraph()
    ...
```

### Change 4: Service Layer - Better Error Messages
**File:** `chatbot_ui/langgraph_service.py`

Enhance error detail propagation:

```python
# Around line 154-169
try:
    final_response = await orchestrator.process_query(request.user_input.strip())
    if isinstance(final_response, dict) and final_response.get("error_info"):
        error_msg = final_response["error_info"].get("message", "Unknown error")
        raise HTTPException(
            status_code=400,
            detail=f"Query processing failed: {error_msg}"
        )
    return QueryResponse(final_response=final_response, status="success")
except HTTPException:
    raise
except Exception as e:
    logger.error(f"Service error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")
```

---

## Testing Strategy

1. **Unit tests** for each fallback path
2. **Integration tests** for the three failure queries
3. **Regression tests** for existing passing queries (customer count, etc.)

---

## Implementation Order

1. Change 2 (Intent Parser) - lowest risk, highest impact
2. Change 1 (Scout Ranking) - improves discovery accuracy
3. Change 3 (Orchestrator Error Handling) - prevents 500 errors
4. Change 4 (Service Layer) - better diagnostics