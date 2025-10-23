# ⚡ Quick Startup Reference Card

**Phase 7: Multi-Agent Orchestrator Ready**

---

## 🟢 macOS Quick Start

### Option A: Python Launcher (Easiest)

```bash
# Start everything (LangGraph + Web UI)
python start_system.py mac --all

# Or start only LangGraph service
python start_system.py mac --langgraph
```

### Option B: Shell Script

```bash
chmod +x start_all_services_mac.sh
./start_all_services_mac.sh
```

### Result:
```
✅ Web UI:         http://localhost:3000
✅ LangGraph:      http://localhost:5001
✅ MCP Server:     http://<windows-ip>:8000
```

---

## 🟦 Windows Quick Start

### Option A: Python Launcher

```bash
python start_system.py windows
```

### Option B: Command Prompt (CMD)

```cmd
vpn_config\start_mcp_server_windows.bat
```

### Option C: PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File vpn_config\start_mcp_server_windows.ps1
```

### Result:
```
✅ MCP Server running on 0.0.0.0:8000
✅ Scout Catalog initialized
✅ Ready for macOS connections
```

---

## 🔍 Verify Services

```bash
# Check all services status
python start_system.py status

# Check system configuration
python start_system.py check

# Test individual endpoints
curl http://localhost:3000         # Web UI
curl http://localhost:5001/health  # LangGraph
curl http://localhost:8000/health  # MCP (from Mac)
```

---

## 📊 View Logs

```bash
# LangGraph logs (real-time)
tail -f logs/langgraph.log

# Web UI logs (real-time)
tail -f logs/web_ui.log

# Last 50 lines
tail -n 50 logs/langgraph.log
```

---

## 🛑 Stop Services

### From the same terminal:
```
Press Ctrl+C
```

### From another terminal:

**macOS:**
```bash
lsof -ti:3000 | xargs kill -9    # Kill Web UI
lsof -ti:5001 | xargs kill -9    # Kill LangGraph
```

**Windows:**
```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

---

## 🔧 Pre-startup Checklist

- [ ] `.env` file exists and configured
- [ ] `OPENAI_API_KEY` is set
- [ ] `MCP_SERVER_URL` points to Windows IP
- [ ] Windows machine is accessible
- [ ] Python 3.8+ installed
- [ ] Ports 3000, 5001 (macOS) or 8000 (Windows) are free

---

## 🚨 Common Issues

| Issue | Solution |
|-------|----------|
| Port already in use | `lsof -ti:PORT \| xargs kill -9` (macOS) or use PowerShell (Windows) |
| Cannot reach MCP | Verify Windows IP, check firewall |
| `.env` not found | Copy `.env.mac` or `.env.windows` template |
| Python not found | Install Python 3.8+ or activate venv |
| Dependencies missing | Run `pip install -r requirements.txt` |

---

## 📖 Full Documentation

- Full guide: `STARTUP_INSTRUCTIONS.md`
- Architecture: `docs/MULTI_AGENT_ARCHITECTURE.md`
- Implementation: `docs/MULTI_AGENT_QUICK_START.md`

---

## 🎯 System Architecture (Quick Diagram)

```
macOS                          Windows/VPN
┌──────────────────────┐       ┌──────────────────────┐
│ Multi-Agent          │       │ MCP Server           │
│ Orchestrator         │◄─────►│ Scout Catalog        │
├──────────────────────┤       │ Safe Query Execution │
│ Discovery Agent      │       └──────────────────────┘
│ JoinSQL Agent        │                ▲
│ Exec Agent           │                │
│ Answer Agent         │                │
├──────────────────────┤         MSSQL ERP
│ HTTP API :5001       │           Database
│ Web UI :3000         │
└──────────────────────┘
```

---

## ✨ Now You're Ready!

1. Start Windows: `vpn_config\start_mcp_server_windows.bat`
2. Start macOS: `python start_system.py mac --all`
3. Open browser: `http://localhost:3000`
4. Ask questions! 🚀

---

**Time to startup: ~30 seconds** ⚡