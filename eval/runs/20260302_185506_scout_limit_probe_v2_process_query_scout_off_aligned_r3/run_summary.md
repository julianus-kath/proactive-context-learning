# /process_query Northwind Run (scout_off_aligned_r3)

- Run ID: `20260302_185506_scout_limit_probe_v2_process_query_scout_off_aligned_r3`
- Run name: `scout_limit_probe_v2_process_query_scout_off_aligned_r3`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `8605.5`
- P95 latency ms: `23595.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 6241 | False |  |
| P_CL10_L2 | success | 10866 | True | public.customers, public.orders, public.order_details |
| P_CL10_L3 | success | 10048 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| P_CL10_L4 | success | 4448 | False |  |
| P_CL10_L5 | success | 6128 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 18862 | True | public.customers, public.orders |
| P_CL2_L1 | success | 6873 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 5100 | True | public.orders, public.order_details |
| P_CL2_L3 | success | 6191 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 5740 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 5286 | True | public.orders, public.order_details |
| P_CL2_L6 | success | 5282 | False |  |
| P_CL6_L1 | success | 18152 | True | public.orders |
| P_CL6_L2 | success | 2888 | False |  |
| P_CL6_L3 | success | 7808 | False |  |
| P_CL6_L4 | success | 4690 | False |  |
| P_CL6_L5 | success | 6701 | False |  |
| P_CL6_L6 | success | 23595 | True | order_date, public.orders |
