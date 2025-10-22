#!/usr/bin/env bash
set -euo pipefail

# Load .env if available (repo root or current dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
  set -a; . "$SCRIPT_DIR/../.env"; set +a
elif [ -f ".env" ]; then
  set -a; . ".env"; set +a
fi

# Defaults if not set
MCP_SERVER_URL="${MCP_SERVER_URL:-http://192.168.1.35:8000}"
MCP_API_KEY="${MCP_API_KEY:-supersecretapikey}"

# Verify requirements
jq --version >/dev/null 2>&1 || { echo "jq is required"; exit 1; }

echo "== tools/list =="
curl -s "${MCP_SERVER_URL}/mcp" \
  -H "Content-Type: application/json" -H "X-API-Key: ${MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq

echo "== list_views (page 1, size 10, exclude empty) =="
curl -s "${MCP_SERVER_URL}/mcp" \
  -H "Content-Type: application/json" -H "X-API-Key: ${MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_views","arguments":{"page":1,"page_size":10,"include_empty":false}}}' | jq

echo "== search_views ('customers', exclude empty) =="
curl -s "${MCP_SERVER_URL}/mcp" \
  -H "Content-Type: application/json" -H "X-API-Key: ${MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_views","arguments":{"query":"customers","page":1,"page_size":5,"include_empty":false}}}' | jq

VIEW_FULL_NAME="${VIEW_FULL_NAME:-public.customers_view}"
echo "== describe_view (${VIEW_FULL_NAME}) =="
curl -s "${MCP_SERVER_URL}/mcp" \
  -H "Content-Type: application/json" -H "X-API-Key: ${MCP_API_KEY}" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"describe_view\",\"arguments\":{\"view_name\":\"${VIEW_FULL_NAME}\",\"include_sample\":false}}}" | jq

echo "== list_view_dependencies (${VIEW_FULL_NAME}) =="
curl -s "${MCP_SERVER_URL}/mcp" \
  -H "Content-Type: application/json" -H "X-API-Key: ${MCP_API_KEY}" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"list_view_dependencies\",\"arguments\":{\"view_name\":\"${VIEW_FULL_NAME}\"}}}" | jq
