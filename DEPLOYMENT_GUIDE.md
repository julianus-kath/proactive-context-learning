# Deployment Guide: Mac + Windows Architecture

## Overview

This system uses a **distributed architecture** where different components run on different machines:

```
┌─────────────────────────────────────────────────────────────┐
│                    MAC MACHINE                              │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                │
│  │   Web UI     │ ◄─────► │  LangGraph   │                │
│  │  Port 3000   │         │  Port 5001   │                │
│  └──────────────┘         └──────┬───────┘                │
│                                   │                         │
│                                   │ MCP JSON-RPC (HTTP)     │
└───────────────────────────────────┼─────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  WINDOWS MACHINE (VPN)                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           MCP SERVER (Port 8000)                     │  │
│  │  - Schema discovery                                  │  │
│  │  - Safe query execution                              │  │
│  │  - Rate limiting                                     │  │
│  │  - Connection pooling                                │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│                     │ Direct SQL (VPN)                      │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         SQL Server Database (Production ERP)         │  │
│  │         192.168.200.16:1433                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Why This Architecture?

1. **VPN Access**: Only Windows machine has VPN access to SQL Server
2. **Separation of Concerns**: Mac handles UI/orchestration, Windows handles data access
3. **Replaces Proxy**: MCP server provides intelligent database layer (rate limiting, caching, safety)
4. **Network Efficiency**: Single HTTP connection from Mac to Windows

## Setup Instructions

### 1. Windows Machine Setup (MCP Server)

#### Prerequisites
- Python 3.11+
- ODBC Driver 17 for SQL Server
- VPN connection to SQL Server
- Git (to clone/pull the repository)

#### Steps

1. **Clone/Update Repository**
   ```bash
   cd "C:\path\to\project"
   git pull origin main
   ```

2. **Create .env File**
   ```bash
   copy config\env.windows.example .env
   ```

3. **Edit .env File**
   - Update `MSSQL_PASSWORD` with your actual password
   - Verify `MSSQL_SERVER` IP address (192.168.200.16)
   - Verify `MSSQL_USER` (SimonM)
   - Set `MCP_API_KEY` (must match Mac configuration)

4. **Install ODBC Driver** (if not already installed)
   - Download: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Install: ODBC Driver 17 for SQL Server

5. **Start MCP Server**
   
   **Option A: Using Batch File (Recommended)**
   ```cmd
   cd vpn_config
   start_mcp_server_windows.bat
   ```

   **Option B: Using Git Bash/WSL**
   ```bash
   cd vpn_config
   ./start_mcp_server_windows.sh
   ```

   **Option C: Manual Start**
   ```cmd
   cd mcp_server
   pip install -r requirements.txt
   python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Verify MCP Server is Running**
   - Open browser: http://localhost:8000/health
   - Should see: `{"ok": true, "status": "healthy", ...}`

7. **Configure Windows Firewall**
   - Allow inbound connections on port 8000
   - Or disable firewall for private networks (if on trusted network)

8. **Get Windows IP Address**
   ```cmd
   ipconfig
   ```
   - Look for IPv4 Address (e.g., 10.255.152.48)
   - You'll need this for Mac configuration

### 2. Mac Machine Setup (Web UI + LangGraph)

#### Prerequisites
- Python 3.11+
- Git
- Network access to Windows machine

#### Steps

1. **Clone/Update Repository**
   ```bash
   cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
   git pull origin main
   ```

2. **Create .env File**
   ```bash
   cp env.mac.template .env
   ```

