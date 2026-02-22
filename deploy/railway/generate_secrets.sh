#!/usr/bin/env bash
set -euo pipefail

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

echo "MCP_API_KEY=$(openssl rand -hex 24)"
echo "API_KEY=$(openssl rand -hex 24)"
