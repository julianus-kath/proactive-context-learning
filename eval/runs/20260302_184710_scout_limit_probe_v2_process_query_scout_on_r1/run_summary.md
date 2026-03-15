# /process_query Northwind Run (scout_on_r1)

- Run ID: `20260302_184710_scout_limit_probe_v2_process_query_scout_on_r1`
- Run name: `scout_limit_probe_v2_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `6235.4`
- P95 latency ms: `13287.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 8081 | False |  |
| P_CL10_L2 | success | 13287 | True | public.customers, public.orders, public.order_details |
| P_CL10_L3 | success | 10531 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L4 | success | 7534 | True | public.orders, public.order_details, public.customers |
| P_CL10_L5 | success | 4719 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| P_CL10_L6 | success | 4740 | False |  |
| P_CL2_L1 | success | 4229 | True | public.orders, public.order_details |
| P_CL2_L2 | success | 5492 | True | public.orders, public.order_details, public.customers |
| P_CL2_L3 | success | 5965 | True | public.orders, public.order_details |
| P_CL2_L4 | success | 6632 | True | public.orders, public.order_details |
| P_CL2_L5 | success | 6087 | False |  |
| P_CL2_L6 | success | 6086 | False |  |
| P_CL6_L1 | success | 5623 | True | public.orders |
| P_CL6_L2 | success | 2547 | False |  |
| P_CL6_L3 | success | 2602 | False |  |
| P_CL6_L4 | success | 2934 | False |  |
| P_CL6_L5 | success | 6290 | False |  |
| P_CL6_L6 | success | 8858 | False |  |
