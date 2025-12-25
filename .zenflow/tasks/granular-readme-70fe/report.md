## Implementation Report – Granular README

### What was implemented

- Added a new root `README.md` that provides a comprehensive, code-grounded description of the ERP assistant system, aligned with ADR‑0024.
- The README includes:
  - Project overview and explanation of all major services (LangGraph Service, Web UI, MCP Server, Evaluation Service, proxy, synthetic data service, MongoDB document store).
  - Two Mermaid diagrams (high-level architecture and low-level ports/protocols).
  - Component index table with paths, ports, how to run, dependencies, and key environment variables.
  - Runtime topology for local development, Windows VPN/proxy mode, and Docker (with unknowns explicitly marked).
  - Complete HTTP API reference for all FastAPI/Flask services implemented in code (`langgraph_service.py`, `web_app.py`, `mcp_server/server.py`, `eval/service.py`, `vpn_config/proxy.py`, `langgraph_integration/api.py`).
  - MCP protocol reference, including request/response envelopes, authentication, and a catalog of tools from `mcp_server/tools.py`.
  - Detailed agent/workflow internals covering `QueryOrchestrator`, state model (`BaseState`), and each agent’s IO contracts and routing logic.
  - Data-layer details: DatabaseAdapter, SchemaCatalog, ScoutRunner, catalog TTL, column index, and all query guardrails (bounded query, redaction, timeouts, budgets).
  - Five end-to-end traces for representative queries (simple count, join aggregation, clarification, recovery/repair, and failure scenarios).
  - Debugging playbook (how to run each service, hit endpoints with curl, reproduce common failures, and locate logs).
  - Configuration reference enumerating env vars actually read in code, with defaults and usage.
  - “Spec vs Implementation Deltas” and “Known Issues / Fragile Points” sections highlighting divergences from ADRs and operational caveats.

### How the solution was tested

- Static inspection:
  - Used `rg` to enumerate HTTP endpoints in Python files (`@app.get/post/...`) and ensured each concrete endpoint is documented in the API reference.
  - Inspected `mcp_server/tools.py` and `langgraph_integration/mcp_client.py` to derive MCP tool names, input schemas, and response envelopes.
  - Reviewed `langgraph_integration/orchestrator.py`, agent modules, and `contracts/state.py` to model orchestration flow, state fields, budgets, and error paths.
  - Inspected `mcp_server/health.py`, `database_adapter.py`, and `bounded_query.py` for health status structure, catalog handling, and guardrails.
  - Searched for `os.getenv` and related patterns to build a concrete configuration/env-var table.
- No automated tests or runtime commands were executed, as the task is documentation-only and does not modify runtime behavior.

### Issues or challenges encountered

- The MCP server’s `/mcp` implementation uses a simplified `{ "result": ... }` response instead of a full JSON-RPC envelope, while models and ADRs describe standard JSON-RPC 2.0; this required careful inspection of `mcp_client.py` to document the actual behavior without guessing.
- Join planning logic in `JoinPlanAndSQLAgent` is partially disabled in favor of MCP-side planning; ADR‑0024 describes richer join behavior, so the README needed an explicit “Spec vs Implementation” section to clarify current limitations.
- The repository contains many legacy scripts and Docker artifacts from earlier architecture phases (proxy-only, crawling agent, older UIs). To keep the README grounded, these components were mentioned only where there is a clear code path and otherwise marked `UNKNOWN (needs verification)` when their integration with the current multi-agent system could not be confirmed from code.
- Startup scripts such as `start_all_services.sh` hard-code machine-specific paths, so the README calls out this fragility instead of trying to generalize behavior that is not actually implemented. 

