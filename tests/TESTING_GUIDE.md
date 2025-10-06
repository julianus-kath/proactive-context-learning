# MCP Testing Guide

**Quick Start Guide for Testing the MCP-First Migration (Phase 1 & Phase 2)**

---

## Prerequisites

✅ MCP server running  
✅ PostgreSQL database available (dev)  
✅ MSSQL database available (production) - optional  
✅ Python dependencies installed  

---

## Quick Test (5 minutes)

### 1. Start MCP Server

```bash
cd mcp_server
python server.py
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Test MCP Health

```bash
curl http://localhost:8000/health | jq
```

**Expected Output:**
```json
{
  "status": "healthy",
  "service": "MCP Database Server",
  "database_ready": true
}
```

### 3. Run Phase 1 Tests

```bash
python scripts/test_phase1.py
```

**Expected Output:**
```
✅ Configuration loaded and validated
✅ Connector initialized (PostgresConnector)
✅ Connection established and verified
✅ Query executed successfully
✅ Schema discovery completed (6 tables in 0.08s)
✅ Schema caching works! (0.00s cached fetch)
✅ Cache statistics retrieved

Tests passed: 6/6 ✅
```

---

## Comprehensive Test (30 minutes)

### Step 1: Verify Migration Readiness

```bash
python scripts/migrate_langgraph_to_mcp.py
```

**Expected Output:**
```
Migration Readiness: 100.0% ✅
All functions are ready! You can proceed with migration.
```

### Step 2: Test MCP Client Directly

```bash
cd langgraph_integration
python mcp_client.py
```

**Expected Output:**
```
Testing MCP Database Tool...
Health check: ✅ Healthy

--- Testing Schema Retrieval ---
Schema: [{"name": "customers", "columns": [...]}]...

--- Testing Query Execution ---
Query result: {"rows": [...], "columns": [...]}

--- Testing Table Info ---
Table info: {"name": "customers", "columns": [...]}

✅ All tests passed!
```

### Step 3: Test LangGraph Integration

```bash
cd langgraph_integration
python test_flow.py
```

**Expected:** Workflow completes without errors

### Step 4: Test Complete System

```bash
cd chatbot_ui
python start_system.py
```

**Expected:** UI starts, queries work

---

## Production Test (MSSQL)

### Prerequisites

1. **Install ODBC Driver (macOS)**
   ```bash
   brew install unixodbc
   brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
   brew install microsoft/mssql-release/mssql-tools
   ```

2. **Configure Production Credentials**
   
   Edit `mcp_server/.env`:
   ```bash
   DB_DIALECT=mssql
   MSSQL_SERVER=your-server.database.windows.net
   MSSQL_DATABASE=your_database
   MSSQL_USER=your_user
   MSSQL_PASSWORD=your_password
   MSSQL_DRIVER=ODBC Driver 17 for SQL Server
   ```

### Run Tests

```bash
DB_DIALECT=mssql python scripts/test_phase1.py
```

**Expected Output:**
```
✅ Configuration loaded and validated
✅ Connector initialized (MSSQLConnector)
✅ Connection established and verified
✅ Query executed successfully
✅ Schema discovery completed (~1000 tables in < 5s)
✅ Schema caching works!
✅ Cache statistics retrieved

Tests passed: 6/6 ✅
```

**Key Metrics to Verify:**
- ✅ Schema fetch time < 5 seconds (for ~1,000 tables)
- ✅ No 429 errors
- ✅ All queries succeed
- ✅ Cache works correctly

---

## Validation Checklist

### MCP Server ✅

- [ ] Server starts without errors
- [ ] Health endpoint returns 200
- [ ] Database connection established
- [ ] Schema caching works
- [ ] Queries execute successfully

### PostgreSQL Connector ✅

- [ ] Connection successful
- [ ] Schema discovery works
- [ ] Queries return results
- [ ] Read-only enforcement works
- [ ] Timeouts enforced
- [ ] Row limits enforced

### MSSQL Connector ⏳

- [ ] Connection successful
- [ ] Schema discovery works (< 5s for 1,000 tables)
- [ ] No 429 errors
- [ ] Queries return results
- [ ] Read-only enforcement works
- [ ] Timeouts enforced
- [ ] Row limits enforced

### LangGraph Integration ⏳

- [ ] Imports work (no errors)
- [ ] All 9 functions available
- [ ] Workflow completes
- [ ] Schema discovery works
- [ ] Query execution works
- [ ] Error handling works
- [ ] Retry logic works

### End-to-End System ⏳

- [ ] UI starts
- [ ] User can ask questions
- [ ] Queries execute
- [ ] Results display correctly
- [ ] Error messages clear
- [ ] Performance acceptable

---

## Troubleshooting

### Issue: Server won't start

**Check:**
```bash
# Verify port is available
lsof -i :8000

