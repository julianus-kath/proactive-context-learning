# /process_query Northwind Run (scout_off_legacy)

- Run ID: `20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2`
- Run name: `underspecified_v1_process_query_scout_off_legacy_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `9771.2`
- P95 latency ms: `16479.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 7853 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| US_CL10_U2 | success | 16479 | True | public.order_details, public.orders, public.customers |
| US_CL10_U3 | success | 7212 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| US_CL2_U1 | success | 10339 | False |  |
| US_CL2_U2 | success | 8852 | True | public.orders, public.order_details, public.customers |
| US_CL2_U3 | success | 9018 | True | public.order_details, public.products |
| US_CL3_U1 | success | 4199 | False |  |
| US_CL3_U2 | success | 13737 | True | public.orders, public.customers |
| US_CL3_U3 | success | 13923 | True | public.orders |
| US_CL6_U1 | success | 12546 | True | public.orders |
| US_CL6_U2 | success | 6343 | False |  |
| US_CL6_U3 | success | 6753 | False |  |
