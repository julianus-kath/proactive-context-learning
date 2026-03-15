# /process_query Northwind Run (scout_on_r2)

- Run ID: `20260302_185226_scout_limit_probe_v2_process_query_scout_on_r2`
- Run name: `scout_limit_probe_v2_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `7003.4`
- P95 latency ms: `24738.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 3924 | False |  |
| P_CL10_L2 | success | 10318 | False |  |
| P_CL10_L3 | success | 7767 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L4 | success | 5012 | True | public.orders, public.order_details, public.customers |
| P_CL10_L5 | success | 4686 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 24738 | True | public.customers, public.orders, public.order_details |
| P_CL2_L1 | success | 5513 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 4462 | True | public.orders, public.order_details |
| P_CL2_L3 | success | 7069 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 4976 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 6862 | True | public.order_details, public.orders, public.customers |
| P_CL2_L6 | success | 9110 | True | public.orders, public.order_details, public.customers, public.region |
| P_CL6_L1 | success | 6093 | False |  |
| P_CL6_L2 | success | 3154 | False |  |
| P_CL6_L3 | success | 3653 | False |  |
| P_CL6_L4 | success | 5743 | False |  |
| P_CL6_L5 | success | 6373 | False |  |
| P_CL6_L6 | success | 6609 | False |  |
