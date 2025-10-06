# Quick Start Testing Guide

**Phase 7 Complete** ✅ - System Ready for Testing

---

## 🚀 Quick Start (5 Minutes)

### 1. Start the MCP Server

```bash
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
python mcp_server/server.py
```

**Expected Output**:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Verify MCP Server Health

Open a new terminal:

```bash
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "mcp_version": "1.0.0",
  "database": "connected"
}
```

### 3. Test Schema Discovery

```bash
curl -X POST http://localhost:8000/tools/search_tables \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"pattern": "customer"}}'
```

**Expected Response**:
```json
{
  "ok": true,
  "tables": [
    {
      "name": "Customers",
      "schema": "dbo",
      "type": "table",
      "row_count": 1000
    }
  ]
}
```

### 4. Test Query Execution

```bash
curl -X POST http://localhost:8000/tools/execute_query \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "SELECT TOP 5 CustomerID, CompanyName FROM Customers",
      "limit": 5
    }
  }'
```

**Expected Response**:
```json
{
  "ok": true,
  "rows": [
    {"CustomerID": "ALFKI", "CompanyName": "Alfreds Futterkiste"},
    ...
  ],
  "row_count": 5,
  "execution_time_ms": 45
}
```

---

## 🧪 Run Test Suite

### Run All MCP Client Tests

```bash
pytest tests/test_mcp_client.py -v
```

**Expected Output**:
```
tests/test_mcp_client.py::test_mcp_client_initialization PASSED
tests/test_mcp_client.py::test_execute_query_success PASSED
tests/test_mcp_client.py::test_execute_query_with_limit PASSED
tests/test_mcp_client.py::test_rate_limiting PASSED
tests/test_mcp_client.py::test_search_tables PASSED
tests/test_mcp_client.py::test_describe_table PASSED
tests/test_mcp_client.py::test_get_table_relations PASSED
tests/test_mcp_client.py::test_health_check PASSED
tests/test_mcp_client.py::test_exponential_backoff PASSED
tests/test_mcp_client.py::test_retry_after_header PASSED
tests/test_mcp_client.py::test_legacy_wrapper PASSED
tests/test_mcp_client.py::test_pagination_enforcement PASSED
tests/test_mcp_client.py::test_query_timeout PASSED
tests/test_mcp_client.py::test_connection_error_handling PASSED
tests/test_mcp_client.py::test_invalid_json_response PASSED

======================== 15 passed in 2.34s ========================
```

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

---

## 🎨 Start Chatbot UI

### 1. Start Streamlit App

```bash
streamlit run chatbot_ui/app.py
```

**Expected Output**:
```
You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.100:8501
```

### 2. Test Chatbot Queries

Open browser to `http://localhost:8501` and try:

**Example Queries**:
1. "Show me the top 5 customers"
2. "What tables are available in the database?"
3. "Describe the Orders table"
4. "How many products do we have?"
5. "Show me recent orders"

---

## 🔍 Verify Phase 7 Migration

### 1. Verify Legacy Endpoint is Deprecated

```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1"}'
```

**Expected Response** (410 Gone):
```json
{
  "ok": false,
  "error": "This endpoint has been deprecated and removed",
  "migration_guide": "...",
  "alternatives": ["Use MCP server at http://localhost:8000"]
}
```

### 2. Verify Only MCP Port is Active

```bash
netstat -an | grep LISTEN | grep -E "5000|8000"
```

**Expected Output**:
```
tcp4       0      0  *.8000                 *.*                    LISTEN
```

(Port 5000 should NOT be listed, or only for `/diag` endpoint)

### 3. Verify No Active Code Uses Legacy Client

```bash
grep -r "from app.db.client import" --include="*.py" . | grep -v test | grep -v deprecated
```

**Expected Output**: Empty (or only test files)

---

## 📊 Performance Testing

### 1. Load Test MCP Server

```bash
# Install Apache Bench if needed
brew install httpd

# Run 1000 requests with 10 concurrent connections
ab -n 1000 -c 10 -p query.json -T application/json http://localhost:8000/tools/execute_query
```

**query.json**:
```json
{
  "arguments": {
    "query": "SELECT TOP 10 * FROM Customers",
    "limit": 10
  }
}
```

**Expected Results**:
- Success rate: >95%
- Average response time: <100ms
- No 429 errors (rate limiting working correctly)

### 2. Monitor Rate Limiting

```bash
# Send 100 rapid requests
for i in {1..100}; do
  curl -X POST http://localhost:8000/tools/execute_query \
    -H "Content-Type: application/json" \
    -d '{"arguments": {"query": "SELECT 1", "limit": 1}}' &
done
wait
```

**Expected Behavior**:
- First 10 requests succeed immediately
- Subsequent requests get 429 with `Retry-After` header
- Exponential backoff applied automatically

---

## 🐛 Troubleshooting

### MCP Server Won't Start

**Problem**: `Address already in use`

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Restart MCP server
python mcp_server/server.py
```

### Database Connection Failed

**Problem**: `Connection refused` or `Authentication failed`

**Solution**:
1. Check `.env` file has correct credentials:
   ```bash
   cat .env | grep DB_
   ```

2. Verify VPN is connected (if using remote database)

3. Test database connection directly:
   ```bash
   python -c "from app.db.mcp_client import MCPDatabaseClient; client = MCPDatabaseClient(); print(client.health_check())"
   ```

### Tests Failing

**Problem**: `ModuleNotFoundError` or import errors

**Solution**:
```bash
# Install dependencies
pip install -r requirements.txt

# Verify Python version (3.11+ required)
python --version

# Run tests with verbose output
pytest tests/test_mcp_client.py -v -s
```

### Chatbot UI Not Loading

**Problem**: Streamlit app crashes or won't start

**Solution**:
1. Check MCP server is running first
2. Verify Streamlit is installed:
   ```bash
   pip install streamlit
   ```
3. Check for port conflicts:
   ```bash
   lsof -i :8501
   ```

---

## 📚 Next Steps

### After Testing

1. **Review Results**
   - Check all tests passed (15/15)
   - Verify chatbot responds correctly
   - Confirm performance meets requirements

2. **Read Documentation**
   - `docs/ARCHITECTURE_OVERVIEW.md` - Complete system design
   - `docs/PHASE_7_COMPLETE.md` - Phase 7 summary
   - `docs/MIGRATION_GUIDE_PHASE_7.md` - Migration details

3. **Plan Phase 8**
   - Multi-source integration (MongoDB, Neo4j)
   - Unified data access abstraction
   - Cross-source query planning

### Production Deployment

When ready for production:

1. **Security Hardening**
   - Enable HTTPS/TLS
   - Add API key authentication
   - Configure rate limiting per user
   - Enable audit logging

2. **Performance Tuning**
   - Adjust connection pool sizes
   - Configure caching strategies
   - Set up monitoring and alerts

3. **Documentation**
   - Create runbook for operations team
   - Document backup/recovery procedures
   - Set up incident response plan

---

## 🎯 Success Criteria

Your system is working correctly if:

- ✅ MCP server starts without errors
- ✅ Health check returns `{"status": "healthy"}`
- ✅ All 15 tests pass
- ✅ Schema discovery returns tables
- ✅ Query execution returns results
- ✅ Chatbot UI loads and responds
- ✅ Legacy `/query` endpoint returns 410 Gone
- ✅ Only port 8000 is active (not 5000)
- ✅ Rate limiting works (429 after 10 requests)
- ✅ Performance is acceptable (<100ms average)

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Phase 7 Status**: ✅ COMPLETE