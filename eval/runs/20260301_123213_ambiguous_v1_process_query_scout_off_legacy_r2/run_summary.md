# /process_query Northwind Run (scout_off_legacy_lexical)

- Run ID: `20260301_123213_ambiguous_v1_process_query_scout_off_legacy_r2`
- Run name: `ambiguous_v1_process_query_scout_off_legacy_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `4570.5`
- P95 latency ms: `8589.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 3823 | True | public.products |
| NW10 | success | 8589 | True | public.order_details, public.orders |
| NW2 | success | 3039 | True | public.order_details, public.products, public.categories |
| NW3 | success | 3474 | True | public.orders, public.customers |
| NW4 | success | 3885 | True | public.orders |
| NW5 | success | 5676 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 5646 | True | public.products, public.order_details |
| NW7 | success | 4564 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 3256 | True | public.orders, public.customers, public.order_details |
| NW9 | success | 3753 | True | public.orders, public.order_details |
