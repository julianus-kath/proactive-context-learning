# /process_query Northwind Run (scout_off_legacy_lexical)

- Run ID: `20260302_132202_scout_advantage_v1_process_query_scout_off_legacy_r1`
- Run name: `scout_advantage_v1_process_query_scout_off_legacy_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `9`
- Successes: `9`
- Failures: `0`
- Avg latency ms: `8593.8`
- P95 latency ms: `13452.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| SA1 | success | 7723 | True | public.order_details, public.orders, public.customers |
| SA2 | success | 5890 | True | public.order_details, public.orders, public.customers |
| SA3 | success | 13452 | True | public.order_details, public.orders |
| SA4 | success | 12015 | True | public.orders |
| SA5 | success | 8599 | True | public.orders, public.order_details |
| SA6 | success | 10936 | True | order_date, public.orders |
| SA7 | success | 7218 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| SA8 | success | 4867 | True | public.order_details, public.orders, public.customer_customer_demo, public.customer_demographics |
| SA9 | success | 6644 | True | public.customers, public.orders, public.order_details |
