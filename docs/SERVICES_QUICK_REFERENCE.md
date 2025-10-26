# Services Quick Reference

## Service Endpoints

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **Web UI** | 3000 | http://localhost:3000 | User chatbot interface (Streamlit) |
| **LangGraph Service** | 5001 | http://localhost:5001 | Agent orchestration & query processing |
| **LangGraph Studio** | 2024 | http://localhost:2024 | 🆕 Graph visualization & debugging |
| **MCP Server** | 8000 | http://10.255.152.48:8000 | Windows (discovery, query execution) |

## Startup

### Start All Services
```bash
./start_all_services_mac.sh
```

### Start Individual Services

**LangGraph Studio** (manual):
```bash
python3 -m langgraph dev langgraph_integration.graph_definition:build_graph --port 2024
```

**LangGraph Service** (manual):
```bash
cd chatbot_ui
python3 langgraph_service.py
```

**Web UI** (manual):
```bash
cd chatbot_ui
python3 web_app.py
```

## Logs

```bash
# All services
tail -f logs/*.log

# Individual logs
tail -f logs/langgraph_studio.log       # Graph visualization
tail -f logs/langgraph.log             # Agent orchestration
tail -f logs/web_ui.log                # Web interface
```

## Health Checks

```bash
# Web UI
curl http://localhost:3000

# LangGraph Service
curl http://localhost:5001/health

# LangGraph Studio
curl http://localhost:2024

# MCP Server
curl http://10.255.152.48:8000/health -H "X-API-Key: ${MCP_API_KEY}"
```

## Common Tasks

### Debug a Query Execution

1. Open LangGraph Studio: http://localhost:2024
2. Click "Execute Graph"
3. Paste query in `user_input` field
4. Click "Run"
5. Step through each node
6. Inspect state at each step

### View Raw Logs

```bash
# Clear logs
> logs/langgraph_studio.log

# Watch logs in real-time
tail -f logs/langgraph_studio.log
```

### Kill All Services

```bash
./start_all_services_mac.sh  # Press Ctrl+C
```

Or manually:
```bash
kill -9 $(lsof -ti:3000)     # Web UI
kill -9 $(lsof -ti:2024)     # LangGraph Studio
kill -9 $(lsof -ti:5001)     # LangGraph Service
```

### Restart a Service

```bash
# Kill service
lsof -ti:PORT | xargs kill -9

# Manual restart
python3 <service>.py
```

## Troubleshooting

### Port Already in Use

```bash
# Find process
lsof -i :PORT

# Kill process
kill -9 <PID>
```

### Service Won't Start

1. Check Python version: `python3 --version` (need 3.11+)
2. Install dependencies: `pip3 install -r requirements.txt`
3. Check .env file: `cat .env`
4. Review logs: `tail -f logs/*.log`

### MCP Server Unreachable

1. Check Windows machine is running
2. Verify network connectivity: `ping 10.255.152.48`
3. Check firewall: Allow port 8000
4. Verify .env has correct IP: `grep MCP_SERVER_URL .env`

### Graph Won't Load in Studio

```bash
# Verify graph can be imported
python3 -c "from langgraph_integration.graph_definition import build_graph; print(build_graph())"

# Check syntax
python3 -m py_compile langgraph_integration/graph_definition.py
```

## Environment Variables

Required in `.env`:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# MCP Server (Windows)
MCP_SERVER_URL=http://10.255.152.48:8000
MCP_API_KEY=your-api-key
```

## Files to Know

| File | Purpose |
|------|---------|
| `start_all_services_mac.sh` | Main startup script |
| `langgraph_integration/graph_definition.py` | Graph definition + build_graph() |
| `langgraph_integration/requirements.txt` | Python dependencies |
| `chatbot_ui/langgraph_service.py` | LangGraph service |
| `chatbot_ui/web_app.py` | Web UI |
| `.env` | Configuration |
| `logs/` | Service logs |

## Quick Stats

```
Services:        4 (Web UI, LangGraph Service, Studio, MCP Server)
Ports Used:      3000, 2024, 5001 (+ 8000 on Windows)
Python Files:    ~20 in langgraph_integration/
Memory Usage:    ~500MB for all Mac services
Startup Time:    ~30-45 seconds
```

## Key Commands

```bash
# Status check
curl http://localhost:3000 && echo "✅ UI up"
curl http://localhost:5001/health && echo "✅ LangGraph up"
curl http://localhost:2024 && echo "✅ Studio up"

# Restart all
./start_all_services_mac.sh  # Ctrl+C to stop
./start_all_services_mac.sh  # Run again to start

# View active services
lsof -i -P -n | grep LISTEN

# Clear all logs
rm logs/*.log

# Reinstall dependencies
pip3 install -r langgraph_integration/requirements.txt --force-reinstall
```

## Documentation Links

- 🎨 **Studio Guide**: [LANGGRAPH_STUDIO_GUIDE.md](./LANGGRAPH_STUDIO_GUIDE.md)
- 🏗️ **Architecture**: [MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md)
- 🚀 **Quick Start**: [MULTI_AGENT_QUICK_START.md](./MULTI_AGENT_QUICK_START.md)
- 📋 **Phase Status**: [PHASE_7_COMPLETE.md](./PHASE_7_COMPLETE.md)
- 🔧 **Implementation**: [PHASE_8_LANGGRAPH_STUDIO_IMPLEMENTATION.md](./PHASE_8_LANGGRAPH_STUDIO_IMPLEMENTATION.md)

---

**Updated**: October 2025 (Phase 8 - LangGraph Studio)