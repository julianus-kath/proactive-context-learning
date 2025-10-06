# Quick Start Guide

## 🚀 Get Up and Running in 5 Minutes

---

## Windows Machine (MCP Server)

### 1. Setup (One-time)
```bash
# Pull latest code
git pull

# Create .env from template
copy config\env.windows.example .env

# Edit .env - set your password
notepad .env
# Update: MSSQL_PASSWORD=your_actual_password
```

### 2. Start MCP Server
```bash
cd vpn_config
start_mcp_server_windows.bat
```

### 3. Verify
Open browser: http://localhost:8000/health

Should see: `{"ok": true, "status": "healthy", ...}`

### 4. Get Your IP Address
```cmd
ipconfig
```
Look for IPv4 Address (e.g., `10.255.152.48`)

---

## Mac Machine (Web UI + LangGraph)

### 1. Setup (One-time)
```bash
# Pull latest code
git pull

# Create .env from template
cp env.mac.template .env

# Edit .env
nano .env
# Update:
# - OPENAI_API_KEY=sk-your-key-here
# - MCP_SERVER_URL=http://10.255.152.48:8000  (use Windows IP)
```

### 2. Test Windows Connection
```bash
curl http://10.255.152.48:8000/health
```

Should return: `{"ok": true, ...}`

### 3. Start Mac Services
```bash
./start_all_services_mac.sh
```

### 4. Access Application
Open browser: http://localhost:3000

---

## Architecture

```
Mac (localhost)                    Windows (10.255.152.48)
┌─────────────────┐               ┌─────────────────────┐
│  Web UI :3000   │               │  MCP Server :8000   │
│       ↕         │               │         ↕           │
│ LangGraph :5001 │ ─── HTTP ───► │   SQL Server (VPN)  │
└─────────────────┘               └─────────────────────┘
```

---

## Common Issues

### Windows: "Cannot connect to SQL Server"
- ✅ Check VPN is connected
- ✅ Verify IP: `ping 192.168.200.16`
- ✅ Check password in .env

### Mac: "Cannot connect to MCP server"
- ✅ Check Windows MCP server is running
- ✅ Verify IP: `ping 10.255.152.48`
- ✅ Check Windows firewall allows port 8000

### Mac: "OPENAI_API_KEY not set"
- ✅ Edit .env and add your OpenAI API key

---

## Stopping Services

### Windows
Press `Ctrl+C` in MCP server terminal

### Mac
Press `Ctrl+C` in startup script terminal

---

## Development Mode (No Windows)

Run everything locally on Mac:

```bash
# Edit .env
MCP_SERVER_URL=http://localhost:8000
DB_DIALECT=postgres
POSTGRES_HOST=localhost
POSTGRES_DATABASE=synthetic_erp_data

# Start PostgreSQL
brew services start postgresql

# Start MCP server locally
cd mcp_server
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, start Mac services
./start_all_services_mac.sh
```

---

## Logs

### Windows
Console output (or redirect to file)

### Mac
```bash
# Web UI logs
tail -f logs/web_ui.log

# LangGraph logs
tail -f logs/langgraph.log
```

---

## Need Help?

📖 Full guide: `DEPLOYMENT_GUIDE.md`  
🔧 Troubleshooting: `DEPLOYMENT_GUIDE.md#troubleshooting`  
📝 Architecture details: `ARCHITECTURE_CLEANUP_SUMMARY.md`

---

## Checklist

### Windows Setup
- [ ] Git pull
- [ ] Create .env from template
- [ ] Set MSSQL_PASSWORD
- [ ] Start MCP server
- [ ] Verify health endpoint
- [ ] Get IP address
- [ ] Configure firewall (allow port 8000)

### Mac Setup
- [ ] Git pull
- [ ] Create .env from template
- [ ] Set OPENAI_API_KEY
- [ ] Set MCP_SERVER_URL (Windows IP)
- [ ] Test Windows connection
- [ ] Start Mac services
- [ ] Access Web UI (localhost:3000)

---

**That's it! You're ready to go! 🎉**