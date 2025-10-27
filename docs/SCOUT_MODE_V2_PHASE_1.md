# Scout Mode v2 — Phase 1: Column Role Enrichment

**Status:** 🚀 Ready to Deploy  
**Date:** January 2025  
**Scope:** German/English fuzzy column role tagging for MCP server catalogs  
**Impact:** Downstream ranking, query planning, and agent grounding

---

## 📋 Overview

Phase 1 adds **fuzzy multilingual role tagging** to every column in the Scout Mode catalog. This enables:

✅ **Semantic understanding** — Columns tagged with roles (id, date, amount, quantity, status, email, phone, postal_code, name, code)  
✅ **German/English bidirectional** — Handles German ERP naming (Datum → date, Betrag → amount) automatically  
✅ **Fuzzy matching** — Doesn't require exact keywords; translates between languages  
✅ **Downstream integration** — Roles feed directly into ranking, planning, and agent decision-making  
✅ **No performance penalty** — Caching + lazy LLM (optional)  
✅ **Backward compatible** — Old code without role_hints still works

---

## 🏗️ Architecture

### Multi-Tier Role Inference

```
Column Name + Type
    ↓
Tier 1: Direct Keyword Match (exact terms + regex)
    ↓ (no match)
Tier 2: Fuzzy Match (string similarity + synonyms)
    ↓ (no match)
Tier 3: LLM Translation (optional, for ambiguous cases)
    ↓ (no match)
Tier 4: Type-Based Fallback (datetime→date, numeric→quantity, etc.)
    ↓
Final Roles: [role1, role2, ...] (e.g., ["date", "fk_to:Order"])
```

### Integration Points

```
scout_mode.py::_build_catalog()
    ↓
[For each table, for each FK]
    ↓
column_enricher.py::enrich_columns()
    ↓
Returns columns with role_hints: List[str]
    ↓
Stored in catalog.json
    ↓
Used by:
  - table_ranker.py (role_coverage scoring)
  - query_blueprints.py (column selection)
  - agent prompts (grounding)
```

---

## 📦 New Components

### 1. `column_enricher.py`

**Main class:** `ColumnRoleEnricher`

```python
from mcp_server.column_enricher import ColumnRoleEnricher

# Create enricher (no LLM needed for basic operation)
enricher = ColumnRoleEnricher(use_llm=False)

# Enrich columns with role hints
enriched_columns = enricher.enrich_columns(
    columns=[
        {"name": "BestellDatum", "type": "datetime"},
        {"name": "Betrag", "type": "decimal"},
    ],
    foreign_keys=[
        {"column": "KundenID", "referenced_table": "Kunde"}
    ]
)

# Result:
# [
#   {"name": "BestellDatum", "type": "datetime", "role_hints": ["date"]},
#   {"name": "Betrag", "type": "decimal", "role_hints": ["amount"]},
# ]
```

**Key methods:**

```python
# Infer roles for a single column
roles = enricher.infer_role_hints(
    col_name="RechnungsDatum",
    col_type="datetime",
    fk_table=None
)
# → ["date"]

# Enrich multiple columns
enriched = enricher.enrich_columns(columns, foreign_keys)

# Get German error message
msg = enricher.get_error_message_de("column_missing", "TestCol")
# → "Spalte fehlt oder ist leer: TestCol"
```

### 2. Updated `catalog.py`

**Change:** Add `role_hints: Optional[List[str]]` to `ColumnInfo`:

```python
@dataclass
class ColumnInfo:
    """Column metadata."""
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    role_hints: Optional[List[str]] = None  # NEW: Phase 1 semantic roles
```

### 3. Updated `scout_mode.py`

**Import:**
```python
from mcp_server.column_enricher import ColumnRoleEnricher
```

**Usage in `_build_catalog()`:**
```python
# After fetching columns and FKs, enrich them:
if ColumnRoleEnricher:
    enricher = ColumnRoleEnricher(use_llm=False)
    table_info["columns"] = enricher.enrich_columns(
        table_info["columns"],
        table_info["foreign_keys"]
    )
```

---

## 🎯 Role Tags Explained

| Role | Matched Patterns | Examples (German/English) | Type Hints |
|------|------------------|---------------------------|-----------|
| **id** | `id`, `_id`, `pk`, `uuid`, `key` | KundenID, ProductKey | int, varchar |
| **fk_to:Table** | FK column detection | CustomerID → Customer | int, varchar |
| **date** | Datum, Lieferdatum, Date, Created, Modified | RechnungsDatum, OrderDate | datetime, date, timestamp |
| **amount** | Betrag, Preis, Amount, Total, Sum | EinzelBetrag, TotalAmount | money, decimal, numeric |
| **quantity** | Menge, Anzahl, Qty, Count | BestellMenge, OrderQuantity | int, smallint |
| **status** | Status, Zustand, State | OrderStatus, AuftragsZustand | varchar, char |
| **email** | Email, E-Mail, Mail | KundenEMail, CustomerEmail | varchar, text |
| **phone** | Telefon, Handy, Phone, Mobile | KundenTelefon, ContactPhone | varchar |
| **postal_code** | PLZ, Postleitzahl, Postal, ZIP | KundenPLZ, BillingZIP | varchar |
| **name** | Name, Titel, Bezeichnung, Description | Kundenname, ProductName | varchar, text |
| **code** | Code, Nummer, Number, ArtikelNr | ArtikelCode, CustomerNumber | varchar |

