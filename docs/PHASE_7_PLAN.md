# Phase 7: Decommission Old Proxy (Cleanup) - PLAN

**Goal**: No drift; one way in. MCP is the only database access layer.

**Status**: Planning  
**Priority**: HIGH (Technical debt cleanup)  
**Architecture Alignment**: ADR-0007, ADR-0010, ADR-0011

---

## 🎯 Objectives

### Primary Goal
Remove all legacy Flask proxy (`/query` endpoint) references and ensure **MCP is the single source of truth** for SQL database access.

### Scope
✅ **In Scope**:
- SQL database access via MCP only
- Decommission Flask `/query` endpoint (410 Gone)
- Migrate `app/db/client.py` to MCP
- Update SQL-related tests
- Enforce design guardrails for SQL access

❌ **Out of Scope** (Experimental, Phase 8+):
- MongoDB/document store integration
- Multi-source query planning
- Cross-database joins
- Document-aware context enrichment

⚠️ **Admin Tools** (Keep with deprecation warnings):
- `populate_document_store.py` (mark as deprecated)
- `synthetic_data_service/document_store/populate.py` (mark as deprecated)

### Design Guardrails (Enforced)
1. **Never enumerate full schema**: Discovery is paged/searchable from MCP's catalog
2. **Small, focused prompts**: Only include schema_snippet for ≤3 tables
3. **One interface**: LangGraph → MCP JSON-RPC (dialect chosen by env); the rest is transparent
4. **Caching everywhere**:
   - Catalog snapshot + in-memory
   - Response caching for discovery tools
   - Session cache in LangGraph for described tables
5. **Backpressure**: MCP rate-limits and returns Retry-After; LangGraph backs off and never fans out

---

## 📊 Current State Analysis

### Legacy `/query` Endpoint Usage

**Active Code Paths**:
1. ✅ **`vpn_config/proxy.py`** (lines 509-650)
   - Flask `/query` endpoint still active
   - Handles direct SQL execution
   - **Status**: Should be removed or marked deprecated

2. ✅ **`app/db/client.py`** (lines 129)
   - DatabaseClient still calls `POST /query`
   - Used by legacy code paths
   - **Status**: Should migrate to MCP or be removed

3. ⚠️ **`synthetic_data_service/document_store/populate.py`** (lines 35, 66)
   - Document store population uses `/query`
   - **Status**: Can be migrated to MCP or kept as admin tool

4. ⚠️ **`scripts/populate_document_store.py`** (lines 36, 67)
   - Script uses `/query` for data population
   - **Status**: Can be migrated to MCP or kept as admin tool

5. ⚠️ **`tests/test_openai_agent.py`** (line 25)
   - Test references old endpoint
   - **Status**: Should be updated or removed

**Documentation References**:
1. **ADR-0006**: References `/query` endpoint
2. **ADR-0010**: Shows `/query` in architecture diagram
3. **ADR-0011**: Documents proxy `/query` API

**Log Files**:
- Multiple log entries showing 429 errors from `/query` endpoint
- Evidence of legacy code still hitting old proxy

---

## ✅ Phase 7 Tasks

### Task 1: Audit & Categorize `/query` Usage

**Subtasks**:
- [x] Search codebase for `/query` references (completed above)
- [ ] Categorize each usage:
  - **Remove**: Dead code, obsolete tests
  - **Migrate**: Active code that should use MCP
  - **Keep**: Admin tools that need direct access
- [ ] Document migration strategy for each category

**Acceptance**:
- Complete inventory of all `/query` references
- Clear categorization (remove/migrate/keep)
- Migration plan documented

### Task 2: Migrate Active Code to MCP

**Files to Migrate**:

1. **`app/db/client.py`**
   - Replace `POST /query` with MCP JSON-RPC calls
   - Use `mcp_server.tools.query_bounded` instead
   - Update error handling for MCP response format

2. **`tests/test_openai_agent.py`**
   - Update test to use MCP endpoint
   - Replace `/query` with MCP tool calls

**Acceptance**:
- All active code uses MCP JSON-RPC
- No direct `/query` calls in production code paths
- Tests pass with MCP integration

### Task 3: Mark Admin Tools as Deprecated

**Files to Update**:

1. **`synthetic_data_service/document_store/populate.py`**
   - Add deprecation warning
   - Document MCP alternative
   - Keep for backward compatibility (optional)

