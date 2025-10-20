# 🚀 System Startup Guide

This guide explains how to start the Multi-Agent Data Fusion System using the universal startup script.

## Quick Start

```bash
./start_all_services.sh
```

This single command will:
1. ✅ Check your database configuration (proxy or local)
2. ✅ Verify connectivity to database backend
3. ✅ Install required dependencies
4. ✅ Start all services (LangGraph, Web UI, MCP Server)
5. ✅ Monitor services and keep them running

Press `Ctrl+C` to stop all services.

---

## Configuration Modes

The system supports **two database modes**:

### 🌐 **Proxy Mode** (Production - Windows VPN)

Use this when connecting to production databases through the Windows proxy server.

**Configuration in `.env`:**
```bash
# Database Mode
DB_MODE=proxy

# Proxy Configuration
PROXY_BASE_URL=http://192.168.1.35:5000
PROXY_API_KEY=your-api-key-here
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_TLS_VERIFY=false

# OpenAI API Key
OPENAI_API_KEY=sk-...
```

**Prerequisites:**
- Windows proxy server must be running: `python vpn_config/proxy.py`
- Windows firewall must allow port 5000
- Network connectivity between Mac and Windows

**What the startup script checks:**
- ✅ Proxy server is reachable
- ✅ Proxy health endpoint responds
- ✅ API key authentication (if configured)
- ✅ Database connections are available

---

### 💻 **Local Mode** (Development - Mac PostgreSQL)

Use this for local development with PostgreSQL on your Mac.

**Configuration in `.env`:**
```bash
# Database Mode
DB_MODE=local

# Local PostgreSQL Configuration
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=juli
DB_PASSWORD=

# OpenAI API Key
OPENAI_API_KEY=sk-...
```

**Prerequisites:**
- PostgreSQL installed on Mac
- Database `synthetic_erp_data` exists (script will create if missing)

**What the startup script checks:**
- ✅ PostgreSQL is running (will try to start if not)
- ✅ Database exists (will create if missing)
- ✅ Database tables exist (will restore if missing)

---

## Services Started

The startup script launches these services:

| Service | Port | Description |
|---------|------|-------------|
| **Web UI** | 3000 | Modern chatbot interface |
| **LangGraph Service** | 5001 | AI agent backend |
| **MCP Server** | 8000 | Database tools server |

**Access URLs:**
- 🌐 Web UI: http://localhost:3000
- 🔧 LangGraph API: http://localhost:5001
- 📊 LangGraph Docs: http://localhost:5001/docs
- 🗄️ MCP Server: http://localhost:8000
- 📖 MCP Docs: http://localhost:8000/docs

---

## Testing Proxy Connection

Before running the full system, you can test the proxy connection:

```bash
python scripts/test_proxy_quick.py
```

This will:
1. Check environment configuration
2. Test network connectivity to proxy
3. Verify proxy health endpoint
4. Execute a simple test query

---

## Troubleshooting

### Proxy Mode Issues

**❌ Cannot connect to proxy server**
```bash
# Check Windows proxy is running
# On Windows: python vpn_config/proxy.py

# Check Windows firewall
# Allow port 5000 in Windows Firewall

# Verify IP address
# Update PROXY_BASE_URL in .env
```

**❌ Proxy authentication failed**
```bash
# Check API key matches
# Windows: $env:PROXY_API_KEY="your-key"
# Mac .env: PROXY_API_KEY=your-key

# Or disable authentication
# Windows: Don't set PROXY_API_KEY
# Mac .env: Remove or comment out PROXY_API_KEY
```

**❌ No database connections found**
```bash
# Check connections.yaml on Windows
# Ensure corp_sql_erp is configured
# Verify database credentials are correct
```

---

### Local Mode Issues

**❌ PostgreSQL not running**
```bash
# Start PostgreSQL
brew services start postgresql

# Or manually
pg_ctl -D /usr/local/var/postgresql@14 start
```

**❌ Database doesn't exist**
```bash
# Create database manually
createdb -U juli synthetic_erp_data

# Or let the script create it
./start_all_services.sh
```

**❌ Missing tables**
```bash
# Restore database
python restore_database.py

# Or let the script restore it
./start_all_services.sh
```

---

### Service Issues

**❌ Port already in use**
```bash
# The script will automatically kill existing processes
# If manual cleanup needed:
lsof -ti:3000 | xargs kill -9
lsof -ti:5001 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

**❌ OpenAI API key not set**
```bash
# Edit .env file
nano .env

# Add your OpenAI API key
OPENAI_API_KEY=sk-your-key-here
```

**❌ Service failed to start**
```bash
# Check logs
tail -f logs/web_ui.log
tail -f logs/langgraph_service.log
tail -f logs/mcp_server.log
```

---

## Log Files

All service logs are stored in the `logs/` directory:

```bash
# View logs in real-time
tail -f logs/web_ui.log
tail -f logs/langgraph_service.log
tail -f logs/mcp_server.log

# View all logs
cat logs/*.log
```

---

## Architecture Compliance

This startup script follows the project's ADR principles:

✅ **Proxy-only separation**: No business logic in proxy, only pass-through  
✅ **Database abstraction**: Agent never holds production credentials  
✅ **Read-only queries**: Only SELECT statements permitted  
✅ **JSON format**: All APIs return structured JSON  
✅ **Security**: API key authentication for all endpoints  
✅ **Modularity**: Clean separation of concerns  

---

## Next Steps

After starting the system:

1. **Open Web UI**: http://localhost:3000
2. **Test a query**: "Show me the top 5 customers"
3. **Check API docs**: http://localhost:5001/docs
4. **Monitor logs**: `tail -f logs/*.log`

For more details, see:
- `PROXY_SETUP_CHECKLIST.md` - Proxy configuration guide
- `README.md` - Project overview
- `docs/ADRs/` - Architecture decision records