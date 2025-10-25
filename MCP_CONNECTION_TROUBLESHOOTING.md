# MCP Server Connection Troubleshooting

## ⚠️ Important: Understand the Network Topology

```
[Mac]  ←→  [Windows/VPN @ 10.255.152.48]  ←→  [SQL Server @ 192.168.200.16]
           (MCP Server)                        (behind VPN)
```

- **10.255.152.48** = Windows machine running MCP server (reachable from Mac)
- **192.168.200.16** = SQL Server (reachable from Windows via VPN only)

---

## Problem: MCP Server Stuck in Connection Loop

**Symptom:**
```
ERROR:mcp_server.db_mssql:❌ Failed to connect to SQL Server: ('08001', '[08001]...')
ERROR:mcp_server.db_mssql:   Server: <MSSQL_SERVER from env>
ERROR:mcp_server.db_mssql:MSSQL query failed: ...
INFO:mcp_server.db_mssql:Creating new MSSQL connection to <MSSQL_SERVER>...
```

The server keeps trying to reconnect without succeeding → **Infinite retry loop** while fetching catalog.

---

## Root Cause

1. **VPN not connected** on Windows machine hosting MCP server
2. **SQL Server not reachable** at `192.168.200.16:1433`
3. **Firewall/Network** blocking TCP connection to SQL Server
4. **SQL Server not running** or not accepting remote connections

---

## Quick Checklist (Do This First)

**Check your `.env` file first for actual IPs:**
```bash
grep MSSQL_SERVER /path/to/.env
# This shows the SQL Server IP you're trying to reach
```

### ✅ Windows VPN Connection
Replace `<SQL_SERVER_IP>` with your actual MSSQL_SERVER from `.env`:

```powershell
# Check if VPN is active and SQL Server is reachable
ping <SQL_SERVER_IP>
# Example: ping 192.168.200.16
```

Expected: `Reply from <SQL_SERVER_IP>: bytes=32 time=...`  
If timeout or "unreachable" → **VPN is NOT connected**

### ✅ SQL Server Port (1433)
```powershell
# Check if SQL Server is listening
Test-NetConnection -ComputerName <SQL_SERVER_IP> -Port 1433
# Example: Test-NetConnection -ComputerName 192.168.200.16 -Port 1433
```

Expected: `TcpTestSucceeded : True`

### ✅ SQL Server Credentials
Verify environment variables on Windows machine:
```powershell
$Env:MSSQL_SERVER
$Env:MSSQL_DATABASE
$Env:MSSQL_USER
# DON'T print password, just verify it's set
$Env:MSSQL_PASSWORD | Measure-Object -Character
```

---

## Detailed Troubleshooting

### 1. VPN Connection (Windows)

**Check VPN status:**
```powershell
Get-VpnConnection
```

**Expected:** One active connection  
**If none:** Connect to your VPN profile first

**Verify SQL Server is reachable** (use your MSSQL_SERVER from `.env`):
```powershell
ping <SQL_SERVER_IP>
nslookup <SQL_SERVER_IP>  # DNS resolution
# Example: ping 192.168.200.16
```

**Common VPN issues:**
- VPN certificate expired
- VPN profile misconfigured
- Network adapter disabled
- Firewall blocking VPN traffic

---

### 2. SQL Server Configuration

**On the Windows machine with SQL Server (or ask DBA):**

Check SQL Server is running:
```sql
-- In SQL Server Management Studio
SELECT @@SERVERNAME, @@VERSION
```

Check remote connections enabled:
```sql
-- EXEC sp_configure 'remote access', 1
-- RECONFIGURE
SELECT * FROM sys.configurations WHERE name LIKE '%remote%'
```

Check TCP/IP is enabled:
- SQL Server Configuration Manager
- SQL Server Network Configuration
- TCP/IP → Enabled

---

### 3. Firewall Rules

**Windows Firewall (SQL Server machine):**
```powershell
# Check if MSSQL port is open
Get-NetFirewallRule -DisplayName "*SQL Server*" | Select DisplayName, Enabled
```

**If not enabled, add rule:**
```powershell
New-NetFirewallRule -DisplayName "SQL Server" `
  -Direction Inbound -Protocol TCP -LocalPort 1433 `
  -Action Allow
```

---

### 4. Network/Routing

**From macOS (LangGraph machine), test Windows machine** (use MCP_SERVER_URL from `.env`):
```bash
# Can macOS reach Windows machine running MCP server?
ping <WINDOWS_IP>
# Example: ping 10.255.152.48 (if that's your Windows machine)

# Can you traceroute?
traceroute <WINDOWS_IP>
```

> Note: macOS → Windows communication is different from Windows → SQL Server (VPN).
> Check MCP_SERVER_URL in your `.env` for the Windows IP.

**If timeout:** Network is isolated or routing misconfigured

---

## Fix: Restart MCP Server After Fixing Connectivity

```bash
# Windows: In MCP Server terminal
python mcp_server/main.py
```

**Expected output:**
```
🔄 Testing database connection (timeout: 10s)...
✅ Database connection verified
✅ MCP Database Server initialized successfully
```

---

## If Still Stuck: Debug Mode

**Add verbose logging:**

Edit `mcp_server/server.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

Then restart and check for detailed connection logs.

---

## Temporary Workaround (Development Only)

If VPN is down but you need to test, use **Mock/Synthetic Database**:

```bash
# macOS: Use Postgres instead of MSSQL
export DB_DIALECT=postgres
export POSTGRES_HOST=localhost
python -m langgraph_integration.main
```

Then in another terminal:
```bash
# Start Postgres (if available)
docker-compose up -d postgres
```

---

## Contact Database Admin If:

1. ✅ VPN is connected  
2. ✅ Port 1433 is reachable (ping `<MSSQL_SERVER>` from your `.env`)  
3. ✅ Windows → SQL Server network verified  
4. ❌ Still can't connect

→ Ask DBA to check:
- Is SQL Server accepting remote connections from this Windows machine?
- Is the database specified in `.env` (`MSSQL_DATABASE=...`) online?
- Can DBA connect from the Windows machine to verify server is up?
- Are there any connection limit warnings in SQL Server logs?
- Is the MSSQL_USER account authorized to connect?

---

## New Timeout Behavior (Phase 7.1 Fix)

The MCP server now **fails fast** instead of retrying forever:

- **Connection test timeout:** 10 seconds
- **Catalog warmup timeout:** 60 seconds  
- **Scout Mode timeout:** 30 seconds

If any of these timeout, the server will stop and report the error instead of hanging indefinitely.

This prevents the "infinite loop" described in this document.