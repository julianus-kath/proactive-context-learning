# /process_query Northwind Run (scout_on)

- Run ID: `20260301_122640_ambiguous_v1_process_query_scout_on_r2`
- Run name: `ambiguous_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `4674.1`
- P95 latency ms: `9357.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 5559 | True | public.products |
| NW10 | success | 3266 | True | public.orders, public.order_details |
| NW2 | success | 3630 | True | public.order_details, public.products, public.categories |
| NW3 | success | 4314 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 9357 | True | public.orders, public.shippers |
| NW5 | success | 5120 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 3066 | True | public.order_details, public.products |
| NW7 | success | 4871 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 5257 | True | public.orders, public.customers, public.order_details |
| NW9 | success | 2301 | True | public.orders, public.order_details |
