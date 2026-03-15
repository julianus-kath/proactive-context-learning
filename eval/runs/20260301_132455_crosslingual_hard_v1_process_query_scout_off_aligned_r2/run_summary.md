# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_132455_crosslingual_hard_v1_process_query_scout_off_aligned_r2`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4361.8`
- P95 latency ms: `7066.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 4077 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 3710 | False |  |
| CL11 | success | 3447 | False |  |
| CL12 | success | 4412 | True | public.orders, public.order_details |
| CL2 | success | 7066 | True | public.orders, public.order_details |
| CL3 | success | 4688 | False |  |
| CL4 | success | 4124 | True | public.orders |
| CL5 | success | 3482 | True | public.customers, public.orders |
| CL6 | success | 3349 | False |  |
| CL7 | success | 5122 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 6165 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 2700 | True | public.suppliers, public.products, public.order_details |
