# ✅ Pre-Start Checklist

Use this checklist before running `./start_all_services.sh` to ensure everything is configured correctly.

---

## 📋 General Prerequisites

- [ ] Python 3.11+ installed
- [ ] OpenAI API key obtained
- [ ] `.env` file exists in project root
- [ ] Project dependencies can be installed

---

## 🌐 For Proxy Mode

### Windows Machine Setup

- [ ] Windows machine is on and accessible
- [ ] VPN connection is active (if required)
- [ ] Python installed on Windows
- [ ] `vpn_config/proxy.py` exists
- [ ] `vpn_config/connections.yaml` configured with database credentials
- [ ] Windows Firewall allows port 5000
- [ ] Proxy server can be started: `python vpn_config/proxy.py`

### Mac Configuration

- [ ] `.env` file has `DB_MODE=proxy`
- [ ] `.env` file has `PROXY_BASE_URL=http://your-windows-ip:5000`
- [ ] `.env` file has `PROXY_DEFAULT_CONN=corp_sql_erp`
- [ ] `.env` file has `OPENAI_API_KEY=sk-...`
- [ ] (Optional) `.env` file has `PROXY_API_KEY` if Windows proxy requires auth
- [ ] Network connectivity between Mac and Windows verified

### Verification Steps

```bash
# Test network connectivity
ping 192.168.1.35

# Test proxy port
nc -zv 192.168.1.35 5000

# Test proxy health
curl http://192.168.1.35:5000/health

# Run full proxy test
python scripts/test_proxy_quick.py
```

---

## 💻 For Local Mode

### Mac Setup

- [ ] PostgreSQL installed on Mac
- [ ] PostgreSQL service can start: `brew services start postgresql`
- [ ] Database user exists (e.g., `juli`)
- [ ] Can create databases: `createdb -U juli test_db`

### Mac Configuration

- [ ] `.env` file has `DB_MODE=local`
- [ ] `.env` file has `DB_HOST=localhost`
- [ ] `.env` file has `DB_PORT=5432`
- [ ] `.env` file has `DB_NAME=synthetic_erp_data`
- [ ] `.env` file has `DB_USER=juli`
- [ ] `.env` file has `OPENAI_API_KEY=sk-...`

### Verification Steps

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check can connect
psql -h localhost -p 5432 -U juli -d postgres -c "SELECT 1;"

# Check database exists (or script will create)
psql -h localhost -p 5432 -U juli -d synthetic_erp_data -c "SELECT 1;"
```

---

## 🔑 Environment Variables

### Required for All Modes

```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-key-here

# LangGraph Service Configuration
LANGGRAPH_URL=http://localhost:5001
API_KEY=supersecretapikey

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
MCP_API_KEY=supersecretapikey
```

### Required for Proxy Mode

```bash
# Database Mode
DB_MODE=proxy

# Proxy Configuration
PROXY_BASE_URL=http://192.168.1.35:5000
PROXY_DEFAULT_CONN=corp_sql_erp

# Optional: API Key (if Windows proxy requires auth)
PROXY_API_KEY=your-api-key-here

# Optional: TLS Configuration
PROXY_TLS_VERIFY=false
```

### Required for Local Mode

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
```

---

## 🔧 System Requirements

### Mac Requirements

- [ ] macOS 10.15+ (Catalina or later)
- [ ] Python 3.11 or higher
- [ ] pip package manager
- [ ] curl or nc (netcat) for connectivity tests
- [ ] 4GB+ RAM available
- [ ] 2GB+ disk space available

### Windows Requirements (Proxy Mode Only)

- [ ] Windows 10/11
- [ ] Python 3.8 or higher
- [ ] Network connectivity to databases
- [ ] VPN client (if required)
- [ ] Firewall configured to allow port 5000

---

## 📦 Python Dependencies

The startup script will install these automatically, but verify you can install packages:

```bash
# Test pip works
pip3 install --upgrade pip

# Test can install a package
pip3 install requests
```

### Required Packages (Auto-installed)

- LangGraph integration: `langgraph_integration/requirements.txt`
- Chatbot UI: `chatbot_ui/requirements.txt`
- MCP Server: `mcp_server/requirements.txt`

---

## 🌐 Network Requirements

### For Proxy Mode

- [ ] Mac can reach Windows machine IP
- [ ] Port 5000 is open on Windows
- [ ] No firewall blocking between Mac and Windows
- [ ] VPN is active (if databases require VPN)

### For Local Mode

- [ ] PostgreSQL port 5432 is available
- [ ] No other services using ports 3000, 5001, 8000

---

## 🔒 Security Checklist

### API Keys

- [ ] OpenAI API key is valid and has credits
- [ ] Proxy API key matches between Windows and Mac (if using auth)
- [ ] API keys are not committed to git
- [ ] `.env` file is in `.gitignore`

