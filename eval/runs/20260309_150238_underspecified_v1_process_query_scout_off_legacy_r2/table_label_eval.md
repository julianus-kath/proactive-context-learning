# /process_query Table-Label Evaluation

- Generated: `2026-03-10T05:45:58.143425Z`
- Run dir: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2`
- Labels file: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/_tmp_underspecified_table_labels_for_smoke.json`

## Summary

- Total queries: `12`
- Responses found: `12`
- SQL present: `8`
- Required tables ok (count): `3`
- Mean required-table recall: `0.4777777777777778`

| Query | Required tables ok | Recall | SQL present | Missing required tables |
|---|---:|---:|---:|---|
| US_CL10_U1 | False | 0.800 | True | customers |
| US_CL10_U2 | False | 0.600 | True | customer_customer_demo, customer_demographics |
| US_CL10_U3 | True | 1.000 | True |  |
| US_CL2_U1 | False | 0.000 | False | customers, order_details, orders |
| US_CL2_U2 | True | 1.000 | True |  |
| US_CL2_U3 | False | 0.333 | True | customers, orders |
| US_CL3_U1 | False | 0.000 | False | orders, shippers |
| US_CL3_U2 | False | 0.500 | True | shippers |
| US_CL3_U3 | False | 0.500 | True | shippers |
| US_CL6_U1 | True | 1.000 | True |  |
| US_CL6_U2 | False | 0.000 | False | orders |
| US_CL6_U3 | False | 0.000 | False | orders |
