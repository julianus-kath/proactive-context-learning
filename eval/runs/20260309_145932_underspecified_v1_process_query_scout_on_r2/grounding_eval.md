# H2b /process_query Grounding Evaluation

- Generated: `2026-03-15T15:09:06.625258Z`
- Run dir: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2`
- Labels: `/private/tmp/us_labels_smoke.json`
- Required stage traces: `discovery, ranked`

## Summary

- Number of queries: `12`
- Mean required-table recall: `0.24444444444444444`
- Queries with all required tables surfaced: `1`
- SQL present count: `5`
- SQL execution success count: `5`
- Median latency: `9871.5`
- Policy violations: `0`

| Query | Required recall | All required ok | SQL present | SQL exec ok | Trace complete | Missing required |
|---|---:|---|---|---|---|---|
| US_CL10_U1 | 1.000 | True | True | True | False |  |
| US_CL10_U2 | 0.600 | False | True | True | False | customers, order_details |
| US_CL10_U3 | 0.000 | False | False | None | False | customer_demographics, customer_customer_demo, customers, orders, order_details |
| US_CL2_U1 | 0.333 | False | True | True | False | customers, orders |
| US_CL2_U2 | 0.667 | False | True | True | False | customers |
| US_CL2_U3 | 0.333 | False | True | True | False | customers, orders |
| US_CL3_U1 | 0.000 | False | False | None | False | orders, shippers |
| US_CL3_U2 | 0.000 | False | False | None | False | orders, shippers |
| US_CL3_U3 | 0.000 | False | False | None | False | orders, shippers |
| US_CL6_U1 | 0.000 | False | False | None | False | orders |
| US_CL6_U2 | 0.000 | False | False | None | False | orders |
| US_CL6_U3 | 0.000 | False | False | None | False | orders |

## Scoring Rule

A required table is counted as surfaced with precedence: `final_sql` -> `ranked` -> `discovery`.
