# Deployment

Production deployment artefacts for the thesis stack. The live instance at **[thesis.julianuskath.com](https://thesis.julianuskath.com)** runs from the Dockerfiles in this directory.

## Layout

```
deploy/railway/
├── Dockerfile.mcp-server      # MCP server (port 8080 in-container)
├── Dockerfile.sql-agent       # LangGraph SQL agent (port 8080 in-container)
├── Dockerfile.web-ui          # Chat UI (port 8080 in-container)
├── env/
│   ├── mcp-server.env.example
│   ├── sql-agent.env.example
│   └── web-ui.env.example
├── generate_secrets.sh        # Creates random MCP_API_KEY / API_KEY
└── smoke_test.sh              # Post-deploy connectivity check
```

## Where they're used

**Production (Railway):** each Dockerfile builds one Railway service. Services talk to each other over Railway's internal DNS (`*.railway.internal`). The three `env.example` files document the minimum set of variables each service needs. Northwind is provisioned via a Railway Postgres add-on.

**Local demo (Docker Compose):** the same three Dockerfiles are reused by the root [`docker-compose.yml`](../docker-compose.yml). The only difference is a bundled Postgres container (seeded from [`data/northwind.sql`](../data/northwind.sql)) instead of the Railway add-on. One source of truth, two deployment targets.

## MSSQL support

`Dockerfile.mcp-server` installs `unixodbc` + `unixodbc-dev` at build time, so the production image can connect to a Sage/MSSQL ERP by flipping `DB_DIALECT=mssql` and supplying `MSSQL_*` env vars. See the root [README's MSSQL section](../README.md#running-on-mssql-production-path).

## Scripts

- `generate_secrets.sh` — one-shot helper to mint random values for `MCP_API_KEY` / `API_KEY` before deploying.
- `smoke_test.sh` — hits `/health` on each service after deployment; used in CI and manually after a rollout.
