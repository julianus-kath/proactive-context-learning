# /process_query Northwind Run (scout_on)

- Run ID: `20260302_135751_scout_limit_ladder_v1_process_query_scout_on_r1`
- Run name: `scout_limit_ladder_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7351.5`
- P95 latency ms: `15146.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 8913 | False |  |
| LT1_CL2 | success | 5498 | True | public.orders, public.order_details |
| LT1_CL6 | success | 6217 | True | public.orders |
| LT2_CL10 | success | 6945 | True | public.orders, public.order_details, public.customers |
| LT2_CL2 | success | 4720 | True | public.orders, public.order_details |
| LT2_CL6 | success | 10382 | True | public.orders |
| LT3_CL10 | success | 10372 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| LT3_CL2 | success | 11275 | True | public.orders, public.order_details |
| LT3_CL6 | success | 3342 | False |  |
| LT4_CL10 | success | 8671 | True | public.orders, public.order_details |
| LT4_CL2 | success | 4717 | True | public.orders, public.order_details |
| LT4_CL6 | success | 3706 | False |  |
| LT5_CL10 | success | 4025 | True | public.order_details, public.products |
| LT5_CL2 | success | 6344 | True | public.orders, public.order_details |
| LT5_CL6 | success | 15146 | True | public.orders, public.order_details |
