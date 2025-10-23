# 🚀 Startup Instructions - Multi-Agent ERP Assistant

**Phase 7 Complete**: Multi-Agent Orchestrator (4 Specialized Agents)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         macOS (LangGraph)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Multi-Agent Orchestrator (4 Specialized Agents)          │ │
│  │  ├─ Discovery Agent (search + ranking)                    │ │
│  │  ├─ JoinSQL Agent (planning + MSSQL generation)           │ │
│  │  ├─ Exec Agent (execution + auto-repair)                  │ │
│  │  └─ Answer Agent (formatting + explanations)              │ │
│  └────────────────────────────────────────────────────────────┘ │
│           │                                                      │
│  ┌────────▼────────────────────────────────────────────────────┐ │
│  │  HTTP API (Port 5001) + Web UI (Port 3000)                 │ │
│  └────────┬────────────────────────────────────────────────────┘ │
└───────────┼──────────────────────────────────────────────────────┘
            │
            │ JSON-RPC (HTTP)
            │
┌───────────▼──────────────────────────────────────────────────────┐
│                    Windows/VPN (MCP Server)                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Scout Catalog (Tables + Views)                           │ │
│  │  Discovery Tools (search, describe, list)                 │ │
│  │  Safe Query Execution (read-only, timeouts)               │ │
│  └────────────────────────────────────────────────────────────┘ │
│           │                                                      │
│  ┌────────▼────────────────────────────────────────────────────┐ │
│  │  MSSQL ERP Database (production)                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Common (Both Platforms)
- ✅ Python 3.8+
- ✅ Virtual environment with dependencies installed
- ✅ `.env` file configured

### macOS
- ✅ `lsof` or `nc` (netcat) for port checking
- ✅ `curl` for health checks

### Windows
- ✅ Administrator access (recommended)
- ✅ Windows firewall allows port 8000
- ✅ SQL Server drivers installed (`pyodbc`)

---

## ⚡ Quick Start

### Option 1: Python Launcher (Recommended - Cross-Platform)

**macOS - Start all services:**
```bash
python start_system.py mac --all
```

**macOS - Start only LangGraph:**
```bash
python start_system.py mac --langgraph
```

**Windows - Start MCP server (batch):**
```bash
python start_system.py windows
```

**Windows - Start MCP server (PowerShell):**
```bash
python start_system.py windows --powershell
```

**Check system status:**
```bash
python start_system.py status
```

**Verify system configuration:**
```bash
python start_system.py check
```

---

### Option 2: Shell Scripts (macOS Native)

**Start all services:**
```bash
./start_all_services_mac.sh
```

---

### Option 3: Windows Batch Files (Windows Native)

**Command Prompt (CMD):**
```cmd
vpn_config\start_mcp_server_windows.bat
```

**PowerShell:**
```powershell
powershell -ExecutionPolicy Bypass -File vpn_config\start_mcp_server_windows.ps1
```

---

## 📋 Detailed Startup Process

### Step 1️⃣ macOS: Start the System

Run the comprehensive startup script:

```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python start_system.py mac --all
```

**What this does:**

1. ✅ **System Checks**
   - Verify Python 3.8+
   - Check required directories exist
   - Verify multi-agent orchestrator is present
   - Check `.env` configuration

2. ✅ **Pre-flight Checks**
   - Validate `OPENAI_API_KEY` is set
   - Validate `MCP_SERVER_URL` is configured
   - Test connection to Windows MCP server
   - Verify MCP health endpoint

3. ✅ **Install Dependencies**
   - Install `langgraph_integration/requirements.txt`
   - Install `chatbot_ui/requirements.txt`

4. ✅ **Start Services**
   - LangGraph Service (Port 5001)
     - Multi-Agent Orchestrator initialized
     - FastAPI server running
   - Web UI (Port 3000)
     - Streamlit or custom web interface

