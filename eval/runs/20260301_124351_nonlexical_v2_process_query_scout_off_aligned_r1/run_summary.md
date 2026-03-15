# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_124351_nonlexical_v2_process_query_scout_off_aligned_r1`
- Run name: `nonlexical_v2_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4590.7`
- P95 latency ms: `8826.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 4445 | True | public.products |
| NL10 | success | 3943 | True | public.customers, public.orders |
| NL11 | success | 4529 | True | public.orders |
| NL12 | success | 3809 | True | public.order_details, public.products |
| NL13 | success | 3203 | False |  |
| NL14 | success | 3347 | True | public.customers, public.orders, public.order_details |
| NL15 | success | 4820 | True | public.order_details, public.products |
| NL16 | success | 4894 | True | public.suppliers, public.products, public.order_details |
| NL17 | success | 3187 | False |  |
| NL18 | success | 4205 | True | public.employees, public.orders |
| NL19 | success | 8960 | False |  |
| NL2 | success | 4672 | True | public.orders, public.order_details |
| NL20 | success | 8826 | True | public.orders, public.order_details |
| NL3 | success | 2925 | True | public.orders, public.shippers |
| NL4 | success | 2737 | True | public.order_details, public.products |
| NL5 | success | 7602 | True | public.orders, public.order_details, public.customers |
| NL6 | success | 4032 | True | public.order_details, public.orders |
| NL7 | success | 3721 | True | public.order_details, public.products, public.suppliers |
| NL8 | success | 5168 | True | public.orders, public.shippers |
| NL9 | success | 2789 | True | public.orders |
