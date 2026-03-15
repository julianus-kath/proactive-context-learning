# Scout Production Audit (20260216_145042_ld_prod_offline_extract)

## H1 Catalog Indexing Completeness
- Table coverage: 100.0% (943/943)
- Column coverage: 100.0% (13759/13759)
- FK coverage: 100.0% (392/392)

## Catalog Quality Diagnostics
- Tables with columns present: 100.0%
- Tables with row estimates: 100.0%
- Tables with FK metadata: 100.0%

## Freshness
- Catalog valid: True
- Catalog age (hours): 0.1
- Catalog TTL (hours): 1.0

## Caveats
- Retrieval usefulness on production requires a production-grounded query contract set.
- Existing cockpit contracts are Northwind-oriented and should not be used as L&D truth labels.

## Diagnostics Issues
- None reported by scout_catalog_diagnostics.

## Diagnostics Recommendations
- None reported.
