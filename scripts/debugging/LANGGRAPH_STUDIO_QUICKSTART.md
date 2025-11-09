# 🚀 LangGraph Studio - Quick Start

## ✅ What Was Fixed

Your `localhost:2024` issue is now **resolved**. Three problems were fixed:

1. ✅ Created missing `langgraph.json` config file
2. ✅ Installed `langgraph-cli[inmem]` backend
3. ✅ Updated startup script with correct commands

---

## 🎯 Get Started in 30 Seconds

### Step 1: Verify Installation
```bash
langgraph --version
# Expected: LangGraph CLI, version 0.4.x
```

### Step 2: Run Services
```bash
./start_all_services_mac.sh
```

### Step 3: Open Studio in Browser
Choose one:
- **Local API Docs:** `http://localhost:2024/docs`
- **Cloud Studio UI:** `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

### Step 4: Test Your Graph
In the Studio UI, create a new thread and run a query!

---

## 🎨 What Can You Do?

### Real-Time Visualization
- See your ERP assistant workflow execute in real-time
- Watch data flow through nodes
- Visualize the LangGraph state machine

### Interactive Debugging
- Create threads and run queries
- Inspect state at each node
- Step through execution
- Modify and test different paths

### Development Features
- Hot reload (disabled by default for stability)
- API documentation at `/docs`
- Real-time message streaming
- Thread management and history

---

## 📊 Example Workflow

1. **Open Studio** → `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

2. **Create a thread** → Click "New Thread" 

3. **Run a query** → Example:
   ```
   "What tables do we have in the database?"
   ```

4. **Watch execution** → See nodes execute:
   - Parse Intent
   - Search Tables
   - Describe Candidates
   - Generate SQL
   - Execute Query
   - Format Result

5. **Inspect State** → Click any node to see:
   - Input data
   - Node logic
   - Output state
   - Error messages

---

## 🔍 Service Status

When you run `start_all_services_mac.sh`, you'll see:

```
Service Status:
  🌐 Web UI:                    http://localhost:3000
  🤖 LangGraph (Orchestrator):  http://localhost:5001
  📊 LangGraph Studio:          http://localhost:2024 ← This now works!
  🗄️  MCP Server:               http://your-windows-ip:8000
```

---

## 📁 Files You Need to Know About

| File | Purpose |
|------|---------|
| `langgraph.json` | ✅ **NEW** - Tells CLI where to find the graph |
| `start_all_services_mac.sh` | ✅ **UPDATED** - Now starts Studio correctly |
| `langgraph_integration/graph_definition.py` | Contains `build_graph()` entry point |
| `.env` | Your API keys (OPENAI_API_KEY, MCP settings, etc.) |

---

## ⚡ Quick Commands

```bash
# Kill all services
./start_all_services_mac.sh  # Press Ctrl+C

# Kill just Studio
pkill -f "langgraph dev"

# Check if port 2024 is open
lsof -i :2024

# View Studio logs
tail -f logs/langgraph_studio.log

# Reinstall CLI (if needed)
pip install -U "langgraph-cli[inmem]"
```

---

## ❓ Frequently Asked

### Q: Is localhost:2024 the only way to access Studio?
**A:** No, you can also use:
- `http://127.0.0.1:2024` (alias for localhost)
- `http://localhost:2024/docs` (API reference)
- Cloud URL: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

### Q: Will my data persist?
**A:** No - it's an in-memory backend for development. Thread history clears on restart.

### Q: Can I use Studio in production?
**A:** No - Studio is development-only. For production, use LangSmith deployment.

### Q: Does Studio work without the Windows MCP server?
**A:** No - your graph needs MCP tools to discover and query databases.

### Q: Why do I need `--no-reload`?
**A:** Without it, file changes in `.venv/` restart the server constantly. `--no-reload` disables hot-reload for stability.

---

## 🐛 Troubleshooting

### "Connection refused" on localhost:2024
```bash
# Check if process is running
ps aux | grep "langgraph dev"

# If not found, run startup script again
./start_all_services_mac.sh

# Check logs
tail -f logs/langgraph_studio.log
```

### "Port 2024 already in use"
```bash
# Kill existing process
lsof -i :2024
kill -9 <PID>

# Or just run
pkill -f "langgraph dev"
```

### Graph fails to load
1. Check `.env` has `OPENAI_API_KEY`
2. Check MCP server is running on Windows
3. Check graph definition has `build_graph()` function
4. View logs: `tail -f logs/langgraph_studio.log`

### "langgraph: command not found"
```bash
pip install -U "langgraph-cli[inmem]"
```

---

## 📚 Next Steps

1. **[Read the detailed fix summary](LANGGRAPH_STUDIO_FIX_SUMMARY.md)** - Understand what was fixed
2. **[Check the changelog](LANGGRAPH_STUDIO_CHANGELOG.md)** - See exactly what changed
3. **[Start the services](../../start_all_services_mac.sh)** - Run the startup script
4. **[Open Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024)** - Visualize your graph!

---

## 🎉 You're All Set!

Everything is now configured. Just run:

```bash
./start_all_services_mac.sh
```

Then open:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Enjoy visualizing your ERP assistant graph! 🚀

---

**Status:** ✅ Ready to Use
**Version:** 1.0
**Last Updated:** October 26, 2025