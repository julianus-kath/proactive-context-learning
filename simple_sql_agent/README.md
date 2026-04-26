# Simple SQL Agent

LangGraph-based ReAct agent that turns natural-language questions into SQL against an ERP database. Runs as a FastAPI service on **port 5001** and exposes OpenAPI docs at `/docs`.

This is one of the three services in the thesis stack; see the [root README](../README.md) for the end-to-end system context.

## What it does

1. Receives a natural-language question via `POST /process_conversation` (or `/query`, `/stream`).
2. Runs a LangGraph ReAct loop against five MCP-backed tools: `discover_tables`, `list_tables`, `get_schema`, `get_column_index`, `execute_query`. SQL validation is handled inside `execute_query` (bounded SELECT) rather than as a separate tool.
3. Generates a dialect-appropriate SQL query (PostgreSQL or MSSQL), validates it, executes it, and streams the answer back.
4. Logs each conversation turn to `logs/conversations/` for replay and debugging.

The agent is deliberately *simple* — one ReAct loop, one LLM, four tools. Complexity lives in Scout Mode (catalog enrichment, ranking) inside the MCP server, not here. See [ADR-0030](../adrs/0030-simple-sql-agent-architecture.md) for the design rationale.

## Layout

| Path | Role |
|---|---|
| [`service.py`](service.py) | FastAPI service + conversation logger (port 5001) |
| [`agent.py`](agent.py) | `create_sql_agent()` — LangGraph ReAct assembly |
| [`state.py`](state.py) | Agent state schema (Pydantic) |
| [`tools/`](tools/) | Tool wrappers around the MCP client |
| [`prompts/`](prompts/) | System prompts for the ReAct loop |
| [`db/mcp_client.py`](db/) | Thin JSON-RPC client for the MCP server |
| [`debug_stream.py`](debug_stream.py) | Structured debug event emitter |
| [`debug_logger.py`](debug_logger.py) | File-based conversation logger |
| [`run_benchmark.py`](run_benchmark.py) | Standalone benchmark runner (used by H2a eval) |
| [`test_agent.py`](test_agent.py) | Manual integration smoke test |

## Running standalone

Inside the Docker stack (`./run.sh` at repo root) the service is brought up automatically and gets its env from `docker-compose.yml`. To run natively:

```bash
# From the repo root, with .env populated:
python -m simple_sql_agent.service
```

Environment variables consumed:

| Var | Purpose | Required |
|---|---|---|
| `OPENAI_API_KEY` | LLM backend | **yes** |
| `OPENAI_MODEL` | Model id (default `gpt-4o`) | no |
| `MCP_SERVER_URL` | Where to reach the MCP server | yes |
| `MCP_API_KEY` | Shared secret with MCP server | yes |
| `API_KEY` | Inbound auth for this service | yes |
| `PORT` | Bind port (default 8080 in Docker, 5001 in Mac scripts) | no |

## API endpoints

Interactive docs: `http://localhost:5001/docs` (FastAPI Swagger).

| Method | Path | Purpose |
|---|---|---|
| GET  | `/` | Welcome / service info |
| GET  | `/health` | Service status + MCP connectivity |
| POST | `/query` | Single-question synchronous invocation |
| POST | `/process_query` | Query processing entry point |
| POST | `/process_conversation` | Multi-turn chat |
| POST | `/stream` | Server-Sent Events stream of agent reasoning |

`POST /query` example:

```json
{ "question": "Who are our top 5 customers by revenue?" }
```

Response:

```json
{
  "answer": "Based on the sales data, your top 5 customers are ...",
  "sql_query": "SELECT ...",
  "success": true,
  "latency_ms": 2500
}
```

## Testing

```bash
# Agent-level unit tests (fast, no DB)
pytest tests/ -m "not integration"

# Full integration: requires Postgres+Northwind running on :55432
pytest tests/
```

Unit tests live under [`../tests/`](../tests/), not in this directory, so they can cover the eval pipeline's use of agent primitives in addition to the agent itself.
