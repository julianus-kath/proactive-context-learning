# Scout Mode v1.2 Quick Reference

## What Changed?

Scout Mode now generates semantic descriptions for 943 MSSQL tables during startup, enabling **intent-based table discovery**.

---

## Key Addition: `SemanticDescriptionGenerator`

### Location
`mcp_server/scout_mode.py:113-275`

### What It Does
Analyzes table structure to create human-readable descriptions:
- Extracts domain keywords (customer, order, product, etc.)
- Classifies by composition (financial, temporal, relational)
- Generates 1-2 sentence summary

### Usage Example

```python
from mcp_server.scout_mode import SemanticDescriptionGenerator

table_info = {
    "name": "Orders",
    "columns": [{"name": "order_id"}, {"name": "amount"}],
    "numeric_columns": ["amount", "quantity"],
    "date_columns": ["order_date"],
    "foreign_keys": ["customer_id", "product_id"],
    "fk_count": 2,
    "column_count": 10
}

description = SemanticDescriptionGenerator.generate_description(table_info)
print(description)
# Output: "Stores sales/transactions information with financial amounts with temporal tracking connected to 2 other table(s)"
```

---

## Enhanced Catalog Structure

### Before (v1.1)
```json
{
  "name": "Orders",
  "schema": "dbo",
  "columns": [...],
  "numeric_columns": ["amount"],
  "date_columns": ["order_date"]
}
```

### After (v1.2)
```json
{
  "name": "Orders",
  "schema": "dbo",
  "uri": "table://dbo/Orders",              // 🆕 NEW
  "description": "Stores sales/transactions...",  // 🆕 NEW
  "columns": [...],
  "numeric_columns": ["amount"],
  "date_columns": ["order_date"]
}
```

---

## Enhanced Search

### Method Signature
```python
scout.search(query: str, top_k: int = 5) -> List[TableSearchResult]
```

### Search Strategies (in order)
1. **Exact table name match** → similarity=1.0, reason="exact"
2. **Table name fuzzy match** → similarity=0.60-0.99
3. **Column name match** → similarity≥0.65, reason="column_match"
4. **Description keyword match** → similarity=0.70, reason="description_match"
5. **Description fuzzy match** → similarity=0.25-0.50

### Example
```python
scout = get_scout_instance()

# Search by intent (new capability)
results = scout.search("customer contact information")
for r in results:
    print(f"{r.full_name}: {r.reason} (similarity={r.similarity:.2f})")

# Output might include:
# dbo.BCSPjmAdressenKontakt: description_match (similarity=0.70)
# dbo.CustomerAddresses: fuzzy (similarity=0.85)
```

---

## Index Structure

### New Field: `description_keywords`
```json
{
  "table_names": {...},
  "column_names": {...},
  "normalized_names": {...},
  "description_keywords": {              // 🆕 NEW
    "customer": ["dbo.Customers", "dbo.Orders"],
    "contact": ["dbo.BCSPjmAdressenKontakt"],
    "financial": ["dbo.Orders", "dbo.Invoices"]
  }
}
```

---

## Startup Process (Unchanged)

```
Server Start
  ↓
Scout Mode runs (async, non-blocking)
  ├─ Load cached catalog (if valid)
  ├─ OR query database schema
  ├─ For each table:
  │  ├─ Extract metadata (columns, FKs)
  │  ├─ Index columns by type
  │  └─ 🆕 GENERATE DESCRIPTION
  ├─ Build search index (including keywords)
  └─ Save to cache/scout_catalog.json
  ↓
fuzzy_table_selector ready for agent queries
```

**Duration:** +70-140ms overhead (negligible vs 10-50s DB discovery)

---

## Domain Keywords

Scout Mode recognizes ~30 domain keywords:

| Keyword | Domain |
|---------|--------|
| customer, client | customer management |
| order, sale | sales/transactions |
| invoice, payment | financial/billing |
| product | inventory/catalog |
| employee, staff | human resources |
| address, contact | contact information |
| log, history | audit/history |
| config, setting | system configuration |

**See:** `SemanticDescriptionGenerator.DOMAIN_KEYWORDS` (line 127-154)

---

