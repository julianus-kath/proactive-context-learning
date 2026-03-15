# /process_query Northwind Run (scout_on_r3)

- Run ID: `20260302_185811_scout_limit_probe_v2_process_query_scout_on_r3`
- Run name: `scout_limit_probe_v2_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `7557.4`
- P95 latency ms: `16933.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 5825 | False |  |
| P_CL10_L2 | success | 7369 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L3 | success | 7377 | False |  |
| P_CL10_L4 | success | 6615 | False |  |
| P_CL10_L5 | success | 4980 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 16933 | True | public.orders, public.order_details, public.customers |
| P_CL2_L1 | success | 5783 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 4629 | True | public.orders, public.order_details |
| P_CL2_L3 | success | 6985 | False |  |
| P_CL2_L4 | success | 6535 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 9272 | True | public.orders, public.order_details |
| P_CL2_L6 | success | 8609 | True | public.orders, public.order_details |
| P_CL6_L1 | success | 13813 | True | public.orders |
| P_CL6_L2 | success | 6900 | False |  |
| P_CL6_L3 | success | 6860 | False |  |
| P_CL6_L4 | success | 3928 | False |  |
| P_CL6_L5 | success | 5075 | False |  |
| P_CL6_L6 | success | 8545 | False |  |
