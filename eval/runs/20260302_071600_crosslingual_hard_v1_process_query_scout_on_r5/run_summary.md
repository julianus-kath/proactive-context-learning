# /process_query Northwind Run (scout_on)

- Run ID: `20260302_071600_crosslingual_hard_v1_process_query_scout_on_r5`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r5`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `5482.8`
- P95 latency ms: `8408.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3472 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 8408 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| CL11 | success | 5597 | False |  |
| CL12 | success | 4426 | True | public.orders, public.order_details |
| CL2 | success | 7814 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 4087 | False |  |
| CL4 | success | 5185 | True | public.orders |
| CL5 | success | 3780 | True | public.customers, public.orders |
| CL6 | success | 5861 | True | public.orders |
| CL7 | success | 6729 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 7468 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 2966 | True | public.suppliers, public.products, public.order_details |
