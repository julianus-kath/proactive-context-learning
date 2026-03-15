# /process_query Northwind Run (scout_off_aligned_r1_recover)

- Run ID: `20260302_184403_scout_limit_probe_v2_process_query_scout_off_aligned_r1_recover`
- Run name: `scout_limit_probe_v2_process_query_scout_off_aligned_r1_recover`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `7986.1`
- P95 latency ms: `18651.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 7861 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L2 | success | 10053 | True | public.orders, public.order_details, public.customers |
| P_CL10_L3 | success | 13267 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L4 | success | 3771 | False |  |
| P_CL10_L5 | success | 5206 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 3089 | False |  |
| P_CL2_L1 | success | 6973 | True | public.order_details, public.orders, public.customers |
| P_CL2_L2 | success | 5575 | True | public.orders, public.order_details, public.customers |
| P_CL2_L3 | success | 5582 | False |  |
| P_CL2_L4 | success | 10096 | True | public.order_details, public.orders, public.region |
| P_CL2_L5 | success | 6493 | True | public.orders, public.order_details |
| P_CL2_L6 | success | 8839 | True | public.orders, public.order_details, public.region |
| P_CL6_L1 | success | 18347 | True | public.orders |
| P_CL6_L2 | success | 2881 | False |  |
| P_CL6_L3 | success | 3960 | False |  |
| P_CL6_L4 | success | 6628 | False |  |
| P_CL6_L5 | success | 6477 | False |  |
| P_CL6_L6 | success | 18651 | True | public.orders |
