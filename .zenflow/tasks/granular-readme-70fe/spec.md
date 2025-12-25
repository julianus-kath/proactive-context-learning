# Technical Specification – Granular System README

## 1. Technical Context

- **Language & Runtime**
  - Primary implementation language: `Python 3`.
  - Main frameworks: `FastAPI` (HTTP services), `LangGraph` (agent orchestration), `Pydantic` (request/response models), `uvicorn` (ASGI server).
  - Supporting libraries: `python-dotenv`, logging via standard library `logging`.

- **Major Services / Binaries (from code)**
  - **MCP Database Server**
    - Entry: `mcp_server/server.py` (`FastAPI` app, JSON-RPC MCP endpoint).
    - Default port: `MCP_PORT` env var or `8000` when run as a module.
    - Responsibilities: DB connectivity, Scout catalog/indexing, MCP tool dispatch, health checks.
  - **LangGraph Service (multi-agent orchestrator API)**
    - Entry: `chatbot_ui/langgraph_service.py` (`FastAPI` app).
    - Default port: `5001` (in `if __name__ == "__main__"` block).
    - Responsibilities: Wrap LangGraph `create_query_orchestrator()`; expose `/process_query`, `/process_conversation`, debug endpoints.
  - **ERP Chatbot Web UI**
    - Entry: `chatbot_ui/web_app.py` (`FastAPI` app serving static UI).
    - Default port: `3000`.
    - Responsibilities: Serve HTML/JS/CSS front-end and expose `/health` and `/config`.
  - **Standalone LangGraph API (simple)**
    - Entry: `langgraph_integration/api.py` (`FastAPI` app).
    - Default port: `8000` (for this API only; in practice `chatbot_ui/langgraph_service.py` uses `5001`).
    - Responsibilities: Simple `/invoke` wrapper around `QueryOrchestrator` (may be legacy/alternate entrypoint).
  - **Synthetic Data Service**
    - Entry: `synthetic_data_service/main.py` and `synthetic_data_service/setup_postgres.py`.
    - Responsibilities: Generate and load synthetic ERP-style data into Postgres and associated document/graph stores.

- **Key Architectural Elements**
  - **Agents (LangGraph)**
    - Agent code under `langgraph_integration/agents/**`:
      - `intent_parser`, `discovery`, `join_sql`, `sql_validator`, `exec_recovery`, `answer`, `interpretation`, plus `result_validator`.
    - Graph wiring and state contracts defined in `langgraph_integration/graph_definition.py`, `langgraph_integration/orchestrator.py`, and `langgraph_integration/contracts/state.py`.
  - **MCP Tooling**
    - MCP server tooling implemented in `mcp_server/tools.py`, with tool metadata in `mcp_server/models.py`, bounded execution in `mcp_server/bounded_query.py`, discovery helpers in `mcp_server/discovery_tools.py`, and catalog handling in `mcp_server/catalog_store.py` + `mcp_server/catalog_builders/*`.
    - JSON-RPC endpoint implemented in `mcp_server/server.py` (`/mcp`).
  - **DB Client Abstractions**
    - Direct and hybrid DB clients for LangGraph: `langgraph_integration/direct_db_client.py`, `langgraph_integration/hybrid_db_client.py`, `langgraph_integration/proxy_db_client.py`.
    - MCP DB adapters: `mcp_server/db_mssql.py`, `mcp_server/db_postgres.py`, `mcp_server/db_proxy.py`, orchestrated by `mcp_server/database_adapter.py`.
  - **Configuration**
    - Global/shared configuration: `shared_config.py` and `mcp_server/config.py`.
    - Environment variable usage spread across services (search via `os.getenv` and `load_dotenv`).
    - Additional docs: `READMEs/ENV_CONFIGURATION_GUIDE.md`, `READMEs/ENVIRONMENT_SETUP.md`, etc.

- **ADR / Spec Source of Truth**
  - ADR for high-level architecture: `adrs/0024-Comprehensive-ERP-Assistant-Architecture.md`.
  - Rule: Prefer code over ADR when conflicting; record differences in “Spec vs Implementation Deltas” section of README.

## 2. Implementation Approach (README Generation)

