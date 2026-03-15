# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_071346_crosslingual_hard_v1_process_query_scout_off_aligned_r4`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r4`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `5497.4`
- P95 latency ms: `8722.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3813 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 5965 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| CL11 | success | 4419 | False |  |
| CL12 | success | 5035 | True | public.orders, public.order_details |
| CL2 | success | 7245 | True | public.orders, public.order_details |
| CL3 | success | 5218 | False |  |
| CL4 | success | 4672 | True | public.orders |
| CL5 | success | 5221 | True | public.customers, public.orders |
| CL6 | success | 4024 | False |  |
| CL7 | success | 7037 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 8722 | True | public.customers, public.orders |
| CL9 | success | 4598 | True | public.suppliers, public.products, public.order_details |
