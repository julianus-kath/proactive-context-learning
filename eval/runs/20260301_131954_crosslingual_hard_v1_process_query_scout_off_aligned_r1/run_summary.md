# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_131954_crosslingual_hard_v1_process_query_scout_off_aligned_r1`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `4315.2`
- P95 latency ms: `6399.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 3499 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 3873 | False |  |
| CL11 | success | 3923 | False |  |
| CL12 | success | 4417 | True | public.orders, public.order_details |
| CL2 | success | 3726 | True | public.orders, public.order_details |
| CL3 | success | 4820 | False |  |
| CL4 | success | 3503 | True | public.orders |
| CL5 | success | 3551 | True | public.customers, public.orders |
| CL6 | success | 5446 | True | public.orders |
| CL7 | success | 6399 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 5453 | True | public.customers, public.orders, public.order_details |
| CL9 | success | 3172 | True | public.suppliers, public.products, public.order_details |
