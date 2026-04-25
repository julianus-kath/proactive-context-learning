# ADR-0014: Scout Mode - Semantic Caching for Table Discovery
**Author**: Julianus Kath


**Date**: 2025-10-20
**Status**: ACCEPTED  
**Context:** Phase 7.1 Enhancement  

## Problem

The original answer-first pipeline (Phase 7) required querying the database to discover all available tables on each request, even though the schema changes infrequently. This created unnecessary latency:

- **Database query time:** 10-50 seconds to scan 943 tables
- **Discovery bottleneck:** Single largest bottleneck in query pipeline
- **Scalability issue:** Linear degradation as table count grows
- **Cache invalidation:** No automatic invalidation when schema changed

## Decision

Implement **Scout Mode**: An autonomous startup discovery system that:

1. **Indexes on startup** - Asynchronously scans entire database schema
2. **Caches semantic metadata** - Stores pre-computed column type information
3. **Serves from disk** - O(1) cache loads instead of O(n) database queries
4. **Respects TTL** - 7-day cache validity with automatic refresh

### Architecture

```
Server Startup
    ↓
Scout Mode Run (async, non-blocking)
    ├─ Query: SELECT * FROM information_schema
    ├─ For each table:
    │   ├─ Extract columns and their types
    │   ├─ Index numeric columns (for AGGREGATE)
    │   ├─ Index date columns (for TREND)
    │   ├─ Count foreign keys (for JOIN analysis)
    │   └─ Store normalized names (for fuzzy matching)
    ├─ Build full catalog with semantic metadata
    └─ Serialize to disk (cache/scout_catalog.json)

Subsequent Requests
    ↓
Load Catalog (50ms from disk)
    ├─ Check TTL (7 days)
    ├─ If valid: use cached version
    └─ If expired: re-run Scout Mode
```

### Semantic Metadata Cached

For each table, Scout Mode pre-computes and caches:

```json
{
  "name": "Orders",
  "schema": "dbo",
  "full_name": "dbo.Orders",
  "type": "TABLE",
  "estimated_rows": 245000,
  "column_count": 12,
  "numeric_columns": ["amount", "quantity", "unit_price", "total"],
  "date_columns": ["order_date", "delivery_date", "created_at"],
  "text_columns": ["customer_name", "product_description", "notes"],
  "fk_count": 3,
  "primary_keys": ["order_id"],
  "foreign_keys": ["customer_id", "product_id", "warehouse_id"]
}
```

## Benefits

| Benefit | Impact |
|---------|--------|
| **Performance** | ~50ms cache load vs 10-50s DB query (200-1000x faster) |
| **Scalability** | O(1) lookup regardless of table count |
| **Autonomy** | Enables answer-first to work without discovery bottleneck |
| **Observability** | Pre-computed metadata for debugging table selection |
| **Reliability** | Works even if database temporarily unavailable |
| **Caching** | Reduces unnecessary DB connections on startup |

## Implementation Details

### Phase 7.1 Changes to Scout Mode

**New Metadata Fields:**
```python
table_info = {
    "numeric_columns": [],      # Lists of column names by type
    "date_columns": [],
    "text_columns": [],
    "fk_count": 0              # Pre-counted foreign key references
}
```

**Type Detection Logic:**
- Numeric: `int`, `float`, `decimal`, `numeric`, `bigint`, `money`
- Date: `date`, `datetime`, `datetime2`, `timestamp`
- Text: `varchar`, `text`, `nvarchar`, `char`

**Cache Strategy:**
- File path: `cache/scout_catalog.json` (version 1.1)
- TTL: 7 days (configurable)
- Fallback: On-demand discovery if cache unavailable

### Integration with Table Ranker

Table Ranker now uses Scout Mode metadata directly:

```python
# Before (Phase 7): Queried database during ranking
numeric_cols = db_adapter.get_table(schema, name).columns
numeric_count = sum(1 for c in numeric_cols if is_numeric(c))

# After (Phase 7.1): Uses cached metadata
numeric_cols = table.get('numeric_columns', [])
numeric_count = len(numeric_cols)  # O(1) dict access
```

### Integration with Answer-first Orchestrator

Orchestrator now loads tables from Scout Mode:

```python
# Before (Phase 7): Discovered via DiscoveryTools
discovery_result = await discovery_tools.list_tables()

# After (Phase 7.1): Loads from cache
scout_catalog = scout_mode._load_cached_catalog()
all_tables = scout_catalog.get("tables", [])
```

## Alternatives Considered

