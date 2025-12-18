# Investigation: MCP ↔ Database Connectivity for Evaluation Runs

## Bug Summary
- All benchmark queries from `eval/datasets/cockpit_queries.jsonl` fail in this branch when executed via `eval/run_benchmark.py`.
- Failures occur along the path: Benchmark CLI → LangGraph service (`/process_query`) → ExecAndRecoveryAgent → `MCPDatabaseTool` → MCP server (`mcp_server/server.py`) → database connector (PostgreSQL for the local ERP sample).
- From the user description and existing tooling (`tests/test_mcp_connectivity.py`), the symptoms present as connectivity/availability errors between the LangGraph layer and the MCP server, and/or between the MCP server and the underlying database.

## Context & Architecture
- Evaluation flow (ADR 0026):
  - `python -m eval.run_benchmark --dataset eval/datasets/cockpit_queries.jsonl --target http://localhost:5001 --eval-service http://localhost:7001`
  - Sends each cockpit query to LangGraph service `/process_query` with evaluation headers.
  - LangGraph orchestrator routes through:
    - `IntentParserAgent` → `DiscoveryAgent` → `JoinPlanAndSQLAgent` → `ExecAndRecoveryAgent` → `AnswerAgent`.
  - `ExecAndRecoveryAgent` uses `langgraph_integration.mcp_client.MCPDatabaseTool` to call MCP tools (`query_bounded` / `run_query`) over HTTP.
  - MCP server (`mcp_server/server.py`) wraps `DatabaseAdapter`, which selects either:
    - `PostgresConnector` (`mcp_server/db_postgres.py`) when `DB_DIALECT=postgres` (local dev / PoC).
    - `MSSQLConnector` (`mcp_server/db_mssql.py`) when `DB_DIALECT=mssql` (Windows ERP).
  - Scout Mode / semantic catalog is initialized on MCP startup for MSSQL via `ScoutRunner` (`mcp_server/scout_runner.py`); for Postgres the server uses the Phase 3 `SchemaCatalog` instead.
- Relevant configuration (.env at repo root):
  - `MCP_SERVER_URL=http://localhost:8000`
  - `MCP_API_KEY=supersecretapikey`
  - `API_KEY=supersecretapikey`
  - `DB_DIALECT=postgres`
  - `POSTGRES_HOST=localhost`
  - `POSTGRES_PORT=55432`
  - `POSTGRES_DATABASE=northwind`
  - `POSTGRES_USER=postgres`
  - `POSTGRES_PASSWORD=postgres`
- MCP server startup (`mcp_server/server.py`):
  - On FastAPI startup:
    - Instantiates `DatabaseAdapter()` (reads `config.db_dialect`).
    - Calls `db_manager.connector.test_connection()` with a 10s timeout.
    - Calls `db_manager.initialize()` (catalog warmup) with a 60s timeout.
    - For MSSQL only: initializes `ScoutRunner` and optionally legacy `run_scout_mode`.
  - Any exception in this startup path is logged and re-raised, preventing the MCP server from starting.
- MCP client used by agents (`langgraph_integration/mcp_client.py`):
  - `MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")`
  - `API_KEY = os.getenv("API_KEY", "supersecretapikey")`
  - Uses `Authorization: Bearer <API_KEY>` when calling `POST {MCP_URL}/mcp`.
  - `call_tool()` performs a JSON-RPC `tools/call` request and raises on:
    - HTTP errors (`aiohttp.ClientResponseError`, `aiohttp.ClientError`).
    - Timeouts / unreachable MCP (`asyncio.TimeoutError`).
    - JSON-RPC or parsing errors (`ValueError`).
- Exec and recovery layer (`langgraph_integration/agents/exec_recovery/agent.py`):
  - `_execute_query_node()`:
    - Normalizes SQL via `prepare_sql_for_execution`.
    - Calls `_query_with_recording()`, which forwards to `self.mcp.query_bounded(...)`.
    - Any exception from MCP is caught at the top level and converted to:
      - `error_info = {"type": "EXECUTION_ERROR", "message": f"Query execution failed: {str(e)}", ...}`.
  - `_query_with_recording()`:
    - Captures timing and logs `executed_tool_calls` in state.
    - Re-raises exceptions so `_execute_query_node()` can surface them.

## Observations
- Root `.env` is configured for local Postgres (`DB_DIALECT=postgres`, `POSTGRES_*` pointing at `localhost:55432` / `northwind`), matching the PoC setup described in ADR 0026.
- MCP client and LangGraph service both rely on `API_KEY`, while the MCP server checks `MCP_API_KEY` (with a fallback default of `supersecretapikey` on both sides):
  - This is safe as long as both env vars remain in sync, but it introduces a configuration hazard: changing `MCP_API_KEY` without updating `API_KEY` leads to 401s that surface as “connectivity” failures at the agent layer.
