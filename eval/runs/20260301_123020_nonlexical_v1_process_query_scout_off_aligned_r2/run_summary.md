# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_123020_nonlexical_v1_process_query_scout_off_aligned_r2`
- Run name: `nonlexical_v1_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4372.8`
- P95 latency ms: `6513.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 3213 | True | public.order_details |
| NL10 | success | 5995 | True | public.customers, public.orders |
| NL11 | success | 3389 | True | public.orders |
| NL12 | success | 4170 | True | public.order_details, public.products |
| NL13 | success | 3698 | False |  |
| NL14 | success | 3719 | True | public.customers, public.orders, public.order_details |
| NL15 | success | 4931 | True | public.order_details, public.products |
| NL16 | success | 8247 | True | public.suppliers, public.products, public.order_details |
| NL17 | success | 2948 | False |  |
| NL18 | success | 2966 | True | public.employees, public.orders, public.customers |
| NL19 | success | 5636 | True | public.order_details, public.products |
| NL2 | success | 4641 | True | public.order_details, public.orders |
| NL20 | success | 2752 | False |  |
| NL3 | success | 6513 | True | public.orders, public.shippers |
| NL4 | success | 3848 | False |  |
| NL5 | success | 5031 | True | public.orders, public.customers, public.order_details |
| NL6 | success | 4330 | True | public.order_details, public.orders |
| NL7 | success | 4028 | True | public.order_details, public.products |
| NL8 | success | 4621 | True | public.orders, public.shippers |
| NL9 | success | 2779 | True | public.orders |
