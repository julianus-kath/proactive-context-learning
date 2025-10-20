# Schema JSON Parsing Fix Guide

## Problem Summary

The system was experiencing a critical error during database indexing:

```
It seems there was an issue parsing the database schema due to a missing or 
malformed JSON object. To fix this, ensure the schema JSON is correctly 
formatted and accessible, then restart the database indexing process.
```

This error indicates that the `index_database()` function is failing to parse the JSON response from the MCP server. The root causes could be:

1. **Empty or missing schema text** - The MCP server returns content but the "text" field is empty
2. **Unexpected response format** - The response structure doesn't match what we expect
3. **Malformed JSON** - The JSON in the response contains syntax errors
4. **Timeout** - The MCP server is slow or unreachable
5. **Different marker format** - The response doesn't contain "Full response (JSON):" marker

## Solution Overview

The fix involves **two components**:

### 1. Enhanced Debugging in `index_database()` Function

The updated function now:
- Logs at each step of the process
- Shows exact data types and content lengths
- Displays previews of the raw response
- Identifies specific problems (empty text, missing braces, missing marker, etc.)
- Returns detailed `debug_info` in error responses

### 2. Improved JSON Extraction Helper

The `_extract_json_from_text()` function now:
- Supports multiple marker variations ("Full response (json):", "JSON Response:", etc.)
- Handles empty whitespace cases
- Provides detailed error messages with context
- Shows exactly where JSON parsing fails (line, column)
- Validates JSON boundaries before attempting parse

## How to Diagnose the Issue

### Step 1: Run the Diagnostic Script

```bash
cd /Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code
python3 tests/diagnose_schema_issue.py
```

This script will:
1. ✅ Test MCP server connection
2. ✅ Fetch the raw schema from MCP
3. ✅ Show exactly what the response looks like
4. ✅ Attempt JSON extraction with detailed feedback
5. ✅ Validate the schema structure

### Step 2: Check the Debug Logs

While running the system, monitor the debug log in real-time:

```bash
# Terminal 1: Start services
./start_all_services_mac.sh

# Terminal 2: Monitor debug log (in another terminal)
tail -f logs/langgraph_debug.log | grep -i "schema\|index\|json"
```

Look for these key markers in the logs:

**Successful indexing:**
```
📋 Fetching schema from MCP server...
   ✓ JSON extraction successful
✅ Database indexed: 50 tables on page 1 of 943 total
```

**JSON parsing failure:**
```
❌ Failed to parse schema JSON: ...
   Schema text preview: ...
   → Problem: Expected 'Full response (JSON):' marker not found
```

**Empty response:**
```
❌ Schema text is empty. First item: ...
```

**Connection failure:**
```
⏱️  TIMEOUT: MCP server timeout (>120s) ...
```

## Common Issues and Solutions

### Issue 1: "No JSON object found (no opening brace)"

**Cause:** The MCP response doesn't contain JSON data

**Debug output:**
```
❌ Failed to parse schema JSON: No JSON object found in content
   → Problem: No JSON object found (no opening brace)
   Schema text preview: Some error message or non-JSON content
```

**Solutions:**
1. **Check MCP server is running:**
   ```bash
   # Windows command
   start_mcp_server_windows.bat
   ```

2. **Verify MCP_SERVER_URL in .env:**
   ```bash
   # Mac: Check your .env file
   grep MCP_SERVER_URL .env
   # Should output something like:
   # MCP_SERVER_URL=http://10.255.152.48:8000
   ```

3. **Test MCP server directly:**
   ```bash
   # Mac: Test if MCP is reachable
   curl -H "X-API-Key: your_key" http://your_mcp_ip:8000/health
   ```

### Issue 2: "Schema text is empty"

**Cause:** MCP returned content but without the expected "text" field

**Debug output:**
```
❌ Schema text is empty. First item: {'type': 'text'}
```

