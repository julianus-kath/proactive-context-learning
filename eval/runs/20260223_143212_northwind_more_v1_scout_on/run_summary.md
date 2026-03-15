# /process_query Northwind Run (scout_on)

- Run ID: `20260223_143212_northwind_more_v1_scout_on`
- Run name: `northwind_more_v1_scout_on`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `30`
- Successes: `30`
- Failures: `0`
- Avg latency ms: `7893.8`
- P95 latency ms: `14351.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NW11 | success | 11376 | True | public.suppliers, public.products, public.order_details |
| NW12 | success | 5839 | True | public.customers, public.orders, public.order_details |
| NW13 | success | 11453 | True | public.orders, public.shippers |
| NW14 | success | 14351 | True | public.products |
| NW15 | success | 7734 | True | public.products, public.categories |
| NW16 | success | 6744 | True | public.employees, public.orders |
| NW17 | success | 4198 | True | public.customers, public.orders |
| NW18 | success | 6620 | True | public.orders |
| NW19 | success | 12063 | True | public.orders, public.customers, public.order_details, public.products, public.suppliers |
| NW20 | success | 7923 | True | public.order_details, public.products |
| NW21 | success | 3546 | True | public.orders, public.shippers |
| NW22 | success | 4642 | True | public.employee_territories, public.territories |
| NW23 | success | 4766 | True | public.employee_territories, public.employees, public.orders, public.order_details, public.territories |
| NW24 | success | 12340 | True | public.customers, public.orders, public.order_details |
| NW25 | success | 7803 | True | public.suppliers, public.products, public.categories, public.order_details |
| NW26 | success | 5436 | True | public.customers, public.orders, public.order_details |
| NW27 | success | 10498 | True | public.order_details, public.products |
| NW28 | success | 15107 | True | public.orders, public.order_details, public.customers |
| NW29 | success | 7833 | True | public.employees, public.orders, public.order_details |
| NW30 | success | 4165 | True | public.suppliers, public.products, public.order_details |
| NW31 | success | 7394 | True | public.products, public.order_details |
| NW32 | success | 7952 | True | public.customer_demographics, public.customer_customer_demo, public.customers, public.orders, public.order_details |
| NW33 | success | 6399 | True | public.employees, public.orders, public.customers |
| NW34 | success | 4535 | True | public.orders |
| NW35 | success | 7665 | True | public.customers, public.orders, public.order_details |
| NW36 | success | 14331 | True | public.products, public.categories |
| NW37 | success | 7868 | True | public.categories, public.products, public.suppliers, public.order_details |
| NW38 | success | 7022 | True | public.order_details, public.products |
| NW39 | success | 5635 | True | o.order_date, public.orders, public.order_details |
| NW40 | success | 3576 | True | public.employees, public.employee_territories, public.territories, public.region |