### Database Access

- [ ] Database credentials are secure
- [ ] Proxy only allows read-only queries
- [ ] No production credentials in code
- [ ] All database access goes through proxy or abstraction layer

---

## 📁 File Structure

Verify these files exist:

```
project_root/
├── .env                          ✓ Your configuration
├── start_all_services.sh         ✓ Startup script
├── scripts/
│   └── test_proxy_quick.py       ✓ Proxy test script
├── chatbot_ui/
│   ├── app.py                    ✓ Web UI
│   ├── web_app.py                ✓ Modern Web UI
│   ├── langgraph_service.py      ✓ LangGraph service
│   └── requirements.txt          ✓ Dependencies
├── mcp_server/
│   ├── server.py                 ✓ MCP server
│   ├── tools.py                  ✓ Database tools
│   └── requirements.txt          ✓ Dependencies
├── app/
│   └── db/
│       └── client.py             ✓ Database client
├── vpn_config/                   (For proxy mode)
│   ├── proxy.py                  ✓ Proxy server
│   └── connections.yaml          ✓ Database config
└── logs/                         (Created automatically)
```

---

## 🧪 Pre-Flight Tests

### Test 1: Python Version

```bash
python3 --version
# Should be 3.11 or higher
```

### Test 2: Environment Variables

```bash
# Load .env
source .env

# Check OpenAI key
echo $OPENAI_API_KEY
# Should show: sk-...

# Check DB mode
echo $DB_MODE
# Should show: proxy or local
```

### Test 3: Network Connectivity (Proxy Mode)

```bash
# Test proxy reachability
python scripts/test_proxy_quick.py
# Should show: ✅ All checks passed!
```

### Test 4: PostgreSQL (Local Mode)

```bash
# Test PostgreSQL
pg_isready -h localhost -p 5432
# Should show: accepting connections
```

### Test 5: Ports Available

```bash
# Check ports are free
lsof -i :3000  # Should be empty
lsof -i :5001  # Should be empty
lsof -i :8000  # Should be empty
```

---

## ✅ Final Checklist

Before running `./start_all_services.sh`:

- [ ] All prerequisites met
- [ ] `.env` file configured correctly
- [ ] Database backend ready (proxy or PostgreSQL)
- [ ] Network connectivity verified
- [ ] Ports 3000, 5001, 8000 are available
- [ ] OpenAI API key is valid
- [ ] Pre-flight tests passed

---

## 🚀 Ready to Start?

If all checkboxes are checked, you're ready to run:

```bash
./start_all_services.sh
```

---

## 🐛 Common Issues

### Issue: "PROXY_BASE_URL not set"

**Solution:**
```bash
# Edit .env
nano .env

# Add:
DB_MODE=proxy
PROXY_BASE_URL=http://192.168.1.35:5000
```

### Issue: "Cannot connect to proxy server"

**Solution:**
```bash
# 1. Check Windows proxy is running
# On Windows: python vpn_config/proxy.py

# 2. Check firewall
# Windows: Allow port 5000 in firewall

# 3. Test connectivity
ping 192.168.1.35
nc -zv 192.168.1.35 5000
```

### Issue: "PostgreSQL not running"

**Solution:**
```bash
# Start PostgreSQL
brew services start postgresql

# Verify
pg_isready -h localhost -p 5432
```

### Issue: "OPENAI_API_KEY not set"

**Solution:**
```bash
# Edit .env
nano .env

# Add:
OPENAI_API_KEY=sk-your-key-here
```

### Issue: "Port already in use"

**Solution:**
```bash
# Kill existing processes
lsof -ti:3000 | xargs kill -9
lsof -ti:5001 | xargs kill -9
lsof -ti:8000 | xargs kill -9

# Or let the script handle it
./start_all_services.sh
```

---

## 📚 Additional Resources

- `READY_TO_START.md` - Quick start guide
- `STARTUP_GUIDE.md` - Comprehensive guide
- `CHANGES_SUMMARY.md` - What changed
- `docs/STARTUP_FLOW.md` - Visual diagrams
- `PROXY_SETUP_CHECKLIST.md` - Proxy setup guide

---

## 💡 Pro Tips

1. **Test proxy first**: Run `python scripts/test_proxy_quick.py` before full start
2. **Check logs**: Keep `tail -f logs/*.log` open in another terminal
3. **Use local mode first**: Test with local PostgreSQL before proxy mode
4. **Verify OpenAI credits**: Ensure your API key has available credits
5. **Keep Windows proxy running**: Don't close the proxy terminal window

---

## ✅ You're Ready!

Once all items are checked, run:

```bash
./start_all_services.sh
```

And enjoy your Multi-Agent Data Fusion System! 🎉