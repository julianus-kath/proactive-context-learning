# ADR 0014: Scout Mode - Semantic Caching for Table Discovery

**Date:** 2024  
**Status:** ACCEPTED  
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

## Decision Record

**Decision:** Implement Scout Mode as described above.

**Rationale:** Semantic caching provides 200-1000x performance improvement for table discovery with minimal complexity and infrastructure changes.

**Approved By:** Architecture Team  
**Implementation Date:** Phase 7.1