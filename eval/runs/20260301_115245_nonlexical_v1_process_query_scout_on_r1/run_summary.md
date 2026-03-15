# /process_query Northwind Run (scout_on)

- Run ID: `20260301_115245_nonlexical_v1_process_query_scout_on_r1`
- Run name: `nonlexical_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4044.5`
- P95 latency ms: `6625.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 2809 | True | public.order_details |
| NL10 | success | 3755 | True | public.customers, public.orders |
| NL11 | success | 3723 | True | public.orders |
| NL12 | success | 3567 | True | public.order_details, public.products |
| NL13 | success | 3381 | False |  |
| NL14 | success | 3449 | True | public.customers, public.orders, public.order_details |
| NL15 | success | 4685 | True | public.order_details, public.products |
| NL16 | success | 5314 | True | public.suppliers, public.products, public.order_details |
| NL17 | success | 8779 | True | public.order_details, public.orders, public.customers |
| NL18 | success | 2887 | True | public.orders, public.employees, public.customers |
| NL19 | success | 4674 | True | public.order_details, public.products |
| NL2 | success | 3147 | True | public.order_details, public.orders |
| NL20 | success | 3566 | False |  |
| NL3 | success | 6625 | True | public.orders, public.shippers |
| NL4 | success | 3388 | True | public.order_details, public.products, public.categories |
| NL5 | success | 3720 | True | public.orders, public.order_details, public.customers |
| NL6 | success | 2853 | True | public.order_details, public.orders |
| NL7 | success | 3451 | True | public.order_details, public.products |
| NL8 | success | 4375 | True | public.orders, public.shippers |
| NL9 | success | 2742 | True | public.orders |