**Example column enrichment:**

```json
{
  "name": "RechnungsDatum",
  "type": "datetime",
  "nullable": false,
  "role_hints": ["date"]
}
```

```json
{
  "name": "KundenID",
  "type": "int",
  "is_foreign_key": true,
  "role_hints": ["id", "fk_to:Kunde"]
}
```

---

## 🌍 Multilingual Support

### German ↔ English

**Lexicon structure:**
```python
LEXICON = {
    "date": {
        "en": ["date", "time", "created", "modified", ...],
        "de": ["datum", "zeit", "erstellt", "geändert", ...],
        "patterns": [r"datum$", r"_date$", ...]
    }
}
```

**Synonyms for fuzzy matching:**
```python
SYNONYMS = {
    "datum": ["date", "timestamp"],
    "betrag": ["amount", "total"],
    "menge": ["quantity", "count"],
    # ... bidirectional
}
```

**Examples:**

| Input | Output | Reason |
|-------|--------|--------|
| `BestellDatum` (German) | `["date"]` | Direct DE keyword match |
| `OrderDate` (English) | `["date"]` | Direct EN keyword match |
| `Rechnng` (typo) | `["date"]` (maybe) | Fuzzy similarity to `RechnungsDatum` + type inference |
| `timestamp` (EN) | `["date"]` | Type + keyword match |
| `bereich` (ambiguous) | `[]` or fallback | No match; too generic |

---

## 🧪 Testing

### Unit Tests

Located in `/tests/scout_mode/test_column_enricher.py`:

```bash
# Run all tests
pytest tests/scout_mode/test_column_enricher.py -v

# Run specific test class
pytest tests/scout_mode/test_column_enricher.py::TestColumnEnricher -v

# Run specific test
pytest tests/scout_mode/test_column_enricher.py::TestColumnEnricher::test_german_columns_direct_match -v
```

**Test Coverage:**

✅ German column tagging (BestellDatum → date, Betrag → amount, etc.)  
✅ English column tagging (OrderDate → date, TotalAmount → amount, etc.)  
✅ Mixed German/English columns  
✅ Foreign key detection (CustomerID → fk_to:Customer)  
✅ Type-based inference fallback  
✅ Edge cases (empty names, unknown types, generic names)  
✅ Caching behavior (repeated calls return cached results)  
✅ Error messages in German  
✅ JSON serialization  
✅ Backward compatibility

### Integration Tests

Located in `/tests/scout_mode/test_scout_phase_1_integration.py`:

```bash
# Run integration tests
pytest tests/scout_mode/test_scout_phase_1_integration.py -v
```

**Test Coverage:**

✅ scout_mode.py successfully imports ColumnRoleEnricher  
✅ _build_catalog calls enricher for each table  
✅ Enriched columns appear in output catalog  
✅ Catalog JSON serialization works  
✅ Backward compatibility (old catalogs still work)  
✅ No performance regression  
✅ Error handling and graceful degradation

---

## 🚀 Deployment Checklist

- [ ] **Code Review**
  - [ ] `column_enricher.py` reviewed for quality + performance
  - [ ] `catalog.py` changes minimal and backward compatible
  - [ ] `scout_mode.py` integration clean and non-blocking
  
- [ ] **Testing**
  - [ ] Unit tests passing: `pytest tests/scout_mode/test_column_enricher.py -v`
  - [ ] Integration tests passing: `pytest tests/scout_mode/test_scout_phase_1_integration.py -v`
  - [ ] No regressions in existing tests: `pytest tests/ -k "not scout_mode" -v`
  
- [ ] **Performance**
  - [ ] Catalog build time not increased >10% (measure baseline first)
  - [ ] Enrichment for 1000 columns completes in <5s
  - [ ] Memory footprint increase < 20%
  
- [ ] **Quality**
  - [ ] No uncaught exceptions in enrichment pipeline
  - [ ] Error messages in German (via `get_error_message_de()`)
  - [ ] No secrets or sensitive data in role_hints
  
- [ ] **Documentation**
  - [ ] This document reviewed
  - [ ] Inline code comments explain lexicon + tiers
  - [ ] ADR updated (reference Phase 1 in ADR-0016)
  
- [ ] **Rollout**
  - [ ] Deploy to dev environment first
  - [ ] Verify with sample ERP data (German + English)
  - [ ] Monitor startup time on Windows/VPN MCP server
  - [ ] Deploy to production

---

## 📊 Example Usage