### 1. In-Memory Cache
- Pros: Fast access, no disk I/O
- Cons: Lost on restart, duplicated per process, no multi-process sharing
- **Rejected**: TTL violations, stateless scaling issues

### 2. External Cache (Redis)
- Pros: Shared, persistent, TTL-aware
- Cons: Added infrastructure, network latency, operational overhead
- **Rejected**: Over-engineering for this problem

### 3. Incremental Indexing
- Pros: Only indexes changed tables
- Cons: Complex change detection, schema tracking overhead
- **Rejected**: 7-day TTL simpler and sufficient

### 4. No Caching (Always Query)
- Pros: Always fresh, simple implementation
- Cons: 10-50s startup delay, scaling issues, poor UX
- **Rejected**: Unacceptable performance

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Stale schema cache | Medium | Wrong table selection | 7-day TTL, manual refresh via API |
| Cache file corruption | Low | Pipeline failure | Fallback to discovery_tools |
| Large catalog size | Low | Slow disk I/O | JSON compression, async loading |
| Multi-process conflicts | Medium | Cache inconsistency | Timestamp-based TTL checks |

## Success Metrics

- ✅ Scout Mode builds cache on first startup (<2 minutes)
- ✅ Subsequent startups: <100ms overhead from Scout Mode
- ✅ Table ranking: 943 tables ranked in <50ms
- ✅ Answer-first response: <500ms end-to-end
- ✅ Cache hit rate: >95% (7-day TTL)

## Future Enhancements

1. **Incremental Updates** - Track schema changes via DDL triggers
2. **Distributed Cache** - Redis integration for multi-instance deployments
3. **Query-Specific Index** - Additional caching of common entity/table pairs
4. **Bloom Filters** - Probabilistic structures for negative lookups
5. **Compression** - GZIP JSON for network transfer efficiency

## References

- ADR 0009: Context-Aware ERP Assistant Query Processing
- ADR 0010: Dynamic ERP Assistant Architecture
- Phase 7 Answer-first Implementation Guide
- Phase 7.1 Scout Mode Integration

---

## Data Structures

This section documents the complete data structure hierarchy used by Scout Mode, showing how data flows from the catalog build through to the Discovery Agent.

### Level 1: Raw Catalog (Built by MSSQLCatalogBuilder)

Stored in `data/catalog/catalog.json.gz` as compressed JSON:

```json
{
    "metadata": {
        "database_type": "mssql",
        "build_timestamp": "2025-11-05T19:15:42.123456",
        "tables_count": 587,
        "views_count": 356,
        "relationships_count": 142
    },
    
    "tables": {
        "dbo.KHKAdressen": {
            "schema": "dbo",
            "name": "KHKAdressen",
            "full_name": "dbo.KHKAdressen",
            "type": "table",
            "estimated_rows": 419,
            "column_count": 34,
            "fk_count": 2,
            "columns": [
                {
                    "name": "Adresse",
                    "type": "int",
                    "nullable": false,
                    "max_length": 4,
                    "is_primary_key": true,
                    "is_foreign_key": false,
                    "role_hints": ["id-like", "key"]
                }
            ],
            "last_updated": "2025-11-05T19:15:42.123456"
        }
    },
    
    "views": {
        "dbo.vwKHK_AC_Auftragscockpit_VkAuftraege": {
            "schema": "dbo",
            "name": "vwKHK_AC_Auftragscockpit_VkAuftraege",
            "full_name": "dbo.vwKHK_AC_Auftragscockpit_VkAuftraege",
            "type": "view",
            "estimated_rows": 1255,
            "column_count": 28,
            "dependencies": [
                "dbo.KHKVKBelege",
                "dbo.KHKAdressen",
                "dbo.KHKVKPositionen"
            ],
            "columns": [],
            "last_updated": "2025-11-05T19:16:12.789012"
        }
    },
    
    "relationships": [
        {
            "constraint_name": "FK_KHKVKPositionen_VKBeleg",
            "from_table": "dbo.KHKVKPositionen",
            "from_column": "VKBeleg",
            "to_table": "dbo.KHKVKBelege",
            "to_column": "VKBeleg",
            "type": "foreign_key"
        }
    ]
}
```

**Size:** ~600KB compressed, ~5MB uncompressed

### Level 2: Scout Search Result (from ScoutRunner.search())

Python Type: `List[Dict[str, Any]]`

