# /process_query Northwind Run (scout_on)

- Run ID: `20260301_132329_crosslingual_hard_v1_process_query_scout_on_r2`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4668.3`
- P95 latency ms: `7029.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3472 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 3358 | False |  |
| CL11 | success | 4523 | True | public.employees, public.orders |
| CL12 | success | 5191 | True | public.orders, public.order_details |
| CL2 | success | 7029 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 4020 | False |  |
| CL4 | success | 5015 | True | public.orders |
| CL5 | success | 4496 | True | public.customers, public.orders |
| CL6 | success | 5612 | False |  |
| CL7 | success | 5612 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 5131 | True | public.customers, public.orders |
| CL9 | success | 2561 | True | public.suppliers, public.products, public.order_details |