**Solution:** This indicates the MCP response structure changed. Contact the MCP server maintainer or check if there was a recent update.

### Issue 3: "MCP server returned empty schema content"

**Cause:** MCP server responded but with empty content list

**Debug output:**
```
❌ MCP server returned empty schema content
   First item: get_schema() returned empty list
```

**Solutions:**
1. **Restart MCP server** (it might be in a bad state)
2. **Check database connectivity** - MCP might not be able to reach the database
3. **Check database credentials** in Windows MCP server config

### Issue 4: "MCP server timeout"

**Cause:** MCP server is taking too long (>120 seconds)

**Debug output:**
```
⏱️  TIMEOUT: MCP server timeout (>120s) - server at http://... may be unreachable or overloaded
```

**Solutions:**
1. **Check Windows MCP server is responsive:**
   ```bash
   ping your_windows_ip
   ```

2. **Check database query performance:**
   - First-time schema discovery can be slow on large databases
   - Wait 2-3 minutes for the server to respond

3. **Restart MCP server:**
   ```bash
   # Windows: Stop and restart
   stop_mcp_server_windows.bat
   start_mcp_server_windows.bat
   ```

4. **Increase timeout** (if schema is legitimately large):
   - Edit `langgraph_integration/mcp_client.py` line ~170
   - Change: `timeout_seconds = 120 if tool_name == "get_schema" else 30`
   - To: `timeout_seconds = 300 if tool_name == "get_schema" else 30` (5 minutes)

### Issue 5: "Expected 'Full response (JSON):' marker not found"

**Cause:** MCP server response format changed

**Debug output:**
```
❌ Failed to parse schema JSON: No JSON object found
   → Problem: Expected 'Full response (JSON):' marker not found
   → The response might be in a different format
   Schema text preview: [{"name": "customers", ...
```

**Solution:** The response might be in plain JSON format (no marker). The improved extraction helper now handles this:

1. **Verify manually** by running diagnostic:
   ```bash
   python3 tests/diagnose_schema_issue.py
   ```

2. **Check actual response format:**
   - Diagnostic will show the exact format returned
   - If it's plain JSON, the new code should handle it

## Implementation Details

### Changes to `index_database()` in `mcp_client.py`

**Lines 722-861: Enhanced function with detailed debugging**

Key improvements:
- ✅ Logs schema content type and length
- ✅ Shows first content item structure
- ✅ Validates schema_text before parsing
- ✅ Detailed error messages identifying specific problems
- ✅ Returns `debug_info` field in error responses

**Example error response (before):**
```python
{
    "status": "FAILED",
    "error": "Failed to parse schema JSON: ...",
    "tables": {},
    "total_tables": 0
}
```

**Example error response (after):**
```python
{
    "status": "FAILED",
    "error": "No JSON object found in content",
    "tables": {},
    "total_tables": 0,
    "debug_info": "First item: {'type': 'text'} ... (showing structure)"
}
```

### Changes to `_extract_json_from_text()` in `mcp_client.py`

**Lines 37-121: Improved JSON extraction**

Key improvements:
- ✅ Handles marker variations (case-insensitive)
- ✅ Better error messages with context
- ✅ Shows problematic section in JSON
- ✅ Validates boundaries before parsing
- ✅ More detailed ValueError messages

## Verification Steps

### Step 1: Run Diagnostic Script

```bash
python3 tests/diagnose_schema_issue.py
```

**Expected output for success:**
```
[Step 1] Testing MCP Server Connection
✅ MCP server is healthy

[Step 2] Fetching Raw Schema
✅ Successfully fetched schema content
   Content type: <class 'list'>
   Content length: 1

[Step 3] Testing JSON Extraction
✅ JSON extraction successful!

[Step 4] Validating Schema Structure
✅ Schema structure is valid
   Tables on current page: 50
   Total tables in database: 943
   Current page: 1
```

### Step 2: Run Service and Check Logs