# Check environment variables
cat mcp_server/.env

# Check logs
tail -f logs/mcp_server.log
```

### Issue: Connection refused

**Solution:**
```bash
# Ensure server is running
ps aux | grep "python server.py"

# Restart server
cd mcp_server
python server.py
```

### Issue: Import errors

**Solution:**
```bash
# Reinstall dependencies
cd mcp_server
pip install -r requirements.txt

# Verify installation
python -c "import pyodbc; import asyncpg; print('OK')"
```

### Issue: ODBC driver not found

**Solution (macOS):**
```bash
# Install driver
brew install unixodbc
brew install microsoft/mssql-release/mssql-tools

# Verify installation
odbcinst -j
```

### Issue: Schema fetch slow

**Check:**
```bash
# Verify cache is enabled
grep SCHEMA_CACHE_TTL mcp_server/.env

# Check cache stats
curl http://localhost:8000/health | jq '.cache_hits'
```

---

## Performance Benchmarks

### Expected Performance

| Operation | Dev (6 tables) | Prod (1,000 tables) |
|-----------|----------------|---------------------|
| First schema fetch | < 0.1s | < 5s |
| Cached schema fetch | < 0.01s | < 0.01s |
| Simple query | < 0.1s | < 1s |
| Complex query | < 1s | < 5s |

### Red Flags 🚩

- Schema fetch > 10s
- Cached fetch > 1s
- 429 errors
- Connection timeouts
- Memory leaks

---

## Success Criteria

### Minimum (Required)

- [x] MCP server starts
- [x] PostgreSQL connector works
- [x] Schema caching works
- [x] Queries execute
- [ ] LangGraph integration works
- [ ] No errors in workflow

### Optimal (Target)

- [ ] MSSQL connector works
- [ ] Schema fetch < 5s (1,000 tables)
- [ ] No 429 errors
- [ ] End-to-end system works
- [ ] Performance meets targets

### Stretch (Nice to Have)

- [ ] Schema fetch < 2s (Phase 2 target)
- [ ] Query result pagination
- [ ] Advanced error handling
- [ ] Monitoring dashboard

---

## Test Reports

### Generate Test Report

```bash
# Run all tests and save output
python scripts/test_phase1.py > test_report.txt 2>&1

# Check results
cat test_report.txt
```

### Share Results

Include in your report:
1. Test output (pass/fail)
2. Performance metrics (timing)
3. Any errors encountered
4. Environment details (OS, Python version, DB version)

---

## Next Steps After Testing

### If All Tests Pass ✅

1. Mark Phase 1 as **VALIDATED**
2. Update `MCP_MIGRATION_STATUS.md`
3. Proceed to Phase 2 (Catalog Optimization)
4. Consider retiring old proxy

### If Tests Fail ❌

1. Review error messages
2. Check troubleshooting section
3. Consult documentation:
   - `docs/PHASE_1_COMPLETE.md`
   - `docs/PHASE_1_STATUS.md`
4. Consider rollback if needed

### If Partial Success ⚠️

1. Document what works
2. Identify specific issues
3. Fix issues incrementally
4. Re-test after fixes

---

## Quick Commands Reference

```bash
# Start server
cd mcp_server && python server.py

# Test PostgreSQL
DB_DIALECT=postgres python scripts/test_phase1.py

# Test MSSQL
DB_DIALECT=mssql python scripts/test_phase1.py

# Check migration readiness
python scripts/migrate_langgraph_to_mcp.py

# Test MCP client
cd langgraph_integration && python mcp_client.py

# Test LangGraph
cd langgraph_integration && python test_flow.py

# Test complete system
cd chatbot_ui && python start_system.py

# Health check
curl http://localhost:8000/health | jq

