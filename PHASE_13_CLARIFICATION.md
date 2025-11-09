# Phase 13: What It Should Be

**Status:** PROPOSED (not started yet)

---

## 📋 Context: Why We Need Phase 13

After Phase 12 (Scout Product Boosting), we have **strong table discovery** for:
- ✅ Product count queries (score 1.0)
- ✅ Top-selling queries (score 1.0)
- ✅ Sales total queries (score 1.0)

**But there are still gaps:**
- 🟡 Composite filter queries: "Show me best-selling products in Electronics category" (needs category filter detection)
- 🟡 Temporal queries: "Products sold in the last 30 days" (needs date filter detection)
- 🟡 Property queries: "Products with more than 100 units sold" (needs aggregation filter detection)

These require **better intent parsing** and **more specific Scout boosts**.

---

## 🎯 Phase 13 Options

### Option A: Intent Parser Improvements ⭐ RECOMMENDED
**Goal:** Extract composite intents more accurately so Scout can apply compound boosts.

**What to improve:**
```
User: "What are the top 3 best-selling products in Electronics category?"

Current Intent Parser might extract:
  ❌ operations: ["top", "best"]
  ❌ entities: ["product", "category"]
  ❌ Missing: the relationship (products IN category, not products AND category)

Improved Intent Parser should extract:
  ✅ operations: ["top", "best", "rank"]
  ✅ entities: ["product"]
  ✅ filters: {category: "Electronics"}
  ✅ relationships: [{"entity": "product", "filtered_by": "category"}]
```

**Scope:**
1. Parse compound filter clauses ("in", "by", "for", "from", "during")
2. Detect aggregation operators ("sum", "count", "average", "min", "max")
3. Extract temporal constraints ("last 30 days", "this month", "2024")
4. Identify categorical filters ("Electronics", "premium", "inactive")

**Impact:**
- Scout can apply +0.3 boost for "category + product" → discovers MAKategorien + MAArtikel
- Scout can apply +0.2 boost for "date filter" → discovers date/time columns
- Phase 11 validation errors drop further (they now indicate real logic bugs, not discovery issues)

---

### Option B: Column Validation ⚠️ LOWER PRIORITY
**Goal:** Verify that SQL references valid columns in discovered tables.

**What to check:**
```
SQL: SELECT TOP 10 a.product_name, SUM(v.sales_amount) FROM dbo.MAArtikel a ...
     Column Check: Does dbo.MAArtikel have columns product_name?
                   Is sales_amount numeric (can be SUMmed)?
```

**Scope:**
1. Extract all columns from SQL (`SELECT a.col1, b.col2 ...`)
2. Verify each column exists in the discovered table
3. Check type compatibility (SUM on numeric, string ops on varchar, etc.)
4. Detect aggregate function errors

**Why it's lower priority:**
- Phase 11 already catches unknown **tables**
- Column errors are rarer (SQL tends to be well-formed if tables are right)
- Intent parsing improvements have more impact on accuracy
- Column validation can be Phase 14

---

## 🏆 Our Recommendation: Phase 13 = Intent Parser Improvements

### Why?
1. **Direct impact:** Better intents → better Scout signals → fewer hallucinations
2. **Addresses gaps:** Can handle filter/temporal/aggregation queries
3. **Synergy with Phase 12:** Strong boosts + precise intents = very high accuracy
4. **Evolutionary:** Natural extension of current intent extraction

### Scope for Phase 13:
```python
# Current (Phase 12)
intent = {
    "operations": ["top"],
    "entities": ["product", "sales"]
}

# After Phase 13
intent = {
    "operations": ["top", "rank"],
    "entities": ["product"],
    "filters": {
        "category": "electronics",
        "date_range": "last_30_days"
    },
    "relationships": [
        {"subject": "product", "filtered_by": "category"},
        {"subject": "product", "temporal_filter": "date_range"}
    ]
}
```

### Phase 13 Tasks:
1. **Parser:** Add composite filter detection (lines starting with "in", "by", "for", "from", "during")
2. **Filter extraction:** Parse "category: Electronics" → `{category: "electronics"}`
3. **Relationship mapping:** "Products in category" → boost both product + category tables
4. **Scout boost:** Add +0.3 for category filters, +0.2 for temporal filters
5. **Test:** Create test_phase13_intent_parser_improvements.py with 5+ scenarios
6. **Observability:** Log extracted filters for debugging

---

## 📊 Phase 13 Effort Estimate

| Task | Effort | Impact |
|------|--------|--------|
| Composite filter detection | 4 hours | High (handles "in category", "by date", etc.) |
| Filter extraction logic | 3 hours | High (enables semantic matching) |
| Scout boost integration | 2 hours | Medium (reuses Phase 12 pattern) |
| Tests | 3 hours | High (verify all query patterns) |
| Documentation | 1 hour | Medium (update READMEs, create ADR if major change) |
| **TOTAL** | **~13 hours** | **Very High (50-70% accuracy improvement estimated)** |

---

## 🗺️ Full Roadmap (Updated)

```
Phase 11 ✅ DONE: SQL Table Validation Gate
  → Catches hallucinated table names
  → Clear error messages

Phase 12 ✅ DONE: Scout Product Query Boosting
  → +0.6 for product count
  → +0.5 for top-selling (product+sales combo)
  → Score improvement: 0.70 → 1.0

Phase 13 📌 PROPOSED: Intent Parser Improvements
  → Extract composite filter intents
  → Relationship mapping (product IN category)
  → Phase 11 errors drop 70%+

Phase 14 🗓️ FUTURE: Column Validation & Type Checking
  → Verify columns exist in tables
  → Check aggregation type compatibility
  → Redundant if Phase 13 succeeds, but valuable for robustness

Phase 15 🗓️ FUTURE: Performance & Observability
  → Metrics on error rates by query type
  → Latency tracking
  → Production monitoring dashboard
```

---

## 🎬 Decision: Which Phase 13?

**Choose One:**

**A) Intent Parser Improvements** (RECOMMENDED) ✅
- More impactful (handles more query patterns)
- Directly reduces Phase 11 errors
- Builds on existing intent extraction code
- Estimated 13 hours

**B) Column Validation** (LOWER PRIORITY) ⚠️
- Safer (validates end result, not upstream)
- Less frequent (rarer errors)
- Easier to defer to Phase 14
- Estimated 8 hours, but lower ROI

---

**Recommendation:** Go with **Option A (Intent Parser)** in Phase 13.

This keeps momentum, directly improves accuracy, and sets up Phase 14 (column validation) as a hardening phase rather than a critical feature.

---

*See PHASE_12_VERIFICATION_COMPLETE.md for Phase 12 results and PHASE_11_NO_DATA_FIX_COMPLETE.md for context.*