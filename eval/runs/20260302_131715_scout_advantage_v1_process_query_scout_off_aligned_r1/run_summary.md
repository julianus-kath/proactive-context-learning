# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_131715_scout_advantage_v1_process_query_scout_off_aligned_r1`
- Run name: `scout_advantage_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `9`
- Successes: `9`
- Failures: `0`
- Avg latency ms: `10600.4`
- P95 latency ms: `23452.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| SA1 | success | 6865 | False |  |
| SA2 | success | 5433 | True | public.orders, public.order_details, public.customers |
| SA3 | success | 10210 | True | public.orders, public.order_details |
| SA4 | success | 13307 | True | public.orders |
| SA5 | success | 7610 | False |  |
| SA6 | success | 9138 | True | public.orders |
| SA7 | success | 14807 | True | public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| SA8 | success | 23452 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| SA9 | success | 4582 | True | public.orders, public.order_details |