3. **Edit .env File**
   - Update `OPENAI_API_KEY` with your OpenAI API key
   - Update `MCP_SERVER_URL` with Windows IP (e.g., http://10.255.152.48:8000)
   - Verify `MCP_API_KEY` matches Windows configuration

4. **Test Windows MCP Server Connection**
   ```bash
   curl http://10.255.152.48:8000/health
   ```
   - Should return: `{"ok": true, ...}`
   - If fails, check Windows firewall and IP address

5. **Start Mac Services**
   ```bash
   ./start_all_services_mac.sh
   ```

   This will:
   - Check Windows MCP server connection
   - Install dependencies
   - Start LangGraph Service (port 5001)
   - Start Web UI (port 3000)

6. **Access the Application**
   - Open browser: http://localhost:3000
   - Start chatting with the ERP assistant!

## Configuration Files

### Windows (.env)
```bash
# MCP Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
MCP_API_KEY=supersecretapikey

# SQL Server
DB_DIALECT=mssql
MSSQL_SERVER=192.168.200.16
MSSQL_DATABASE=master
MSSQL_USER=SimonM
MSSQL_PASSWORD=your_password_here
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

### Mac (.env)
```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# MCP Client (points to Windows)
MCP_SERVER_URL=http://10.255.152.48:8000
MCP_API_KEY=supersecretapikey

# LangGraph
LANGGRAPH_URL=http://localhost:5001
LANGGRAPH_API_KEY=supersecretapikey
```

## Troubleshooting

### Windows MCP Server Issues

**Problem: Port 8000 already in use**
```cmd
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

**Problem: Cannot connect to SQL Server**
- Verify VPN is connected
- Check SQL Server IP: `ping 192.168.200.16`
- Verify credentials in .env
- Check ODBC Driver is installed

**Problem: ODBC Driver not found**
- Install ODBC Driver 17 for SQL Server
- Or update `MSSQL_DRIVER` in .env to match installed driver

### Mac Connection Issues

**Problem: Cannot connect to Windows MCP server**
- Verify Windows MCP server is running
- Check Windows IP address: `ping 10.255.152.48`
- Check Windows firewall allows port 8000
- Verify both machines on same network

**Problem: MCP authentication failed (401)**
- Verify `MCP_API_KEY` matches in both .env files

**Problem: LangGraph or Web UI won't start**
- Check logs: `tail -f logs/langgraph.log` or `logs/web_ui.log`
- Verify OPENAI_API_KEY is set
- Check ports 3000 and 5001 are not in use

## Development Mode (Local PostgreSQL)

For development without Windows/VPN access:

1. **Start PostgreSQL on Mac**
   ```bash
   brew services start postgresql
   ```

2. **Update .env on Mac**
   ```bash
   # Comment out MCP_SERVER_URL or set to localhost
   MCP_SERVER_URL=http://localhost:8000
   
   # Add PostgreSQL config
   DB_DIALECT=postgres
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DATABASE=synthetic_erp_data
   POSTGRES_USER=juli
   POSTGRES_PASSWORD=
   ```

3. **Start MCP Server Locally**
   ```bash
   cd mcp_server
   python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Start Mac Services**
   ```bash
   ./start_all_services_mac.sh
   ```

## Logs

### Windows
- MCP Server logs: Console output or redirect to file

### Mac
- Web UI: `logs/web_ui.log`
- LangGraph: `logs/langgraph.log`

## Stopping Services

### Windows
- Press `Ctrl+C` in the MCP server terminal

### Mac
- Press `Ctrl+C` in the startup script terminal
- Or manually: `pkill -f "web_app.py" && pkill -f "langgraph_service.py"`

## Security Notes

1. **API Keys**: Use strong, unique API keys in production
2. **Network**: Ensure Windows MCP server is only accessible on trusted network
3. **Firewall**: Configure Windows firewall to allow only Mac IP on port 8000
4. **TLS**: For production, use HTTPS/TLS for MCP server (not implemented yet)
5. **Credentials**: Never commit .env files to Git

## Architecture Benefits

✅ **Clean Separation**: Mac handles UI/orchestration, Windows handles data access  
✅ **VPN Isolation**: Only Windows needs VPN access  
✅ **Intelligent Layer**: MCP provides rate limiting, caching, safety controls  
✅ **Scalable**: Can add more Mac clients or Windows MCP servers  
✅ **Testable**: Can run locally with PostgreSQL for development  

## Next Steps

1. ✅ Remove deprecated proxy.py (replaced by MCP server)
2. ✅ Update documentation (ADRs, diagrams)
3. 🔲 Add TLS/HTTPS support for MCP server
4. 🔲 Add authentication/authorization for multi-user support
5. 🔲 Add monitoring/metrics for MCP server
6. 🔲 Add connection pooling optimization