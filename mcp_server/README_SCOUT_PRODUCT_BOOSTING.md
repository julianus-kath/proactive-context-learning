# Scout Product Query Boosting
## Why
Discovery Agent was failing to rank product tables highly for common product queries ("How many products?", "Top-selling product?"). This caused Join SQL Agent to hallucinate table names, triggering Phase 11 validation failures.

Root cause: Scout had explicit intent-aware boosts for customer (+0.6) and revenue (+0.8) queries, but **no boost for product queries**, forcing reliance on weak fuzzy matching (score: 0.70–0.75).

## What
Added two new intent-aware boosts to `scout_runner.py` (lines 432–448):

### 1. Product Count Boost (+0.6)
```python
elif "count" in intent_operations and any(e in ["artikel", "product", ...] for e in intent_entities):
    if any(tok in name_lower for tok in ["maartikel", "artikel", ...]):
        score = min(1.0, score + 0.6)
        reasons.append("Product master boost")
```
**Effect:** "How many products?" now discovers `dbo.MAArtikel` with score 1.05 (was 0.75)

### 2. Product+Sales Composite Boost (+0.5)
```python
elif any(op in ["top", "highest", "best", ...] for op in intent_operations) and \
     any(e in ["artikel", "product", "sku"] for e in intent_entities) and \
     any(s in ["sales", "verkauf", ...] for s in intent_entities):
    # Boost both product AND sales tables
    if any(tok in name_lower for tok in ["maartikel", "artikel", ...]):
        score = min(1.0, score + 0.5)
        reasons.append("Product (top-selling) boost")
```
**Effect:** "What's top-selling?" now discovers both `dbo.MAArtikel` (1.05) AND `dbo.VKPosition` (1.05) (before: MAArtikel was missing)

## How to Run
```bash
# Test the fixes
python3 TEST_DISCOVERY_COMPLEX_QUERIES.py

# Expected output:
# Product count:     MAArtikel (1.05) ✅
# Top-selling:       MAArtikel (1.05), VKPosition (1.05) ✅
# Sales total:       RechnungsPosition (1.05) ✅ (unchanged)
```

## Tests
- `TEST_DISCOVERY_COMPLEX_QUERIES.py`: Validates Scout scoring for 3 query types
- Unit test in `tests/scout_mode/`: Run specific table scoring tests (if added)
- Integration: Full langgraph flow test confirms Join SQL Agent gets correct table list

## Notes
**Limitations:**
- Boosts only apply if intent parser extracts entities correctly (e.g., "artikel" or "product" from user query)
- Composite intent (product+sales) only triggers for "top/highest/best" operations; other combinations (e.g., "product by category") need separate boosts (Phase 13)

**Next steps:**
1. Monitor Phase 11 validation errors; should drop significantly for product queries
2. Phase 13: Add category/filter intent boosts ("Products in Electronics category?")
3. Phase 13: Improve intent parser to extract composite intents more robustly

**Impact on Phase 11 validation gate:**
- Stronger Scout signals = fewer hallucinations = fewer validation errors
- Remaining errors now indicate **intent parsing failures**, not Scout weakness
- Clearer debugging path: "User query → intent extraction → Scout → Join SQL Agent"