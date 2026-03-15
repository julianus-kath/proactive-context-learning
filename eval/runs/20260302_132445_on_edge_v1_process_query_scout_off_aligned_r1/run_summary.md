# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_132445_on_edge_v1_process_query_scout_off_aligned_r1`
- Run name: `on_edge_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `3`
- Successes: `3`
- Failures: `0`
- Avg latency ms: `8054.3`
- P95 latency ms: `9978.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| OE1 | success | 9978 | True | public.customers, public.orders, public.order_details |
| OE2 | success | 7156 | False |  |
| OE3 | success | 7029 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
