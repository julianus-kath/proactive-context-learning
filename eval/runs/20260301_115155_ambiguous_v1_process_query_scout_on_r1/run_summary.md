# /process_query Northwind Run (scout_on)

- Run ID: `20260301_115155_ambiguous_v1_process_query_scout_on_r1`
- Run name: `ambiguous_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `10`
- Successes: `10`
- Failures: `0`
- Avg latency ms: `4106.5`
- P95 latency ms: `10070.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW1 | success | 10070 | True | public.products |
| NW10 | success | 4008 | True | public.orders, public.order_details |
| NW2 | success | 4511 | True | public.order_details, public.products, public.categories |
| NW3 | success | 4083 | True | public.customers, public.orders, public.order_details |
| NW4 | success | 3259 | True | public.orders, public.shippers |
| NW5 | success | 2752 | True | public.employees, public.orders, public.order_details |
| NW6 | success | 2307 | True | public.order_details, public.products |
| NW7 | success | 4015 | True | public.order_details, public.products, public.suppliers |
| NW8 | success | 3821 | True | public.orders, public.order_details, public.customers |
| NW9 | success | 2239 | True | public.orders, public.order_details |
