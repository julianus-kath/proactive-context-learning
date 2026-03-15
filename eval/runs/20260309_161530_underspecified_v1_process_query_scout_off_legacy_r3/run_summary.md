# /process_query Northwind Run (scout_off_legacy)

- Run ID: `20260309_161530_underspecified_v1_process_query_scout_off_legacy_r3`
- Run name: `underspecified_v1_process_query_scout_off_legacy_r3`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `9677.3`
- P95 latency ms: `17183.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| US_CL10_U1 | success | 17183 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| US_CL10_U2 | success | 7697 | True | public.order_details, public.orders, public.customers |
| US_CL10_U3 | success | 7714 | False |  |
| US_CL2_U1 | success | 8305 | True | public.order_details, public.orders |
| US_CL2_U2 | success | 9551 | True | public.orders, public.order_details, public.customers |
| US_CL2_U3 | success | 8307 | True | public.order_details, public.products |
| US_CL3_U1 | success | 5466 | False |  |
| US_CL3_U2 | success | 8823 | True | public.orders, public.customers |
| US_CL3_U3 | success | 15276 | True | public.orders |
| US_CL6_U1 | success | 13742 | True | public.orders |
| US_CL6_U2 | success | 7897 | False |  |
| US_CL6_U3 | success | 6167 | False |  |
