# /process_query Northwind Run (scout_on)

- Run ID: `20260302_132546_on_edge_v1_process_query_scout_on_r1`
- Run name: `on_edge_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `3`
- Successes: `3`
- Failures: `0`
- Avg latency ms: `11064.7`
- P95 latency ms: `14919.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| OE1 | success | 14919 | True | public.orders, public.order_details |
| OE2 | success | 9177 | True | public.orders |
| OE3 | success | 9098 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
