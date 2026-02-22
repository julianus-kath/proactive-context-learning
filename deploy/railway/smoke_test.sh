#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-}}"
if [[ -z "${BASE_URL}" ]]; then
  echo "Usage: ./deploy/railway/smoke_test.sh https://thesis.julianuskath.com" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"

echo "==> GET ${BASE_URL}/health"
curl -fsS "${BASE_URL}/health" | tee /tmp/railway_health.json

echo "==> GET ${BASE_URL}/backend_health"
curl -fsS "${BASE_URL}/backend_health" | tee /tmp/railway_backend_health.json

echo "==> POST ${BASE_URL}/process_conversation"
curl -fsS -X POST "${BASE_URL}/process_conversation" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"How many customers are in the database?"}]}' \
  | tee /tmp/railway_process_conversation.json

echo "==> POST ${BASE_URL}/stream_conversation (first events)"
{
  curl -fsS -N -X POST "${BASE_URL}/stream_conversation" \
    -H "Content-Type: application/json" \
    -H "Accept: text/event-stream" \
    -d '{"messages":[{"role":"user","content":"List 3 customers."}]}'
} | head -n 12

echo "Smoke test completed."
