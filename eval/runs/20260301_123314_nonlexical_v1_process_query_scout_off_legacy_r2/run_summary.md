# /process_query Northwind Run (scout_off_legacy_lexical)

- Run ID: `20260301_123314_nonlexical_v1_process_query_scout_off_legacy_r2`
- Run name: `nonlexical_v1_process_query_scout_off_legacy_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `20`
- Successes: `20`
- Failures: `0`
- Avg latency ms: `4930.4`
- P95 latency ms: `7675.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 3143 | True | public.order_details, public.products |
| NL10 | success | 7675 | True | public.customers, public.orders |
| NL11 | success | 4165 | True | public.orders |
| NL12 | success | 3848 | True | public.order_details, public.products |
| NL13 | success | 7051 | True | public.territories, public.employee_territories, public.orders, public.order_details |
| NL14 | success | 4036 | True | public.customers, public.orders |
| NL15 | success | 5245 | True | public.order_details, public.products |
| NL16 | success | 3185 | True | public.suppliers, public.products, public.order_details |
| NL17 | success | 5971 | True | public.order_details, public.orders, public.customer_customer_demo, public.customer_demographics |
| NL18 | success | 2686 | True | public.orders, public.employees |
| NL19 | success | 4334 | True | public.order_details, public.products, public.categories |
| NL2 | success | 4344 | True | public.order_details, public.orders, public.customers |
| NL20 | success | 5356 | True | order_date, public.orders, public.order_details |
| NL3 | success | 6008 | True | public.orders |
| NL4 | success | 5843 | True | public.order_details, public.products, public.categories |
| NL5 | success | 4879 | True | public.order_details, public.orders, public.customers |
| NL6 | success | 8194 | True | public.order_details, public.orders |
| NL7 | success | 3625 | True | public.suppliers, public.products, public.order_details |
| NL8 | success | 5721 | True | public.orders, public.shippers |
| NL9 | success | 3298 | True | public.orders, public.employees |
