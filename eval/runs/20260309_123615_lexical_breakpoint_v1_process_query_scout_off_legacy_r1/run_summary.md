# /process_query Northwind Run (scout_off_legacy)

- Run ID: `20260309_123615_lexical_breakpoint_v1_process_query_scout_off_legacy_r1`
- Run name: `lexical_breakpoint_v1_process_query_scout_off_legacy_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `10036.1`
- P95 latency ms: `16262.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| LB_CL10_LX1 | success | 16262 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| LB_CL10_LX2 | success | 9703 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| LB_CL10_LX3 | success | 9286 | True | public.order_details, public.orders, public.customers |
| LB_CL2_LX1 | success | 13608 | True | public.order_details, public.orders, public.customers |
| LB_CL2_LX2 | success | 7731 | True | public.order_details, public.orders |
| LB_CL2_LX3 | success | 7776 | True | public.orders, public.order_details, public.territories, public.region |
| LB_CL3_LX1 | success | 4030 | False |  |
| LB_CL3_LX2 | success | 10610 | True | public.orders |
| LB_CL3_LX3 | success | 12893 | True | public.orders, public.shippers |
| LB_CL6_LX1 | success | 10594 | True | public.orders |
| LB_CL6_LX2 | success | 6545 | True | public.orders |
| LB_CL6_LX3 | success | 11395 | True | public.orders |