```bash
# Start services
./start_all_services_mac.sh

# In another terminal, monitor logs
tail -f logs/langgraph_debug.log | grep "Database indexed"

# Expected output:
# ✅ Database indexed: 50 tables on page 1 of 943 total
```

### Step 3: Test Query

1. Open Web UI: http://localhost:3000
2. Ask a question: "What products do we have?"
3. Check that it:
   - ✅ Doesn't ask for clarification (uses answer-first defaults)
   - ✅ Executes the query successfully
   - ✅ Returns results

## Deployment Checklist

Before deployment, verify:

- [ ] All syntax is valid:
  ```bash
  python3 -m py_compile langgraph_integration/mcp_client.py
  python3 -m py_compile langgraph_integration/graph_definition.py
  ```

- [ ] Diagnostic script runs without errors:
  ```bash
  python3 tests/diagnose_schema_issue.py
  ```

- [ ] Services start successfully:
  ```bash
  ./start_all_services_mac.sh
  # Wait for 🚀 Starting Mac services... ✅ All Mac services started successfully
  ```

- [ ] Schema is indexed properly:
  ```bash
  tail -f logs/langgraph_debug.log | grep "indexed"
  # Should see: ✅ Database indexed: ... tables
  ```

## Rollback Instructions

If you encounter issues, you can rollback to the previous version:

```bash
# Restore from git if available
git checkout langgraph_integration/mcp_client.py

# Or manually revert to the previous implementation
# (your system administrator should have a backup)
```

## Advanced Troubleshooting

### Log Everything to File

For more detailed analysis, redirect debug logs to a file:

```bash
# In .env or before starting services
export LANGGRAPH_DEBUG_LOG=/Users/juli/Desktop/Studies/Master/Year\ 2/Semester\ 2/Master\ Thesis/code/logs/detailed_debug.log

./start_all_services_mac.sh
```

Then analyze:
```bash
cat logs/detailed_debug.log | grep -A 10 "Fetching schema"
```

### Test with Mock Data

Create a test with mock MCP responses:

```python
# In a test file
from langgraph_integration.mcp_client import _extract_json_from_text

mock_response = """Full response (JSON): {
    "data": {
        "tables": [{"name": "test", "columns": []}],
        "page_info": {"total_items": 100, "total_pages": 2, "page": 1}
    }
}"""

result = _extract_json_from_text(mock_response)
assert result["data"]["page_info"]["total_items"] == 100
print("✅ Mock test passed")
```

### Monitor Network Traffic

To debug network issues:

```bash
# Mac: Monitor HTTP calls to MCP server
sudo tcpdump -i en0 -n 'host your_windows_ip and port 8000'

# Or use netstat to check connection state
netstat -an | grep 8000
```

## Performance Notes

- **First run:** Schema indexing typically takes 60-120 seconds (slow database discovery)
- **Subsequent runs:** Should be much faster as results are cached
- **Timeout:** Set to 120 seconds by default; increase if working with very large schemas

## Future Improvements

Future enhancements to consider:

1. **Schema caching** - Cache results to eliminate 60-120s first-run delay
2. **Pagination** - Load schema in pages rather than all at once
3. **Retry logic** - Exponential backoff for transient failures
4. **Metrics** - Track MCP call durations and success rates
5. **Compression** - Compress large schema responses

## Support

If you still encounter issues after following this guide:

1. **Collect diagnostic information:**
   ```bash
   python3 tests/diagnose_schema_issue.py > /tmp/diagnostic_output.txt 2>&1
   ```

2. **Share with development team:**
   - Output from diagnostic script
   - Last 100 lines of `logs/langgraph_debug.log`
   - `.env` file (with secrets redacted)
   - Any error messages from MCP server logs (Windows)

3. **Contact:** Check project documentation for support contacts

---

**Document version:** 1.0  
**Last updated:** 2024  
**System:** Proactive Context Learning / Dynamic ERP Assistant