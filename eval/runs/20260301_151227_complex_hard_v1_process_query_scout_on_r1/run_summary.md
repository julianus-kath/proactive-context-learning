# /process_query Northwind Run (scout_on)

- Run ID: `20260301_151227_complex_hard_v1_process_query_scout_on_r1`
- Run name: `complex_hard_v1_process_query_scout_on_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `8121.7`
- P95 latency ms: `18454.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 18454 | True | public.orders, MonthlyRevenue, FirstLastMonthRevenue, CustomerGrowth, public.customers |
| HX10 | success | 4068 | True | public.customers, public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| HX11 | success | 4574 | True | public.orders, public.order_details |
| HX12 | success | 11502 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 8919 | True | public.orders, public.order_details, public.employees, regional_sales, regional_totals |
| HX14 | success | 8923 | True | public.orders, public.order_details, CustomerOrderValues, public.products, CustomerAverageOrderValue, public.customers, CustomerProductFamilies, AverageOrderValue |
| HX15 | success | 6575 | False |  |
| HX2 | success | 14459 | True | public.orders, public.order_details, RegionUmsatz, public.region, MedianAuftragszahl |
| HX3 | success | 4379 | False |  |
| HX4 | success | 6474 | True | public.order_details, public.products, supplier_revenue, category_revenue |
| HX5 | success | 6233 | True | public.orders, public.order_details, CustomerOrderStats, AverageStats, public.customers |
| HX6 | success | 8363 | True | public.orders, public.order_details |
| HX7 | success | 9512 | True | public.order_details, product_pairs, product_totals |
| HX8 | success | 4651 | False |  |
| HX9 | success | 4740 | True | public.suppliers, public.products, public.order_details |
