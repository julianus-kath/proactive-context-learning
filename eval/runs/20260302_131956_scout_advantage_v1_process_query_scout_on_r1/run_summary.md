# /process_query Northwind Run (scout_on)

- Run ID: `20260302_131956_scout_advantage_v1_process_query_scout_on_r1`
- Run name: `scout_advantage_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `9`
- Successes: `9`
- Failures: `0`
- Avg latency ms: `7785.7`
- P95 latency ms: `16218.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| SA1 | success | 4033 | False |  |
| SA2 | success | 4598 | True | public.orders, public.order_details, public.customers |
| SA3 | success | 4333 | True | public.orders, public.order_details |
| SA4 | success | 9533 | False |  |
| SA5 | success | 16218 | True | public.orders, public.order_details |
| SA6 | success | 3186 | False |  |
| SA7 | success | 16175 | False |  |
| SA8 | success | 7176 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| SA9 | success | 4819 | True | public.orders, public.order_details |
