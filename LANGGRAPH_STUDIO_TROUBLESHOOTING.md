# LangGraph Studio Troubleshooting Guide

## ✅ Configuration Status

All graphs are **verified and working**:
- ✅ langgraph.json - Valid with 5 graphs  
- ✅ All imports - Working  
- ✅ All graph building - 5/5 successful  
- ✅ Dev server - Responsive  

Run `python3 test_langgraph_studio_setup.py` to verify.

---

## If You See "Failed to Preview Graph" Error

### 1. **Clear Browser Cache**
This is the most common cause. The error might be cached from a previous configuration.

**Chrome/Brave:**
- Press `Cmd + Shift + Delete`
- Select "All time"
- Check "Cookies and other site data" and "Cached images and files"
- Click "Clear data"

**Safari:**
- Menu → Develop → Empty Web Storage Cache
- OR: Preferences → Advanced → Show Develop menu (if not visible)

### 2. **Use a Fresh Browser Tab**
- Open an **Incognito/Private window**
- Navigate to LangGraph Studio URL
- Try again

### 3. **Check Browser Console for Full Error**
1. Open LangGraph Studio
2. Press `F12` (or `Cmd+Option+I` on Mac)
3. Go to **Console** tab
4. Look for red error messages
5. Screenshot the full error and share

---

## How to Start LangGraph Studio

### **Option A: Using the Startup Script (Recommended)**
```bash
./start_all_services_mac.sh
```
This starts:
- LangGraph Studio on port 2024
- LangGraph Service on port 5001
- Web UI on port 3000

### **Option B: Manual Start**
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
langgraph dev --port 2024
```

Then open: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

---

## Available Graphs in Studio

When you start LangGraph Studio, you should see **5 graphs** in the dropdown:

| Graph | Purpose | Nodes |
|-------|---------|-------|
| `main_orchestrator` | Complete query workflow | 15 |
| `discovery_agent` | Find relevant tables/views | 8 |
| `join_sql_agent` | Build joins & generate SQL | 6 |
| `exec_recovery_agent` | Execute & recover errors | 9 |
| `answer_agent` | Format results | 7 |

---

## Quick Test: Verify Graphs Load

```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python3 test_langgraph_studio_setup.py
```

Expected output:
```
✅ PASS - langgraph.json
✅ PASS - imports
✅ PASS - building
✅ PASS - dev_server
```

---

## Common Issues & Solutions

### Issue: "TypeError: Load failed"
**Cause:** Browser cache or network issue  
**Fix:**
1. Clear browser cache (see above)
2. Open LangGraph Studio in incognito mode
3. Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+F5` (Windows/Linux)

### Issue: "Graphs dropdown is empty"
**Cause:** Server didn't load graphs from langgraph.json  
**Fix:**
1. Check `langgraph.json` exists and is valid:
   ```bash
   python3 -m json.tool langgraph.json
   ```
2. Restart `langgraph dev`
3. Wait 5 seconds for graphs to load

### Issue: "Port 2024 already in use"
**Fix:**
```bash
# Kill process on port 2024
lsof -ti:2024 | xargs kill -9

# Then restart
langgraph dev --port 2024
```

### Issue: "Cannot connect to server"
**Fix:**
1. Verify server is running: `curl http://127.0.0.1:2024/info`
2. Check firewall settings
3. Ensure you're using the correct port (default: 2024)

---

## Next Steps if Still Having Issues

1. **Run the diagnostic script:**
   ```bash
   python3 test_langgraph_studio_setup.py
   ```

2. **Check the exact error in browser console** (F12 → Console)

3. **Provide:**
   - Full error message from browser console
   - Which graph you're trying to preview
   - Output of the diagnostic script
   - Browser type and version

---

## File Structure

```
.
├── langgraph.json                                    # ✅ Configuration with 5 graphs
├── langgraph_integration/
│   ├── graph_definition.py                          # ✅ Main orchestrator
│   └── agents/
│       ├── discovery/agent.py                       # ✅ build_discovery_graph()
│       ├── join_sql/agent.py                        # ✅ build_join_sql_graph()
│       ├── exec_recovery/agent.py                   # ✅ build_exec_recovery_graph()
│       └── answer/agent.py                          # ✅ build_answer_graph()
└── test_langgraph_studio_setup.py                   # ✅ Run this to verify
```

---

## Success Indicator

When everything works, you should see:
- ✅ LangGraph Studio starts without errors
- ✅ All 5 graphs appear in the graph dropdown
- ✅ You can click each graph and see the workflow visualization
- ✅ Each graph shows correct number of nodes and connections

---

**Last updated:** November 2, 2025  
**Configuration:** All 5 graphs verified working