# /process_query Northwind Run (scout_on)

- Run ID: `20260302_132718_crosslingual_hard_v1_process_query_scout_on_r6`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r6`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `6976.8`
- P95 latency ms: `12784.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 4875 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 5232 | False |  |
| CL11 | success | 12784 | True | public.employees, public.orders |
| CL12 | success | 7639 | True | public.orders, public.order_details |
| CL2 | success | 9317 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 5373 | False |  |
| CL4 | success | 5422 | True | public.orders |
| CL5 | success | 4125 | True | public.customers, public.orders |
| CL6 | success | 10990 | True | public.orders |
| CL7 | success | 6072 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 8345 | True | public.customers, public.orders |
| CL9 | success | 3548 | True | public.suppliers, public.products, public.order_details |