# Check logs
tail -f logs/mcp_server.log
```

---

## Support

### Documentation

- `docs/PHASE_1_COMPLETE.md` - Detailed implementation docs
- `docs/PHASE_1_STATUS.md` - Status and next steps
- `docs/PHASE_1_MIGRATION_COMPLETE.md` - Migration guide
- `PHASE_1_SUMMARY.md` - Executive summary

### Scripts

- `scripts/test_phase1.py` - Automated validation tests
- `scripts/migrate_langgraph_to_mcp.py` - Migration analysis
- `scripts/ping_mcp.py` - MCP server diagnostics

### Configuration

- `mcp_server/.env.example` - Configuration template
- `langgraph_integration/.env.example` - LangGraph config

---

---

## Phase 2 Testing (Safety & Bounded Execution)

### Quick Test (5 minutes)

```bash
# Run all Phase 2 unit tests
pytest tests/test_phase2_*.py -v

# Expected: 43/43 tests passing
```

### Integration Test (15 minutes)

```bash
# Test with PostgreSQL
python scripts/test_phase2.py

# Test with SQL Server
DB_DIALECT=mssql python scripts/test_phase2.py
```

**Expected Output:**
```
============================================================
Phase 2 Integration Tests - POSTGRES
============================================================

✅ Database adapter initialized (postgres)

--- Test 1: Query Validation ---
✅ Valid SELECT query accepted
✅ INSERT query rejected
✅ UPDATE query rejected
✅ DELETE query rejected
✅ DROP query rejected
✅ Multi-statement query rejected

--- Test 2: Row Cap Injection ---
✅ LIMIT injected when missing
✅ LIMIT preserved when below max
✅ LIMIT clamped when above max

--- Test 3: Bounded Query Execution ---
✅ Valid query executed successfully
✅ Row cap enforced
✅ Execution time tracked

--- Test 4: Error Handling ---
✅ Invalid query returns structured error
✅ Empty query returns error
✅ Invalid SQL returns error

--- Test 5: Column Redaction ---
✅ Sensitive columns redacted
✅ Redaction can be disabled

--- Test 6: Response Envelope ---
✅ Response has required fields
✅ Response converts to dict

============================================================
Test Summary
============================================================
✅ Passed: 19
❌ Failed: 0
Total: 19
Success Rate: 100.0%
============================================================

🎉 All Phase 2 tests passed!
```

### Validation Checklist

#### Query Validation ✅

- [ ] SELECT queries accepted
- [ ] INSERT queries rejected
- [ ] UPDATE queries rejected
- [ ] DELETE queries rejected
- [ ] DROP queries rejected
- [ ] Multi-statement queries rejected
- [ ] Comments stripped correctly

#### Row Cap Injection ✅

- [ ] LIMIT/TOP injected when missing
- [ ] LIMIT/TOP preserved when below max
- [ ] LIMIT/TOP clamped when above max
- [ ] Works for PostgreSQL (LIMIT)
- [ ] Works for SQL Server (TOP)

#### Bounded Query Execution ✅

- [ ] Valid queries execute successfully
- [ ] Row caps enforced
- [ ] Execution time tracked
- [ ] Timeouts enforced
- [ ] Errors handled gracefully

#### Column Redaction ✅

- [ ] Sensitive columns identified
- [ ] Values redacted correctly
- [ ] Redaction can be disabled
- [ ] Custom patterns work

#### Response Envelope ✅

- [ ] Success responses structured correctly
- [ ] Error responses structured correctly
- [ ] All required fields present
- [ ] Converts to JSON correctly

---

## Phase 2 Testing (Safety & Bounded Execution)

### Quick Test (5 minutes)

#### 1. Run Phase 2 Unit Tests

```bash
# Test query validator (27 tests)
python -m pytest tests/test_phase2_query_validator.py -v

# Test column redactor (16 tests)
python -m pytest tests/test_phase2_column_redactor.py -v

# Run all Phase 2 tests
python -m pytest tests/test_phase2_*.py -v
```

**Expected Output:**
```
43 passed in 0.08s ✅
```

#### 2. Test Bounded Query Tool

```bash
# Quick sanity check
python -c "
from mcp_server.query_validator import validate_query
from mcp_server.column_redactor import redact_sensitive_data

