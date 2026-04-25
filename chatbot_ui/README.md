# Chatbot Web UI

FastAPI service that serves the chat interface (static HTML/CSS/JS) and proxies requests to the SQL Agent. Runs on **port 3000**.

This is the user-facing layer of the thesis stack; see the [root README](../README.md) for the end-to-end system context.

## What it does

- Serves [`index.html`](index.html) + [`script.js`](script.js) + [`styles.css`](styles.css) as the chat UI.
- Proxies `/process_conversation` and `/stream_conversation` to the SQL Agent (preserving streaming).
- Exposes `/health` and `/backend_health` for the bundled health check in `run.sh`.
- Reads agent URL and API key from env.

There is no client-side state beyond the browser session. All reasoning happens server-side on the SQL Agent; this UI just renders the stream.

## Layout

| Path | Role |
|---|---|
| [`web_app.py`](web_app.py) | FastAPI app (port 3000) — static serving + proxy |
| [`index.html`](index.html) | Chat UI markup |
| [`script.js`](script.js) | Frontend logic (SSE rendering, form handling) |
| [`styles.css`](styles.css) | Styling |
| [`icons/`](icons/) | UI icons |
| [`requirements.txt`](requirements.txt) | Python deps (FastAPI, httpx, uvicorn) |

## Environment variables

| Var | Purpose | Required |
|---|---|---|
| `LANGGRAPH_URL` | Where to reach the SQL Agent (default `http://localhost:5001`) | yes |
| `API_KEY` | Shared secret forwarded to the agent | yes |
| `DB_DIALECT` | Displayed in UI status banner (`postgres` / `mssql`) | no |
| `POSTGRES_DATABASE` / `MSSQL_DATABASE` | Displayed in UI status banner | no |
| `PORT` | Bind port (default 8080 in Docker, 3000 in Mac scripts) | no |

## Running standalone

Inside Docker (`./run.sh` at repo root) the UI is brought up automatically. To run natively:

```bash
# From the repo root, with .env populated:
cd chatbot_ui
python web_app.py
```

Then open http://localhost:3000.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/` | Chat UI (HTML) |
| GET  | `/styles.css`, `/script.js` | Static assets |
| GET  | `/health` | This service's status |
| GET  | `/config` | UI config (dialect, database name) |
| GET  | `/backend_health` | Proxied health of the SQL Agent |
| POST | `/process_conversation` | Proxied chat to SQL Agent |
| POST | `/stream_conversation` | Proxied stream from SQL Agent |
