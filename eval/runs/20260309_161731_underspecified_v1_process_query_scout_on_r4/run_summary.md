# /process_query Northwind Run (scout_on)

- Run ID: `20260309_161731_underspecified_v1_process_query_scout_on_r4`
- Run name: `underspecified_v1_process_query_scout_on_r4`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `10490.2`
- P95 latency ms: `20623.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 17963 | True | public.customers, public.customer_customer_demo, public.customer_demographics, public.orders, public.order_details |
| US_CL10_U2 | success | 11945 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders |
| US_CL10_U3 | success | 12956 | True | public.orders, public.order_details, public.customers |
| US_CL2_U1 | success | 6158 | True | public.orders, public.order_details |
| US_CL2_U2 | success | 8807 | True | public.orders, public.order_details |
| US_CL2_U3 | success | 9103 | True | public.order_details |
| US_CL3_U1 | success | 5659 | False |  |
| US_CL3_U2 | success | 20623 | False |  |
| US_CL3_U3 | success | 11946 | False |  |
| US_CL6_U1 | success | 6027 | False |  |
| US_CL6_U2 | success | 6779 | False |  |
| US_CL6_U3 | success | 7917 | False |  |
