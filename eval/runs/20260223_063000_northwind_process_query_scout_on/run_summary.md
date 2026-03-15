# /process_query Northwind Run (scout_on)

- Run ID: `20260223_063000_northwind_process_query_scout_on`
- Run name: `northwind_process_query_scout_on`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `4234.3`
- P95 latency ms: `5438.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 5438 | True | public.products |
| NW10 | success | 5116 | True | public.orders, public.order_details |
| NW2 | success | 3527 | True | public.order_details, public.products, public.categories |
| NW3 | success | 4462 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 3595 | True | public.orders, public.shippers |
| NW5 | success | 3965 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 3169 | True | public.order_details, public.products |
| NW7 | success | 5246 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 4960 | True | public.orders, public.order_details, public.customers |
| NW9 | success | 2865 | True | public.orders, public.order_details |