2. **`scripts/populate_document_store.py`**
   - Add deprecation warning
   - Document MCP alternative
   - Keep for backward compatibility (optional)

**Acceptance**:
- Clear deprecation warnings in code
- Documentation updated with MCP alternatives
- Admin tools still functional (if kept)

### Task 4: Update Documentation

**Files to Update**:

1. **ADR-0006**: `adrs/0006-agent-architecture-and-data-integration.md`
   - Remove `/query` endpoint references
   - Update to show MCP as primary interface
   - Add migration notes

2. **ADR-0010**: `adrs/0010-dynamic-erp-assistant-complete-system-architecture.md`
   - Update architecture diagram (remove `/query` flow)
   - Show MCP JSON-RPC as only database access
   - Document design guardrails

3. **ADR-0011**: `adrs/0011-proxy-for-vpn-tunneling.md`
   - Mark `/query` endpoint as deprecated
   - Document MCP migration path
   - Update proxy role description

4. **README.md**
   - Update setup instructions
   - Remove `/query` endpoint documentation
   - Add MCP-only access instructions

**Acceptance**:
- All ADRs updated to reflect MCP-only architecture
- No references to `/query` as primary interface
- Clear migration guide for legacy users

### Task 5: Decommission Flask `/query` Endpoint

**Options**:

**Option A: Complete Removal** (Recommended)
- Remove `/query` endpoint from `vpn_config/proxy.py`
- Remove all Flask dependencies
- Proxy becomes MCP-only

**Option B: Deprecation with Warning**
- Keep `/query` endpoint but return 410 Gone
- Include migration instructions in response
- Log all attempts to use deprecated endpoint

**Option C: Admin-Only Mode**
- Require special admin API key for `/query`
- Add rate limiting (1 req/min)
- Log all usage for audit

**Recommendation**: **Option B** (Deprecation with Warning)
- Provides clear migration path
- Doesn't break existing scripts immediately
- Allows monitoring of legacy usage

**Implementation**:
```python
@app.route("/query", methods=["POST"])
def query_deprecated():
    """DEPRECATED: Use MCP JSON-RPC instead."""
    logger.warning("Deprecated /query endpoint called")
    return jsonify({
        "ok": False,
        "error": "This endpoint is deprecated. Please use MCP JSON-RPC instead.",
        "code": "ENDPOINT_DEPRECATED",
        "migration_guide": "https://docs.example.com/mcp-migration",
        "mcp_endpoint": "http://localhost:8000/mcp",
        "mcp_tools": ["query_bounded", "list_tables", "search_tables"]
    }), 410  # 410 Gone
```

**Acceptance**:
- `/query` endpoint returns 410 Gone
- Clear migration instructions in response
- All usage logged for monitoring

### Task 6: Enforce Design Guardrails

**Implementation**:

1. **Never enumerate full schema**
   - Add validation in MCP tools
   - Reject requests without pagination
   - Log violations

2. **Small, focused prompts (≤3 tables)**
   - Add prompt size validation
   - Warn when schema_snippet > 3 tables
   - Provide guidance for splitting queries

3. **One interface (LangGraph → MCP)**
   - Remove all direct database access
   - Enforce MCP as only entry point
   - Update architecture diagrams

4. **Caching everywhere**
   - ✅ Catalog snapshot (already implemented)
   - ✅ Response caching (already implemented)
   - [ ] Session cache in LangGraph
   - [ ] Document caching strategy

5. **Backpressure (rate limiting + Retry-After)**
   - ✅ Rate limiting (already implemented)
   - ✅ Retry-After headers (already implemented)
   - [ ] LangGraph exponential backoff
   - [ ] Circuit breaker pattern

**Acceptance**:
- All guardrails enforced in code
- Validation errors logged
- Documentation updated with guardrails

### Task 7: Validation & Testing

**Test Plan**:

1. **Grep Test**
   ```bash
   # Should return only deprecated/admin references
   grep -r "/query" --include="*.py" --include="*.md" .
   ```

2. **Port Test**
   ```bash
   # Only MCP port should be open
   netstat -an | grep LISTEN | grep -E "5000|8000"
   # Expected: Only 8000 (MCP)
   ```

3. **Integration Test**
   - Start MCP server
   - Verify all tools work
   - Verify `/query` returns 410
   - Verify LangGraph uses MCP

4. **Load Test**
   - Run Phase 6 load tests
   - Verify no `/query` calls
   - Verify MCP handles all traffic

