# /process_query Table-Label Evaluation

- Generated: `2026-03-10T05:45:58.087814Z`
- Run dir: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2`
- Labels file: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/_tmp_underspecified_table_labels_for_smoke.json`

## Summary

- Total queries: `12`
- Responses found: `12`
- SQL present: `5`
- Required tables ok (count): `1`
- Mean required-table recall: `0.24444444444444444`

| Query | Required tables ok | Recall | SQL present | Missing required tables |
|---|---:|---:|---:|---|
| US_CL10_U1 | True | 1.000 | True |  |
| US_CL10_U2 | False | 0.600 | True | customers, order_details |
| US_CL10_U3 | False | 0.000 | False | customer_customer_demo, customer_demographics, customers, order_details, orders |
| US_CL2_U1 | False | 0.333 | True | customers, orders |
| US_CL2_U2 | False | 0.667 | True | customers |
| US_CL2_U3 | False | 0.333 | True | customers, orders |
| US_CL3_U1 | False | 0.000 | False | orders, shippers |
| US_CL3_U2 | False | 0.000 | False | orders, shippers |
| US_CL3_U3 | False | 0.000 | False | orders, shippers |
| US_CL6_U1 | False | 0.000 | False | orders |
| US_CL6_U2 | False | 0.000 | False | orders |
| US_CL6_U3 | False | 0.000 | False | orders |
