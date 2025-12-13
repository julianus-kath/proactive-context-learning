# Evaluation System Integration Guide

This guide explains how to integrate the evaluation client into the LangGraph service to emit structured trace events.

## Overview

The evaluation system is designed to be **non-intrusive**:
1. LangGraph service receives optional headers: `X-Eval-Run-Id`, `X-Eval-Query-Id`
2. Service passes these IDs through the agent state
3. Service emits trace events via `eval_client.emit_event()` at key pipeline stages
4. If eval service is unavailable, events are silently dropped (non-blocking)

## Integration Steps

### Step 1: Import EvalClient in langgraph_service.py

At the top of `chatbot_ui/langgraph_service.py`:

```python
from eval.eval_client import get_eval_client
```

### Step 2: Extract Eval Headers and Add to State

In the `/chat` endpoint handler:

```python
@app.post("/chat")
async def chat(
    request: QueryRequest,
    x_eval_run_id: Optional[str] = Header(None),
    x_eval_query_id: Optional[str] = Header(None),
):
    """Process user query through orchestrator."""
    
    # Extract eval headers
    eval_run_id = x_eval_run_id or str(uuid.uuid4())
    eval_query_id = x_eval_query_id or "standalone"
    
    # Include in orchestrator state
    state = {
        "user_input": request.user_input,
        # ... other fields ...
        "eval_run_id": eval_run_id,
        "eval_query_id": eval_query_id,
    }
    
    # ... rest of handler ...
```

### Step 3: Emit Trace Events at Key Stages

After each major pipeline stage, emit an event:

```python
import asyncio
from eval.eval_client import get_eval_client

@app.post("/chat")
async def chat(request: QueryRequest, ...):
    eval_client = get_eval_client()
    eval_run_id = "..."  # from header
    eval_query_id = "..."  # from header
    
    try:
        # Stage 1: Intent Parsing
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_start",
            stage="intent_parsing",
        )
        
        intent = await parse_intent(request.user_input)
        
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_complete",
            stage="intent_parsing",
            data={"intent": intent},
        )
        
        # Stage 2: Discovery
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_start",
            stage="discovery",
        )
        
        tables = await discover_tables(intent)
        
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_complete",
            stage="discovery",
            data={"tables_found": tables},
        )
        
        # ... continue for other stages ...
        
        # Final stage: Execution
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_start",
            stage="execution",
        )
        
        result = await execute_query(sql)
        rows = result.get("rows", [])
        
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="stage_complete",
            stage="execution",
            data={
                "row_count": len(rows),
                "sql": sql,
                "tables_used": tables,
            },
        )
        
        return {
            "final_response": final_text,
            "exec_result": {
                "sql_query": sql,
                "tables_used": tables,
                "rows": rows,
            }
        }
    
    except Exception as e:
        eval_client.emit_event_sync(
            run_id=eval_run_id,
            query_id=eval_query_id,
            event_type="error",
            stage="execution",
            error=str(e),
        )
        raise
```

### Step 4: Save Final Artifact (Optional)

After query completes, save the full artifact:

```python
# In the /chat handler, at the end:

artifact = {
    "query_id": eval_query_id,
    "question": request.user_input,
    "status": "success",
    "final_answer_text": result["final_response"],
    "sql_executed": [result.get("exec_result", {}).get("sql_query", "")],
    "tables_used": result.get("exec_result", {}).get("tables_used", []),
    "row_count": len(result.get("exec_result", {}).get("rows", [])),
    "latency_ms_total": int((time.time() - start_time) * 1000),
}

# Non-blocking save (sync version to avoid blocking response)
eval_client.save_query_artifact_sync(eval_run_id, eval_query_id, artifact)

return result
```

## Example: Minimal Integration

Here's the minimal code needed to add evaluation support to an existing `/chat` endpoint:

