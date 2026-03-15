# /process_query Northwind Run (scout_on)

- Run ID: `20260302_071815_complex_hard_v1_process_query_scout_on_r3`
- Run name: `complex_hard_v1_process_query_scout_on_r3`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7639.4`
- P95 latency ms: `12925.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 12925 | True | public.orders, public.order_details, MonthlySales, CustomerGrowth, FilteredCustomers, public.customers |
| HX10 | success | 4917 | True | public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| HX11 | success | 7515 | True | public.orders, public.order_details |
| HX12 | success | 7922 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 8370 | True | public.orders, public.order_details, public.employees, public.territories, public.region, regional_sales |
| HX14 | success | 10790 | True | public.orders, public.order_details, CustomerOrderValues, public.products, AverageOrderValue, ProductFamilyCount, public.customers |
| HX15 | success | 8239 | False |  |
| HX2 | success | 7149 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragsanzahl |
| HX3 | success | 5261 | False |  |
| HX4 | success | 4069 | True | public.order_details, public.products |
| HX5 | success | 9012 | True | public.orders, public.order_details, CustomerOrderStats, public.customers, AverageStats |
| HX6 | success | 7006 | True | public.orders, public.order_details |
| HX7 | success | 11171 | True | public.order_details, public.products, public.categories, ProductPairs, ProductCategories, CategoryPairs, LiftCalculation |
| HX8 | success | 5401 | False |  |
| HX9 | success | 4844 | True | public.suppliers, public.products, public.order_details |
