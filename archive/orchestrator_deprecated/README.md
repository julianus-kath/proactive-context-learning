# DEPRECATED: QueryOrchestrator (orchestrator.py)

**Status**: ARCHIVED - NOT USED IN PRODUCTION

## Why This Was Removed

The `QueryOrchestrator` class in `orchestrator.py` was an **experimental multi-agent system** that tried to compose four specialized agents (Discovery, JoinSQL, Exec, Answer).

However, this was replaced by the **unified `DatabaseWorkflow` system** in `graph_definition.py`, which:
- ✅ Is proven to work
- ✅ Is currently used by the FastAPI service (`langgraph_service.py`)
- ✅ Uses both `/process_query` and `/process_conversation` endpoints
- ✅ Implements the Scout Catalog (views-first) architecture from repo.md

## What Happened

Both code paths were causing confusion and technical debt:

```
BEFORE (Broken):
  UI → /process_conversation → QueryOrchestrator (fails to find tables)
  Curl → /process_query → DatabaseWorkflow (works fine)

AFTER (Fixed):
  UI → /process_conversation → DatabaseWorkflow (now works!)
  Curl → /process_query → DatabaseWorkflow (still works)
  
  ❌ QueryOrchestrator removed
```

## Real Fix

The actual issue wasn't two systems—it was that the **intent parser was too conservative** about asking for clarification.

### Solution Implemented:

1. **Intent Parser Refactor** (`langgraph_integration/prompts/__init__.py`)
   - CHANGED: Intent parser now ALWAYS returns `operation="query"`
   - CHANGED: Removed "clarify" option—table discovery is downstream
   - REASON: Intent parsing should only extract keywords, not try to find tables
   - The `select_tables` node uses `search_tables_mcp` (Scout) to find actual tables

2. **Remove QueryOrchestrator**
   - Archived the experimental multi-agent system
   - Focus on one proven system: `DatabaseWorkflow`

## If You Need The Code Later

The full `orchestrator.py` is saved here: `archive/orchestrator_deprecated/orchestrator.py`

To restore it:
```bash
mv archive/orchestrator_deprecated/orchestrator.py langgraph_integration/
```

But **don't do this**. Use `graph_definition.py` instead.

## Architecture Now

```
langgraph_service.py (FastAPI)
  ├─ /process_query → DatabaseWorkflow ✅
  └─ /process_conversation → DatabaseWorkflow ✅

DatabaseWorkflow (graph_definition.py)
  ├─ _index_database → check MCP health
  ├─ _get_schema → list_tables_mcp (Scout catalog overview)
  ├─ _parse_intent → extract keywords (intent parser)
  ├─ _select_tables → search_tables_mcp (discover relevant tables)
  ├─ _generate_sql → use LLM to generate MSSQL
  ├─ _execute_query → query_bounded_mcp (safe execution)
  └─ _format_results → present to user
```

---

**Last Updated**: During bug fix session  
**Reason**: Consolidate to single proven orchestration system