# Test validator
result = validate_query('SELECT * FROM customers', dialect='postgres', max_rows=100)
print(f'✅ Validator: {result.valid}, Query: {result.query[:50]}...')

# Test redactor
rows = [{'id': 1, 'password': 'secret'}]
redacted, cols = redact_sensitive_data(rows)
print(f'✅ Redactor: password={redacted[0][\"password\"]}, redacted_cols={cols}')

print('✅ Phase 2 modules loaded successfully!')
"
```

**Expected Output:**
```
✅ Validator: True, Query: SELECT * FROM customers LIMIT 100...
✅ Redactor: password=[REDACTED], redacted_cols={'password'}
✅ Phase 2 modules loaded successfully!
```

### Comprehensive Test (30 minutes)

#### Step 1: Run Integration Tests (PostgreSQL)

```bash
# Set PostgreSQL dialect
export DB_DIALECT=postgres

# Run integration tests
python scripts/test_phase2.py
```

**Expected Output:**
```
=== Phase 2 Integration Tests ===
Dialect: postgres

✅ Test 1: Query Validation - Read-only enforcement
✅ Test 2: Query Validation - Multi-statement rejection
✅ Test 3: Query Validation - Comment stripping
✅ Test 4: Row Cap Injection - PostgreSQL LIMIT
✅ Test 5: Row Cap Injection - Clamp existing LIMIT
✅ Test 6: Bounded Execution - Success case
✅ Test 7: Bounded Execution - Timeout handling
✅ Test 8: Error Handling - Validation errors
✅ Test 9: Error Handling - Execution errors
✅ Test 10: Column Redaction - Sensitive columns
✅ Test 11: Column Redaction - Multiple patterns
✅ Test 12: Response Envelope - Metadata
✅ Test 13: Response Envelope - Truncated flag
✅ Test 14: End-to-End - Simple query
✅ Test 15: End-to-End - Complex query with CTE
✅ Test 16: End-to-End - Query with existing limit
✅ Test 17: Performance - Validation overhead
✅ Test 18: Performance - Redaction overhead
✅ Test 19: Performance - End-to-end overhead

Tests passed: 19/19 ✅
```

#### Step 2: Run Integration Tests (SQL Server)

```bash
# Set MSSQL dialect
export DB_DIALECT=mssql

# Run integration tests
python scripts/test_phase2.py
```

**Expected Output:**
```
=== Phase 2 Integration Tests ===
Dialect: mssql

✅ Test 4: Row Cap Injection - SQL Server TOP
✅ Test 5: Row Cap Injection - Clamp existing TOP
... (all 19 tests passing)

Tests passed: 19/19 ✅
```

#### Step 3: Test MCP Tool Integration

```bash
# Start MCP server
cd mcp_server
python server.py &

# Test query_bounded tool
curl -X POST http://localhost:8000/tools/query_bounded \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM customers",
    "max_rows": 10
  }' | jq
```

**Expected Output:**
```json
{
  "ok": true,
  "rows": [...],
  "row_count": 10,
  "execution_time_ms": 45,
  "truncated": true,
  "redacted_columns": [],
  "metadata": {
    "dialect": "postgres",
    "original_limit": null,
    "applied_limit": 10
  }
}
```

### Validation Checklist

#### Query Validator ✅

- [x] Read-only enforcement (INSERT/UPDATE/DELETE rejected)
- [x] Multi-statement rejection
- [x] Comment stripping (single-line and multi-line)
- [x] Row cap injection (PostgreSQL LIMIT)
- [x] Row cap injection (SQL Server TOP)
- [x] Existing limit clamping
- [x] WITH...SELECT (CTE) support
- [x] Structured error codes

#### Column Redactor ✅

- [x] Pattern-based sensitive column detection
- [x] Case-insensitive matching
- [x] Multiple pattern support
- [x] Configurable redaction text
- [x] Custom pattern addition/removal
- [x] Redaction can be disabled

#### Bounded Query Executor ✅

- [x] Query validation integration
- [x] Timeout enforcement (driver-level)
- [x] Execution time tracking
- [x] Response envelope with metadata
- [x] Truncated flag when row cap applied
- [x] Column redaction integration
- [x] Structured error handling

#### MCP Tool Integration ⏳

- [ ] `query_bounded` tool available
- [ ] Tool accepts query and max_rows parameters
- [ ] Tool returns structured response
- [ ] Tool handles validation errors
- [ ] Tool handles execution errors
- [ ] Tool integrates with LangGraph

### Acceptance Criteria Verification

#### ✅ Bad Verbs Rejected

```bash
# Test INSERT rejection
python -c "
from mcp_server.query_validator import validate_query
result = validate_query('INSERT INTO customers VALUES (1)', dialect='postgres')
assert not result.valid
assert result.error_code == 'READ_ONLY_VIOLATION'
print('✅ INSERT rejected with READ_ONLY_VIOLATION')
"
```

#### ✅ Long-Running Queries Timeout

```bash
# Test timeout (requires real database)
python scripts/test_phase2.py --test timeout
```

#### ✅ Queries Without Caps Return Truncated

```bash
# Test truncated flag
python -c "
from mcp_server.query_validator import validate_query
result = validate_query('SELECT * FROM customers', dialect='postgres', max_rows=100)
assert 'LIMIT 100' in result.query
print('✅ Row cap injected, truncated=true will be set')
"
```

#### ✅ Works for Both Dialects

```bash
# Test PostgreSQL
python -m pytest tests/test_phase2_query_validator.py::TestQueryValidatorPostgres -v

