# Scout Production Audit (20260216_150213_northwind_offline_extract)

## H1 Catalog Indexing Completeness
- Table coverage: 100.0% (14/14)
- Column coverage: 100.0% (92/92)
- FK coverage: 100.0% (13/13)

## Catalog Quality Diagnostics
- Tables with columns present: 100.0%
- Tables with row estimates: 100.0%
- Tables with FK metadata: 100.0%

## Freshness
- Catalog valid: False
- Catalog age (hours): 1.031
- Catalog TTL (hours): 1.0

## Caveats
- Retrieval usefulness on production requires a production-grounded query contract set.
- Existing cockpit contracts are Northwind-oriented and should not be used as L&D truth labels.

## Diagnostics Issues
- None reported by scout_catalog_diagnostics.

## Diagnostics Recommendations
- None reported.
