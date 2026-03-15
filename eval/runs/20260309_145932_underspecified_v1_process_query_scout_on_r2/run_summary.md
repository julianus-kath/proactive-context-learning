# /process_query Northwind Run (scout_on)

- Run ID: `20260309_145932_underspecified_v1_process_query_scout_on_r2`
- Run name: `underspecified_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `10735.6`
- P95 latency ms: `20312.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 9907 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| US_CL10_U2 | success | 10441 | True | public.customer_customer_demo, public.customer_demographics, public.orders |
| US_CL10_U3 | success | 6047 | False |  |
| US_CL2_U1 | success | 20312 | True | public.order_details |
| US_CL2_U2 | success | 7951 | True | public.orders, public.order_details |
| US_CL2_U3 | success | 13328 | True | public.order_details |
| US_CL3_U1 | success | 7789 | False |  |
| US_CL3_U2 | success | 14839 | False |  |
| US_CL3_U3 | success | 9836 | False |  |
| US_CL6_U1 | success | 8765 | False |  |
| US_CL6_U2 | success | 5775 | False |  |
| US_CL6_U3 | success | 13837 | False |  |
