# /process_query Northwind Run (scout_off_aligned_r1)

- Run ID: `20260302_184107_scout_limit_probe_v2_process_query_scout_off_aligned_r1`
- Run name: `scout_limit_probe_v2_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `9582.1`
- P95 latency ms: `21748.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 12406 | True | public.order_details, public.orders |
| P_CL10_L2 | success | 9598 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L3 | success | 10857 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| P_CL10_L4 | success | 8710 | False |  |
| P_CL10_L5 | success | 6353 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 21748 | True | public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL2_L1 | success | 7541 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 6075 | True | public.orders, public.order_details |
| P_CL2_L3 | success | 6652 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 14672 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 4724 | False |  |
| P_CL2_L6 | success | 5735 | False |  |
| P_CL6_L1 | success | 6322 | True | public.orders |
| P_CL6_L2 | success | 7133 | False |  |
| P_CL6_L3 | success | 17015 | True | order_date, public.orders, public.order_details |
| P_CL6_L4 | success | 3453 | False |  |
| P_CL6_L5 | success | 6138 | False |  |
| P_CL6_L6 | success | 17346 | True | order_date, public.orders |