The task is **complex (hard)** because it requires:
- End-to-end tracing of a multi-service, multi-agent system.
- Full enumeration of HTTP endpoints, MCP tools, and internal call chains.
- A debugging-oriented README with concrete payloads and state transitions.

Implementation will be purely documentation (no behavior changes), but must be tightly code-grounded. The approach:

### 2.1. Repository & Service Inventory

- Use `rg` and direct file inspection to enumerate all HTTP services:
  - Search patterns: `FastAPI(`, `@app.get`, `@app.post`, `uvicorn.run(`.
  - Target directories: `mcp_server`, `langgraph_integration`, `chatbot_ui`, `synthetic_data_service`, top-level scripts (`start_system.py`, `start_all_services*.sh`, `docker/`).
- For each discovered FastAPI app:
  - Record file path, `uvicorn.run` parameters (host, port), and any environment-variable-based configuration (e.g., `MCP_PORT`, `LANGGRAPH_URL`).
  - Capture how it is started in practice:
    - Direct `python` entrypoint.
    - Helper scripts (`start_all_services.sh`, `start_system.py`, `docker-compose.yml`).

### 2.2. Agent / Orchestrator Mapping

- Inspect orchestrator/graph and contracts:
  - `langgraph_integration/orchestrator.py`
  - `langgraph_integration/graph_definition.py`
  - `langgraph_integration/contracts/state.py`
  - Per-agent modules under `langgraph_integration/agents/**`.
- Extract:
  - Agents’ responsibilities and input/output fields (state keys) from the `State` model and agent call signatures.
  - Exact state mutations and routing logic (conditions that choose next agent, clarify vs execute paths).
  - Error handling and recovery strategies (e.g., how exec failures bubble back).
- Cross-check with ADR-0024 and note any differences in agents present, ordering, or behaviors for the “Spec vs Implementation Deltas” README section.

### 2.3. MCP Tools & Protocol

- MCP endpoint & routing:
  - `mcp_server/server.py`:
    - `/mcp` POST handler: JSON-RPC envelope, `method == "tools/call"` routing, API key verification (`X-API-Key` and `Authorization: Bearer` behavior).
  - Capture JSON-RPC request/response base models: `JSONRPCRequest`, `JSONRPCResponse`.
- MCP tool catalog:
  - `mcp_server/tools.py`:
    - Enumerate all tool handlers referenced from `server.py`: `search_tables`, `list_tables`, `describe_table`, `query`, `query_bounded`, `run_query`, `get_column_index`, `list_relations`, `list_views`, `search_views`, `describe_view`, `scout_catalog_diagnostics`, `scout_catalog_get`, `scout_catalog_refresh`.
    - For each tool:
      - Document expected argument schema (from function signatures and `MCPTool` definitions in `mcp_server/models.py` and any Pydantic models).
      - Document response structure based on `MCPToolResult` model and actual fields returned in each helper.
      - Capture guardrails: row limits, timeouts, allowed SQL operations, redaction or column filtering.
  - Discovery & catalog tools:
    - `mcp_server/discovery_tools.py`, `mcp_server/catalog_store.py`, `mcp_server/catalog_builders/*`, `mcp_server/table_ranker.py`, `mcp_server/scout_runner.py`.
    - Capture catalog storage paths, TTL, and cache invalidation logic.
- Protocol Examples:
  - Construct real JSON-RPC examples based on these models and tool call sites (e.g., from `langgraph_integration/mcp_client.py`).

### 2.4. HTTP API Reference (Complete)

- Enumerate endpoints by scanning for route decorators:
  - `@app.get`, `@app.post`, `@app.put`, `@app.delete`, `@app.options`, `@app.head`.
  - Target files: `mcp_server/server.py`, `chatbot_ui/langgraph_service.py`, `chatbot_ui/web_app.py`, `langgraph_integration/api.py`, and any additional FastAPI/Flask endpoints (search for `APIRouter(`, `FastAPI(`).
