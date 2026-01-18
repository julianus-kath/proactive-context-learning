# ADR 0034: SQL Agent Quality Debugging and Fixes

## Status
Accepted

## Date
2026-01-18

## Context

The SQL agent was experiencing quality degradation when handling German ERP queries via the Web UI. Despite the Windows MCP server being correctly connected to the MSSQL database, the agent appeared to fail silently on German queries while previously working on English Northwind-style queries.

### Symptoms Observed

1. Agent gave poor/incomplete answers to German ERP questions
2. Debug log file (`/tmp/sql_agent_debug.jsonl`) was stale - last modified 45 minutes before current session
3. Old logs showed PostgreSQL table references (`public.employees`) instead of MSSQL tables
4. Tool calls like `get_column_index` were returning errors silently

### Root Cause Analysis

Investigation revealed **THREE distinct issues**:

| Issue | Severity | Description |
|-------|----------|-------------|
| Debug Logger Not Working | P0 | `/stream` endpoint didn't write to debug logs |
| `get_column_index` Bug | P1 | Response parsing failed on nested list format |
| German Error Detection | P2 | Error keywords only checked English, not German |

## Decision

### Fix 1: Add Debug Logging to `stream_agent_execution()`

**Problem**: The `/stream` endpoint (used by Web UI) called `stream_agent_execution()` in `debug_stream.py`, which only yielded events for HTTP SSE streaming but did NOT write to the debug log file. Only `invoke_async()` in `agent.py` wrote debug logs, but this method was NOT used by `/stream`.

**Solution**: Import and call `DebugLogger` methods alongside each yield statement:

```python
from simple_sql_agent.debug_logger import get_debug_logger

async def stream_agent_execution(...):
    debug_log = get_debug_logger()

    # At query start:
    debug_log.query_start(display_question)
    yield {"type": "query_start", ...}

    # At LLM events:
    debug_log.llm_start()
    yield {"type": "llm_start", ...}

    # At tool events:
    debug_log.tool_call(tool_name, tool_input)
    yield {"type": "tool_call", ...}

    # At tool results:
    debug_log.tool_result(event_name, tool_output_str)
    yield {"type": "tool_result", ...}

    # At completion:
    debug_log.final_answer(...)
    yield {"type": "complete", ...}
```

**Files Modified**: `simple_sql_agent/debug_stream.py`

### Fix 2: Handle Nested List Format in `get_column_index`

**Problem**: The MCP server was returning `[[{...}]]` (nested list) but the parsing code expected `[{...}]` (flat list of dicts). This caused:
```json
{"tool_name": "get_column_index", "output": "Error getting column index: 'list' object has no attribute 'get'"}
```

**Solution**: Detect and unwrap nested list format before processing:

```python
if isinstance(result, list) and len(result) > 0:
    first_item = result[0]

    # Handle nested list format [[...]] - unwrap one level
    if isinstance(first_item, list):
        result = first_item
        first_item = result[0] if result else None

    # Now handle standard format [{"type": "text", "text": "..."}]
    if isinstance(first_item, dict):
        texts = [item.get("text", "") for item in result if isinstance(item, dict)]
        # ... rest of parsing
```

**Files Modified**: `simple_sql_agent/db/mcp_client.py`

### Fix 3: Add `list_tables` Fallback in `discover_tables`

**Problem**: When semantic search (`search_tables`) found no matches for German keywords, the agent had no fallback and returned empty results.

**Solution**: Fall back to `list_tables()` when search returns empty:

```python
# Fallback: If search returns empty or no results, try list_tables
if not search_results or (isinstance(search_results, str) and "no tables found" in search_results.lower()):
    logger.info(f"search_tables returned no results for '{query}', falling back to list_tables")
    list_result = await client.list_tables(page=1, page_size=20)
    if list_result:
        return {
            "ok": True,
            "text": f"Search for '{query}' found no direct matches. Here are all available tables:\n\n{list_result}",
            "tables": [],
            "fallback_used": True,
        }
```

**Files Modified**: `simple_sql_agent/tools/db_tools.py`

### Fix 4: German Error Keyword Detection

**Problem**: Error detection only checked for English keywords like `"error"` and `"failed"`, missing German database errors like `"Fehler"`, `"fehlgeschlagen"`, `"ungültig"`.

**Solution**: Added German error keywords to detection:

```python
# In mcp_client.py - execute_query response parsing
text_lower = text.lower()
if "error" in text_lower or "fehler" in text_lower or "fehlgeschlagen" in text_lower:
    return {"ok": False, "error": text}

# In agent.py - result parsing
error_keywords = ["failed", "error", "fehler", "fehlgeschlagen", "ungültig", "nicht gefunden"]
if any(kw in content_lower for kw in error_keywords):
    result["ok"] = False
    result["error"] = content
```

**Files Modified**: `simple_sql_agent/db/mcp_client.py`, `simple_sql_agent/agent.py`

## Consequences

### Positive

1. **Full observability**: All `/stream` endpoint events now logged to debug file
2. **Robust parsing**: `get_column_index` handles both flat and nested list formats
3. **Better fallback**: Agent can still discover tables even when semantic search fails
4. **German support**: Error detection works with both English and German database messages

### Debugging Workflow

After these fixes, debugging workflow is:

```bash
# Terminal 1: Watch debug stream
python simple_sql_agent/debug_stream.py

# Terminal 2: Run service
python -m simple_sql_agent.service

# Terminal 3: Send queries via Web UI or curl
```

The debug stream now shows real-time events:

```
═══════════════════════════════════════════════════════════════════════════════
🔍 USER QUESTION [17:45:12.345]
────────────────────────────────────────────────────────────────────────────────
Wie viele offene Kundenaufträge haben wir aktuell?
═══════════════════════════════════════════════════════════════════════════════

💭 LLM thinking... [17:45:12.500]

🔧 TOOL CALL: discover_tables [17:45:13.100]
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
📥 Input:
  {"query": "Kundenaufträge offen", "include_join_paths": true}

✓ TOOL RESULT: discover_tables [17:45:14.200]
📤 Output:
  ## Discovery Results for 'Kundenaufträge offen'
  ### dbo.Auftraege (relevance: 0.85, ~12000 rows)
  ...
```

## Lessons Learned

1. **Dual logging paths**: When adding streaming endpoints, ensure they use the same logging infrastructure as non-streaming paths
2. **MCP response formats**: Always handle multiple response formats (nested vs flat lists, text vs JSON)
3. **Internationalization**: Error detection must handle the language of the data source, not just English
4. **Fallback strategies**: Semantic search failures should degrade gracefully to broader queries

## References

- ADR 0030: Simple SQL Agent Architecture
- ADR 0031: Simple SQL Agent Complete Architecture
- MCP Server documentation (Windows deployment)
