# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_152002_complex_hard_v1_process_query_scout_off_aligned_r2`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7590.4`
- P95 latency ms: `13274.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 13151 | True | public.orders, public.order_details, MonthlyRevenue, CustomerGrowth |
| HX10 | success | 3823 | True | public.customers, public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| HX11 | success | 5921 | True | public.orders, public.order_details |
| HX12 | success | 9649 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 8945 | True | public.orders, public.order_details, public.employees, public.territories, public.region, regional_sales |
| HX14 | success | 8139 | True | public.orders, public.order_details, public.products, CustomerOrderData, public.customers, AverageBasketValue |
| HX15 | success | 9948 | False |  |
| HX2 | success | 6483 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragszahl |
| HX3 | success | 4333 | False |  |
| HX4 | success | 4011 | True | public.order_details, public.products |
| HX5 | success | 6339 | True | public.orders, public.order_details, CustomerOrderStats, AverageStats, public.customers |
| HX6 | success | 13274 | True | public.orders, public.order_details, UmsatzProAuftrag, DurchschnittlicherUmsatz |
| HX7 | success | 10632 | True | public.order_details, product_pairs, product_totals, lift_calculation, public.products |
| HX8 | success | 4102 | False |  |
| HX9 | success | 5106 | True | public.suppliers, public.products, public.order_details |