- For each endpoint:
  - Record:
    - HTTP method and path.
    - Pydantic request/response models (e.g., `InvokeRequest`, `QueryRequest`, `QueryResponse`, `ConversationRequest`, `ConversationResponse`, `DebugLogsResponse`).
    - Auth expectations (e.g., `API_KEY` requirement, `X-API-Key` header, MCP `API_KEY` vs LangGraph `API_KEY`).
    - Error behaviors: `HTTPException` statuses, error messages, and fallback responses.
  - Generate canonical example `curl` commands using **exact** header names, JSON payload schemas, and default ports inferred from code.

### 2.5. End-to-End Flow Tracing

- Identify primary end-user flows:
  - Web UI (`chatbot_ui/web_app.py` + `script.js`) → LangGraph Service (`/process_query`, `/process_conversation`) → LangGraph orchestrator → MCP client → MCP server → DB.
  - Direct LangGraph API usage (`langgraph_integration/api.py`) → orchestrator → DB/MCP.
  - Synthetic data setup flows (`synthetic_data_service`).
- For each of the 5 required representative queries:
  - Use the orchestrator and agent code to build **realistic** call chains:
    - Simple count query.
    - Join across tables.
    - Ambiguous query requiring clarification.
    - Query that triggers recovery/repair.
    - Query that fails (timeout or schema mismatch).
  - For each:
    - Identify which agent(s) and MCP tools are invoked.
    - Document state mutations (using `contracts/state.py` and agent implementations), including flags like `clarify`, intermediate SQL, discovery logs, and error metadata.
    - Capture payload shapes for:
      - HTTP calls (Web UI → LangGraph Service; LangGraph Service → MCP server if applicable).
      - MCP tool invocations (`mcp_client.py`).
      - DB queries (SQL text, bounded execution parameters).
  - Where behavior is implied but not fully explicit in code, label as `UNKNOWN (needs verification)` and reference the likely file(s).

### 2.6. Error Handling, Timeouts, and Recovery

- Survey error-handling and timeout logic:
  - MCP-level: `mcp_server/bounded_query.py`, `mcp_server/health.py`, `mcp_server/observability.py`, `mcp_server/scout_mode.py`, `mcp_server/scout_runner.py`.
  - Orchestrator-level: `langgraph_integration/agents/exec_recovery/agent.py`, `langgraph_integration/agents/sql_validator/agent.py`, `langgraph_integration/agents/result_validator/agent.py`, `langgraph_integration/debug_logger.py`.
  - UI/service-level: `chatbot_ui/langgraph_service.py` `HTTPException` paths and `ErrorInfo` normalization.
- Extract:
  - Retry strategies (counts, backoff, agent loops).
  - Timeout values (seconds or ms) used for MCP DB calls and Scout mode.
  - Fallback behavior when Scout catalog or catalog builder fails.
  - Logging pathways (where `logger.info/debug/error` and centralized debug logging are used).

### 2.7. Configuration & Environment Variables

- Enumerate env vars using a combination of:
  - Grep: search for `os.getenv(`, `os.environ.get(`, and `load_dotenv`.
  - Inspect: `shared_config.py`, `mcp_server/config.py`, `chatbot_ui/*.py`, `langgraph_integration/mcp_client.py`, `docker/docker-compose*.yml`.
- For each env var:
  - Record:
    - Name and default value (from code or `.env` loading).
    - Purpose.
    - Service(s) that read it.
  - Summarize in a “Configuration Reference” table in the README.

### 2.8. Runtime Topology & Deployment Modes

- Analyze local startup scripts:
  - `start_all_services.sh`, `start_all_services_mac.sh`, `start_system.py`, `start_all_services.bat` or equivalents (if present).
  - Identify in which order services are started and ports used.
- Analyze Docker configuration:
  - `docker/docker-compose.yml`, `docker/docker-compose-simple.yml`, and `docker/Dockerfile*`.
  - Document:
    - Service names, images, port mappings, environment variables, volumes, and networks.
    - How ports map between containers and localhost.
  - Note any “VPN/proxy mode” configuration by inspecting `vpn_config/`, `update_env_for_proxy.sh`, and relevant ADRs (`0011-erp-proxy-integration-architecture.md`, `0011-proxy-for-vpn-tunneling.md`).
  - Label unresolved/indirect behavior as `UNKNOWN (needs verification)` with file references.

