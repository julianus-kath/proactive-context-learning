# Proxy Connection Setup Guide

**Goal:** Connect your Mac agent to the Windows proxy to test Phase 2 with a real database.

---

## Prerequisites

### On Windows (Proxy Server)
1. ✅ VPN connected to corporate network
2. ✅ `proxy.py` running on Windows
3. ✅ `connections.yaml` configured with database credentials
4. ✅ TLS certificates generated (if using HTTPS)
5. ✅ Firewall allows incoming connections on port 5000

### On Mac (Agent)
1. ✅ Python 3.11+ installed
2. ✅ Project dependencies installed (`pip install -r requirements.txt`)
3. ✅ `.env` file configured (see below)

---

## Step 1: Start Proxy on Windows

### Option A: Using PowerShell
```powershell
cd "path\to\vpn_config"
python proxy.py
```

### Option B: Using Command Prompt
```cmd
cd path\to\vpn_config
python proxy.py
```

### Expected Output
```
 * Proxy version: 1.5.0
 * Python version: 3.11.x
 * Serving Flask app 'proxy'
 * Running on https://0.0.0.0:5000
 * Loaded 2 connection(s) from connections.yaml
```

**Note the Windows IP address** - you'll need this for the Mac configuration.

---

## Step 2: Find Windows IP Address

On Windows, run:
```cmd
ipconfig
```

Look for the IP address under your network adapter (usually starts with `10.` or `192.168.`).

Example:
```
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 10.255.152.48
```

---

## Step 3: Configure Mac .env File

Create or edit `.env` in your project root:

```bash
# Copy template if .env doesn't exist
cp .env.template .env

# Edit with your favorite editor
nano .env
```

### Required Configuration

```bash
# =============================================================================
# DATABASE MODE
# =============================================================================
DB_MODE=proxy

# =============================================================================
# PROXY CLIENT CONFIGURATION (Mac → Windows)
# =============================================================================
# Replace with your Windows IP address
PROXY_BASE_URL=https://10.255.152.48:5000

# API key from Windows proxy (check proxy.py or .env on Windows)
PROXY_API_KEY=your_secure_api_key_here

# Default connection name (from connections.yaml on Windows)
PROXY_DEFAULT_CONN=corp_sql_erp

# TLS verification (set to false for self-signed certs in development)
PROXY_TLS_VERIFY=false

# Optional: Path to CA bundle if using custom certificates
# PROXY_CA_BUNDLE=/path/to/ca-bundle.crt

# Timeout settings
PROXY_TIMEOUT=30
PROXY_MAX_RETRIES=3
```

### Important Notes

1. **PROXY_BASE_URL**: Must match Windows IP and port
2. **PROXY_API_KEY**: Must match the key configured on Windows proxy
3. **PROXY_DEFAULT_CONN**: Must match a connection name in `connections.yaml` on Windows
4. **PROXY_TLS_VERIFY**: Set to `false` for self-signed certificates (development only)

---

## Step 4: Test Connection

Run the comprehensive test suite:

```bash
python tests/test_proxy_connection.py
```

### Expected Output

```
================================================================================
  PHASE 2 - PROXY CONNECTION TEST SUITE
  Testing Query Safety & Validation with Real Database
================================================================================

================================================================================
  Test 1: Environment Configuration
================================================================================

Required Configuration:
✅ DB_MODE = proxy
✅ PROXY_BASE_URL = https://10.255.152.48:5000
✅ PROXY_API_KEY = ********************

Optional Configuration:
ℹ️  PROXY_DEFAULT_CONN = corp_sql_erp
ℹ️  PROXY_TLS_VERIFY = false
ℹ️  PROXY_CA_BUNDLE = (not set)
ℹ️  PROXY_TIMEOUT = 30

✅ All required environment variables are configured!

================================================================================
  Test 2: Proxy Health Check
================================================================================

ℹ️  Database client initialized in proxy mode
ℹ️  Proxy URL: https://10.255.152.48:5000

Checking proxy health...
✅ Proxy is healthy and responding!

Fetching available connections...
✅ Found 2 available connection(s):
  - corp_sql_erp (sqlserver)
  - dev_postgres (postgres)

... (more tests)

================================================================================
  TEST SUMMARY
================================================================================
✅ PASS  Environment Configuration
✅ PASS  Proxy Health Check
✅ PASS  Simple Query
✅ PASS  Schema Discovery
✅ PASS  Query Validation
✅ PASS  Safe Execution
✅ PASS  Table Selection
✅ PASS  End-to-End Workflow

================================================================================
Results: 8/8 tests passed
================================================================================

✅ 🎉 All tests passed! Phase 2 is working with real database!
```

---

## Step 5: Troubleshooting

### Problem: Connection Refused

**Symptoms:**
```
❌ Proxy connection failed: Connection refused
```

**Solutions:**
1. Verify proxy is running on Windows
2. Check Windows firewall allows port 5000
3. Verify Windows IP address is correct
4. Ensure both machines are on same network

