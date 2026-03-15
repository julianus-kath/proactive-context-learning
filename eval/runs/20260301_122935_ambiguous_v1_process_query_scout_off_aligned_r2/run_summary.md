# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_122935_ambiguous_v1_process_query_scout_off_aligned_r2`
- Run name: `ambiguous_v1_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `3358.1`
- P95 latency ms: `4609.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 2853 | True | public.products |
| NW10 | success | 3397 | True | public.orders, public.order_details |
| NW2 | success | 4007 | True | public.order_details, public.products, public.categories |
| NW3 | success | 3062 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 2820 | True | public.orders, public.shippers |
| NW5 | success | 3453 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 2330 | True | public.order_details, public.products |
| NW7 | success | 4353 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 4609 | True | public.customers, public.orders, public.order_details |
| NW9 | success | 2697 | True | public.orders, public.order_details |
