# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_140659_scout_limit_ladder_v1_process_query_scout_off_aligned_r3`
- Run name: `scout_limit_ladder_v1_process_query_scout_off_aligned_r3`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `4889.7`
- P95 latency ms: `10792.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 4342 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| LT1_CL2 | success | 3926 | True | public.orders, public.order_details, public.customers |
| LT1_CL6 | success | 4025 | True | public.orders |
| LT2_CL10 | success | 6625 | False |  |
| LT2_CL2 | success | 2926 | True | public.orders, public.order_details |
| LT2_CL6 | success | 4918 | False |  |
| LT3_CL10 | success | 7530 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| LT3_CL2 | success | 10792 | True | public.order_details, public.orders |
| LT3_CL6 | success | 2174 | False |  |
| LT4_CL10 | success | 5854 | False |  |
| LT4_CL2 | success | 4227 | True | public.orders, public.order_details |
| LT4_CL6 | success | 4267 | False |  |
| LT5_CL10 | success | 3348 | True | public.order_details, public.orders |
| LT5_CL2 | success | 6055 | True | public.orders, public.order_details |
| LT5_CL6 | success | 2337 | False |  |