- MCP server startup is strict with respect to database connectivity:
  - If `PostgresConnector.test_connection()` fails or times out within 10 seconds (e.g., Postgres container not yet up, wrong port, VPN issues, etc.), startup aborts.
  - Because FastAPI startup exceptions bubble up, there is no “degraded but alive” mode: the entire `/mcp` endpoint is unavailable.
- On the agent side, MCP connectivity issues manifest as generic execution errors:
  - `MCPDatabaseTool.call_tool()` raises on `aiohttp.ClientError` / timeouts / JSON-RPC errors.
  - ExecAndRecoveryAgent wraps these in `EXECUTION_ERROR` with the raw string message from the exception.
  - From the evaluation framework’s perspective (`artifact_validation_errors()`), these appear as failed queries with missing tables/results and error text, not as a specialized “MCP unreachable” category.
- Scout Mode is currently only activated for `db_dialect == "mssql"`:
  - For the Postgres PoC, ScoutRunner is explicitly skipped (`"⏭️ Skipping Scout Runner for POSTGRES mode"`), and discovery relies on the Phase 3 schema catalog.
  - This means the connectivity problem described for the cockpit queries is not caused by Scout Mode itself blocking startup for Postgres; it is more likely a generic MCP or database connection failure that happens before or outside of Scout operations.
- Existing tooling (`tests/test_mcp_connectivity.py`) already encodes the expected health:
  - `/health` on the MCP server must return 200.
  - A `tools/call` for `list_tables` over `/mcp` must succeed with status 200 and valid JSON.
  - Failures are explicitly framed as network/API key/server availability issues.

## Likely Root Cause (Technical)
Based on the code and configuration, the most probable technical failure modes for “all cockpit queries fail due to connectivity to MCP/database” are:

1. **MCP server not actually up, due to DB connection failure on startup**
   - If Postgres at `localhost:55432` is not reachable or misconfigured (wrong port, DB name, or credentials), then:
     - `PostgresConnector.test_connection()` returns `False` or raises.
     - `DatabaseAdapter.initialize()` raises, causing the FastAPI `startup_event` in `mcp_server/server.py` to raise.
     - Result: no MCP server listening on `http://localhost:8000`, so `MCPDatabaseTool` (and thus ExecAndRecoveryAgent) hit connection timeouts or `aiohttp.ClientConnectorError`.
   - From the evaluation’s point of view, **every query fails early** with an execution error mentioning connection/timeout, and no SQL ever reaches the database.

2. **API key mismatch between LangGraph/MCP client and MCP server**
   - MCP server uses `MCP_API_KEY` (or its default) to validate:
     - `Authorization: Bearer <token>` or `X-API-Key` header.
   - LangGraph + evaluation clients use `API_KEY` for both:
     - LangGraph `/process_query` API key check.
     - MCP client (`MCPDatabaseTool`) Authorization header.
   - If a user updates `MCP_API_KEY` in `.env` but does not update `API_KEY` accordingly:
     - MCP server happily starts and passes `/health`.
     - Every `/mcp` call receives `401 Invalid API key`, which `MCPDatabaseTool` surfaces as errors.
     - ExecAndRecoveryAgent wraps these as `EXECUTION_ERROR`, so evaluation sees “connectivity” failures even though the underlying issue is authentication.

3. **MCP URL or port mismatch**
   - `MCP_SERVER_URL` is the single source for:
     - MCP client (LangGraph + tests).
     - connectivity diagnostics (`tests/test_mcp_connectivity.py`).
   - If `MCP_SERVER_URL` points to a Windows MSSQL instance while the current branch has been reconfigured for local Postgres, or vice versa, LangGraph may be hitting a non-existent or misconfigured server.
   - This again manifests as connection errors or timeouts in `MCPDatabaseTool.call_tool()`.

4. **(Secondary) Dialect-specific SQL normalization vs. Postgres**
   - `ExecAndRecoveryAgent` currently always runs `prepare_sql_for_execution(sql)` before calling MCP.
   - `prepare_sql_for_execution` is tuned primarily for MSSQL semantics (e.g., `TOP` vs `LIMIT`, bracketed identifiers).
   - For the Postgres PoC:
     - If the generated SQL is already Postgres-appropriate (using `LIMIT` and standard quoting), the normalization layer may rewrite it in a way that causes server-side SQL errors.
     - These are not strictly “connectivity” problems but could appear as blanket failures during evaluation runs.
   - This is likely a **secondary issue** after connectivity is fixed, but worth accounting for in the implementation plan.

