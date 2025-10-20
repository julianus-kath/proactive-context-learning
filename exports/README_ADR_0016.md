# ADR-0016 Architecture Exports

## 📋 Overview

This directory contains exported versions of **ADR-0016: Phase 7+ Complete Architecture with Scout Mode and Semantic Ranking**.

ADR-0016 documents the complete end-to-end architecture incorporating:
- **Scout Mode**: Semantic caching for 200-1000x faster schema discovery
- **MCP-Only Data Access**: Single unified interface eliminating dual code paths
- **Semantic Table Ranking**: Multi-dimensional scoring for autonomous table selection
- **Answer-First Pipeline**: Sub-second query execution before interactive clarification
- **Windows MCP Server**: Remote database access via JSON-RPC on Port 8000

---

## 📁 Contents

### 📄 Main Documents
- **`ADR-0016-Architecture.html`** - Interactive HTML version with all diagrams
- **`../adrs/0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md`** - Original Markdown source

### 🖼️ Architecture Diagrams (`diagrams/adr_0016/` folder)

12 high-resolution architecture diagrams:

1. **`01_system_overview.png`** - High-level system with all major components and data flow
2. **`02_scout_mode_lifecycle.png`** - Scout Mode startup discovery and cache lifecycle
3. **`03_answer_first_pipeline.png`** - Complete answer-first query pipeline
4. **`04_mcp_data_access.png`** - Unified MCP-only data access layer
5. **`05_complete_query_flow.png`** - End-to-end query execution sequence
6. **`06_windows_mcp_server.png`** - Windows MCP Server on Port 8000 (JSON-RPC)
7. **`07_component_responsibilities.png`** - Component role breakdown
8. **`08_scout_cache_lifecycle.png`** - Cache states and TTL management
9. **`09_performance_characteristics.png`** - Phase 6 vs 7 vs 7.1 comparison
10. **`10_error_handling.png`** - Error detection and recovery strategies
11. **`11_observability_logging.png`** - Debug logging and observability system
12. **`12_deployment_architecture.png`** - Dev and production deployment

---

## 🎯 Key Improvements

### Performance
| Metric | Phase 6 | Phase 7 | Phase 7.1 | Improvement |
|--------|---------|---------|-----------|-------------|
| **Schema Discovery** | 10-50s | 10-50s | 50ms | **200-1000x** ✓ |
| **Table Ranking** | N/A | 2-5s | 50-100ms | **20-100x** ✓ |
| **Total Query Time** | 17-65s | 16-62s | **<500ms** | **40-130x** ✓ |

### Architecture
- **Single Interface**: MCP-only eliminates dual code paths
- **Autonomous Execution**: Answer-first enables sub-second response
- **Cache-First**: Scout Mode provides O(1) metadata access
- **Multi-Dimensional Scoring**: Semantic ranking handles diverse queries
- **Secure Production Access**: Windows proxy with VPN tunneling

---

## 📚 Architecture Components

### 1. Scout Mode (ADR-0014)
**Problem**: Schema discovery was bottleneck (10-50s per query)

**Solution**: Pre-compute and cache semantic metadata
- 943 tables analyzed on startup
- Metadata cached: columns, types, FK count, numeric/date fields
- 7-day TTL with auto-refresh
- **Result**: 50ms instead of 10-50s (200-1000x faster)

### 2. MCP-Only Data Access (ADR-0012)
**Problem**: Dual interfaces (direct adapter + MCP) caused code drift

**Solution**: Single unified MCP Server interface
- All database access flows through MCP Server
- JSON-RPC 2.0 protocol
- Centralized safety guardrails
- Consistent error handling

### 3. Semantic Table Ranking (ADR-0015)
**Problem**: Binary decisions (is this table relevant?) not accurate

**Solution**: Multi-dimensional scoring system
```
Score = Entity_Match (0-1.0)
      + Type_Compatibility (0-0.5)
      + Fuzzy_Match (0-0.4)
      + FK_Connectivity (0-0.1)
      + Table_Size (0-0.05)
      
Max: 3.05 → capped at 1.0 (normalized confidence)
```

### 4. Answer-First Pipeline (Phase 7)
**Problem**: Interactive clarification required user input for every query

