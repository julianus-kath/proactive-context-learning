# Deployment Checklist

Use this checklist to ensure proper deployment of the Mac + Windows architecture.

---

## 📋 Pre-Deployment Checklist

### Both Machines
- [ ] Git repository is up to date on both machines
- [ ] Python 3.11+ is installed
- [ ] Network connectivity between Mac and Windows verified
- [ ] API keys are generated and documented

### Windows Machine
- [ ] VPN connection to SQL Server is working
- [ ] ODBC Driver 17 for SQL Server is installed
- [ ] Can ping SQL Server: `ping 192.168.200.16`
- [ ] SQL Server credentials are available
- [ ] Windows Firewall is configured (or disabled for private network)

### Mac Machine
- [ ] OpenAI API key is available
- [ ] Can ping Windows machine
- [ ] PostgreSQL installed (for local development)

---

## 🪟 Windows Machine Deployment

### Step 1: Update Code
- [ ] Open terminal/PowerShell
- [ ] Navigate to project directory
- [ ] Run: `git pull origin main`
- [ ] Verify latest code is pulled

### Step 2: Configure Environment
- [ ] Copy template: `copy config\env.windows.example .env`
- [ ] Open .env in editor: `notepad .env`
- [ ] Set `MSSQL_PASSWORD` to actual password
- [ ] Verify `MSSQL_SERVER=192.168.200.16`
- [ ] Verify `MSSQL_USER=SimonM`
- [ ] Verify `MSSQL_DATABASE=master`
- [ ] Set `MCP_API_KEY` (remember this for Mac)
- [ ] Save and close .env

### Step 3: Verify ODBC Driver
- [ ] Open ODBC Data Sources (64-bit)
- [ ] Check "Drivers" tab
- [ ] Verify "ODBC Driver 17 for SQL Server" is listed
- [ ] If not, download and install from Microsoft

### Step 4: Test SQL Server Connection
- [ ] Open SQL Server Management Studio (if available)
- [ ] Or use command: `sqlcmd -S 192.168.200.16 -U SimonM -P your_password`
- [ ] Verify connection works
- [ ] If fails, check VPN and credentials

### Step 5: Start MCP Server
- [ ] Navigate to vpn_config: `cd vpn_config`
- [ ] Run: `start_mcp_server_windows.bat`
- [ ] Wait for "MCP Server started" message
- [ ] Check for errors in console

### Step 6: Verify MCP Server
- [ ] Open browser
- [ ] Navigate to: `http://localhost:8000/health`
- [ ] Should see: `{"ok": true, "status": "healthy", ...}`
- [ ] Check console for connection pool initialization
- [ ] Verify no errors in logs

### Step 7: Get Windows IP Address
- [ ] Run: `ipconfig`
- [ ] Find IPv4 Address (e.g., 10.255.152.48)
- [ ] Write it down for Mac configuration
- [ ] Verify it's on the same network as Mac

### Step 8: Configure Firewall
- [ ] Open Windows Defender Firewall
- [ ] Click "Advanced settings"
- [ ] Click "Inbound Rules" → "New Rule"
- [ ] Select "Port" → Next
- [ ] TCP, Specific port: 8000 → Next
- [ ] Allow the connection → Next
- [ ] Check all profiles → Next
- [ ] Name: "MCP Server" → Finish
- [ ] Or: Disable firewall for private networks (if trusted)

### Step 9: Test from Windows
- [ ] Open browser
- [ ] Navigate to: `http://localhost:8000/tools/list_databases`
- [ ] Should see list of databases
- [ ] Verify SQL Server connection is working

---

## 🍎 Mac Machine Deployment

### Step 1: Update Code
- [ ] Open terminal
- [ ] Navigate to project directory
- [ ] Run: `git pull origin main`
- [ ] Verify latest code is pulled

### Step 2: Configure Environment
- [ ] Copy template: `cp env.mac.template .env`
- [ ] Open .env in editor: `nano .env`
- [ ] Set `OPENAI_API_KEY=sk-your-key-here`
- [ ] Set `MCP_SERVER_URL=http://10.255.152.48:8000` (use Windows IP)
- [ ] Set `MCP_API_KEY` (must match Windows)
- [ ] Verify `LANGGRAPH_URL=http://localhost:5001`
- [ ] Verify `WEB_UI_PORT=3000`
- [ ] Save and close .env (Ctrl+X, Y, Enter)

### Step 3: Test Windows Connection
- [ ] Ping Windows: `ping 10.255.152.48`
- [ ] Should get replies
- [ ] If timeout, check network and firewall

### Step 4: Test MCP Server Connection
- [ ] Run: `curl http://10.255.152.48:8000/health`
- [ ] Should see: `{"ok": true, ...}`
- [ ] If fails, check Windows firewall and MCP server

### Step 5: Test MCP Authentication
- [ ] Run: `curl -H "X-API-Key: supersecretapikey" http://10.255.152.48:8000/tools/list_databases`
- [ ] Should see list of databases
- [ ] If 401 error, check MCP_API_KEY matches

### Step 6: Install Dependencies
- [ ] Run: `pip3 install -r langgraph_integration/requirements.txt`
- [ ] Run: `pip3 install -r chatbot_ui/requirements.txt`
- [ ] Verify no errors

