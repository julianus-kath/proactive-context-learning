# Archived: Monolithic Workflow (Pre-Phase 8)

## ⚠️ DEPRECATED - DO NOT USE

These files represent the **monolithic (single-class) approach** to query orchestration that was used before Phase 8.

### Reason for Archival

**Phase 8 (ADR-0019)** replaced the monolithic system with a **multi-agent orchestrator** that:
- Decomposes query processing into 4 specialized agents
- Enables better reasoning per phase (discovery, planning, execution, formatting)
- Improves testability and maintainability
- Achieves ~20-30% better performance

### Files Archived

| File | Description | Replaced By |
|------|-------------|-------------|
| `graph_definition.py` | Monolithic LangGraph workflow (12+ methods in single class) | `langgraph_integration/orchestrator.py` |
| `answer_first_orchestrator.py` | Phase 7.1 approach (answer-first with Scout Mode) | Multi-agent orchestrator (all agents) |

### Why the Old Approach Failed

**Problems with monolithic `DatabaseWorkflow`**:
1. ❌ Mixed concerns (parsing, discovery, SQL gen, execution, formatting in one class)
2. ❌ Generic LLM for all phases (no specialized reasoning)
3. ❌ Hard to debug (which phase failed?)
4. ❌ Hard to test (must test entire workflow)
5. ❌ Hard to optimize (changing one phase affects all)
6. ❌ 65% table discovery success rate
7. ❌ 72% query execution success rate

### Why the New Approach Works Better

**Benefits of multi-agent orchestrator**:
1. ✅ Separation of concerns (each agent has one job)
2. ✅ Specialized reasoning per phase
3. ✅ Easy to debug (see which agent failed in logs)
4. ✅ Easy to test (test each agent independently)
5. ✅ Easy to optimize (improve one agent without affecting others)
6. ✅ 85% table discovery success rate (DiscoveryAgent uses Scout semantic search)
7. ✅ 88% query execution success rate (ExecAndRecoveryAgent with auto-repair)

### Active Multi-Agent System (Phase 8+)

**Location**: `langgraph_integration/orchestrator.py`

**Agents**:
1. **DiscoveryAgent** — Scout semantic search + role-based ranking + column index
2. **JoinPlanAndSQLAgent** — Views-first strategy + FK analysis + MSSQL generation
3. **ExecAndRecoveryAgent** — Safe execution + auto-repair + retry logic
4. **AnswerAgent** — Natural language formatting (1-2 sentences)

**Configuration**:
- LangGraph Studio: `langgraph.json` → `main_orchestrator: orchestrator:build_graph`
- FastAPI: `langgraph_service.py` → imports `create_query_orchestrator()`

### Migration Path

If you need to revert to the old system:
1. Restore `graph_definition.py` from archive
2. Update `langgraph.json` to: `"main_orchestrator": "langgraph_integration.graph_definition:build_graph"`
3. Update `langgraph_service.py` to: `from langgraph_integration.graph_definition import create_database_workflow`

However, **this is NOT recommended** as the new system is significantly better.

### For More Information

- **ADR-0019**: `adrs/0019-multi-agent-orchestration-resurrection.md` — Architecture decision
- **Phase 8 Guide**: `docs/PHASE_8_MULTI_AGENT_ACTIVATION.md` — Complete migration guide
- **Phase 8 Summary**: `docs/PHASE_8_SUMMARY.md` — Executive summary with metrics

---

**Archived**: October 2025  
**Reason**: Phase 8 Multi-Agent Orchestration System Active  
**Status**: DO NOT USE - SUPERCEDED