# /process_query Northwind Run (scout_off)

- Run ID: `20260223_063107_northwind_process_query_scout_off`
- Run name: `northwind_process_query_scout_off`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog. Catalog source is schema_catalog.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `3968.9`
- P95 latency ms: `8214.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 2915 | True | public.products |
| NW10 | success | 5180 | True | public.orders, public.order_details |
| NW2 | success | 3956 | True | public.order_details, public.products, public.categories |
| NW3 | success | 3712 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 3667 | True | public.orders, public.shippers |
| NW5 | success | 8214 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 2473 | True | public.order_details, public.products |
| NW7 | success | 3446 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 3258 | True | public.orders, public.order_details, public.customers |
| NW9 | success | 2868 | True | public.orders, public.order_details |
