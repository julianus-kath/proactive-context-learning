# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_135320_scout_limit_ladder_v1_process_query_scout_off_aligned_r1_recover`
- Run name: `scout_limit_ladder_v1_process_query_scout_off_aligned_r1_recover`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `15454.3`
- P95 latency ms: `34182.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 33584 | False |  |
| LT1_CL2 | success | 34182 | True | public.orders, public.order_details, public.customers |
| LT1_CL6 | success | 31047 | True | public.orders |
| LT2_CL10 | success | 16394 | True | public.orders, public.order_details |
| LT2_CL2 | success | 4944 | True | public.orders, public.order_details |
| LT2_CL6 | success | 9349 | False |  |
| LT3_CL10 | success | 11834 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| LT3_CL2 | success | 8269 | False |  |
| LT3_CL6 | success | 5821 | False |  |
| LT4_CL10 | success | 29893 | False |  |
| LT4_CL2 | success | 6142 | False |  |
| LT4_CL6 | success | 14873 | False |  |
| LT5_CL10 | success | 4642 | True | public.order_details, public.products |
| LT5_CL2 | success | 16862 | True | public.orders, public.order_details |
| LT5_CL6 | success | 3979 | False |  |
