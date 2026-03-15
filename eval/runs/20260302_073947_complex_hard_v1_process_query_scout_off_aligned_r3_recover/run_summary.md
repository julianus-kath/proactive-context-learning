# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_073947_complex_hard_v1_process_query_scout_off_aligned_r3_recover`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r3_recover`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `10653.7`
- P95 latency ms: `21304.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 20702 | True | public.orders, public.order_details, MonthlyRevenue, CustomerGrowth, public.customers |
| HX10 | success | 6370 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 12779 | True | public.orders, public.order_details |
| HX12 | success | 19300 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 9703 | True | public.orders, public.employees, public.region, regional_sales |
| HX14 | success | 10398 | True | public.orders, public.order_details, public.products, AverageBasketValue, public.customers, ProductFamilyCount, OverallAverage |
| HX15 | success | 12273 | False |  |
| HX2 | success | 8692 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragszahl |
| HX3 | success | 3507 | False |  |
| HX4 | success | 6482 | True | public.order_details, public.products, SupplierRevenue, CategoryRevenue |
| HX5 | success | 8567 | True | public.orders, public.order_details, CustomerOrderStats, AverageStats, public.customers |
| HX6 | success | 10214 | True | public.orders, public.order_details, public.employees |
| HX7 | success | 21304 | True | public.order_details, public.products, public.categories, ProductPairs, ProductCounts, CategoryCounts |
| HX8 | success | 5120 | False |  |
| HX9 | success | 4395 | True | public.suppliers, public.products, public.order_details |
