# H2b Overnight No-Intervention Runbook

## What is automated now
- Mode switching between `scout_on`, `scout_off_aligned`, and `scout_off_legacy`
- Health gating before each mode run (`/mcp/health` and `/process_query` service health)
- Optional strict mode verification via MCP health backend/off-control-mode
- Full run orchestration + evaluation + final report

## Option A: Run orchestrator on the same machine as services
Use built-in per-mode service restart:

```bash
python -m eval.run_h2b_process_query_grounding \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --table-labels eval/datasets/cockpit_partner_table_labels_v1.json \
  --target http://127.0.0.1:5001 \
  --mcp-url http://127.0.0.1:8000 \
  --api-key "$API_KEY" \
  --mcp-api-key "$MCP_API_KEY" \
  --start-services-per-mode \
  --replicates 1 \
  --run-tag h2b_overnight_local
```

## Option B: Run orchestrator remotely from Mac and restart Windows services per mode
1. Place `eval/scripts/set_h2b_mode_windows.ps1` on the Windows host.
2. Ensure your remote command can execute it (SSH/PowerShell remoting).
3. Run with `--mode-prepare-cmd`:

```bash
python -m eval.run_h2b_process_query_grounding \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --table-labels eval/datasets/cockpit_partner_table_labels_v1.json \
  --target "http://<windows-host>:5001" \
  --mcp-url "http://<windows-host>:8000" \
  --api-key "$API_KEY" \
  --mcp-api-key "$MCP_API_KEY" \
  --mode-prepare-cmd "ssh <win-user>@<windows-host> 'powershell -ExecutionPolicy Bypass -File C:\\h2b\\set_h2b_mode_windows.ps1 -Mode {mode} -ProjectRoot C:\\path\\to\\repo\\code -ApiKey $API_KEY -McpApiKey $MCP_API_KEY'" \
  --replicates 1 \
  --run-tag h2b_overnight_remote
```

## Safety checks
- Do a setup preview first:

```bash
python -m eval.run_h2b_process_query_grounding \
  --setup-only --dry-run \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --table-labels eval/datasets/cockpit_partner_table_labels_v1.json \
  --target "http://<windows-host>:5001" \
  --mcp-url "http://<windows-host>:8000" \
  --mode-prepare-cmd "<your command with {mode}>"
```

- Keep strict stage traces enabled (default): `discovery,ranked`.
- Default run aborts on missing required stage traces (default).

## Morning outputs
- Root orchestration manifest: `eval/runs/<timestamp>_<run-tag>/setup_manifest.json`
- Per-mode run outputs: each run dir has `process_query_results.json`, `grounding_eval.json`, `grounding_eval.md`
- Final report directory printed at the end (`report.md` + `report.json`)