5. ✅ **Output**
   ```
   Service Status:
     🌐 Web UI:              http://localhost:3000
     🤖 LangGraph (Orch):    http://localhost:5001
     🗄️  MCP Server:         http://10.255.152.48:8000 (Windows)
   
   Logs:
     Web UI:     tail -f logs/web_ui.log
     LangGraph:  tail -f logs/langgraph.log
   ```

---

### Step 2️⃣ Windows: Start the MCP Server

Open Command Prompt or PowerShell and run:

```cmd
cd C:\path\to\project
vpn_config\start_mcp_server_windows.bat
```

**Or with PowerShell:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\vpn_config\start_mcp_server_windows.ps1
```

**What this does:**

1. ✅ **Environment Setup**
   - Resolve project root
   - Find Python in virtual environment
   - Ensure uvicorn + fastapi are installed

2. ✅ **Start MCP Server**
   - Uvicorn server on `0.0.0.0:8000`
   - Reload mode enabled for development
   - Debug logging enabled

3. ✅ **Scout Catalog Initialization**
   - Builds on first request
   - Caches tables + views from MSSQL
   - Refreshes on TTL

4. ✅ **Ready for Connections**
   ```
   Application startup complete
   Uvicorn running on http://0.0.0.0:8000
   ```

---

## 🔗 Service Endpoints

### macOS (LangGraph)

| Endpoint | Port | Purpose | Status |
|----------|------|---------|--------|
| Web UI | 3000 | User interface | `http://localhost:3000` |
| LangGraph | 5001 | Agent orchestrator + API | `http://localhost:5001/health` |

### Windows (MCP Server)

| Endpoint | Port | Purpose | Status |
|----------|------|---------|--------|
| MCP Server | 8000 | Discovery + Execution | `http://<windows-ip>:8000/health` |

---

## 🧪 Verify System is Running

### Check All Services:
```bash
python start_system.py status
```

**Expected output:**
```
Service Status:
  ✅ Web UI                http://localhost:3000
  ✅ LangGraph Service     http://localhost:5001/health
  ✅ MCP Server            http://localhost:8000/health
```

### Check Individual Endpoints:

**Web UI:**
```bash
curl http://localhost:3000
```

**LangGraph Health:**
```bash
curl http://localhost:5001/health
```

**MCP Health (from Mac):**
```bash
curl http://<windows-ip>:8000/health
```

---

## 📊 Service Logs

All logs are stored in `logs/` directory:

```bash
# Watch LangGraph logs in real-time
tail -f logs/langgraph.log

# Watch Web UI logs in real-time
tail -f logs/web_ui.log

# View last 100 lines of LangGraph logs
tail -n 100 logs/langgraph.log
```

---

## 🛑 Stopping Services

### From the same terminal:
Press `Ctrl+C` to stop all services gracefully

### From another terminal:

**macOS (kill by port):**
```bash
lsof -ti:3000 | xargs kill -9    # Kill Web UI
lsof -ti:5001 | xargs kill -9    # Kill LangGraph
```

**Windows (PowerShell):**
```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

---

## 🔧 Environment Configuration

### macOS `.env` Template (`.env.mac`)

```bash
# OpenAI API
OPENAI_API_KEY=sk-...

# MCP Server (Windows)
MCP_SERVER_URL=http://10.255.152.48:8000
MCP_API_KEY=your-api-key

# Safety & Performance
RESULT_ROW_CAP=1000
QUERY_TIMEOUT_SECONDS=30
CATALOG_TTL_SECONDS=3600

# Orchestrator Configuration
ORCHESTRATOR_MODE=multi_agent
MAX_JOINS=3
MAX_RETRIES=2
```

### Windows Configuration (`.env` in project root)

```bash
# Database
DB_DIALECT=mssql
DB_MSSQL_DSN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...;Encrypt=yes;TrustServerCertificate=yes;"

# MCP Server
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_API_KEY=your-api-key

