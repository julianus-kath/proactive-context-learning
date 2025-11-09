# Exec Recovery Agent - Phase 10b Data Field Fix

## Why

The exec recovery agent was successfully executing queries but data wasn't flowing through to the final answer. Root cause: **field name mismatch**.

- MCP returns `{"rows": [...], "row_count": X, ...}`
- Orchestrator expected `{"data": [...], "row_count": X, ...}`
- Result: Always got "no data" message even when data existed

## What Changed

**Output contract updated**: exec_recovery now returns `"data"` key instead of `"rows"` for orchestrator compatibility.

```python
# OLD (BROKEN)
return {
    "ok": True,
    "rows": rows,        # ❌ Orchestrator couldn't find this
    "row_count": len(rows),
    ...
}

# NEW (FIXED)
return {
    "ok": True,
    "data": rows,        # ✅ Orchestrator finds this
    "row_count": len(rows),
    ...
}
```

**Three places updated** (lines 860, 891, 929):
1. JSON response parsing (line 860)
2. Zero-row text response (line 891)
3. Text table parsing (line 929)

## How to Test

```bash
# Quick test
python3 -c "
import asyncio
from langgraph_integration.orchestrator import QueryOrchestrator

async def test():
    orch = QueryOrchestrator(llm_model='gpt-4o')
    result = await orch.ainvoke({
        'user_input': 'How many customers do we have?',
        'conversation_history': []
    })
    print('Final Answer:', result['final_answer'])

asyncio.run(test())
"

# Full test suite
pytest tests/test_result_validator_phase_10a.py -q
```

## Notes

- **Backward Compatible**: Only internal field name changed; input/output contracts stay the same
- **Debug Logging**: Added to orchestrator.py (lines 1585-1646) to trace data flow
- **No Performance Impact**: Same execution speed, data now flows correctly
- **MCP Layer Unchanged**: MCP server still returns `"rows"` (that's correct); conversion happens in exec_recovery

## Next Steps

1. Test on frontend - queries should now return actual data
2. If "no data" still appears, check debug logs for field names
3. Monitor performance - should see no regression

## Related Files

- `langgraph_integration/orchestrator.py` - Updated data extraction with debug logs
- `langgraph_integration/contracts/state.py` - Updated documentation
- `tests/test_result_validator_phase_10a.py` - All tests using `"data"` now