# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_071708_crosslingual_hard_v1_process_query_scout_off_aligned_r5`
- Run name: `crosslingual_hard_v1_process_query_scout_off_aligned_r5`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `12`
- Successes: `12`
- Failures: `0`
- Avg latency ms: `5482.2`
- P95 latency ms: `7409.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| CL1 | success | 6720 | True | public.order_details, public.products, public.suppliers |
| CL10 | success | 3960 | False |  |
| CL11 | success | 4682 | False |  |
| CL12 | success | 5007 | True | public.orders, public.order_details |
| CL2 | success | 7409 | True | public.customers, public.orders, public.order_details |
| CL3 | success | 6359 | False |  |
| CL4 | success | 5623 | True | public.orders |
| CL5 | success | 2690 | True | public.customers, public.orders |
| CL6 | success | 4840 | False |  |
| CL7 | success | 6740 | True | public.orders, public.order_details, public.territories, public.region |
| CL8 | success | 5609 | True | public.customers, public.orders |
| CL9 | success | 6148 | True | public.suppliers, public.products, public.order_details |
