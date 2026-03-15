# /process_query Northwind Run (scout_on)

- Run ID: `20260302_140029_scout_limit_ladder_v1_process_query_scout_on_r2`
- Run name: `scout_limit_ladder_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `8129.8`
- P95 latency ms: `18630.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 7754 | False |  |
| LT1_CL2 | success | 5304 | True | public.orders, public.order_details |
| LT1_CL6 | success | 5213 | True | public.orders |
| LT2_CL10 | success | 9706 | True | public.orders, public.order_details |
| LT2_CL2 | success | 3646 | True | public.orders, public.order_details |
| LT2_CL6 | success | 6674 | False |  |
| LT3_CL10 | success | 18630 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| LT3_CL2 | success | 6348 | True | public.orders, public.order_details |
| LT3_CL6 | success | 11081 | False |  |
| LT4_CL10 | success | 14316 | False |  |
| LT4_CL2 | success | 6462 | True | public.orders, public.order_details |
| LT4_CL6 | success | 5144 | False |  |
| LT5_CL10 | success | 8613 | True | public.order_details, public.orders, public.products |
| LT5_CL2 | success | 5899 | True | public.orders, public.order_details |
| LT5_CL6 | success | 7157 | False |  |
