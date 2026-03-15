# /process_query Northwind Run (scout_off_aligned_r2)

- Run ID: `20260302_184950_scout_limit_probe_v2_process_query_scout_off_aligned_r2`
- Run name: `scout_limit_probe_v2_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `7523.9`
- P95 latency ms: `20243.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 6402 | False |  |
| P_CL10_L2 | success | 14761 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L3 | success | 11398 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L4 | success | 8159 | True | public.orders, public.order_details, public.customers |
| P_CL10_L5 | success | 4786 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 3584 | False |  |
| P_CL2_L1 | success | 4957 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 5026 | True | public.orders, public.order_details, public.customers |
| P_CL2_L3 | success | 6697 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 4728 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 5044 | False |  |
| P_CL2_L6 | success | 7635 | False |  |
| P_CL6_L1 | success | 5505 | True | public.orders |
| P_CL6_L2 | success | 3163 | False |  |
| P_CL6_L3 | success | 6853 | False |  |
| P_CL6_L4 | success | 5071 | False |  |
| P_CL6_L5 | success | 11419 | False |  |
| P_CL6_L6 | success | 20243 | True | order_date, public.orders |
