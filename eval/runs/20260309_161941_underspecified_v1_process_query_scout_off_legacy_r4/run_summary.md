# /process_query Northwind Run (scout_off_legacy)

- Run ID: `20260309_161941_underspecified_v1_process_query_scout_off_legacy_r4`
- Run name: `underspecified_v1_process_query_scout_off_legacy_r4`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `10349.2`
- P95 latency ms: `16301.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 10293 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| US_CL10_U2 | success | 15842 | True | public.order_details, public.orders, public.customers |
| US_CL10_U3 | success | 8029 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| US_CL2_U1 | success | 16301 | True | public.order_details, public.orders |
| US_CL2_U2 | success | 11237 | True | public.orders, public.order_details, public.customers, public.region |
| US_CL2_U3 | success | 4375 | True | public.order_details, public.products |
| US_CL3_U1 | success | 5295 | False |  |
| US_CL3_U2 | success | 13379 | True | public.orders, public.customers |
| US_CL3_U3 | success | 11097 | True | public.orders |
| US_CL6_U1 | success | 14553 | True | public.orders |
| US_CL6_U2 | success | 7474 | False |  |
| US_CL6_U3 | success | 6316 | False |  |
