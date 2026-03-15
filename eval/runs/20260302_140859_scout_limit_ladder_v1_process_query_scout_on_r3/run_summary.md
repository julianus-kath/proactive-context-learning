# /process_query Northwind Run (scout_on)

- Run ID: `20260302_140859_scout_limit_ladder_v1_process_query_scout_on_r3`
- Run name: `scout_limit_ladder_v1_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `6650.3`
- P95 latency ms: `19841.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LT1_CL10 | success | 8763 | True | public.orders, public.order_details, public.customers |
| LT1_CL2 | success | 4188 | True | public.orders, public.order_details |
| LT1_CL6 | success | 4550 | True | public.orders |
| LT2_CL10 | success | 19841 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| LT2_CL2 | success | 4602 | True | public.orders, public.order_details |
| LT2_CL6 | success | 19712 | True | public.orders |
| LT3_CL10 | success | 4635 | False |  |
| LT3_CL2 | success | 5403 | True | public.orders, public.order_details |
| LT3_CL6 | success | 2685 | False |  |
| LT4_CL10 | success | 4822 | False |  |
| LT4_CL2 | success | 4612 | True | public.orders, public.order_details |
| LT4_CL6 | success | 2914 | False |  |
| LT5_CL10 | success | 4809 | True | public.order_details, public.orders, public.products |
| LT5_CL2 | success | 4881 | True | public.orders, public.order_details |
| LT5_CL6 | success | 3338 | False |  |