```python
import time
from typing import Optional
from fastapi import Header
from eval.eval_client import get_eval_client

@app.post("/chat")
async def chat(
    request: QueryRequest,
    x_eval_run_id: Optional[str] = Header(None),
    x_eval_query_id: Optional[str] = Header(None),
):
    start_time = time.time()
    eval_client = get_eval_client()
    eval_run_id = x_eval_run_id or str(uuid.uuid4())
    eval_query_id = x_eval_query_id or "standalone"
    
    try:
        # ... existing query logic ...
        result = await process_query(request.user_input)
        
        # Emit final artifact
        artifact = {
            "query_id": eval_query_id,
            "question": request.user_input,
            "status": "success",
            "final_answer_text": result.get("final_response"),
            "sql_executed": [],  # populate if available
            "tables_used": [],   # populate if available
            "row_count": None,   # populate if available
            "latency_ms_total": int((time.time() - start_time) * 1000),
        }
        eval_client.save_query_artifact_sync(eval_run_id, eval_query_id, artifact)
        
        return result
    
    except Exception as e:
        eval_client.emit_event_sync(
            eval_run_id, eval_query_id, "error", error=str(e)
        )
        raise
```

## Event Types

Standard event types emitted:

- **`stage_start`**: Pipeline stage beginning (sent before work)
- **`stage_complete`**: Pipeline stage finished (sent with results)
- **`error`**: Stage failed with exception
- **`retry`**: Query is being retried (for recovery agents)
- **`final_result`**: Complete query result is ready

## Data Field Guidelines

The `data` field in events should include:

For discovery stages:
```json
{
  "tables_found": ["orders", "customers"],
  "table_confidence": [0.95, 0.87]
}
```

For SQL generation:
```json
{
  "sql_generated": "SELECT * FROM orders WHERE...",
  "tables_referenced": ["orders", "customers"]
}
```

For execution:
```json
{
  "row_count": 42,
  "sql_executed": "SELECT * FROM orders WHERE...",
  "tables_used": ["orders"],
  "execution_time_ms": 234
}
```

For answer formatting:
```json
{
  "final_answer": "There are 42 orders from 2024...",
  "answer_length": 50
}
```

## Handling Non-Blocking Failures

The `eval_client` methods have built-in non-blocking error handling:

```python
# This will NOT raise, even if eval service is down
eval_client.emit_event_sync(run_id, query_id, "stage_complete", data={...})

# Failures are logged at DEBUG level (silent by default)
# Set LOG_LEVEL=DEBUG to see eval client debug messages
```

To verify events are being sent:

```bash
# In one terminal
python -m eval.service

# In another, watch the trace_events file
tail -f eval/runs/<run_id>/trace_events.jsonl
```

## Testing Instrumentation

Create a simple test in `tests/test_eval_integration.py`:

```python
import pytest
import json
from pathlib import Path
from eval.eval_client import EvalClient

def test_eval_client_non_blocking():
    """Verify eval client failures don't break queries."""
    client = EvalClient("http://localhost:9999")  # bad URL
    
    # Should not raise
    client.emit_event_sync(
        "test_run",
        "Q1",
        "stage_complete",
        data={"test": "data"}
    )
    
    # Confirm no exceptions
    assert True

def test_eval_artifact_storage():
    """Verify artifacts are stored correctly."""
    client = EvalClient("http://localhost:7001")
    
    artifact = {
        "query_id": "Q1",
        "question": "Test question",
        "status": "success",
        "sql_executed": ["SELECT 1"],
        "row_count": 1,
    }
    
    client.save_query_artifact_sync("test_run", "Q1", artifact)
    
    # Check filesystem
    run_dir = Path("eval/runs/test_run")
    assert (run_dir / "Q1.json").exists()
```

## Troubleshooting

### Events not being recorded

1. Check eval service is running: `curl http://localhost:7001/health`
2. Check `EVAL_TRACKING_URL` in .env matches running service
3. Verify headers are being passed through FastAPI correctly:
   ```python
   # Add debug log in handler
   print(f"Eval headers: run_id={x_eval_run_id}, query_id={x_eval_query_id}")
   ```

### LangGraph service is slower

The eval_client uses 2s timeout and non-blocking calls. If you're seeing slowdown:

1. Reduce timeout in eval_client.py (currently 2.0s)
2. Use async emit_event() instead of emit_event_sync()
3. Run eval service on faster machine
4. Disable eval system with `EVAL_ENABLED=0`

### Events are sent but artifacts are empty

The artifact saving happens at the /chat endpoint level. Ensure:

1. The final response contains all necessary data
2. You're calling `save_query_artifact_sync()` with complete artifact
3. Check logs for any write permission errors

---

**Status**: Instrumentation is optional; system works without it.  
**Recommendation**: Add instrumentation gradually, starting with stage_complete events.