**Test connectivity:**
```bash
# On Mac, test if port is reachable
nc -zv 10.255.152.48 5000

# Or use curl
curl -k https://10.255.152.48:5000/diag
```

---

### Problem: SSL Certificate Verification Failed

**Symptoms:**
```
❌ Proxy connection failed: SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions:**
1. Set `PROXY_TLS_VERIFY=false` in `.env` (development only)
2. Or provide CA bundle: `PROXY_CA_BUNDLE=/path/to/ca-bundle.crt`
3. Or copy Windows certificate to Mac and configure path

---

### Problem: Authentication Failed

**Symptoms:**
```
❌ Proxy query failed: Authentication failed
```

**Solutions:**
1. Verify `PROXY_API_KEY` matches Windows proxy configuration
2. Check Windows proxy logs for authentication errors
3. Ensure API key doesn't have extra spaces or quotes

---

### Problem: No Connections Available

**Symptoms:**
```
❌ No connections available!
```

**Solutions:**
1. Check `connections.yaml` on Windows is properly configured
2. Verify database credentials in `connections.yaml`
3. Test database connectivity from Windows directly
4. Check Windows proxy logs for connection errors

---

### Problem: Query Timeout

**Symptoms:**
```
❌ Proxy query error: Timeout
```

**Solutions:**
1. Increase `PROXY_TIMEOUT` in `.env`
2. Check database performance on Windows
3. Simplify query or add LIMIT clause
4. Verify VPN connection is stable

---

## Step 6: Verify Individual Components

### Test 1: Health Check Only
```python
from app.db.client import DatabaseClient

client = DatabaseClient()
print(f"Healthy: {client.health_check()}")
print(f"Connections: {client.get_available_connections()}")
```

### Test 2: Simple Query
```python
from app.db.client import DatabaseClient

client = DatabaseClient()
columns, rows = client.query("SELECT 1 AS test", limit=1)
print(f"Columns: {columns}")
print(f"Rows: {rows}")
```

### Test 3: Schema Discovery
```python
from app.db.client import DatabaseClient
from app.db.schema_cache import SchemaCache

client = DatabaseClient()
cache = SchemaCache(client)
schema = cache.get_schema()
print(f"Tables: {list(schema.keys())[:5]}")
```

### Test 4: Safe Query Execution
```python
from app.db.client import DatabaseClient
from app.db.query_executor import execute_safe_query

client = DatabaseClient()
result = execute_safe_query(client, "SELECT * FROM customers LIMIT 5")
print(f"Success: {result.success}")
print(f"Rows: {result.row_count}")
print(result.formatted_result)
```

---

## Step 7: Next Steps

Once all tests pass:

1. ✅ **Phase 2 Complete** - Query safety system working with real database
2. 🔄 **Integrate with LangGraph** - Use in agent workflows
3. 🔄 **Add to MCP Server** - Expose as MCP tools
4. 🔄 **Connect to UI** - Enable chatbot queries
5. 🚀 **Phase 3** - Advanced features and optimization

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_MODE` | Yes | `proxy` | Database access mode (`proxy` or `direct`) |
| `PROXY_BASE_URL` | Yes | - | Windows proxy URL (e.g., `https://10.255.152.48:5000`) |
| `PROXY_API_KEY` | Yes | - | API key for proxy authentication |
| `PROXY_DEFAULT_CONN` | No | - | Default connection name from `connections.yaml` |
| `PROXY_TLS_VERIFY` | No | `true` | Verify TLS certificates (`true` or `false`) |
| `PROXY_CA_BUNDLE` | No | - | Path to CA certificate bundle |
| `PROXY_TIMEOUT` | No | `30` | Request timeout in seconds |
| `PROXY_MAX_RETRIES` | No | `3` | Maximum retry attempts |

---

## Security Checklist

- [ ] API key is strong and unique
- [ ] TLS/HTTPS is enabled (not HTTP)
- [ ] Firewall rules are restrictive (only allow Mac IP)
- [ ] Database credentials are not in agent code
- [ ] All queries go through validation
- [ ] Row limits are enforced
- [ ] Timeouts are configured
- [ ] Logs don't contain sensitive data

---

## Quick Reference Commands

```bash
# Test proxy connection
python tests/test_proxy_connection.py

# Run Phase 2 integration tests
pytest tests/integration/ -v

# Check environment configuration
python -c "from app.db.client import DatabaseClient; c = DatabaseClient(); print(f'Mode: {c.mode}, URL: {c.base_url}')"

# Test health check
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().health_check())"

# Get available connections
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().get_available_connections())"
```

---

## Support

If you encounter issues:

1. Check Windows proxy logs
2. Check Mac agent logs
3. Verify network connectivity
4. Review this troubleshooting guide
5. Check ADR-0011 for architecture details

---

**Status:** Ready for testing! 🚀