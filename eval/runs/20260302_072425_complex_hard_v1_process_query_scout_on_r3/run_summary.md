# /process_query Northwind Run (scout_on)

- Run ID: `20260302_072425_complex_hard_v1_process_query_scout_on_r3`
- Run name: `complex_hard_v1_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `8801.2`
- P95 latency ms: `19810.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 19810 | True | public.orders, MonthlySales, FirstLastMonthRevenue, public.customers |
| HX10 | success | 6939 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 5825 | True | public.orders, public.order_details |
| HX12 | success | 17689 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 9662 | True | public.orders, public.order_details, public.employees, public.territories, public.region, regional_sales, region_totals |
| HX14 | success | 10131 | True | public.orders, public.order_details, public.products, CustomerOrderSummary, AverageOrderValue, public.customers |
| HX15 | success | 5207 | False |  |
| HX2 | success | 6562 | True | public.orders, public.order_details, RegionOrderSummary, MedianOrderCount |
| HX3 | success | 4212 | False |  |
| HX4 | success | 8199 | True | public.order_details, public.products, SupplierRevenue, CategoryRevenue |
| HX5 | success | 6683 | True | public.order_details, public.orders, CustomerMetrics, public.customers, AverageValues |
| HX6 | success | 6180 | True | public.orders, public.order_details |
| HX7 | success | 10373 | True | public.order_details, public.products, product_pairs, product_totals |
| HX8 | success | 8669 | False |  |
| HX9 | success | 5877 | True | public.suppliers, public.products, public.order_details |
