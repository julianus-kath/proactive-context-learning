# H2b /process_query Grounding Report

## Experiment Definition

- Generated: `2026-03-15T15:09:17.862824Z`
- Endpoint(s): `http://localhost:5001`
- Dataset(s): `eval/datasets/northwind_queries_underspecified_v1.jsonl`
- Modes: `scout_on`
- Scoring logic: `required-table grounding with surfaced precedence final_sql > ranked > discovery`

## Label Normalization Summary

- Source: `eval/runs/20260315_150849_smoke_label_normalization/label_normalization.json`
- Exact: `9`
- Alias/prefix-normalized: `4`
- Manual-confirmed: `0`
- Unresolved: `0`

## Aggregate Metrics by Mode

| Mode | #Queries | Mean required recall | All-required surfaced | SQL present | SQL exec success | Median latency (ms) | Policy violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| scout_on | 12 | 0.24444444444444444 | 1 | 5 | 5 | 9871.5 | 0 |

## Per-Query Tables

### scout_on

| Query ID | Required tables | Surfaced tables | Required recall | All-required-ok | SQL present | Execution success | Latency (ms) | Notes/mismatches |
|---|---|---|---:|---|---|---|---:|---|
| US_CL10_U1 | customer_demographics, customer_customer_demo, customers, orders, order_details | customer_customer_demo, customer_demographics, customers, orders, order_details | 1.0 | True | True | True | 9907 | missing_traces=discovery,ranked |
| US_CL10_U2 | customer_demographics, customer_customer_demo, customers, orders, order_details | customer_customer_demo, customer_demographics, orders | 0.6 | False | True | True | 10441 | missing_required=customers,order_details; missing_traces=discovery,ranked |
| US_CL10_U3 | customer_demographics, customer_customer_demo, customers, orders, order_details |  | 0.0 | False | False | None | 6047 | missing_required=customer_demographics,customer_customer_demo,customers,orders,order_details; missing_traces=discovery,ranked |
| US_CL2_U1 | customers, orders, order_details | order_details | 0.3333333333333333 | False | True | True | 20312 | missing_required=customers,orders; missing_traces=discovery,ranked |
| US_CL2_U2 | customers, orders, order_details | orders, order_details | 0.6666666666666666 | False | True | True | 7951 | missing_required=customers; missing_traces=discovery,ranked |
| US_CL2_U3 | customers, orders, order_details | order_details | 0.3333333333333333 | False | True | True | 13328 | missing_required=customers,orders; missing_traces=discovery,ranked |
| US_CL3_U1 | orders, shippers |  | 0.0 | False | False | None | 7789 | missing_required=orders,shippers; missing_traces=discovery,ranked |
| US_CL3_U2 | orders, shippers |  | 0.0 | False | False | None | 14839 | missing_required=orders,shippers; missing_traces=discovery,ranked |
| US_CL3_U3 | orders, shippers |  | 0.0 | False | False | None | 9836 | missing_required=orders,shippers; missing_traces=discovery,ranked |
| US_CL6_U1 | orders |  | 0.0 | False | False | None | 8765 | missing_required=orders; missing_traces=discovery,ranked |
| US_CL6_U2 | orders |  | 0.0 | False | False | None | 5775 | missing_required=orders; missing_traces=discovery,ranked |
| US_CL6_U3 | orders |  | 0.0 | False | False | None | 13837 | missing_required=orders; missing_traces=discovery,ranked |

## Interpretation

Primary signal: required-table grounding under full `/process_query` pipeline. Best mean required-table recall in this run set: `scout_on`.

## Methodological Comparability (H2a vs H2b)

H2a and H2b both use the same `/process_query` full agent pipeline.
H2a is scored on semantic correctness; H2b is scored on production table grounding and operational robustness.