# Test SQL Server
python -m pytest tests/test_phase2_query_validator.py::TestQueryValidatorMSSQL -v
```

### Performance Benchmarks

#### Expected Performance

| Operation | Overhead | Target |
|-----------|----------|--------|
| Query validation | < 1ms | < 5ms |
| Comment stripping | < 0.5ms | < 2ms |
| Row cap injection | < 0.5ms | < 2ms |
| Column redaction (1000 rows) | < 5ms | < 10ms |
| Response envelope | < 1ms | < 2ms |
| **Total overhead** | **< 10ms** | **< 20ms** |

#### Measure Performance

```bash
# Run performance tests
python scripts/test_phase2.py --test performance
```

### Troubleshooting

#### Issue: Validation tests failing

**Check:**
```bash
# Verify query validator module
python -c "from mcp_server.query_validator import QueryValidator; print('OK')"

# Run specific test
python -m pytest tests/test_phase2_query_validator.py::TestQueryValidatorPostgres::test_insert_rejected -v
```

#### Issue: Redaction not working

**Check:**
```bash
# Verify redactor module
python -c "from mcp_server.column_redactor import ColumnRedactor; print('OK')"

# Test redaction manually
python -c "
from mcp_server.column_redactor import redact_sensitive_data
rows = [{'password': 'secret'}]
redacted, cols = redact_sensitive_data(rows)
print(f'Redacted: {redacted}, Columns: {cols}')
"
```

#### Issue: Integration tests failing

**Solution:**
```bash
# Check database connection
python scripts/test_phase1.py

# Verify environment variables
echo $DB_DIALECT

# Check MCP server is running
curl http://localhost:8000/health
```

### Success Criteria

#### Minimum (Required)

- [x] All 43 unit tests passing
- [x] Query validator works for both dialects
- [x] Column redactor works
- [x] Bounded query executor works
- [ ] Integration tests pass (PostgreSQL)
- [ ] Integration tests pass (SQL Server)

#### Optimal (Target)

- [ ] MCP tool integration complete
- [ ] LangGraph uses `query_bounded` tool
- [ ] Performance overhead < 10ms
- [ ] End-to-end system works
- [ ] No breaking changes to existing code

#### Stretch (Nice to Have)

- [ ] Custom redaction patterns configured
- [ ] Monitoring dashboard for query stats
- [ ] Query result caching
- [ ] Pagination support

### Phase 2 Documentation

- `docs/PHASE_2_COMPLETE.md` - Full implementation guide
- `PHASE_2_SUMMARY.md` - Executive summary
- `docs/PHASE_2_QUICK_REFERENCE.md` - Quick commands
- `PHASE_2_IMPLEMENTATION_REPORT.md` - Detailed report

### Phase 2 Scripts

- `tests/test_phase2_query_validator.py` - Validator unit tests (27 tests)
- `tests/test_phase2_column_redactor.py` - Redactor unit tests (16 tests)
- `scripts/test_phase2.py` - Integration test suite (19 tests)

---

**Happy Testing! 🚀**

*If you encounter any issues not covered in this guide, please document them for future reference.*