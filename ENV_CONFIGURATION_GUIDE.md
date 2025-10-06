# .env Configuration Guide

This guide explains how to configure the `.env` file for different deployment scenarios.

---

## Quick Setup

### 1. Copy the Template

**On both Windows and Mac:**
```bash
# Windows
copy .env.template .env

# Mac/Linux
cp .env.template .env
```

### 2. Choose Your Configuration

Based on which machine you're on, follow the appropriate section below.

---

## Windows Machine Configuration (MCP Server)

### What Runs on Windows
- ✅ MCP Server (port 8000)
- ✅ Direct connection to SQL Server via VPN
- ❌ Does NOT run Web UI or LangGraph

### Required Settings

Edit your `.env` file and configure these sections:

```bash
# =============================================================================
# MCP SERVER CONFIGURATION (Windows Machine)
# =============================================================================

# MCP Server Settings
MCP_SERVER_HOST=0.0.0.0  # IMPORTANT: Must be 0.0.0.0 to allow Mac to connect
MCP_SERVER_PORT=8000
MCP_API_KEY=supersecretapikey  # Change this to a secure key

# SQL Server Configuration
DB_DIALECT=mssql  # IMPORTANT: Must be "mssql" for Windows
MSSQL_SERVER=192.168.200.16
MSSQL_PORT=1433
MSSQL_DATABASE=master
MSSQL_USER=SimonM
MSSQL_PASSWORD=your_actual_password_here  # ⚠️ CHANGE THIS!
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

# Query Safety
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT=30
MIN_POOL_SIZE=1
MAX_POOL_SIZE=10
```

### What to Change

1. **MSSQL_PASSWORD** - Set your actual SQL Server password
2. **MCP_API_KEY** - Choose a secure key (remember it for Mac setup)
3. **MSSQL_SERVER** - Verify the IP is correct (default: 192.168.200.16)
4. **MSSQL_USER** - Verify the username (default: SimonM)

### What to Keep

- ✅ `MCP_SERVER_HOST=0.0.0.0` - Allows Mac to connect
- ✅ `DB_DIALECT=mssql` - Required for SQL Server
- ✅ `MSSQL_DRIVER=ODBC Driver 17 for SQL Server` - Standard driver

---

## Mac Machine Configuration (Web UI + LangGraph)

### What Runs on Mac
- ✅ Web UI (port 3000)
- ✅ LangGraph Service (port 5001)
- ❌ Does NOT run MCP Server (connects to Windows)

### Required Settings

Edit your `.env` file and configure these sections:

```bash
# =============================================================================
# OPENAI CONFIGURATION
# =============================================================================
OPENAI_API_KEY=sk-your-openai-api-key-here  # ⚠️ CHANGE THIS!
OPENAI_MODEL=gpt-4

# =============================================================================
# MCP CLIENT CONFIGURATION (Mac Machine)
# =============================================================================
MCP_SERVER_URL=http://10.255.152.48:8000  # ⚠️ CHANGE to your Windows IP!
MCP_API_KEY=supersecretapikey  # ⚠️ Must match Windows!

# =============================================================================
# LANGGRAPH SERVICE CONFIGURATION
# =============================================================================
LANGGRAPH_URL=http://localhost:5001
LANGGRAPH_API_KEY=supersecretapikey

# =============================================================================
# WEB UI CONFIGURATION
# =============================================================================
WEB_UI_HOST=localhost
WEB_UI_PORT=3000
```

### What to Change

1. **OPENAI_API_KEY** - Set your OpenAI API key (starts with `sk-`)
2. **MCP_SERVER_URL** - Set to your Windows machine's IP address
   - Find Windows IP: Run `ipconfig` on Windows
   - Example: `http://10.255.152.48:8000`
3. **MCP_API_KEY** - Must match the key you set on Windows

### What to Keep

- ✅ `LANGGRAPH_URL=http://localhost:5001` - LangGraph runs locally
- ✅ `WEB_UI_PORT=3000` - Standard Web UI port

---

## Local Development Configuration (All on Mac)

### What Runs Locally
- ✅ Web UI (port 3000)
- ✅ LangGraph Service (port 5001)
- ✅ MCP Server (port 8000) - Runs locally
- ✅ PostgreSQL (port 5432) - Local test database

### Required Settings

```bash
# =============================================================================
# OPENAI CONFIGURATION
# =============================================================================
OPENAI_API_KEY=sk-your-openai-api-key-here  # ⚠️ CHANGE THIS!

# =============================================================================
# MCP SERVER CONFIGURATION (Local)
# =============================================================================
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
MCP_API_KEY=supersecretapikey

# =============================================================================
# MCP CLIENT CONFIGURATION (Local)
# =============================================================================
MCP_SERVER_URL=http://localhost:8000  # Points to local MCP server

# =============================================================================
# DATABASE CONFIGURATION (PostgreSQL)
# =============================================================================
DB_DIALECT=postgres  # ⚠️ IMPORTANT: Use "postgres" for local dev
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=synthetic_erp_data
POSTGRES_USER=juli
POSTGRES_PASSWORD=

# =============================================================================
# LANGGRAPH & WEB UI
# =============================================================================
LANGGRAPH_URL=http://localhost:5001
WEB_UI_PORT=3000
```

