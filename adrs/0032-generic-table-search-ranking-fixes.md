# ADR 0032: Generic Table Search Ranking Fixes

**Date:** 2026-01-18
**Status:** ACCEPTED
**Context:** Bug fix for Scout Mode table search

## Problem

The SQL agent failed on basic queries because **table search returned wrong tables**:

**Example from logs:**
- Query: "Umsatz Kunden Bestellungen" (Revenue Customers Orders)
- Expected: `KHKStatVKKunden` (customer sales stats)
- Actual: `BSEinstellungen` (settings table) - Score 0.635

### Root Causes Identified

1. **No Query Decomposition**: Multi-word queries treated as single string
   - `"Umsatz Kunden Bestellungen"` not split into `["umsatz", "kunden", "bestellungen"]`

2. **False Fuzzy Matches**: Words sharing suffixes matched incorrectly
   - `"Bestellungen"` matched `"Einstellungen"` (both end in "-stellungen")
   - Similarity score: 0.833 (very high despite being semantically wrong)

3. **Broken CamelCase Extraction**: Original implementation lost uppercase prefixes
   - `KHKStatVKKunden` → `["tat", "unden"]` instead of `["khk", "stat", "vk", "kunden"]`
   - The algorithm discarded uppercase characters instead of treating them as word boundaries

4. **Hardcoded Database-Specific Logic**: Previous implementation had German ERP-specific terms
   - Penalty tokens in German (`einstellungen`, `berechtigung`, `protokoll`)
   - Intent boosting for specific table patterns (`khkadressen`, `maartikel`, `vkposition`)
   - Hardcoded prefix list (`khk`, `vk`, `bs`, `ma`, etc.)

## Decision

Rewrite the table search algorithm to be **fully generic** with no database-specific logic.

### Change 1: Generic CamelCase Component Extraction

**Before (broken):**
```python
for char in name:
    if char.isupper() or not char.isalpha():
        if current:
            components.append(current.lower())
        current = ""
    else:
        current += char
# KHKStatVKKunden → ["tat", "unden"]  ← WRONG
```

**After (fixed):**
```python
def extract_components(name: str) -> List[str]:
    # Split on lowercase→uppercase transitions
    split1 = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
    # Split uppercase runs before final capital (XMLParser → XML_Parser)
    split2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', split1)
    return [c.lower() for c in split2.split('_') if len(c) >= 2]
# KHKStatVKKunden → ["khk", "stat", "vk", "kunden"]  ← CORRECT
```

This uses **general CamelCase rules** that work for any naming convention:
- German ERP: `KHKStatVKKunden` → `["khk", "stat", "vk", "kunden"]`
- English: `OrderLineItems` → `["order", "line", "items"]`
- Acronyms: `XMLHttpRequest` → `["xml", "http", "request"]`

### Change 2: Safe Fuzzy Matching (Prefix Validation)

**Problem:** Standard fuzzy matching gives high scores to words with matching suffixes.
```
"bestellungen" vs "einstellungen" → 0.833 similarity (WRONG!)
```

**Solution:** Require prefix overlap before accepting fuzzy match.

```python
def safe_fuzzy_match(query: str, target: str) -> float:
    if query in target:
        return 0.9  # Substring match is strong

    # Require query prefix to appear in first half of target
    min_prefix_len = min(3, len(query) // 2 + 1)
    query_prefix = query[:min_prefix_len]
    target_check_region = target[:len(target) // 2 + min_prefix_len]

    if query_prefix not in target_check_region:
        return 0.0  # False suffix match - reject

    return difflib.SequenceMatcher(None, query, target).ratio()
```

**Result:**
```
"bestellungen" vs "einstellungen" → 0.00 (CORRECT - "bes" not in "einste")
"kunden" vs "kunden" → 0.90 (CORRECT)
"order" vs "orderitems" → 0.90 (CORRECT)
```

### Change 3: Multi-Token Query Decomposition

**Before:** Query treated as single atomic string.

**After:** Split into tokens, match each independently.

```python
query_tokens = [t.lower().strip() for t in query.split() if len(t.strip()) >= 3]
# "Umsatz Kunden Bestellungen" → ["umsatz", "kunden", "bestellungen"]

for token in query_tokens:
    if token in name_lower or token in full_name_lower:
        matched_tokens.append(token)
    else:
        for component in table_components:
            if safe_fuzzy_match(token, component) >= 0.8:
                matched_tokens.append(token)
                break

# Score = matched_tokens / total_tokens
token_match_score = len(matched_tokens) / len(query_tokens)
```

### Change 4: Remove All Hardcoded Database-Specific Logic

**Removed:**
- `PREFIXES` dictionary with ERP-specific prefixes (`khk`, `vk`, `bs`, `ma`, etc.)
- `penalty_tokens` list with German words
- Intent-aware boosting with hardcoded table patterns
- ~60 lines of German ERP-specific scoring logic

**Kept only:**
- `dbo.` schema prefix removal (standard SQL Server)
- Row count bonus (prefer non-empty tables)

## Implementation

**File:** `mcp_server/scout/runner.py`

**Functions modified:**
- `TableNameNormalizer.normalize()` - Simplified to only remove `dbo.`
- `TableNameNormalizer.extract_components()` - New generic CamelCase splitter
- `TableNameNormalizer.safe_fuzzy_match()` - New prefix-validated fuzzy matching
- `TableNameNormalizer.get_component_match()` - Updated to use new functions
- `ScoutRunner.search()` - Added token decomposition, removed hardcoded logic

## Verification

**Test Results:**
```
1. Component extraction (general CamelCase rules):
   KHKStatVKKunden -> ['khk', 'stat', 'vk', 'kunden']     ✓
   BSEinstellungen -> ['bs', 'einstellungen']             ✓
   OrderLineItems -> ['order', 'line', 'items']           ✓
   XMLHttpRequest -> ['xml', 'http', 'request']           ✓

2. Safe fuzzy match (suffix attack prevention):
   "bestellungen" vs "einstellungen": 0.00               ✓
   "kunden" vs "kunden": 0.90                            ✓
   "order" vs "orderitems": 0.90                         ✓

3. Component match:
   "kunden" vs "KHKStatVKKunden": 0.85                   ✓
   "bestellungen" vs "BSEinstellungen": 0.00             ✓
```

## Expected Behavior After Fix

**Query:** "Umsatz Kunden Bestellungen"

| Before (broken) | After (fixed) |
|-----------------|---------------|
| `BSEinstellungen` (0.635) | `KHKStatVKKunden` (0.9+) |

The algorithm now:
1. Splits query into `["umsatz", "kunden", "bestellungen"]`
2. Extracts table components: `KHKStatVKKunden` → `["khk", "stat", "vk", "kunden"]`
3. Matches "kunden" token to "kunden" component (0.9 score)
4. Rejects "bestellungen" → "einstellungen" match (prefix validation fails)

## Consequences

### Positive
- **Generic algorithm** works for any database schema, not just German ERP
- **No false suffix matches** due to prefix validation
- **Proper CamelCase handling** for any naming convention
- **Multi-word queries** now work correctly
- **Maintainable** - no hardcoded terms to update

### Negative
- **No domain-specific boosting** - settings/config tables not penalized
- **Relies on naming conventions** - tables with poor names harder to find

### Mitigation
If domain-specific boosting is needed in the future, it should be loaded from configuration rather than hardcoded.

## References

- ADR 0014: Scout Mode Semantic Caching
- ADR 0015: Semantic Table Ranking for Autonomous Query Execution
