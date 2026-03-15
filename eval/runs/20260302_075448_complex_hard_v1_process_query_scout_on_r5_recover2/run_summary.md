# /process_query Northwind Run (scout_on)

- Run ID: `20260302_075448_complex_hard_v1_process_query_scout_on_r5_recover2`
- Run name: `complex_hard_v1_process_query_scout_on_r5_recover2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7466.7`
- P95 latency ms: `19679.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 19679 | True | public.orders, public.order_details, MonthlyRevenue, FirstLastMonthRevenue, CustomerGrowth, public.customers |
| HX10 | success | 6381 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 6098 | True | public.orders, public.order_details |
| HX12 | success | 8541 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 9556 | True | public.orders, public.order_details, public.employees, public.territories, public.region, regional_sales, region_totals |
| HX14 | success | 8949 | True | public.orders, public.order_details, public.products, AverageBasketValue, public.customers, ProductFamilyCount, OverallAverage |
| HX15 | success | 5774 | False |  |
| HX2 | success | 5996 | True | public.orders, public.order_details, RegionOrderStats, MedianOrderCount |
| HX3 | success | 4264 | False |  |
| HX4 | success | 4326 | True | public.order_details, public.products |
| HX5 | success | 8515 | True | public.orders, public.order_details, CustomerOrderStats, AverageStats, public.customers |
| HX6 | success | 5095 | True | public.orders, public.order_details, public.employees |
| HX7 | success | 9522 | True | public.order_details, public.products, public.orders, ProductPairs, CategoryCounts, ExpectedPairs, Lift |
| HX8 | success | 5606 | False |  |
| HX9 | success | 3698 | True | public.suppliers, public.products, public.order_details |
