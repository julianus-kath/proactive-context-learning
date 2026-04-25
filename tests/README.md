# Test Suite

Focused tests covering the critical evaluation-correctness path plus the Scout ranking primitives. Integration tests run against a local Northwind Postgres container.

## Running

```bash
# Unit tests only (no DB required)
pytest -m "not integration"

# Full suite (requires Northwind Postgres on localhost:55432)
pytest
```

## Layout

```
tests/
├── eval/
│   ├── test_metrics.py             # compute_recall, normalize_table
│   ├── test_sql_extraction.py      # extract_tables_from_sql
│   └── test_contracts_loading.py   # load_contracts() — ground-truth JSON loader
├── scout/
│   └── test_normalizer.py       # TableNameNormalizer components + fuzzy
└── integration/
    └── test_northwind_smoke.py  # Live DB sanity checks (gated by @integration marker)
```

Separately, the Scout module owns its own unit-test suite at [mcp_server/scout/tests/](../mcp_server/scout/tests/) covering description generation, description enrichment, runner toggles, and ranker description-scoring. Both trees are discovered by `pytest.ini`.

## Testing strategy

Development was **evaluation-driven**, not test-first. The controlled Northwind dataset (N=64) and the Cockpit partner dataset (N=9) served as continuous integration throughout the thesis: every change was exercised end-to-end against these queries and surfaced in run comparisons.

The test suites here harden the **scoring path** — the functions that turn raw run artefacts into the numbers reported in the thesis. If these are wrong, the thesis numbers are wrong. Everything else was validated through the eval runs at [eval/runs/](../eval/runs/).