### 2.9. README Structure & Content Strategy

- Implement the README as a single, comprehensive Markdown document at the repo root: `README.md`.
  - Existing high-level or phase-specific READMEs (under `READMEs/`, `mcp_server/README*.md`, `chatbot_ui/README*.md`, `langgraph_integration/README*.md`, etc.) will be treated as **auxiliary references** and not modified.
  - The new root `README.md` will:
    - Incorporate a high-level system overview.
    - Include **two Mermaid diagrams**:
      - High-level system diagram (user → UI → orchestrator → MCP → DB).
      - Low-level diagram with concrete ports and protocols.
    - Provide:
      - Component index table.
      - Runtime topology for local/dev, VPN/proxy, and Docker (documenting unknowns).
      - Full HTTP API reference grouped by service.
      - MCP protocol reference (JSON-RPC examples and tools catalog).
      - Agent/workflow internals and state model overview.
      - Data-layer description (DBs, cataloging, guardrails).
      - End-to-end traces for 5 representative query scenarios.
      - Debugging playbook and configuration reference.
      - Spec vs implementation and known issues sections.
- Ensure that when exact values are not derivable from code (e.g., production VPN hostnames), they are explicitly marked as:
  - `UNKNOWN (needs verification)` with a short note and candidate files to confirm.

## 3. Source Code Structure Changes

- **New / Modified Files**
  - `README.md` (root)
    - Overwrite or substantially replace existing content with the new granular, code-grounded system README.
    - Keep it self-contained but reference existing docs (e.g., `READMEs/ENV_CONFIGURATION_GUIDE.md`, `mcp_server/IMPLEMENTATION_GUIDE.md`) for deeper dives.
  - **No runtime code changes are planned** as part of this task.
    - If small code references (e.g., typo in endpoint docstring or misleading comment) are discovered, they will be documented in the README under “Known Issues / Fragile Points” instead of being changed.

- **No new modules or packages**
  - The task is documentation-only; no new Python modules, packages, or configuration files should be created.

## 4. Data Model / API / Interface Changes

- **No behavioral changes**
  - The README will document existing APIs, models, and flows but will not modify them.
  - No changes to Pydantic models, FastAPI route signatures, MCP tool shapes, or LangGraph state contracts are planned.

- **Documentation Clarifications**
  - Where the ADR describes behaviors that are **not implemented** (or are implemented differently), those will be explicitly called out in:
    - “Spec vs Implementation Deltas” section.
  - Where code behavior is ambiguous, the README will:
    - Describe what can be confirmed.
    - Provide hypotheses or intended behavior **only** under `UNKNOWN (needs verification)` labels.

## 5. Verification Approach

Because this task is purely documentation, verification focuses on correctness and completeness rather than runtime tests:

- **Static Consistency Checks**
  - After drafting the README:
    - Re-scan for HTTP endpoints (`rg '@app.(get|post|put|delete|options|head)'`) and confirm all are listed.
    - Re-scan MCP tools (`rg 'def _[a-z_]+\\(' mcp_server/tools.py` and references from `server.py`) to confirm full coverage.
    - Re-scan env var usage (`rg 'os.getenv\\(' -n` and `rg 'os.environ.get\\(' -n`) and confirm every variable appears in the Configuration Reference section.
  - Ensure all referenced file paths in the README match actual paths (by spot-checking using `ls` and `rg`).

- **Optional Test Run (Non-blocking)**
  - If desired and feasible:
    - Run `pytest` or existing test commands (e.g., `python -m pytest` or project-specific scripts under `tests/`) to ensure no accidental side effects—but this is unlikely to be necessary since only docs are changed.

- **Manual Review**
  - Sanity-check the end-to-end traces against:
    - Orchestrator code (`langgraph_integration/orchestrator.py`, agents).
    - MCP client (`langgraph_integration/mcp_client.py`).
    - MCP server tools and bounded query logic.
  - Confirm that:
    - Every component with executable code (services, agents, tools) is mentionned in at least one section of the README.
    - No unverified claims remain unlabeled (all such items must carry `UNKNOWN (needs verification)`).

