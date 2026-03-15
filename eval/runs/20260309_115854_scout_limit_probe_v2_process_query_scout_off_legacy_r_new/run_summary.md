# /process_query Northwind Run (scout_off_legacy)

- Run ID: `20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new`
- Run name: `scout_limit_probe_v2_process_query_scout_off_legacy_r_new`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with legacy lexical schema-linking baseline.
- Total queries: `18`
- Successes: `18`
- Failures: `0`
- Avg latency ms: `10679.9`
- P95 latency ms: `25377.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| P_CL10_L1 | success | 10852 | True | public.order_details, public.orders, public.customers |
| P_CL10_L2 | success | 7336 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L3 | success | 8506 | True | public.order_details, public.orders, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L4 | success | 25377 | True | public.customers, public.customer_customer_demo, public.customer_demographics, public.orders, public.order_details |
| P_CL10_L5 | success | 15019 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL10_L6 | success | 17551 | True | public.orders, public.order_details, public.customers, public.customer_customer_demo, public.customer_demographics |
| P_CL2_L1 | success | 6738 | True | public.order_details, public.orders, public.customers |
| P_CL2_L2 | success | 6494 | True | public.order_details, public.orders, public.customers |
| P_CL2_L3 | success | 9421 | True | public.order_details, public.orders, public.customers |
| P_CL2_L4 | success | 5420 | False |  |
| P_CL2_L5 | success | 7772 | True | public.order_details, public.orders, public.employee_territories, public.territories |
| P_CL2_L6 | success | 7562 | True | public.order_details, public.orders, public.territories, public.region |
| P_CL6_L1 | success | 12056 | True | public.orders |
| P_CL6_L2 | success | 7403 | True | public.orders |
| P_CL6_L3 | success | 15809 | True | public.orders |
| P_CL6_L4 | success | 5155 | False |  |
| P_CL6_L5 | success | 6172 | False |  |
| P_CL6_L6 | success | 17595 | True | public.orders |
