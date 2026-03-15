# /process_query Northwind Run (scout_on)

- Run ID: `20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new`
- Run name: `scout_limit_probe_v2_process_query_scout_on_r_new`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `5939.4`
- P95 latency ms: `17885.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 7645 | False |  |
| P_CL10_L2 | success | 4426 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L3 | success | 8154 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L4 | success | 4785 | False |  |
| P_CL10_L5 | success | 4695 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 12463 | True | public.customers, public.orders |
| P_CL2_L1 | success | 17885 | True | public.orders, public.order_details, public.customers |
| P_CL2_L2 | success | 3989 | True | public.orders, public.order_details |
| P_CL2_L3 | success | 5297 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 4521 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 4193 | True | public.orders, public.order_details |
| P_CL2_L6 | success | 4787 | False |  |
| P_CL6_L1 | success | 3145 | True | public.orders |
| P_CL6_L2 | success | 2249 | False |  |
| P_CL6_L3 | success | 3654 | False |  |
| P_CL6_L4 | success | 2603 | False |  |
| P_CL6_L5 | success | 3878 | False |  |
| P_CL6_L6 | success | 8541 | False |  |
