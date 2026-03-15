# /process_query Northwind Run (scout_off_legacy_lexical)

- Run ID: `20260301_132133_crosslingual_hard_v1_process_query_scout_off_legacy_r1`
- Run name: `crosslingual_hard_v1_process_query_scout_off_legacy_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `5859.2`
- P95 latency ms: `11772.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 4043 | True | public.suppliers, public.products, public.order_details |
| CL10 | success | 4728 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| CL11 | success | 6095 | True | public.orders, public.employees |
| CL12 | success | 5806 | True | public.orders, public.order_details |
| CL2 | success | 10031 | True | public.order_details, public.orders, public.customers |
| CL3 | success | 6602 | True | public.orders |
| CL4 | success | 3465 | True | public.employees, public.orders |
| CL5 | success | 3096 | True | public.customers, public.orders |
| CL6 | success | 7667 | True | public.orders |
| CL7 | success | 11772 | True | public.orders, public.order_details, public.customers |
| CL8 | success | 3295 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 3710 | True | public.suppliers, public.products, public.order_details |
