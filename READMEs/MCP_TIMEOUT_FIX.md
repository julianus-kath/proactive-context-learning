# MCP Server Timeout - Root Cause & Fix

## 🔍 Root Cause Analysis

The errors you saw in `langgraph.log` were caused by:

```
ERROR:langgraph_integration.mcp_client:Unexpected error calling MCP server: 
...TimeoutError
INFO:langgraph_integration.graph_definition:Database indexed: 0 tables across 0 schemas
```

**The Problem:**
- LangGraph tried to call the MCP server at `http://192.168.1.35:8000/mcp`
- The request timed out after **30 seconds**
- When timeout occurred, the system silently returned **0 tables** without alerting you to the real issue
- This made debugging very difficult because the error was buried in logs and the system just appeared "empty"

**Why it times out:**
1. The MCP server on Windows is not responding within 30 seconds
2. Could be: server not running, network issue, firewall blocking, or server is overloaded

---

## ✅ What Was Fixed

### 1. **Increased Timeout for `get_schema` (30s → 120s)**
   - Schema discovery is an expensive operation (scans all databases and tables)
   - First run can take a while, so increased timeout to 120 seconds
   - Other operations still use 30s timeout

   ```python
   # Before: All operations used 30s timeout
   timeout=aiohttp.ClientTimeout(total=30)
   
   # After: get_schema gets 120s, others get 30s
   timeout_seconds = 120 if tool_name == "get_schema" else 30
   ```

### 2. **Better Error Messages for Timeouts**
   - Now clearly shows when a timeout occurs
   - Provides diagnostic information about what to check

   ```
   ⏱️  TIMEOUT: MCP server timeout (>120s) - server at http://192.168.1.35:8000 may be unreachable
      → Check Windows MCP server is running and accessible
      → Verify MCP_SERVER_URL=http://192.168.1.35:8000 is correct
      → Check network connectivity to the Windows machine
   ```

### 3. **Improved Error Handling in `index_database`**
   - Now distinguishes between timeout errors and other errors
   - Returns error status so workflow knows something went wrong
   - Provides specific troubleshooting hints

   ```python
   # Before: Silent failure
   except Exception as e:
       logger.error(f"Error indexing database: {e}")
       return {"tables": {}, "total_tables": 0}
   
   # After: Clear error reporting
   except ValueError as e:
       logger.error(f"❌ Error indexing database: {error_str}")
       if "timeout" in error_str.lower():
           logger.error(f"   MCP server is not responding. Check: ...")
       return {"error": error_str, "status": "FAILED"}
   ```

### 4. **New Diagnostic Script**
   - Created `tests/test_mcp_connectivity.py` to test MCP server connectivity
   - Tests health endpoint, network connectivity, and tool calls
   - Provides clear pass/fail results with troubleshooting hints

---

## 🧪 How to Verify the Fix

### Step 1: Run the Diagnostic Script
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python tests/test_mcp_connectivity.py
```

**Expected output if MCP server is working:**
```
✅ OK: Health endpoint responded in 234ms
✅ OK: TCP connection successful in 45ms
✅ OK: Tool call succeeded in 2456ms
```

**If it fails:**
```
❌ FAIL: Cannot reach health endpoint: ConnectionRefusedError
   → Start Windows MCP server: start_mcp_server_windows.bat
   → Verify MCP_SERVER_URL is correct in .env
```

### Step 2: Check your `.env` file
```bash
# Should contain:
MCP_SERVER_URL=http://192.168.1.35:8000
MCP_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### Step 3: Start Services
```bash
./start_all_services_mac.sh
```

### Step 4: Watch the Logs
```bash
# In a new terminal, watch for clear error messages:
tail -f logs/langgraph_debug.log
```

**With the fix, you'll now see:**
- ✅ Clear success messages when MCP works
- ❌ Clear error messages with diagnostics if MCP is unreachable
- ⏱️ Explicit timeout warnings (instead of silent failures)

---

## 🔧 Troubleshooting Checklist

### If you see "MCP server timeout" error:

**1. Is the Windows MCP server running?**
```bash
# On Windows:
start_mcp_server_windows.bat
# or
python mcp_server/main.py
```

**2. Is the network connection working?**
```bash
# On Mac, test connectivity:
ping 192.168.1.35
nc -zv 192.168.1.35 8000
```

**3. Is MCP_SERVER_URL correct in .env?**
```bash
# Check your actual Windows IP:
# (It might have changed since you last configured it)
cat .env | grep MCP_SERVER_URL
```

**4. Are there firewall blocks?**
- Windows Firewall might be blocking port 8000
- Check Windows Firewall settings on the MCP server machine
- Or run the MCP server with firewall disabled temporarily for testing

**5. Is the MCP server overloaded?**
- Check Windows CPU/memory usage
- First schema scan can be slow on large databases
- Subsequent runs should be faster

---

## 📝 Modified Files

### `langgraph_integration/mcp_client.py`

1. **Lines 122-130**: Increased timeout logic
   - `get_schema`: 120 seconds (was 30)
   - Other tools: 30 seconds (unchanged)

2. **Lines 200-208**: New TimeoutError handler
   - Catches asyncio.TimeoutError specifically
   - Provides diagnostic messages
   - Properly logs with debug logger

3. **Lines 678-700**: Improved index_database error handling
   - Catches ValueError (from timeouts)
   - Distinguishes timeout vs other errors
   - Returns status="FAILED" so workflow knows

### `tests/test_mcp_connectivity.py` (NEW)
- Comprehensive MCP connectivity tester
- Tests health endpoint, network, and tool calls
- Provides colored output and troubleshooting hints

---

## 🎯 What's Next

After applying this fix:

1. **Run the diagnostic** to verify MCP server connectivity
2. **Check the logs** for the new error messages
3. **If still failing**, use the troubleshooting checklist above
4. **If working**, you'll see proper table counts instead of "0 tables across 0 schemas"

Example successful log output:
```
📋 Pre-flight checks...
✅ MCP server is reachable
🔍 Scout Mode: list_tables
   result_count: 15
   tables_searched: [orders, customers, products, ...]
```

Instead of (before fix):
```
Database indexed: 0 tables across 0 schemas
```

---

## 📊 Performance Impact

- ⏱️ **Startup**: +90 seconds for first `get_schema` call (was 30s)
  - Necessary because schema discovery is expensive
  - This is a one-time cost for the workflow initialization
  - Subsequent calls are much faster

- 💾 **Memory**: No change

- 🔌 **Network**: More robust connection handling with better error messages

---

## Questions?

Check the logs for the specific error message. They're now much more informative:

```bash
# Real-time logs:
tail -f logs/langgraph_debug.log

# Or search for specific issues:
grep -i "timeout" logs/langgraph_debug.log
grep -i "mcp server" logs/langgraph_debug.log
```