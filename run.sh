#!/usr/bin/env bash
# ============================================================================
# Thesis demo — boot the full stack locally
# ============================================================================
# Prerequisites: Docker Desktop, an OpenAI API key.
# First run takes ~2 minutes (image builds + Northwind seeding).
# ============================================================================

set -euo pipefail
cd "$(dirname "$0")"

echo "[thesis] Preflight checks..."

if ! command -v docker >/dev/null 2>&1; then
    echo "[error] Docker is not installed."
    echo "        Install Docker Desktop: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "[error] The 'docker compose' plugin is missing."
    echo "        Update Docker Desktop or install the compose plugin."
    exit 1
fi

# The CLI works even when the daemon isn't running; probe for a live daemon.
if ! docker info >/dev/null 2>&1; then
    echo "[error] Docker is installed but the daemon is not running."
    echo "        Start Docker Desktop (or 'sudo systemctl start docker' on Linux)"
    echo "        and re-run this script. On macOS, wait for the whale icon"
    echo "        in the menu bar to be steady before retrying."
    exit 1
fi

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[info]  No .env file found. Copying .env.example → .env"
        cp .env.example .env
        echo ""
        echo "[action needed] Open .env and set your OPENAI_API_KEY, then re-run:"
        echo "                \$EDITOR .env && ./run.sh"
        exit 1
    fi
    echo "[error] Neither .env nor .env.example found. Repo may be corrupt."
    exit 1
fi

# Load .env
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${OPENAI_API_KEY:-}" ] \
   || [[ "$OPENAI_API_KEY" == "sk-..." ]] \
   || [[ "$OPENAI_API_KEY" == sk-proj-REDACTED* ]] \
   || [[ "$OPENAI_API_KEY" == sk-REPLACE* ]]; then
    echo "[error] OPENAI_API_KEY is not set (or is still the placeholder) in .env."
    echo "        Edit .env and add your OpenAI key, then re-run."
    exit 1
fi

if [ ! -f data/northwind.sql ]; then
    echo "[error] data/northwind.sql is missing. Cannot seed Northwind."
    echo "        Ensure the file is committed to git (git ls-files data/)."
    exit 1
fi

WEB_UI_PORT="${WEB_UI_PORT:-3000}"
SQL_AGENT_PORT="${SQL_AGENT_PORT:-5001}"
MCP_PORT="${MCP_PORT:-8000}"

echo "[thesis] Building and starting services..."
docker compose up --build -d

echo "[thesis] Waiting for the stack to become healthy..."
for i in $(seq 1 120); do
    if curl -sf "http://localhost:${WEB_UI_PORT}/" >/dev/null 2>&1; then
        echo ""
        echo "============================================================"
        echo "  Stack is ready."
        echo ""
        echo "  Web UI:    http://localhost:${WEB_UI_PORT}"
        echo "  SQL Agent: http://localhost:${SQL_AGENT_PORT}/docs"
        echo "  MCP:       http://localhost:${MCP_PORT}/health"
        echo ""
        echo "  Try:  \"What are the top 5 products by revenue?\""
        echo ""
        echo "  Logs: docker compose logs -f"
        echo "  Stop: docker compose down"
        echo "============================================================"
        exit 0
    fi
    sleep 2
done

echo ""
echo "[error] Timed out after ~4 minutes waiting for the web UI."
echo "        Inspect logs with: docker compose logs"
exit 1