**Solution**: Autonomous execution before confirmation
1. Parse intent from natural language
2. Load Scout cache (50ms)
3. Rank candidate tables (50-100ms)
4. Generate SQL blueprint
5. Execute query (150ms)
6. Format response for user

Result: **Sub-second end-to-end execution**

### 5. Windows Proxy (VPN Access)
**Architecture**:
```
Mac (LangGraph) 
    ↓ HTTPS/TLS
Proxy (Windows) 
    ↓ VPN Tunnel
Production SQL Server (ERP)
```

**Security**:
- API key authentication
- SELECT-only enforcement
- Row/time limits
- SQL injection prevention
- Sensitive data redaction

---

## 🔄 System Flow

### User Query to Response (Phase 7.1)

```
1. User types: "Show recent invoices"
   ↓
2. Intent Parser extracts: entity="invoices", intent=QUERY
   ↓
3. Scout Cache loads in 50ms (943 tables pre-computed)
   ↓
4. Semantic Ranker scores all tables, selects top 3:
   - dbo.InvoiceHeader (1.0)
   - dbo.InvoiceLines (0.95)
   - dbo.InvoiceStatus (0.7)
   ↓
5. Query Blueprint generates template SQL
   ↓
6. MCP Server describes selected tables (schema discovery)
   ↓
7. LLM generates concrete SQL:
   SELECT TOP 10 * FROM dbo.InvoiceHeader
   ORDER BY created_at DESC
   ↓
8. MCP Server executes with guardrails:
   - Read-only check ✓
   - Row limit (10) ✓
   - Timeout (30s) ✓
   ↓
9. LLM formats response in natural language:
   "Here are the 10 most recent invoices..."
   ↓
10. Response streamed to user via WebSocket

Total time: <500ms
```

---

## 💾 Scout Mode Cache

### Cache Contents
```json
{
  "version": "1.0",
  "generated_at": "2025-01-15T14:23:45Z",
  "ttl_days": 7,
  "next_refresh": "2025-01-22T14:23:45Z",
  "tables": {
    "dbo.Orders": {
      "name": "Orders",
      "schema": "dbo",
      "full_name": "dbo.Orders",
      "type": "TABLE",
      "estimated_rows": 500000,
      "column_count": 12,
      "numeric_columns": ["amount", "quantity", "unit_price"],
      "date_columns": ["order_date", "created_at"],
      "text_columns": ["customer_name"],
      "fk_count": 3,
      "primary_keys": ["order_id"],
      "foreign_keys": ["customer_id", "product_id"]
    },
    ...943 more tables
  }
}
```

### Cache Lifecycle
- **Startup**: Scout Mode runs async, discovers all tables
- **Runtime**: O(1) cache loads, ~50ms
- **TTL Check**: Every request checks 7-day validity
- **Refresh**: Auto-refresh on expiration or manual trigger
- **Fallback**: If cache unavailable, query DB (slower but works)

---

## 🛠️ Using the Diagrams

### For Presentations
```bash
# Open in any image viewer
open exports/diagrams/adr_0016/*.png

# Or browse HTML version
open exports/ADR-0016-Architecture.html
```

### For Documentation
- **Use individual PNG files** for technical documentation
- **Use HTML version** for interactive viewing
- **Reference Markdown** for detailed descriptions

### For Integration
```markdown
# System Architecture

![System Overview](exports/diagrams/adr_0016/01_system_overview.png)

See ADR-0016 for complete architecture details.
```

---

## 📊 Diagram Details

### 1. System Overview
Shows all layers:
- User Interface (Web UI)
- API & Orchestration (LangGraph Service)
- Scout Mode Cache
- Answer-First Pipeline
- MCP Data Access Layer
- Database Connectivity

### 2. Scout Mode Lifecycle
- Startup phase discovery
- Runtime cache loading
- TTL checking
- Cache refresh on expiration

### 3. Answer-First Pipeline
- Intent extraction
- Semantic ranking
- Query blueprint generation
- Safe execution
- Response formatting

### 4. MCP Data Access
- MCPClient unified interface
- JSON-RPC communication
- Tool handlers
- Database manager

### 5. Query Execution Flow
- Complete sequence diagram
- Timing annotations
- Error handling

### 6. Windows Proxy Architecture
- VPN tunneling
- API authentication
- Query validation
- Security guardrails