### Before Phase 1 (Current)

```python
# Catalog.json - columns without roles
{
  "tables": [
    {
      "name": "Invoice",
      "columns": [
        {"name": "BestellDatum", "type": "datetime"},
        {"name": "Betrag", "type": "decimal"}
      ]
    }
  ]
}
```

### After Phase 1 (Enriched)

```python
# scout_catalog.json - columns WITH roles
{
  "tables": [
    {
      "name": "Invoice",
      "columns": [
        {
          "name": "BestellDatum",
          "type": "datetime",
          "role_hints": ["date"]  # ✨ NEW
        },
        {
          "name": "Betrag",
          "type": "decimal",
          "role_hints": ["amount"]  # ✨ NEW
        }
      ]
    }
  ]
}
```

### Downstream Usage (Phase 2+)

```python
# In table_ranker.py
role_coverage = {
    "date": bool(any("date" in h for h in col["role_hints"])),
    "measure": bool(any("amount" in h for h in col["role_hints"])),
    "identifier": bool(any("id" in h for h in col["role_hints"])),
}

# Role coverage used in ranking score:
score = 0.45 * text_sim + 0.25 * role_coverage + ...
```

---

## 🔧 Configuration

**Environment variables** (optional):

```bash
# Enable LLM-powered translation (requires API key setup)
# COLUMN_ENRICHER_USE_LLM=true
# OPENAI_API_KEY=sk_xxx

# Column enrichment strictness (future)
# COLUMN_ENRICHER_CONFIDENCE_THRESHOLD=0.7
```

**In code:**

```python
# Default: no LLM, pure fuzzy matching (fast)
enricher = ColumnRoleEnricher(use_llm=False)

# Optional: with LLM for ambiguous columns
enricher = ColumnRoleEnricher(use_llm=True, llm_client=openai_client)
```

---

## 🐛 Troubleshooting

### Issue: Columns not getting role_hints

**Cause:** ColumnRoleEnricher not imported in scout_mode.py

**Solution:** Check import:
```python
# scout_mode.py line 29-33
try:
    from mcp_server.column_enricher import ColumnRoleEnricher
except ImportError:
    ColumnRoleEnricher = None
    logger.warning("⚠️ ColumnRoleEnricher not available, column role tagging disabled")
```

If `ColumnRoleEnricher` is None, enrichment is skipped (graceful).

### Issue: Role tags seem incorrect

**Cause:** Fuzzy matching might have caught a different keyword

**Solution:** Check the multi-tier inference:
1. Is the exact keyword in the lexicon?
2. Is the column type matching (e.g., datetime for "date")?
3. Are there competing keywords?

**Debug:**
```python
enricher = ColumnRoleEnricher()
roles = enricher.infer_role_hints("ProblematicColumn", "varchar")
print(f"Roles: {roles}")

# Check direct match
if enricher._direct_match("problematiccolumn", "varchar", enricher.LEXICON["date"]):
    print("Direct match found")

# Check fuzzy match
fuzzy = enricher._fuzzy_match("problematiccolumn", "varchar")
print(f"Fuzzy matches: {fuzzy}")
```

### Issue: German error messages not appearing

**Solution:** Use `get_error_message_de()`:
```python
from mcp_server.column_enricher import ColumnRoleEnricher

msg = ColumnRoleEnricher.get_error_message_de("column_missing", "TestColumn")
logger.error(msg)  # "Spalte fehlt oder ist leer: TestColumn"
```

---

## 📚 Related Documentation

- **ADR-0014:** Scout Mode / Semantic Caching
- **ADR-0016:** Phase 7 Complete Architecture with Scout and Semantic Ranking
- **ADR-0017:** Phases 1–5 Integration and Module Organization
- **Phase 2 Plan:** Semantic Summaries ("Diary One-Liners")
- **Phase 3 Plan:** Non-Empty Filtering & Row Tiers
- **Phase 4 Plan:** View Ingestion & Lineage
- **Phase 5 Plan:** Dependency Graph Snapshot

---

## 🎓 Next Steps

**Phase 2** will add:
- `semantic_summary: str` (one-liner per table/view)
- Domain inference from name + FK neighbors
- Stored in catalog for ranking + grounding

**Phase 3** will add:
- `has_rows: bool` signal
- Row tier bucketing (empty, tiny, small, medium, large)
- Default `include_empty=false` in discovery tools

**Phase 4** will add:
- View ingestion + dependencies
- `role_coverage: Dict[str, bool]` for ranking

**Phase 5** will add:
- Dependency graph snapshot
- Fast pathfinding for ≤3 hop joins

---

## 📞 Support

For issues or questions:

1. Check **Troubleshooting** section above
2. Review **test cases** in `/tests/scout_mode/`
3. Check **scout_mode.py** for integration details
4. Review **LEXICON** in `column_enricher.py` for role definitions

---

*Generated January 2025 — Scout Mode v2 Phase 1 Documentation*