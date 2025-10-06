# ERP Chatbot System - Deployment Documentation

## 📚 Documentation Index

This directory contains all the documentation you need to deploy and run the ERP chatbot system in a distributed Mac + Windows architecture.

---

## 🚀 Quick Start

**New to the system? Start here:**

1. **Read:** [`QUICK_START.md`](QUICK_START.md) - Get up and running in 5 minutes
2. **Follow:** [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md) - Step-by-step deployment
3. **Reference:** [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) - Complete setup guide

---

## 📖 Documentation Files

### Getting Started
- **[QUICK_START.md](QUICK_START.md)** - 5-minute quick start guide
  - Minimal steps to get running
  - Common issues and fixes
  - Development mode setup

### Deployment
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide
  - Detailed setup for Windows and Mac
  - Configuration examples
  - Troubleshooting section
  - Security notes

- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist
  - Pre-deployment checks
  - Windows deployment steps
  - Mac deployment steps
  - Post-deployment verification
  - Troubleshooting guide

### Architecture
- **[ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)** - Visual architecture guide
  - Production architecture diagram
  - Data flow visualization
  - Component responsibilities
  - Security layers
  - Development vs production

- **[ARCHITECTURE_CLEANUP_SUMMARY.md](ARCHITECTURE_CLEANUP_SUMMARY.md)** - Change log
  - What changed and why
  - Migration guide
  - Files modified/created
  - Testing checklist

### Reference
- **[CHANGES_SUMMARY.md](CHANGES_SUMMARY.md)** - Quick summary of changes
  - What was done
  - Before vs after
  - How to use
  - Key configuration

---

## 🏗️ Architecture Overview

```
Mac Machine                      Windows Machine (VPN)
┌─────────────────┐             ┌─────────────────────┐
│  Web UI :3000   │             │  MCP Server :8000   │
│       ↕         │             │         ↕           │
│ LangGraph :5001 │ ── HTTP ──► │   SQL Server (VPN)  │
└─────────────────┘             └─────────────────────┘
```

**Key Points:**
- Mac runs Web UI and LangGraph (no database access)
- Windows runs MCP server with VPN access to SQL Server
- Mac calls Windows MCP server via HTTP
- Clean separation of concerns

---

## 📋 Quick Reference

### Windows Machine

**Start MCP Server:**
```bash
cd vpn_config
start_mcp_server_windows.bat
```

**Verify:**
```
http://localhost:8000/health
```

**Configuration:**
```bash
# .env
DB_DIALECT=mssql
MSSQL_SERVER=192.168.200.16
MSSQL_USER=SimonM
MSSQL_PASSWORD=your_password
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
```

### Mac Machine

**Start Services:**
```bash
./start_all_services_mac.sh
```

**Access:**
```
http://localhost:3000
```

**Configuration:**
```bash
# .env
OPENAI_API_KEY=sk-your-key
MCP_SERVER_URL=http://10.255.152.48:8000
LANGGRAPH_URL=http://localhost:5001
WEB_UI_PORT=3000
```

---

## 🔧 Configuration Templates

### Both Machines
- **Template:** `.env.template`
- **Copy to:** `.env` (in project root)

### Windows Configuration
- **Required:** MSSQL_PASSWORD, MCP_API_KEY, DB_DIALECT=mssql

### Mac Configuration
- **Required:** OPENAI_API_KEY, MCP_SERVER_URL, MCP_API_KEY

---

## 🛠️ Startup Scripts

### Windows
- `vpn_config/start_mcp_server_windows.bat` - Batch script (recommended)
- `vpn_config/start_mcp_server_windows.sh` - Bash script (Git Bash/WSL)

### Mac
- `start_all_services_mac.sh` - Starts Web UI + LangGraph

---

## 📊 System Requirements

### Windows Machine
- Python 3.11+
- ODBC Driver 17 for SQL Server
- VPN access to SQL Server
- Network connectivity to Mac

### Mac Machine
- Python 3.11+
- OpenAI API key
- Network connectivity to Windows

---

## 🔍 Troubleshooting

### Common Issues

**Windows: Cannot connect to SQL Server**
- Check VPN connection
- Verify SQL Server IP: `ping 192.168.200.16`
- Check credentials in .env

**Mac: Cannot connect to Windows MCP server**
- Verify Windows MCP server is running
- Check Windows IP: `ping 10.255.152.48`
- Check Windows firewall allows port 8000

**Mac: Authentication failed (401)**
- Verify MCP_API_KEY matches on both machines

**See:** [`DEPLOYMENT_GUIDE.md#troubleshooting`](DEPLOYMENT_GUIDE.md#troubleshooting) for detailed solutions

---

## 📝 Development Mode

Run everything locally on Mac without Windows:

```bash
# .env
DB_DIALECT=postgres
POSTGRES_HOST=localhost
MCP_SERVER_URL=http://localhost:8000

# Start PostgreSQL
brew services start postgresql

# Start MCP server locally
cd mcp_server
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start Mac services
./start_all_services_mac.sh
```

---

## 🔐 Security

- **API Keys:** Use strong, unique keys
- **Network:** Ensure Windows MCP server only accessible on trusted network
- **Firewall:** Configure Windows firewall to allow only Mac IP
- **TLS:** Consider adding HTTPS for production (not implemented yet)
- **Credentials:** Never commit .env files to Git

---

## 📈 Monitoring

### Windows
- Console output from MCP server
- Connection pool stats
- Query execution times

### Mac
- `logs/web_ui.log` - Web UI logs
- `logs/langgraph.log` - LangGraph logs

---

## 🎯 Next Steps After Deployment

1. **Test end-to-end flow**
   - Ask questions in chatbot
   - Verify database queries work
   - Check error handling

2. **Monitor performance**
   - Watch logs for errors
   - Check query execution times
   - Monitor connection pool

3. **Optimize**
   - Tune connection pool settings
   - Adjust schema cache TTL
   - Configure rate limiting

4. **Secure**
   - Add TLS/HTTPS
   - Implement IP whitelisting
   - Add audit logging

5. **Scale**
   - Add more Mac clients if needed
   - Consider load balancing
   - Add monitoring/alerting

---

## 📞 Support

### Documentation
- **Quick Start:** [`QUICK_START.md`](QUICK_START.md)
- **Full Guide:** [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)
- **Checklist:** [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md)
- **Architecture:** [`ARCHITECTURE_DIAGRAM.md`](ARCHITECTURE_DIAGRAM.md)

### Logs
- Windows: Console output
- Mac Web UI: `logs/web_ui.log`
- Mac LangGraph: `logs/langgraph.log`

---

## ✅ Success Checklist

Your system is working when:

- [ ] Windows MCP server health check returns 200 OK
- [ ] Mac can curl Windows MCP server
- [ ] Web UI is accessible at http://localhost:3000
- [ ] Chatbot responds to questions
- [ ] Database queries return results
- [ ] No errors in logs

---

## 🎉 You're Ready!

Follow the documentation in order:

1. **[QUICK_START.md](QUICK_START.md)** - Get running fast
2. **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Detailed steps
3. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete reference

**Happy deploying! 🚀**