### What to Change

1. **OPENAI_API_KEY** - Set your OpenAI API key
2. **DB_DIALECT** - Must be `postgres` for local development
3. **POSTGRES_USER** - Your PostgreSQL username (default: juli)

### Prerequisites

- PostgreSQL must be installed and running
- Database `synthetic_erp_data` must exist

---

## Configuration Checklist

### Windows Machine
- [ ] Copied `.env.template` to `.env`
- [ ] Set `MSSQL_PASSWORD` to actual password
- [ ] Set `MCP_API_KEY` to a secure key
- [ ] Verified `MSSQL_SERVER` IP address
- [ ] Verified `DB_DIALECT=mssql`
- [ ] Verified `MCP_SERVER_HOST=0.0.0.0`

### Mac Machine
- [ ] Copied `.env.template` to `.env`
- [ ] Set `OPENAI_API_KEY` to your API key
- [ ] Set `MCP_SERVER_URL` to Windows IP
- [ ] Set `MCP_API_KEY` to match Windows
- [ ] Verified `LANGGRAPH_URL=http://localhost:5001`
- [ ] Verified `WEB_UI_PORT=3000`

---

## Common Mistakes

### ❌ Wrong: MCP_SERVER_HOST on Windows
```bash
MCP_SERVER_HOST=localhost  # ❌ Mac won't be able to connect!
```

### ✅ Correct:
```bash
MCP_SERVER_HOST=0.0.0.0  # ✅ Allows connections from Mac
```

---

### ❌ Wrong: MCP_API_KEY mismatch
```bash
# Windows .env
MCP_API_KEY=key123

# Mac .env
MCP_API_KEY=key456  # ❌ Different keys!
```

### ✅ Correct:
```bash
# Both Windows and Mac .env
MCP_API_KEY=supersecretapikey  # ✅ Same key on both machines
```

---

### ❌ Wrong: DB_DIALECT on Windows
```bash
DB_DIALECT=postgres  # ❌ Won't connect to SQL Server!
```

### ✅ Correct:
```bash
DB_DIALECT=mssql  # ✅ Required for SQL Server
```

---

### ❌ Wrong: MCP_SERVER_URL on Mac
```bash
MCP_SERVER_URL=http://localhost:8000  # ❌ Points to Mac, not Windows!
```

### ✅ Correct:
```bash
MCP_SERVER_URL=http://10.255.152.48:8000  # ✅ Points to Windows IP
```

---

## Testing Your Configuration

### Windows
```bash
# Start MCP server
cd vpn_config
start_mcp_server_windows.bat

# Test health endpoint
# Open browser: http://localhost:8000/health
# Should see: {"ok": true, "status": "healthy", ...}
```

### Mac
```bash
# Test Windows connection
curl http://10.255.152.48:8000/health

# Should see: {"ok": true, ...}

# Start Mac services
./start_all_services_mac.sh

# Access Web UI
# Open browser: http://localhost:3000
```

---

## Environment Variables Reference

### Required on Windows
| Variable | Example | Description |
|----------|---------|-------------|
| `DB_DIALECT` | `mssql` | Database type (must be "mssql") |
| `MSSQL_SERVER` | `192.168.200.16` | SQL Server IP address |
| `MSSQL_USER` | `SimonM` | SQL Server username |
| `MSSQL_PASSWORD` | `your_password` | SQL Server password |
| `MCP_SERVER_HOST` | `0.0.0.0` | Listen on all interfaces |
| `MCP_SERVER_PORT` | `8000` | MCP server port |
| `MCP_API_KEY` | `supersecretapikey` | API key for authentication |

### Required on Mac
| Variable | Example | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key |
| `MCP_SERVER_URL` | `http://10.255.152.48:8000` | Windows MCP server URL |
| `MCP_API_KEY` | `supersecretapikey` | Must match Windows |
| `LANGGRAPH_URL` | `http://localhost:5001` | LangGraph service URL |
| `WEB_UI_PORT` | `3000` | Web UI port |

---

## Security Best Practices

1. **Never commit .env to Git**
   - `.env` is in `.gitignore`
   - Only commit `.env.template`

2. **Use strong API keys**
   - Don't use `supersecretapikey` in production
   - Generate random keys: `openssl rand -hex 32`

3. **Protect SQL Server password**
   - Don't share your `.env` file
   - Use environment-specific passwords

4. **Restrict network access**
   - Configure Windows firewall
   - Only allow Mac IP on port 8000

---

## Need Help?

- **Full Guide:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Quick Start:** [QUICK_START.md](QUICK_START.md)
- **Checklist:** [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

---

**Remember: The `.env` file is the ONLY thing you need to configure differently on each machine!**