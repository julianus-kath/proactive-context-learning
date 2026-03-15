# /process_query Northwind Run (scout_on)

- Run ID: `20260301_131827_crosslingual_hard_v1_process_query_scout_on_r1`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4599.8`
- P95 latency ms: `8719.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3623 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 5094 | True | public.customers, public.customer_customer_demo, public.customer_demographics, public.orders, public.order_details |
| CL11 | success | 3803 | False |  |
| CL12 | success | 4709 | True | public.orders, public.order_details |
| CL2 | success | 8719 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 4041 | False |  |
| CL4 | success | 3881 | True | public.orders |
| CL5 | success | 3330 | True | public.customers, public.orders |
| CL6 | success | 4936 | True | public.orders |
| CL7 | success | 4928 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 5035 | True | public.customers, public.orders |
| CL9 | success | 3098 | True | public.suppliers, public.products, public.order_details |