**Acceptance**:
- Grep yields only expected references
- Only MCP port is open
- All integration tests pass
- Load tests show MCP-only traffic

---

## 📋 Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Grep for `/query` yields nothing in active code | ⏳ | Grep test passes |
| Only MCP port (8000) is open | ⏳ | Port scan shows only 8000 |
| All ADRs updated to reflect MCP-only | ⏳ | Documentation review |
| `/query` endpoint returns 410 Gone | ⏳ | HTTP test |
| LangGraph uses MCP exclusively | ⏳ | Integration test |
| Design guardrails enforced | ⏳ | Code review + tests |
| No legacy proxy calls in logs | ⏳ | Log analysis |

---

## 🚀 Implementation Order

### Week 1: Audit & Planning
1. Complete audit of `/query` usage
2. Categorize all references
3. Create detailed migration plan
4. Get stakeholder approval

### Week 2: Migration
1. Migrate `app/db/client.py` to MCP
2. Update tests to use MCP
3. Mark admin tools as deprecated
4. Update documentation

### Week 3: Decommission
1. Implement `/query` deprecation (410 Gone)
2. Enforce design guardrails
3. Run validation tests
4. Monitor for legacy usage

### Week 4: Cleanup
1. Remove dead code
2. Final documentation updates
3. Acceptance testing
4. Phase 7 completion review

---

## 🎓 Architecture Alignment

### Before Phase 7
```
LangGraph ──┬──> Flask Proxy /query ──> Database
            └──> MCP JSON-RPC ──> Database
```
**Problem**: Two paths, drift risk, complexity

### After Phase 7
```
LangGraph ──> MCP JSON-RPC ──> Database
```
**Solution**: One path, no drift, simple

### Design Guardrails Enforced

1. ✅ **Proxy-only separation**: MCP is the only proxy
2. ✅ **Database abstraction**: No direct database access
3. ✅ **Read-only, safe queries**: MCP enforces SELECT-only
4. ✅ **JSON as single data format**: MCP JSON-RPC only
5. ✅ **Security & privacy**: MCP handles all validation
6. ✅ **Minimal API calls**: Paged discovery, focused prompts
7. ✅ **Caching everywhere**: Catalog + response + session
8. ✅ **Backpressure**: Rate limiting + Retry-After

---

## 🔧 Configuration Changes

### Environment Variables to Remove
```bash
# Old proxy configuration (deprecated)
PROXY_URL=http://192.168.1.35:5000
PROXY_API_KEY=...
PROXY_DEFAULT_CONN=...
```

### Environment Variables to Add
```bash
# MCP-only configuration
MCP_SERVER_URL=http://localhost:8000
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_BACKOFF_FACTOR=2.0
```

---

## 📚 Related Documentation

- **ADR-0007**: MCP Database Server Implementation
- **ADR-0010**: Dynamic ERP Assistant Complete System Architecture
- **ADR-0011**: Proxy for VPN Tunneling (to be updated)
- **PHASE_6_COMPLETE.md**: Observability & Guardrails (prerequisite)

---

## 🚨 Risks & Mitigation

### Risk 1: Breaking Existing Scripts
**Mitigation**: 
- Use 410 Gone instead of removing endpoint
- Provide clear migration guide
- Keep admin tools functional with warnings

### Risk 2: Undiscovered `/query` Usage
**Mitigation**:
- Comprehensive grep audit
- Log all deprecated endpoint calls
- Monitor for 410 responses in production

### Risk 3: Performance Regression
**Mitigation**:
- Run Phase 6 load tests
- Compare MCP vs. old proxy performance
- Optimize MCP if needed

### Risk 4: Documentation Drift
**Mitigation**:
- Update all ADRs in single PR
- Review all documentation
- Add "last updated" timestamps

---

## 🎉 Success Metrics

- **Code Cleanliness**: Zero active `/query` references
- **Architecture Simplicity**: One database access path
- **Performance**: No regression vs. old proxy
- **Reliability**: >99% uptime with MCP-only
- **Developer Experience**: Clear migration path, good docs

---

## 📖 Next Steps After Phase 7

1. **Phase 8**: Advanced Query Planning & Optimization
2. **Phase 9**: Multi-Database Support (SQL Server + PostgreSQL)
3. **Phase 10**: Production Deployment & Monitoring

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Maintained By**: Dynamic ERP Assistant Team