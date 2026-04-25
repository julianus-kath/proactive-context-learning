#!/usr/bin/env bash
# ============================================================================
# Smoke test the live deployment end-to-end.
#
# Usage:
#   # Public endpoint only (always works):
#   ./deploy/railway/smoke_test.sh https://thesis.julianuskath.com
#
#   # Full protected surface (when SITE_PASSWORD is enabled in the env):
#   SITE_PASSWORD=<pw> ./deploy/railway/smoke_test.sh https://thesis.julianuskath.com
# ============================================================================
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-}}"
if [[ -z "${BASE_URL}" ]]; then
  echo "Usage: ./deploy/railway/smoke_test.sh <base-url>" >&2
  echo "       SITE_PASSWORD=<pw> ./deploy/railway/smoke_test.sh <base-url>   # for protected routes" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
COOKIE_JAR="$(mktemp -t railway_smoke_cookies.XXXXXX)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

echo "==> GET ${BASE_URL}/health (public)"
curl -fsS "${BASE_URL}/health" | tee /tmp/railway_health.json
echo

# If a SITE_PASSWORD is provided, log in first so subsequent requests carry the
# session cookie. The site applies an auth gate to every non-public route.
if [[ -n "${SITE_PASSWORD:-}" ]]; then
  echo "==> POST ${BASE_URL}/login (authenticating)"
  HTTP_STATUS=$(curl -sS -o /dev/null -w '%{http_code}' \
    -c "${COOKIE_JAR}" \
    -X POST "${BASE_URL}/login" \
    --data-urlencode "password=${SITE_PASSWORD}")
  if [[ "${HTTP_STATUS}" != "303" && "${HTTP_STATUS}" != "200" && "${HTTP_STATUS}" != "302" ]]; then
    echo "    login failed (HTTP ${HTTP_STATUS}). Aborting protected checks." >&2
    exit 1
  fi
  echo "    login ok (HTTP ${HTTP_STATUS})"
  AUTH_ARGS=(-b "${COOKIE_JAR}")
else
  echo "==> SITE_PASSWORD not set — skipping protected endpoints."
  echo "    Set SITE_PASSWORD to also test /backend_health, /process_conversation, /stream_conversation."
  echo "Smoke test completed (public-only)."
  exit 0
fi

echo "==> GET ${BASE_URL}/backend_health"
curl -fsS "${AUTH_ARGS[@]}" "${BASE_URL}/backend_health" | tee /tmp/railway_backend_health.json
echo

echo "==> POST ${BASE_URL}/process_conversation"
curl -fsS "${AUTH_ARGS[@]}" -X POST "${BASE_URL}/process_conversation" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"How many customers are in the database?"}]}' \
  | tee /tmp/railway_process_conversation.json
echo

echo "==> POST ${BASE_URL}/stream_conversation (first events)"
curl -fsS -N "${AUTH_ARGS[@]}" -X POST "${BASE_URL}/stream_conversation" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"messages":[{"role":"user","content":"List 3 customers."}]}' \
  | head -n 12

echo "Smoke test completed."
