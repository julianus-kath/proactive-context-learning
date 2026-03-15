# /process_query Northwind Run (scout_on)

- Run ID: `20260309_161345_underspecified_v1_process_query_scout_on_r3`
- Run name: `underspecified_v1_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `8350.6`
- P95 latency ms: `17356.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 10506 | True | public.customers, public.orders, public.order_details |
| US_CL10_U2 | success | 6250 | True | public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| US_CL10_U3 | success | 5155 | False |  |
| US_CL2_U1 | success | 8800 | True | public.order_details, public.orders |
| US_CL2_U2 | success | 17356 | True | public.orders, public.order_details |
| US_CL2_U3 | success | 7799 | True | public.order_details |
| US_CL3_U1 | success | 6052 | False |  |
| US_CL3_U2 | success | 5040 | False |  |
| US_CL3_U3 | success | 8208 | False |  |
| US_CL6_U1 | success | 10791 | False |  |
| US_CL6_U2 | success | 5496 | False |  |
| US_CL6_U3 | success | 8754 | False |  |