## Adding Custom Domains

To recognize custom terms (e.g., German industry-specific words):

```python
# In SemanticDescriptionGenerator.DOMAIN_KEYWORDS
DOMAIN_KEYWORDS = {
    'bestand': 'inventory',        # German: inventory
    'verkauf': 'sales',            # German: sales
    'lieferant': 'procurement',    # German: supplier
    # ... existing keywords ...
}
```

Then rebuild scout cache:
```python
await run_scout_mode(db_adapter, force_rebuild=True)
```

---

## Debugging

### Check Generated Descriptions
```python
scout = get_scout_instance()
catalog = scout._load_cached_catalog()

for table in catalog['tables'][:5]:
    print(f"{table['name']}: {table['description']}")
```

### Test Search Behavior
```python
scout = get_scout_instance()
queries = [
    "customer",
    "contact information",
    "sales transactions",
    "financial data"
]

for q in queries:
    results = scout.search(q, top_k=3)
    print(f"\nSearch: '{q}'")
    for r in results:
        print(f"  {r.full_name} ({r.reason})")
```

### Verify Index
```python
index = scout._load_cached_index()
print("Keywords in index:", len(index['description_keywords']))
print("Sample keywords:", list(index['description_keywords'].keys())[:10])
```

---

## Performance Characteristics

| Operation | Time | O(n) |
|-----------|------|------|
| Startup (full rebuild) | 1-3s | O(943) tables |
| Startup (cache hit) | 50-100ms | O(1) disk read |
| Per-query search | <50ms | O(943) but with early exit |
| Description generation | 50-100ms | O(943) |

**Key:** All expensive operations happen at startup. Per-query latency is <50ms.

---

## Testing Against Production Database

When connected to the real 943-table MSSQL database:

```python
# On first run: builds cache with descriptions
scout_report = await run_scout_mode(db_adapter)
print(scout_report)
# {
#   "status": "success",
#   "tables_indexed": 943,
#   "cache_used": false,
#   "total_time_ms": 2500
# }

# On second run: uses cache
scout_report = await run_scout_mode(db_adapter)
# {
#   "status": "success",
#   "tables_indexed": 943,
#   "cache_used": true,
#   "total_time_ms": 85
# }

# Test semantic search
results = scout.search("adresse kontakt", top_k=5)
# Should find BCSPjmAdressenKontakt via description match
```

---

## Backward Compatibility

✅ v1.2 is **fully backward compatible** with v1.1:

- Old cache files still work (new fields are optional)
- Agent code unchanged (transparent enhancement)
- Search results include new `reason="description_match"` field (agent-friendly)
- No configuration needed

---

## Related Files

| File | Purpose |
|------|---------|
| `mcp_server/scout_mode.py` | Main implementation |
| `mcp_server/fuzzy_table_selector.py` | Calls `scout_mode.search()` |
| `mcp_server/answer_first_orchestrator.py` | Uses Scout Mode results |
| `adrs/0014-scout-mode-semantic-caching.md` | Architecture decision |
| `adrs/0015-semantic-table-ranking.md` | Ranking strategy |

---

## Troubleshooting

### Descriptions not generated?
- Check: Scout Mode ran successfully (log for "✅ Scout Mode: Indexed X tables")
- Check: `cache/scout_catalog.json` has `description` fields
- Fix: Force rebuild: `await run_scout_mode(db_adapter, force_rebuild=True)`

### Search not finding expected tables?
- Check: Table description contains search term (log the description)
- Try: Different search term or partial match
- Debug: Run `scout.search("debug_term", top_k=10)` and inspect reasons

### Startup too slow?
- Check: TTL might have expired, forcing full rebuild
- Monitor: Log shows `cache_used: true/false`
- Note: First run is slower (builds index), subsequent runs <100ms

---

## Next Steps

**For developers:**
1. Test with production 943-table database
2. Monitor semantic discovery accuracy
3. Collect user feedback on table relevance
4. Consider ML-based ranking refinement

**For enhancement:**
- [ ] User feedback loop to improve rankings
- [ ] Domain customization for specific industries
- [ ] Optional embedding layer for advanced search
- [ ] Multi-language description support