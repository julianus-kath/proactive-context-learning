# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_075712_complex_hard_v1_process_query_scout_off_aligned_r5_recover2`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r5_recover2`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `14`
- Failures: `1`
- Avg latency ms: `12570.0`
- P95 latency ms: `72001.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | failed | 72001 | False |  |
| HX10 | success | 4668 | True | public.customers, public.orders, public.order_details, public.customer_customer_demo, public.customer_demographics |
| HX11 | success | 5529 | True | public.orders, public.order_details |
| HX12 | success | 5816 | True | o.order_date, public.orders, public.order_details, public.products, public.categories |
| HX13 | success | 11592 | True | public.orders, public.employees, public.order_details, regional_sales, region_totals |
| HX14 | success | 11559 | True | public.customers, public.orders, public.order_details, public.products |
| HX15 | success | 4572 | False |  |
| HX2 | success | 18569 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragszahl |
| HX3 | success | 4419 | False |  |
| HX4 | success | 4402 | True | public.order_details, public.products |
| HX5 | success | 6681 | True | public.order_details, public.orders, CustomerMetrics, public.customers, AverageValues |
| HX6 | success | 12143 | True | public.orders, public.order_details, UmsatzProAuftrag, DurchschnittlicherUmsatz |
| HX7 | success | 12917 | True | public.order_details, public.products, product_pairs, product_totals, lift_calculation |
| HX8 | success | 4811 | False |  |
| HX9 | success | 8871 | True | public.suppliers, public.products, public.order_details |