```python
[
    {
        "full_name": "dbo.KHKAdressen",
        "name": "KHKAdressen",
        "schema": "dbo",
        "type": "BASE TABLE",
        "estimated_rows": 419,
        "column_count": 34,
        "relevance_score": 0.95,
        "reasons": [
            "Fuzzy match: kunde → KHKAdressen (score 0.45)",
            "Customer master boost (+0.60)",
            "Row count bonus (+0.05 for 419 rows)"
        ],
        "columns": [
            "Adresse",
            "Mandant",
            "Kategorie"
        ]
    }
]
```

### Level 3: MCP Server Wrapper (from tools.py)

Python Type: `Dict[str, Any]`

The MCP server wraps Scout results in a JSON-RPC envelope:

```python
{
    "ok": true,
    "data": {
        "results": []  # Scout search results here
    },
    "page_info": {
        "page": 1,
        "page_size": 25,
        "total_items": 3,
        "total_pages": 1,
        "has_next": false,
        "has_prev": false
    },
    "execution_time_ms": 12.5,
    "cached": true,
    "source": "scout_catalog"
}
```

Plus human-readable text summary with emoji markers and JSON footer.

### Level 4: MCP Client Response (to Discovery Agent)

Python Type: `List[Dict[str, str]]`

```python
[
    {
        "type": "text",
        "text": "🔍 Search Results...\n\n📊 Full response (JSON):\n{...}"
    }
]
```

### Level 5: Discovery Agent Parsed (after _parse_search_result)

Python Type: `List[Dict[str, Union[str, float, bool, int]]]`

```python
[
    {
        "table_name": "KHKAdressen",
        "full_name": "dbo.KHKAdressen",
        "relevance_score": 0.95,
        "is_view": false,
        "role_coverage": 0.0,
        "has_rows": true,
        "estimated_rows": 419,
        "column_count": 34
    }
]
```

### Level 6: Discovery Agent Final Output (to Orchestrator)

Multiple optimized structures in the state:

```python
{
    "relevant_tables": [
        "KHKAdressen",
        "KHKAdressenTelefon",
        "KHKArtikelKunden"
    ],
    
    "candidate_views": [
        {
            "table_name": "vwKHK_AC_Auftragscockpit_VkAuftraege",
            "full_name": "dbo.vwKHK_AC_Auftragscockpit_VkAuftraege",
            "relevance_score": 0.75,
            "is_view": true,
            "role_coverage": 0.82,
            "has_rows": true,
            "estimated_rows": 1255,
            "column_count": 28
        }
    ],
    
    "schema_snippet": "KHKAdressen: Adresse (int), Mandant (smallint)...",
    
    "column_index": {
        "dbo.KHKAdressen": [
            "Adresse",
            "Mandant",
            "Kategorie"
        ]
    },
    
    "session_described_tables": {
        "KHKAdressen": {
            "schema": "dbo",
            "name": "KHKAdressen",
            "full_name": "dbo.KHKAdressen",
            "type": "BASE TABLE",
            "estimated_rows": 419,
            "columns": []
        }
    }
}
```

**Python Types:**
- `relevant_tables`: `List[str]`
- `candidate_views`: `List[Dict[str, Any]]`
- `schema_snippet`: `str`
- `column_index`: `Dict[str, List[str]]`
- `session_described_tables`: `Dict[str, Dict[str, Any]]`

### Data Flow Summary

```
Raw Catalog (disk)
    ↓ ScoutRunner loads & indexes
Scout Search Result (scored list)
    ↓ MCP Server wraps
JSON-RPC Envelope (paginated response)
    ↓ MCP Client extracts
Text + JSON Content (list wrapper)
    ↓ Discovery Agent parses
Normalized Dicts (unified format)
    ↓ Discovery Agent transforms
Multiple Outputs (optimized for consumers)
    ↓ Used by
Join Planner, SQL Generator, Answer Formatter
```

### Key Design Decisions

1. **Catalog on Disk**: Nested dict with metadata/tables/views/relationships for complete schema representation
2. **Scout Search**: Flat list with scores and reasons for transparency and debugging
3. **MCP Wrapper**: JSON-RPC envelope for protocol compliance and pagination
4. **Discovery Output**: Multiple structures optimized for different consumers (lists for quick reference, dicts for metadata, indexes for lookups)
5. **Column Details**: Full metadata cached in `session_described_tables`, but only column names in `column_index` for performance

This transformation from nested catalog → flat search results → normalized dicts → multiple outputs ensures each agent gets exactly what it needs with minimal overhead.

---

## Decision Record

**Decision:** Implement Scout Mode as described above.

**Rationale:** Semantic caching provides 200-1000x performance improvement for table discovery with minimal complexity and infrastructure changes.

**Approved By:** Architecture Team  
**Implementation Date:** Phase 7.1