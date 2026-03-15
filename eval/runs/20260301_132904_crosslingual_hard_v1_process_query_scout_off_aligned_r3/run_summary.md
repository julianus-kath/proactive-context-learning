# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r3`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4968.9`
- P95 latency ms: `8903.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 4354 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 3688 | False |  |
| CL11 | success | 4782 | False |  |
| CL12 | success | 3935 | True | public.orders, public.order_details |
| CL2 | success | 3790 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 3927 | False |  |
| CL4 | success | 6535 | True | public.employees, public.employee_territories, public.customers |
| CL5 | success | 4914 | True | public.customers, public.orders |
| CL6 | success | 8903 | True | public.orders |
| CL7 | success | 5258 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 6288 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 3253 | True | public.suppliers, public.products, public.order_details |
