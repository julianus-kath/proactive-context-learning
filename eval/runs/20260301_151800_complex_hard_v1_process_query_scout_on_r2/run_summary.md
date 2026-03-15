# /process_query Northwind Run (scout_on)

- Run ID: `20260301_151800_complex_hard_v1_process_query_scout_on_r2`
- Run name: `complex_hard_v1_process_query_scout_on_r2`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `6087.3`
- P95 latency ms: `9854.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 9854 | True | public.orders, MonthlyRevenue, CustomerOrderCount, RevenueGrowth, public.customers |
| HX10 | success | 4130 | True | public.customers, public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| HX11 | success | 5089 | True | public.orders, public.order_details |
| HX12 | success | 8423 | True | o.order_date, public.order_details, public.orders, public.products, public.categories |
| HX13 | success | 7191 | True | public.orders, public.employees, regional_sales, region_totals |
| HX14 | success | 7006 | True | public.customers, public.orders, public.order_details, public.products |
| HX15 | success | 7156 | False |  |
| HX2 | success | 5117 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragszahl |
| HX3 | success | 3858 | False |  |
| HX4 | success | 5884 | True | public.order_details, public.products, SupplierRevenue, CategoryRevenue |
| HX5 | success | 5482 | True | public.order_details, public.orders, CustomerMetrics, public.customers, AverageValues |
| HX6 | success | 6378 | True | public.orders, public.order_details |
| HX7 | success | 7882 | True | public.order_details, public.products, ProductPairs, ProductCounts, LiftCalculation |
| HX8 | success | 4179 | False |  |
| HX9 | success | 3681 | True | public.suppliers, public.products, public.order_details |
