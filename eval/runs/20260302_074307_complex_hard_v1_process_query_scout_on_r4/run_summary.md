# /process_query Northwind Run (scout_on)

- Run ID: `20260302_074307_complex_hard_v1_process_query_scout_on_r4`
- Run name: `complex_hard_v1_process_query_scout_on_r4`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7749.1`
- P95 latency ms: `17394.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 17394 | True | public.orders, public.order_details, MonthlyRevenue, FirstLastMonthRevenue, CustomerGrowth, public.customers |
| HX10 | success | 8749 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 5138 | True | public.orders, public.order_details |
| HX12 | success | 9979 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 14414 | True | public.orders, public.order_details, public.territories, public.employees, public.region, regional_totals |
| HX14 | success | 9154 | True | public.orders, public.order_details, public.products, AverageBasketValue, public.customers, ProductFamilyCount, OverallAverage |
| HX15 | success | 6568 | False |  |
| HX2 | success | 6565 | True | public.region, public.territories, public.orders, public.order_details, RegionUmsatz |
| HX3 | success | 4909 | False |  |
| HX4 | success | 3634 | True | public.order_details, public.products |
| HX5 | success | 6645 | True | public.order_details, public.orders, CustomerMetrics, public.customers, AverageValues |
| HX6 | success | 6818 | True | public.orders, public.order_details |
| HX7 | success | 6113 | True | public.order_details, public.products |
| HX8 | success | 4650 | False |  |
| HX9 | success | 5507 | True | public.suppliers, public.products, public.order_details |