### Step 7: Start Mac Services
- [ ] Make script executable: `chmod +x start_all_services_mac.sh`
- [ ] Run: `./start_all_services_mac.sh`
- [ ] Watch for pre-flight checks to pass
- [ ] Wait for "All Mac services started successfully!"

### Step 8: Verify Services
- [ ] Check LangGraph: `curl http://localhost:5001/health`
- [ ] Should see: `{"status": "healthy", ...}`
- [ ] Check Web UI: Open browser to `http://localhost:3000`
- [ ] Should see chatbot interface

### Step 9: Test End-to-End
- [ ] In Web UI, type: "What databases are available?"
- [ ] Should get response listing databases
- [ ] Type: "What tables are in the master database?"
- [ ] Should get response listing tables
- [ ] Type: "Show me 5 products"
- [ ] Should get response with product data

---

## ✅ Post-Deployment Verification

### Windows Checks
- [ ] MCP server is running without errors
- [ ] Health endpoint returns 200 OK
- [ ] Can query SQL Server through MCP
- [ ] No connection errors in logs
- [ ] Port 8000 is accessible from Mac

### Mac Checks
- [ ] LangGraph service is running (port 5001)
- [ ] Web UI is running (port 3000)
- [ ] Can access Web UI in browser
- [ ] Can send messages in chatbot
- [ ] Responses are generated correctly

### Integration Checks
- [ ] Mac can reach Windows MCP server
- [ ] Authentication works (API key)
- [ ] Database queries execute successfully
- [ ] Schema discovery works
- [ ] Query results are returned correctly
- [ ] Error handling works (try invalid query)

---

## 🔍 Troubleshooting

### Windows: MCP Server Won't Start

**Check:**
- [ ] Python is installed: `python --version`
- [ ] .env file exists and is configured
- [ ] ODBC Driver is installed
- [ ] Port 8000 is not in use: `netstat -ano | findstr :8000`
- [ ] SQL Server is reachable: `ping 192.168.200.16`

**Fix:**
- [ ] Install missing dependencies: `pip install -r mcp_server\requirements.txt`
- [ ] Kill process on port 8000: `taskkill /F /PID <PID>`
- [ ] Check VPN connection
- [ ] Verify SQL Server credentials

### Windows: Cannot Connect to SQL Server

**Check:**
- [ ] VPN is connected
- [ ] SQL Server IP is correct: `ping 192.168.200.16`
- [ ] Credentials are correct in .env
- [ ] ODBC Driver is installed

**Fix:**
- [ ] Reconnect VPN
- [ ] Test with SQL Server Management Studio
- [ ] Verify username/password
- [ ] Check SQL Server allows remote connections

### Mac: Cannot Connect to Windows MCP Server

**Check:**
- [ ] Windows MCP server is running
- [ ] Windows IP is correct: `ping 10.255.152.48`
- [ ] Windows firewall allows port 8000
- [ ] Both machines on same network

**Fix:**
- [ ] Start Windows MCP server
- [ ] Update MCP_SERVER_URL in .env
- [ ] Configure Windows firewall
- [ ] Check network connectivity

### Mac: Authentication Failed (401)

**Check:**
- [ ] MCP_API_KEY in Mac .env
- [ ] MCP_API_KEY in Windows .env
- [ ] Keys match exactly

**Fix:**
- [ ] Update MCP_API_KEY to match on both machines
- [ ] Restart both services

### Mac: Services Won't Start

**Check:**
- [ ] Python 3 is installed: `python3 --version`
- [ ] .env file exists and is configured
- [ ] OPENAI_API_KEY is set
- [ ] Ports 3000 and 5001 are free

**Fix:**
- [ ] Install dependencies: `pip3 install -r langgraph_integration/requirements.txt`
- [ ] Set OPENAI_API_KEY in .env
- [ ] Kill processes on ports: `lsof -ti:3000 | xargs kill -9`

---

## 📊 Monitoring

### Windows
- [ ] Monitor MCP server console for errors
- [ ] Check connection pool stats
- [ ] Monitor SQL Server connection health
- [ ] Watch for query timeouts

### Mac
- [ ] Monitor logs: `tail -f logs/langgraph.log`
- [ ] Monitor logs: `tail -f logs/web_ui.log`
- [ ] Check for OpenAI API errors
- [ ] Watch for MCP connection errors

---

## 🛑 Shutdown Procedure

### Mac
1. [ ] Press Ctrl+C in startup script terminal
2. [ ] Verify services stopped
3. [ ] Or manually: `pkill -f "web_app.py" && pkill -f "langgraph_service.py"`

### Windows
1. [ ] Press Ctrl+C in MCP server terminal
2. [ ] Verify server stopped
3. [ ] Or manually: `taskkill /F /IM python.exe` (careful!)

---

## 📝 Notes

### Windows IP Address
```
Current IP: ___________________
Date: ___________________
```

### API Keys
```
MCP_API_KEY: ___________________
OPENAI_API_KEY: ___________________
```

### SQL Server Credentials
```
Server: 192.168.200.16
Database: master
User: SimonM
Password: (stored in .env)
```

---

## ✨ Success Criteria

You've successfully deployed when:

- [x] Windows MCP server is running and healthy
- [x] Mac can connect to Windows MCP server
- [x] Web UI is accessible at http://localhost:3000
- [x] Can ask questions in chatbot
- [x] Chatbot returns database results
- [x] No errors in logs
- [x] All services are stable

---

**Congratulations! Your distributed ERP chatbot system is now deployed! 🎉**