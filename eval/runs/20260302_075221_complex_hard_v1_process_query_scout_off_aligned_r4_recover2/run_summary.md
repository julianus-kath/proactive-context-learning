# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_075221_complex_hard_v1_process_query_scout_off_aligned_r4_recover2`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r4_recover2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `15`
- Failures: `0`
- Avg latency ms: `7635.1`
- P95 latency ms: `15460.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 11427 | True | public.orders, public.order_details, MonthlySales, CustomerGrowth, public.customers |
| HX10 | success | 11282 | True | public.customer_customer_demo, public.customer_demographics, public.customers, public.orders, public.order_details |
| HX11 | success | 6675 | True | public.orders, public.order_details |
| HX12 | success | 6599 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 7808 | True | public.orders, public.employees, public.territories, public.region, regional_sales |
| HX14 | success | 7516 | True | public.orders, public.order_details, public.products, CustomerOrderData, public.customers, AverageBasketValue |
| HX15 | success | 4009 | False |  |
| HX2 | success | 8176 | True | public.orders, public.order_details, OrderSummary, MedianOrderCount |
| HX3 | success | 4557 | False |  |
| HX4 | success | 5751 | True | public.order_details, public.products |
| HX5 | success | 6420 | True | public.orders, public.order_details, Rabatt_Nettoumsatz, Durchschnittswerte, public.customers |
| HX6 | success | 5946 | True | public.orders, public.order_details |
| HX7 | success | 15460 | True | public.order_details, public.products, product_pairs, category_totals, lift_values |
| HX8 | success | 8630 | False |  |
| HX9 | success | 4271 | True | public.suppliers, public.products, public.order_details |