Given the description (“all cockpit queries failing” + “connectivity issue to MCP layer and via that to the database”), the combination of **(1) strict MCP startup on DB connectivity** and **(2) fragile API key configuration between `API_KEY` and `MCP_API_KEY`** is the most plausible root cause family for the current failures.

## Affected Components
- `eval/run_benchmark.py`
  - Drives the evaluation and surfaces failures for each query.
- `chatbot_ui/langgraph_service.py`
  - Exposes `/process_query` and calls the multi-agent orchestrator.
- `langgraph_integration/agents/exec_recovery/agent.py`
  - Orchestrates execution via MCP and wraps connectivity/SQL errors into `error_info`.
- `langgraph_integration/mcp_client.py`
  - Manages MCP URL, API key, and JSON-RPC `tools/call` to `/mcp`.
- `mcp_server/server.py`
  - Handles MCP startup, database adapter initialization, and ScoutMode wiring.
- `mcp_server/database_adapter.py` and `mcp_server/db_postgres.py`
  - Implement database connectivity and schema/catalog hydration in Postgres mode.
- Configuration files:
  - Root `.env` and `mcp_server/config.py` (dialect selection + DB details).

## Proposed Solution (High-Level Plan)

1. **Harden MCP startup and health reporting for DB connectivity**
   - Refactor `startup_event` in `mcp_server/server.py` to:
     - Catch and classify DB connection failures (Postgres/MSSQL) without fully killing the FastAPI app.
     - Expose this state via `/health` (e.g., `db_status: "down"`, `last_error: ...`).
   - Optionally allow a “degraded mode” where `/mcp` returns structured `DATABASE_UNAVAILABLE` errors instead of the process not starting at all.

2. **Unify API key configuration between MCP client and server**
   - In `langgraph_integration/mcp_client.py`:
     - Prefer `MCP_API_KEY` if set, fall back to `API_KEY`, and only then to the default.
       - Example: `API_KEY = os.getenv("MCP_API_KEY") or os.getenv("API_KEY", "supersecretapikey")`.
   - Ensure LangGraph service and evaluation runner continue to use `API_KEY` for their own `/process_query` auth, but MCP client uses the same value as the MCP server.
   - Document this clearly in README / startup scripts so changing the MCP key remains a single step.

3. **Add explicit MCP connectivity guardrails in ExecAndRecoveryAgent**
   - Extend `_execute_query_node()` / `_query_with_recording()` to:
     - Detect typical MCP connectivity errors (timeout, `ClientConnectorError`, 401/403) and map them to a dedicated error type, e.g., `MCP_CONNECTION_ERROR` or `MCP_AUTH_ERROR`.
     - Populate `exec_result` with a structured envelope indicating that **no SQL was executed** due to MCP unavailability.
   - This will make evaluation artifacts and debugging more informative (e.g., clearly distinguishing “no DB connection” from “SQL syntax error”).

4. **Adjust SQL normalization for Postgres PoC (if needed)**
   - Make `prepare_sql_for_execution` dialect-aware by:
     - Passing through Postgres-style SQL unchanged in PoC mode (based on a `DB_DIALECT` or similar flag exposed to the LangGraph layer).
     - Only applying MSSQL-specific rewrites when targeting the production ERP MSSQL system.
   - This avoids secondary failures once MCP connectivity is fixed.

5. **Add an end-to-end connectivity sanity check for evaluation**
   - Implement a lightweight scripted check (or repurpose `tests/test_mcp_connectivity.py`) that:
     - Verifies MCP `/health`.
     - Performs a simple `query_bounded("SELECT 1")` round-trip via ExecAndRecoveryAgent / MCPDatabaseTool.
   - Integrate this into local dev instructions and optionally run it before `eval/run_benchmark.py` to fail fast with a clear message if MCP or DB is down.

## Next Steps for Implementation
- Wire MCP client to prefer `MCP_API_KEY` when available and ensure `.env` remains consistent.
- Introduce clearer error typing and messages for MCP connectivity/authentication failures in `ExecAndRecoveryAgent`.
- Optionally relax MCP startup behavior to surface DB connectivity issues via `/health` rather than aborting the whole server, depending on how much complexity we want in this branch.
- After changes:
  - Start Postgres + MCP server (`DB_DIALECT=postgres`).
  - Start LangGraph service and Evaluation service.
  - Run `python -m eval.run_benchmark --dataset eval/datasets/cockpit_queries.jsonl --run-name postgres_poc --target http://localhost:5001 --eval-service http://localhost:7001`.
  - Confirm a majority of cockpit queries complete with non-empty results and no connectivity-related failures.

