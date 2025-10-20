# Schema JSON Parsing - Quick Fix Reference

## The Problem

```
❌ Error: missing or malformed JSON object parsing database schema
```

This happens when the MCP server response can't be parsed as JSON.

## Quick Diagnosis (1 minute)

```bash
# Run diagnostic - it will identify the exact problem
python3 tests/diagnose_schema_issue.py
```

## Common Fixes

### ✅ Fix 1: MCP Server Not Running (Most Common)

```bash
# Windows: Start MCP server
start_mcp_server_windows.bat

# Then restart Mac services
./start_all_services_mac.sh
```

**Symptom:** "MCP server timeout" or "Cannot connect"

### ✅ Fix 2: Wrong MCP_SERVER_URL

```bash
# Edit .env file
nano .env

# Find this line:
# MCP_SERVER_URL=http://10.255.152.48:8000

# Update the IP address to match your Windows machine
# Test it works:
curl -H "X-API-Key: your_key" http://your_ip:8000/health
```

**Symptom:** Timeout or connection refused

### ✅ Fix 3: Database Not Accessible from MCP Server

The MCP server can't reach your database. Check:

1. Database is running
2. Database credentials are correct in MCP server config
3. Network/VPN is connected

**Symptom:** "MCP server returned empty schema content"

### ✅ Fix 4: Network Connectivity

```bash
# Test from Mac to Windows machine
ping your_windows_ip
nc -zv your_windows_ip 8000
curl -v http://your_windows_ip:8000/health
```

**Symptom:** Timeout after 120 seconds

### ✅ Fix 5: Schema is Too Large

First-time schema discovery on large databases can take 2-3 minutes:

```bash
# Just wait... this is normal behavior
# Logs should show: "📋 Fetching schema from MCP server..."

# If timeout, increase in mcp_client.py line ~170:
timeout_seconds = 300  # instead of 120
```

**Symptom:** "MCP server timeout" but server is running

## Debug Log Markers

While services are running, check for these in logs:

**Good:**
```
📋 Fetching schema from MCP server...
   ✓ JSON extraction successful
✅ Database indexed: 50 tables on page 1 of 943 total
```

**Bad - shows the specific problem:**
```
❌ Failed to parse schema JSON: No JSON object found
   → Problem: [One of these will tell you what's wrong]
   → Problem: Expected 'Full response (JSON):' marker not found
   → Problem: No opening brace '{'
   → Problem: No closing brace '}'
```

## Watch the Logs in Real-Time

```bash
# Terminal 1: Start services
./start_all_services_mac.sh

# Terminal 2: Monitor schema indexing
tail -f logs/langgraph_debug.log | grep -E "indexed|Fetching|JSON|FAILED"
```

## Verify the Fix Worked

After fixing the issue:

1. **Check logs show success:**
   ```bash
   grep "Database indexed" logs/langgraph_debug.log | tail -1
   # Should show: ✅ Database indexed: XXX tables on page 1 of 943 total
   ```

2. **Open Web UI:** http://localhost:3000

3. **Ask a question:** "What products do we have?"
   - Should NOT ask for clarification
   - Should return results

## Restart Everything

If nothing else works:

```bash
# Kill all services
pkill -f "python3"
pkill -f "web_app"
pkill -f "langgraph"

# Wait 2 seconds
sleep 2

# Windows: Restart MCP server
start_mcp_server_windows.bat

# Mac: Restart services
./start_all_services_mac.sh
```

## Emergency Rollback

If all else fails and you need to revert:

```bash
# If you have git
git checkout langgraph_integration/mcp_client.py

# Otherwise, ask system administrator for backup
```

## Still Stuck?

1. Run full diagnostic:
   ```bash
   python3 tests/diagnose_schema_issue.py > /tmp/diag.txt 2>&1
   cat /tmp/diag.txt
   ```

2. Check Windows MCP server logs for errors

3. Verify database credentials on Windows side

4. Look for firewall blocking port 8000

---

**Takes 5 minutes to fix most issues.** Start with diagnostic script!