### 7. Component Responsibilities
- Clear role definition
- File locations
- Interaction paths

### 8. Cache Lifecycle
- State transitions
- TTL management
- Fallback behavior

### 9. Performance Comparison
- Phase-by-phase timing
- Bottleneck identification
- Improvement metrics

### 10. Error Handling
- Failure modes
- Detection strategies
- Recovery actions

### 11. Observability
- Log collection points
- Storage mechanisms
- Real-time streaming

### 12. Deployment
- Development environment
- Production containers
- Data source connections

---

## 🔧 Regenerating Exports

### Prerequisites
```bash
# Install mermaid-cli for PNG export
npm install -g @mermaid-js/mermaid-cli

# Or using Homebrew
brew install mermaid-cli
```

### Export Diagrams
```bash
# Export all formats (PNG + HTML)
python3 scripts/export_adr_0016.py --format=all

# Export PNG only
python3 scripts/export_adr_0016.py --format=png

# Export HTML only
python3 scripts/export_adr_0016.py --format=html
```

### Output Locations
- **PNG Diagrams**: `exports/diagrams/adr_0016/`
- **HTML**: `exports/ADR-0016-Architecture.html`
- **Log**: `exports/export_log.txt`

---

## 📋 File Structure

```
exports/
├── README.md (ADR-0010 exports)
├── README_ADR_0016.md (this file)
├── ADR-0010-Architecture.html (legacy)
├── ADR-0016-Architecture.html (new)
├── export_log.txt
└── diagrams/
    ├── proxy_architecture/ (legacy)
    └── adr_0016/
        ├── 01_system_overview.png
        ├── 02_scout_mode_lifecycle.png
        ├── ...
        └── 12_deployment_architecture.png

adrs/
├── 0010-dynamic-erp-assistant-complete-system-architecture.md (legacy)
├── 0012-mcp-only-architecture-migration.md
├── 0014-scout-mode-semantic-caching.md
├── 0015-semantic-table-ranking.md
└── 0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md (new)

scripts/
├── export_adr_to_pdf.py (legacy)
└── export_adr_0016.py (new)
```

---

## 🎓 Learning Path

1. **Start with**: System Overview (Diagram 1)
   - Understand major components
   - See data flow

2. **Then learn**: Scout Mode (Diagrams 2, 8)
   - Understand caching strategy
   - See performance improvement

3. **Understand**: Answer-First Pipeline (Diagrams 3, 5)
   - Complete query flow
   - Autonomous execution

4. **Explore**: MCP Architecture (Diagram 4)
   - Unified data access
   - Protocol details

5. **Deep dive**: Windows Proxy (Diagram 6)
   - Production access
   - Security model

6. **Reference**: Component responsibilities (Diagram 7)
   - Who does what
   - File locations

7. **Debug**: Observability (Diagram 11)
   - Logging points
   - Monitoring

---

## 📞 Questions & Support

### Common Questions

**Q: Why Scout Mode instead of real-time discovery?**
A: Scout Mode trades freshness (7-day TTL) for speed (50ms vs 10-50s). The 200-1000x improvement enables real-time query execution.

**Q: How does semantic ranking work?**
A: Multi-dimensional scoring combining:
- Entity matching (exact/fuzzy)
- Type compatibility (numeric/date fields for operations)
- Connectivity (FK relationships)
- Table size (central tables typically larger)

**Q: What if Scout cache is stale?**
A: TTL checked on every request. If >7 days, auto-refresh in background. Fallback queries information_schema if cache unavailable.

**Q: How is production data accessed securely?**
A: Windows proxy with:
- VPN tunneling (encrypted connection)
- API key authentication
- SELECT-only enforcement
- Row/time limits
- SQL injection prevention

### For More Information
- Read: `adrs/0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md`
- Browse: `exports/ADR-0016-Architecture.html`
- Review: Related ADRs (0012, 0014, 0015)

---

## 📈 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-15 | Initial ADR-0016 export with 12 diagrams |

---

**Generated**: 2025-01-15  
**Source**: ADR-0016 Phase 7+ Complete Architecture  
**Export Script**: `scripts/export_adr_0016.py`  
**Status**: Phase 7+ Active Architecture