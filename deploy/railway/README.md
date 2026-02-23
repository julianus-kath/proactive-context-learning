# Railway Deployment Runbook (Northwind Demo)

This runbook deploys the thesis system as 4 services:

1. `northwind-db` (separate repo, private)
2. `mcp-server` (private)
3. `sql-agent` (private)
4. `web-ui` (public, custom domain)

## 0) Preflight

- Rotate any previously exposed keys before going live.
- Keep all secrets in Railway variables only.
- Use one Railway project and one region for all services.

## 1) Northwind DB service (repo: `northwind_psql`)

Create a Railway service from the Northwind repo and set:

- `POSTGRES_DB=northwind`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=<strong-random-password>`

Attach a Railway volume to `/var/lib/postgresql/data`.

Keep `northwind-db` private (no public domain).

## 2) MCP server service (this repo)

- Service name: `mcp-server`
- Builder: Dockerfile
- Dockerfile path: `deploy/railway/Dockerfile.mcp-server`

Set variables (template: `deploy/railway/env/mcp-server.env.example`):

- `DB_DIALECT=postgres`
- `POSTGRES_HOST=northwind-db.railway.internal`
- `POSTGRES_PORT=5432`
- `POSTGRES_DATABASE=northwind`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=<same as northwind-db>`
- `POSTGRES_SCHEMA=public`
- `MCP_API_KEY=<random shared key>`
- `MAX_QUERY_RESULTS=1000`
- `QUERY_TIMEOUT=30`
- `LOG_LEVEL=INFO`

Do not expose this service publicly.

## 3) SQL agent service (this repo)

- Service name: `sql-agent`
- Builder: Dockerfile
- Dockerfile path: `deploy/railway/Dockerfile.sql-agent`

Set variables (template: `deploy/railway/env/sql-agent.env.example`):

- `OPENAI_API_KEY=<your key>`
- `DB_DIALECT=postgres`
- `MCP_SERVER_URL=http://mcp-server.railway.internal`
- `MCP_API_KEY=<same MCP key>`
- `API_KEY=<random app key>`
- `PORT=8080`

Do not expose this service publicly.

## 4) Web UI service (this repo)

- Service name: `web-ui`
- Builder: Dockerfile
- Dockerfile path: `deploy/railway/Dockerfile.web-ui`

Set variables (template: `deploy/railway/env/web-ui.env.example`):

- `LANGGRAPH_URL=http://sql-agent.railway.internal`
- `API_KEY=<same app key as sql-agent>`
- `DB_DIALECT=postgres`
- `POSTGRES_DATABASE=northwind`
- `PORT=8080`

Expose this service publicly.

## 5) Domain cutover

Add custom domain on `web-ui`: `thesis.julianuskath.com`.

As of **2026-02-22**, the domain resolves to `217.160.0.217`.

Update DNS per Railway instructions (usually CNAME to Railway-provided hostname), then wait for TLS issuance and propagation.

## 6) Validation

Run:

```bash
./deploy/railway/smoke_test.sh https://thesis.julianuskath.com
```

Expected:

- `/health` returns healthy
- `/backend_health` reports backend online
- `/process_conversation` returns SQL + response
- `/stream_conversation` emits SSE events

## 7) Rollback

If cutover fails, revert DNS to previous target `217.160.0.217`.

## Utility

Generate random service keys:

```bash
./deploy/railway/generate_secrets.sh
```
