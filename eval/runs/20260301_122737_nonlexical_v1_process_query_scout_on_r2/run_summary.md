# /process_query Northwind Run (scout_on)

- Run ID: `20260301_122737_nonlexical_v1_process_query_scout_on_r2`
- Run name: `nonlexical_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4344.2`
- P95 latency ms: `6341.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 2752 | True | public.order_details |
| NL10 | success | 4152 | True | public.customers, public.orders |
| NL11 | success | 4162 | True | public.orders |
| NL12 | success | 6341 | True | public.order_details, public.products |
| NL13 | success | 3374 | False |  |
| NL14 | success | 3763 | True | public.customers, public.orders, public.order_details |
| NL15 | success | 5164 | True | public.order_details, public.products |
| NL16 | success | 6957 | True | public.products, public.order_details |
| NL17 | success | 4884 | True | public.order_details, public.orders |
| NL18 | success | 3860 | True | public.orders, public.employees, public.customers |
| NL19 | success | 2795 | False |  |
| NL2 | success | 3763 | True | public.order_details, public.orders |
| NL20 | success | 3518 | False |  |
| NL3 | success | 3893 | False |  |
| NL4 | success | 4796 | True | public.order_details, public.products, public.categories |
| NL5 | success | 4396 | True | public.orders, public.order_details, public.customers |
| NL6 | success | 6295 | True | public.order_details, public.orders |
| NL7 | success | 3674 | True | public.order_details, public.products |
| NL8 | success | 5410 | True | public.orders, public.shippers |
| NL9 | success | 2936 | True | public.orders, public.employees |
