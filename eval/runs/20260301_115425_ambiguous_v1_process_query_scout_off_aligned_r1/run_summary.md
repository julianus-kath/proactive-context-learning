# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_115425_ambiguous_v1_process_query_scout_off_aligned_r1`
- Run name: `ambiguous_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `3764.7`
- P95 latency ms: `6910.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 2964 | True | public.products |
| NW10 | success | 3737 | True | public.orders, public.order_details |
| NW2 | success | 3715 | True | public.order_details, public.products, public.categories |
| NW3 | success | 3279 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 2713 | True | public.orders, public.shippers |
| NW5 | success | 3333 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 2898 | True | public.order_details, public.products |
| NW7 | success | 6910 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 5075 | True | public.orders, public.customers, public.order_details |
| NW9 | success | 3023 | True | public.orders, public.order_details |
