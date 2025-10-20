# ⚡ Quick MCP Timeout Fix - 2 Minute Guide

## Problem
Your MCP server was timing out, returning `0 tables across 0 schemas`

## What Changed
✅ Timeout increased from 30s → 120s for `get_schema`  
✅ Better error messages showing what's wrong  
✅ Added diagnostic tool  

## Verify the Fix (90 seconds)

### Step 1: Run diagnostic (30 sec)
```bash
python tests/test_mcp_connectivity.py
```

**Should see:**
```
✅ OK: Health endpoint responded
✅ OK: TCP connection successful
✅ OK: Tool call succeeded
```

### Step 2: Restart services (30 sec)
```bash
./start_all_services_mac.sh
```

### Step 3: Check logs (30 sec)
```bash
tail -f logs/langgraph_debug.log
```

**Should see:**
```
✅ LangGraph workflow initialized successfully
📝 Processing conversation...
🔍 Scout Mode: list_tables
   result_count: 15 (NOT 0!)
```

---

## If Diagnostic Fails

### "❌ FAIL: Cannot reach health endpoint"
```bash
# 1. Is Windows MCP server running?
# On Windows, run: start_mcp_server_windows.bat

# 2. Is IP correct in .env?
cat .env | grep MCP_SERVER_URL
# Should be your Windows machine IP

# 3. Can you reach it?
ping 192.168.1.35
```

### "⏱️ TIMEOUT: Tool call timeout after 60s"
```bash
# MCP server is running but slow/overloaded

# Option 1: Wait and try again (schema scan might be slow first time)
python tests/test_mcp_connectivity.py

# Option 2: Check Windows machine
# - Is disk I/O high?
# - Is CPU maxed out?
# - Restart MCP server on Windows
```

---

## Files Changed
- ✏️ `langgraph_integration/mcp_client.py` - Timeout logic & error handling
- ✨ `tests/test_mcp_connectivity.py` - New diagnostic tool
- 📚 `MCP_TIMEOUT_FIX.md` - Detailed explanation

---

## Next Steps
1. ✅ Run diagnostic
2. ✅ Restart services  
3. ✅ Check logs show proper table counts
4. 🎉 Done!

Questions? See `MCP_TIMEOUT_FIX.md` for detailed troubleshooting.