# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_132916_crosslingual_hard_v1_process_query_scout_off_aligned_r6`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r6`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `7770.6`
- P95 latency ms: `24784.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 4761 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 8125 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| CL11 | success | 6158 | False |  |
| CL12 | success | 6390 | True | public.orders, public.order_details |
| CL2 | success | 9072 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 5053 | False |  |
| CL4 | success | 24784 | True | public.orders |
| CL5 | success | 5133 | True | public.customers, public.orders |
| CL6 | success | 5501 | False |  |
| CL7 | success | 6630 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 6623 | True | public.customers, public.orders |
| CL9 | success | 5017 | True | public.suppliers, public.products, public.order_details |
