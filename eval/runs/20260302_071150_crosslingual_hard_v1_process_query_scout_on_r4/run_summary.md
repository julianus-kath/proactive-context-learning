# /process_query Northwind Run (scout_on)

- Run ID: `20260302_071150_crosslingual_hard_v1_process_query_scout_on_r4`
- Run name: `crosslingual_hard_v1_process_query_scout_on_r4`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `7309.6`
- P95 latency ms: `14187.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 7610 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 4262 | False |  |
| CL11 | success | 4220 | False |  |
| CL12 | success | 5545 | True | public.orders, public.order_details |
| CL2 | success | 13138 | True | public.orders, public.order_details |
| CL3 | success | 7088 | False |  |
| CL4 | success | 6824 | True | public.orders |
| CL5 | success | 6177 | True | public.customers, public.orders |
| CL6 | success | 14187 | True | public.orders |
| CL7 | success | 5304 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 9687 | True | public.customers, public.orders |
| CL9 | success | 3673 | True | public.suppliers, public.products, public.order_details |