# Safety & Performance
RESULT_ROW_CAP=1000
QUERY_TIMEOUT_SECONDS=30
CATALOG_TTL_SECONDS=3600
INCLUDE_EMPTY_BY_DEFAULT=false
```

---

## 🚨 Troubleshooting

### Port Already in Use

**macOS:**
```bash
# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Find and kill process on port 5001
lsof -ti:5001 | xargs kill -9
```

**Windows:**
```powershell
# Find process on port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
taskkill /PID <PID> /F
```

### Cannot Connect to Windows MCP Server

1. **Verify Windows machine is running:**
   - Check Windows MCP server process
   - Look for "Uvicorn running on" message

2. **Check network connectivity:**
   ```bash
   ping 10.255.152.48  # Replace with your Windows IP
   ```

3. **Check firewall:**
   - Windows firewall must allow port 8000
   - Check network security rules

4. **Verify MCP_SERVER_URL in .env:**
   ```bash
   # Should match Windows machine IP
   MCP_SERVER_URL=http://10.255.152.48:8000
   ```

### LangGraph Service Won't Start

1. **Check Python dependencies:**
   ```bash
   pip install -r langgraph_integration/requirements.txt
   ```

2. **Check orchestrator file:**
   ```bash
   ls -la langgraph_integration/orchestrator.py
   ```

3. **Check logs:**
   ```bash
   tail -f logs/langgraph.log
   ```

### MCP Server Connection Refused

1. **Verify server is running:**
   ```cmd
   netstat -an | findstr 8000
   ```

2. **Check ports:**
   - Ensure 8000 is not blocked by firewall
   - Restart firewall if needed

3. **Restart MCP server:**
   - Stop current process
   - Run `start_mcp_server_windows.bat` again

---

## 📖 Documentation

For more detailed information, see:

- 📋 **Architecture**: `docs/MULTI_AGENT_ARCHITECTURE.md`
- 🚀 **Quick Start**: `docs/MULTI_AGENT_QUICK_START.md`
- 🎨 **Visual Guide**: `docs/MULTI_AGENT_VISUAL_GUIDE.md`
- 🔍 **Implementation**: `docs/MULTI_AGENT_IMPLEMENTATION_COMPLETE.md`
- 📊 **Summary**: `IMPLEMENTATION_SUMMARY.md`

---

## 🎯 System Health Check

Run comprehensive system health check:

```bash
# Full verification
python start_system.py check

# Skip .env check
python start_system.py check --no-check
```

This verifies:
- ✅ Python version
- ✅ Required directories
- ✅ Multi-Agent Orchestrator
- ✅ .env configuration
- ✅ OPENAI_API_KEY
- ✅ MCP_SERVER_URL

---

## 🔄 Workflow Summary

### User Question → Answer Flow

```
1. User Input (Web UI)
   ↓
2. LangGraph Service receives request
   ↓
3. Multi-Agent Orchestrator routes to:
   ├─ DiscoveryAgent: Find relevant tables/views
   ├─ JoinPlanAndSQLAgent: Plan joins + generate SQL
   ├─ ExecAndRecoveryAgent: Execute + repair on error
   └─ AnswerAgent: Format natural language response
   ↓
4. MCP Server (Windows) provides:
   ├─ Scout Catalog (tables/views search)
   ├─ describe_table (schema info)
   ├─ query_bounded (safe execution)
   └─ list_relations (join keys)
   ↓
5. MSSQL Database returns results
   ↓
6. Final Response to User (1-2 sentences, no jargon)
```

---

## 💡 Pro Tips

1. **Keep logs accessible:** Use `tail -f` in separate terminal to monitor in real-time
2. **Test MCP connectivity first:** Run health check before starting LangGraph
3. **Verify .env before starting:** Catch credential issues early
4. **Use Python launcher:** Most flexible and cross-platform
5. **Check port availability:** Free up ports before startup if previous session crashed

---

## 🎉 Ready to Start!

You now have a complete, production-ready multi-agent ERP assistant system.

**Next steps:**
1. ✅ Start Windows MCP server
2. ✅ Start macOS services
3. ✅ Open Web UI: `http://localhost:3000`
4. ✅ Ask questions and watch 4 agents collaborate!

---

**For questions or issues, see troubleshooting section above or check logs.**