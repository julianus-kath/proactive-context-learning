# /process_query Northwind Run (scout_on)

- Run ID: `20260301_124203_nonlexical_v2_process_query_scout_on_r1`
- Run name: `nonlexical_v2_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4038.1`
- P95 latency ms: `5893.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 4404 | True | public.products |
| NL10 | success | 3574 | True | public.customers, public.orders |
| NL11 | success | 7021 | True | public.orders |
| NL12 | success | 3792 | True | public.order_details, public.products |
| NL13 | success | 3027 | False |  |
| NL14 | success | 2772 | True | public.customers, public.orders, public.order_details |
| NL15 | success | 4230 | True | public.order_details, public.products |
| NL16 | success | 5526 | True | public.products, public.order_details |
| NL17 | success | 2881 | False |  |
| NL18 | success | 3335 | True | public.orders, public.employees, public.customers |
| NL19 | success | 4194 | False |  |
| NL2 | success | 5893 | True | public.orders, public.order_details |
| NL20 | success | 3214 | False |  |
| NL3 | success | 3022 | True | public.orders, public.shippers |
| NL4 | success | 3085 | True | public.order_details, public.products |
| NL5 | success | 4440 | True | public.orders, public.order_details |
| NL6 | success | 5147 | True | public.order_details, public.orders |
| NL7 | success | 3970 | True | public.order_details, public.products |
| NL8 | success | 4820 | True | public.orders, public.shippers |
| NL9 | success | 2414 | True | public.orders |
