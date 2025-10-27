# Scout Mode v2 Tests

Tests for Scout Mode v2 enhancements — Column Role Enrichment (Phase 1), Semantic Summaries (Phase 2), and beyond.

## Structure

```
tests/scout_mode/
├── README.md                           # This file
├── __init__.py                         # Package marker
├── fixtures.py                         # Test fixtures (sample columns, tables, FKs)
├── test_column_enricher.py            # Unit tests for ColumnRoleEnricher
├── test_scout_phase_1_integration.py  # Integration tests (scout_mode.py + enricher)
└── test_scout_phase_2_*.py            # (Future) Semantic summaries tests
```

## Running Tests

### Run All Scout Mode Tests

```bash
# From project root
pytest tests/scout_mode/ -v

# Or specific test file
pytest tests/scout_mode/test_column_enricher.py -v
pytest tests/scout_mode/test_scout_phase_1_integration.py -v
```

### Run Specific Test Class

```bash
# Column enricher unit tests
pytest tests/scout_mode/test_column_enricher.py::TestColumnEnricher -v

# German column tests
pytest tests/scout_mode/test_column_enricher.py::TestColumnEnricher::test_german_columns_direct_match -v

# Lexicon tests
pytest tests/scout_mode/test_column_enricher.py::TestMultilingualLexicon -v
```

### Run with Coverage

```bash
pytest tests/scout_mode/ --cov=mcp_server.column_enricher --cov-report=html
# Open htmlcov/index.html to view coverage
```

## Test Files

### `test_column_enricher.py` — Unit Tests

**Target:** `mcp_server/column_enricher.py`

**Test Classes:**

1. **TestColumnEnricher** (main test suite)
   - German column tagging (15+ parameterized tests)
   - English column tagging (15+ parameterized tests)
   - Mixed German/English columns
   - Type-based inference
   - Foreign key detection
   - Full enrichment pipeline
   - Edge cases (empty names, unknown types, generic names)
   - Caching behavior
   - Error handling
   - Bulk operations

2. **TestMultilingualLexicon** (lexicon validation)
   - Coverage of all expected roles
   - German keywords in lexicon
   - English keywords in lexicon
   - Bidirectional synonyms

**Example Tests:**

```python
# German column tagging
@pytest.mark.parametrize("col_name,expected_roles", [
    ("BestellDatum", ["date"]),
    ("Betrag", ["amount"]),
    ("Menge", ["quantity"]),
])
def test_german_columns_direct_match(self, enricher, col_name, expected_roles):
    roles = enricher.infer_role_hints(col_name, "varchar")
    assert any(r in roles for r in expected_roles)

# Foreign key detection
def test_fk_detection(self, enricher):
    roles = enricher.infer_role_hints("customer_id", "int", fk_table="Customer")
    assert "fk_to:Customer" in roles

# Full enrichment pipeline
def test_enrich_german_columns_with_fks(self, enricher):
    columns = [...]  # German columns
    fks = [...]      # Foreign keys
    enriched = enricher.enrich_columns(columns, fks)
    # Verify all roles are correctly assigned
```

### `test_scout_phase_1_integration.py` — Integration Tests

**Target:** Scout Mode integration with column enricher

**Test Classes:**

1. **TestScoutModeIntegration** (main integration tests)
   - Enricher import in scout_mode.py
   - _build_catalog calls enricher
   - Enriched columns in output
   - JSON serialization
   - Backward compatibility
   - Semantic descriptions still present

2. **TestColumnEnrichmentInScout** (enricher availability)
   - Enricher imported in scout_mode
   - Graceful fallback if missing

3. **TestCatalogStructure** (catalog format)
   - Catalog version field
   - Column structure preservation
   - role_hints field presence

4. **TestPerformance** (scalability)
   - Large batch enrichment (500 columns)
   - Caching performance improvement

5. **TestErrorHandling** (edge cases)
   - Handles None FKs
   - Handles malformed columns
   - German error messages

### `fixtures.py` — Test Data

Provides reusable test fixtures:

- **GERMAN_COLUMNS:** 20 typical German ERP column names
- **ENGLISH_COLUMNS:** 20 typical English ERP column names
- **MIXED_COLUMNS:** 12 German/English mixed columns
- **EDGE_CASES:** Empty names, generic names, unknown types
- **EXPECTED_ROLES:** Expected role mappings for validation
- **SAMPLE_FOREIGN_KEYS:** FK relationships
- **SAMPLE_INVOICE_TABLE_DE:** Full German invoice table
- **SAMPLE_INVOICE_TABLE_EN:** Full English invoice table

## Acceptance Criteria (Phase 1)

All tests verify these criteria:

✅ **German columns** — Correctly tagged (Datum → date, Betrag → amount)  
✅ **English columns** — Correctly tagged (Date → date, Amount → amount)  
✅ **Mixed columns** — German/English mix handled properly  
✅ **Foreign keys** — Detected and tagged as `fk_to:TableName`  
✅ **Edge cases** — Empty names, unknown types handled gracefully  
✅ **Multi-tier matching** — Direct > fuzzy > fallback works correctly  
✅ **No false positives** — Nullable/defaults don't cause incorrect tagging  
✅ **Error messages** — In German (via `get_error_message_de()`)  
✅ **Backward compatible** — Old code without role_hints still works  
✅ **JSON serialization** — Enriched catalogs serialize correctly  
✅ **Performance** — 500 columns enriched in < 5 seconds  
✅ **Caching** — Repeated calls return cached results faster  

## Running Tests Locally

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# From project root
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
```

### Quick Test Run

```bash
# Test just the column enricher
pytest tests/scout_mode/test_column_enricher.py -v --tb=short

# Test integration with scout_mode
pytest tests/scout_mode/test_scout_phase_1_integration.py -v --tb=short

# Test everything
pytest tests/scout_mode/ -v
```

### Verbose Output

```bash
# Show print statements
pytest tests/scout_mode/ -v -s

# Full traceback on failures
pytest tests/scout_mode/ -v --tb=long
```

### Debug Specific Test

```bash
# Run with pdb on failure
pytest tests/scout_mode/test_column_enricher.py::TestColumnEnricher::test_german_columns_direct_match -v --pdb

# Run and stop on first failure
pytest tests/scout_mode/ -v -x
```

## Common Issues

### Issue: Import errors in tests

**Solution:** Ensure mcp_server is in PYTHONPATH:

```bash
export PYTHONPATH=/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code:$PYTHONPATH
pytest tests/scout_mode/ -v
```

### Issue: Fixture file not found

**Solution:** Make sure you're running from project root:

```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
pytest tests/scout_mode/ -v
```

### Issue: Some tests skipped

This is OK! Tests skip gracefully if:
- `scout_mode.py` can't be imported
- `ColumnRoleEnricher` isn't available
- Performance tests are environment-specific

Check logs for skip reasons.

## Test Coverage

Current coverage target: **≥ 90%** for Phase 1

```bash
pytest tests/scout_mode/ --cov=mcp_server.column_enricher --cov-report=term-missing
```

## Adding New Tests

### For Phase 2 (Semantic Summaries)

Create `test_scout_phase_2_summaries.py`:

```python
import pytest
from summary_builder import SemanticSummaryBuilder

class TestSemanticSummaries:
    @pytest.fixture
    def builder(self):
        return SemanticSummaryBuilder()
    
    def test_summary_generation(self, builder):
        table = {"name": "Invoice", "columns": [...]}
        summary = builder.build_summary(table)
        assert len(summary) < 150  # One-liner
        assert "Invoice" in summary or "invoice" in summary
```

### For Phase 3 (Non-Empty Filtering)

Create `test_scout_phase_3_filtering.py`:

```python
import pytest
from discovery_tools import list_tables

class TestNonEmptyFiltering:
    def test_include_empty_false(self):
        # Should exclude empty tables
        pass
    
    def test_include_empty_true(self):
        # Should include empty tables
        pass
```

## Continuous Integration

These tests should run in CI/CD pipeline:

```yaml
# .github/workflows/test.yml (example)
- name: Test Scout Mode Phase 1
  run: |
    pytest tests/scout_mode/test_column_enricher.py -v --tb=short
    pytest tests/scout_mode/test_scout_phase_1_integration.py -v --tb=short
```

---

**Last Updated:** January 2025  
**Maintainer:** Zencoder Scout Mode Team