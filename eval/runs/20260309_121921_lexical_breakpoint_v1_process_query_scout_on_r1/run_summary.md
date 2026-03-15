# /process_query Northwind Run (scout_on)

- Run ID: `20260309_121921_lexical_breakpoint_v1_process_query_scout_on_r1`
- Run name: `lexical_breakpoint_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `6693.8`
- P95 latency ms: `12379.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LB_CL10_LX1 | success | 6984 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| LB_CL10_LX2 | success | 5036 | False |  |
| LB_CL10_LX3 | success | 5300 | False |  |
| LB_CL2_LX1 | success | 5005 | True | public.orders, public.order_details |
| LB_CL2_LX2 | success | 8365 | True | public.orders, public.order_details, public.customers |
| LB_CL2_LX3 | success | 4089 | False |  |
| LB_CL3_LX1 | success | 4943 | False |  |
| LB_CL3_LX2 | success | 4881 | False |  |
| LB_CL3_LX3 | success | 9352 | False |  |
| LB_CL6_LX1 | success | 12379 | True | public.orders |
| LB_CL6_LX2 | success | 10735 | True | public.orders |
| LB_CL6_LX3 | success | 3256 | False |  |
