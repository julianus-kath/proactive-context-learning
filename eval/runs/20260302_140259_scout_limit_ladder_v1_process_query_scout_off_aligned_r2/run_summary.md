# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_140259_scout_limit_ladder_v1_process_query_scout_off_aligned_r2`
- Run name: `scout_limit_ladder_v1_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7501.7`
- P95 latency ms: `25833.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 6729 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| LT1_CL2 | success | 4974 | True | public.orders, public.order_details |
| LT1_CL6 | success | 5408 | True | public.orders |
| LT2_CL10 | success | 4216 | False |  |
| LT2_CL2 | success | 3265 | True | public.orders, public.order_details |
| LT2_CL6 | success | 5851 | False |  |
| LT3_CL10 | success | 10156 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| LT3_CL2 | success | 11762 | False |  |
| LT3_CL6 | success | 25833 | True | public.orders |
| LT4_CL10 | success | 3736 | False |  |
| LT4_CL2 | success | 8004 | True | public.orders, public.order_details |
| LT4_CL6 | success | 4752 | False |  |
| LT5_CL10 | success | 4688 | True | public.order_details, public.products |
| LT5_CL2 | success | 6061 | True | public.orders, public.order_details |
| LT5_CL6 | success | 7091 | False |  |
