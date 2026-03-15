# /process_query Northwind Run (scout_on)

- Run ID: `20260301_132643_crosslingual_hard_v1_process_query_scout_on_r3`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4919.2`
- P95 latency ms: `10326.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3459 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 10326 | True | public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| CL11 | success | 3892 | False |  |
| CL12 | success | 4557 | True | public.orders, public.order_details |
| CL2 | success | 7124 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 3831 | False |  |
| CL4 | success | 4942 | True | public.orders |
| CL5 | success | 3388 | True | public.customers, public.orders |
| CL6 | success | 4817 | True | public.orders |
| CL7 | success | 4485 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 5575 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 2634 | True | public.suppliers, public.products, public.order_details |
