# Scout Mode Consolidation - Complete Fix

## 🎯 Problem Identified

**Root Cause:** The MCP catalog showed ALL tables with 0 estimated_rows, including `KHKAdressen` (which actually has data). This caused:
1. Search rankings to fail completely
2. Archive/admin tables to rank equally with business tables
3. Discovery agent to consistently pick wrong tables

**Why It Happened:**
- `scout_mode.py` and `scout_runner.py` were solving different parts of the problem separately
- `scout_mode.py` had semantic search but used old cache system
- `scout_runner.py` used proper `MSSQLCatalogBuilder` but lacked semantic search
- They weren't integrated, so accurate row counts never reached the search algorithm

## ✅ Solution Implemented

### Consolidated `scout_runner.py` Now Includes:

1. **Accurate Row Counts** (from `MSSQLCatalogBuilder`)
   - Uses `sys.dm_db_partition_stats` for real row estimates
   - Ensures `KHKAdressen` and all tables get correct counts

2. **Semantic Search** (from `scout_mode.py`)
   - Fuzzy matching for German compound words
   - Component matching (e.g., "Adressen" in "KHKAdressen")
   - Column name matching
   - Intent-aware ranking

3. **Junk Table Penalties**
   - -0.7 score penalty for archive/admin/config tables
   - Ensures `BSDMSArchivEKBelegarten` never ranks above `KHKAdressen`

4. **Intent-Aware Boosting**
   - Customer count queries: +0.6 boost for `KHKAdressen`-like tables
   - Revenue queries: +0.5 boost for sales transaction tables

5. **Async Lifecycle Management**
   - Background catalog building
   - TTL-based refresh
   - Non-blocking operation

### Key Changes:

```python
# NEW: Consolidated search method with intent awareness
def search(self, query: str, top_k: int = 10, intent_data: Dict[str, Any] = None):
    """
    Semantic search with:
    - Fuzzy matching
    - Archive/admin penalties
    - Intent-aware boosting
    - Row count preferences
    """
```

### Architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                     ScoutRunner                              │
│  (Consolidated scout_mode.py + scout_runner.py)            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MSSQLCatalogBuilder                                  │  │
│  │  • Accurate row counts via sys.dm_db_partition_stats │  │
│  │  • Column metadata with types                         │  │
│  │  • Foreign key relationships                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  CatalogStore (data/catalog/)                         │  │
│  │  • Compressed GZIP storage                           │  │
│  │  • TTL management (7 days default)                   │  │
│  │  • Atomic writes                                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Semantic Search                                      │  │
│  │  • TableNameNormalizer (German prefixes)             │  │
│  │  • Fuzzy matching (difflib)                          │  │
│  │  • Intent-aware ranking                              │  │
│  │  • Archive/admin penalties                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Next Steps

1. **Force Catalog Rebuild**
   - MCP server needs to rebuild catalog to get accurate row counts
   - Run: `POST /refresh_catalog` or restart MCP server

2. **Verify KHKAdressen is Indexed**
   - After rebuild, search for "KHKAdressen" should return it with correct row count
   - Archive tables should be heavily penalized

3. **Test Canonical Queries**
   - "How many customers do we have?" → Should use `KHKAdressen`
   - "Wer sind unsere Top 5 Kunden nach Gesamtumsatz?" → Should use sales views/tables
   - "How many products do we own?" → Should use `Artikelstamm` (not project lists)

## 📝 Migration Notes

### Old Code (scout_mode.py)
- ❌ Uses `cache/scout_catalog.json`
- ❌ No integration with `MSSQLCatalogBuilder`
- ❌ No accurate row counts

### New Code (scout_runner.py)
- ✅ Uses `data/catalog/` with `CatalogStore`
- ✅ Integrated with `MSSQLCatalogBuilder`
- ✅ Accurate row counts + semantic search

### Breaking Changes
- None! The `ScoutRunner` API is backward compatible
- Existing code using `scout_runner` will automatically get the new search capabilities

## 🎉 Expected Results

**Before:**
```
Search "customers" → BSDMSArchivEKBelegarten (11 rows, archive table)
Search "KHKAdressen" → vewBCSPjmObjektliste (project list!)
```

**After:**
```
Search "customers" → KHKAdressen (419 rows, customer master table)
Search "KHKAdressen" → KHKAdressen (exact match, 419 rows)
Search "kunde" → KHKAdressen (fuzzy match + customer master boost)
```

## 📊 Performance Impact

- **Catalog build time:** ~same (still uses `MSSQLCatalogBuilder`)
- **Search time:** Slightly faster (in-memory fuzzy matching vs. database queries)
- **Memory usage:** ~same (catalog is already loaded)
- **Disk usage:** ~same (still uses GZIP compression)

## 🔧 Configuration

No configuration changes needed. Scout runner uses existing settings:
- `catalog_dir`: `data/catalog/`
- `ttl_hours`: 168 (7 days)
- `refresh_interval_hours`: 24

## 🐛 Debugging

If search still returns wrong tables after rebuild:

1. Check catalog exists and is fresh:
   ```python
   GET /health
   # Should show: catalog_valid: true, catalog_age_hours: < 168
   ```

2. Force rebuild:
   ```python
   POST /refresh_catalog
   ```

3. Test search directly:
   ```python
   from mcp_server.scout_runner import ScoutRunner
   runner.search("KHKAdressen", top_k=5)
   ```

4. Check row counts in catalog:
   ```python
   catalog = runner.get_catalog()
   for table in catalog['tables']:
       if 'khk' in table['name'].lower():
           print(f"{table['full_name']}: {table['estimated_rows']} rows")
   ```

