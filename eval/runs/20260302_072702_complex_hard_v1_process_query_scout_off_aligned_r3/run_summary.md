# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260302_072702_complex_hard_v1_process_query_scout_off_aligned_r3`
- Run name: `complex_hard_v1_process_query_scout_off_aligned_r3`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `15`
- Successes: `6`
- Failures: `9`
- Avg latency ms: `4600.1`
- P95 latency ms: `12358.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| HX1 | success | 12358 | True | public.orders, public.order_details, MonthlyRevenue, CustomerGrowth |
| HX10 | failed | 1898 | False |  |
| HX11 | failed | 1863 | False |  |
| HX12 | failed | 1879 | False |  |
| HX13 | failed | 2029 | False |  |
| HX14 | failed | 1798 | False |  |
| HX15 | failed | 1752 | False |  |
| HX2 | success | 7879 | True | public.orders, public.order_details, RegionUmsatz, MedianAuftragszahl |
| HX3 | success | 5903 | False |  |
| HX4 | success | 8542 | True | public.order_details, public.products, public.categories, supplier_revenue, category_revenue, max_supplier_revenue |
| HX5 | success | 10537 | True | public.order_details, public.orders, CustomerMetrics, public.customers, AverageValues |
| HX6 | success | 5947 | True | public.orders, public.order_details, public.employees |
| HX7 | failed | 2282 | False |  |
| HX8 | failed | 2276 | False |  |
| HX9 | failed | 2058 | False |  |
