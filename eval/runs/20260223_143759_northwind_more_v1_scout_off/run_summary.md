# /process_query Northwind Run (scout_off)

- Run ID: `20260223_143759_northwind_more_v1_scout_off`
- Run name: `northwind_more_v1_scout_off`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog. Catalog source is schema_catalog.
- Total queries: `30`
- Successes: `30`
- Failures: `0`
- Avg latency ms: `12379.9`
- P95 latency ms: `29296.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW11 | success | 11627 | True | public.suppliers, public.products, public.order_details |
| NW12 | success | 6542 | True | public.customers, public.orders, public.order_details |
| NW13 | success | 12434 | True | public.orders, public.shippers |
| NW14 | success | 8332 | True | public.products |
| NW15 | success | 7077 | True | public.products, public.categories |
| NW16 | success | 5284 | True | public.employees, public.orders |
| NW17 | success | 2965 | True | public.customers, public.orders |
| NW18 | success | 7240 | True | public.orders |
| NW19 | success | 20354 | True | public.orders, public.customers, public.order_details, public.products, public.suppliers |
| NW20 | success | 4977 | True | public.order_details, public.products |
| NW21 | success | 4444 | True | public.orders, public.shippers |
| NW22 | success | 4489 | True | public.territories, public.employee_territories |
| NW23 | success | 6935 | True | public.employee_territories, public.employees, public.orders, public.order_details, public.territories |
| NW24 | success | 5204 | True | public.customers, public.orders, public.order_details |
| NW25 | success | 6245 | True | public.suppliers, public.products, public.categories, public.order_details |
| NW26 | success | 8012 | True | public.customers, public.orders, public.order_details |
| NW27 | success | 5749 | True | public.order_details, public.products, public.categories |
| NW28 | success | 12637 | True | public.orders, public.order_details, public.customers |
| NW29 | success | 6981 | True | public.employees, public.orders, public.order_details |
| NW30 | success | 5423 | True | public.suppliers, public.products, public.order_details |
| NW31 | success | 12440 | True | public.products, public.order_details |
| NW32 | success | 19520 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| NW33 | success | 25519 | True | public.employees, public.orders |
| NW34 | success | 20951 | True | public.orders |
| NW35 | success | 28412 | True | public.customers, public.orders, public.order_details |
| NW36 | success | 5213 | True | public.products, public.categories |
| NW37 | success | 29296 | True | public.suppliers, public.products, public.categories, public.order_details |
| NW38 | success | 22631 | True | public.order_details, public.products |
| NW39 | success | 24487 | True | o.order_date, public.orders, public.order_details |
| NW40 | success | 29978 | True | public.employees, public.employee_territories, public.territories, public.region |
