# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_151456_complex_hard_v1_process_query_scout_off_aligned_r1`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `8354.5`
- P95 latency ms: `16174.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 16174 | True | public.orders, public.order_details, MonthlyRevenue, CustomerGrowth, CustomerOrderCount, public.customers |
| HX10 | success | 6679 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 5218 | True | public.orders, public.order_details |
| HX12 | success | 9484 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 11416 | True | public.orders, public.order_details, public.territories, public.region, public.employees, employee_revenue, regional_revenue |
| HX14 | success | 8419 | True | public.orders, public.order_details, public.products, AverageBasketValue, public.customers, ProductFamilyCount, OverallAverage |
| HX15 | success | 9542 | False |  |
| HX2 | success | 9878 | True | public.orders, public.order_details, RegionOrderCount, RegionRevenue, MedianOrderCount |
| HX3 | success | 4426 | False |  |
| HX4 | success | 4549 | True | public.order_details, public.products |
| HX5 | success | 10178 | True | public.orders, public.order_details, OrderSummary, CustomerStats, public.customers, OverallStats |
| HX6 | success | 10793 | True | public.orders, public.order_details, public.employees |
| HX7 | success | 9536 | True | public.order_details, public.products, ProductPairs, ProductCounts, LiftCalculation |
| HX8 | success | 4487 | False |  |
| HX9 | success | 4539 | True | public.suppliers, public.products, public.order_details |
