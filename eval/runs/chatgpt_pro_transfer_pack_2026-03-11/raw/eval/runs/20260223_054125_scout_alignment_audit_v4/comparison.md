# Scout Alignment Audit (v4)

## Retrieval A/B (aligned ranker)
- Scout ON run: `20260223_054022_ambiguous_v1_retrieval_scout_on_pg_v4_aligned`
- Scout OFF run: `20260223_054040_ambiguous_v1_retrieval_scout_off_pg_v4_aligned`
- ON path: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_054022_ambiguous_v1_retrieval_scout_on_pg_v4_aligned`
- OFF path: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_054040_ambiguous_v1_retrieval_scout_off_pg_v4_aligned`

| Metric | ON | OFF | Delta (OFF-ON) |
|---|---:|---:|---:|
| mean_recall_at_1 | 0.3667 | 0.3667 | +0.0000 |
| mean_recall_at_3 | 0.7917 | 0.7917 | +0.0000 |
| mean_recall_at_5 | 0.8950 | 0.8950 | +0.0000 |
| mean_recall_at_10 | 0.9350 | 0.9350 | +0.0000 |
| mrr | 0.8033 | 0.8033 | +0.0000 |

## Retrieval Query Examples (Top-5)
| Query | Recall@5 ON | Recall@5 OFF | ON Top-5 | OFF Top-5 |
|---|---:|---:|---|---|
| NW1 | 1.00 | 1.00 | products, order_details, customer_customer_demo, customer_demographics, customers | products, order_details, customer_customer_demo, customer_demographics, customers |
| NW10 | 1.00 | 1.00 | order_details, products, orders | order_details, products, orders |
| NW2 | 1.00 | 1.00 | categories, order_details, products, orders | categories, order_details, products, orders |
| NW3 | 1.00 | 1.00 | customers, order_details, orders, products, customer_customer_demo | customers, order_details, orders, products, customer_customer_demo |
| NW4 | 1.00 | 1.00 | shippers, orders, us_states, products | shippers, orders, us_states, products |
| NW5 | 1.00 | 1.00 | employee_territories, employees, order_details, orders, products | employee_territories, employees, order_details, orders, products |
| NW6 | 1.00 | 1.00 | order_details, products, employees | order_details, products, employees |
| NW7 | 0.20 | 0.20 | customer_customer_demo, customer_demographics, customers, orders, suppliers | customer_customer_demo, customer_demographics, customers, orders, suppliers |
| NW8 | 0.75 | 0.75 | customer_customer_demo, customer_demographics, customers, order_details, orders | customer_customer_demo, customer_demographics, customers, order_details, orders |
| NW9 | 1.00 | 1.00 | order_details, orders, products | order_details, orders, products |

## H2a End-to-End A/B
- Scout ON run: `20260223_063813_h2a_baseline_scout_on_v4_aligned`
- Scout OFF run: `20260223_063709_h2a_baseline_scout_off_v4_aligned`
- ON path: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_063813_h2a_baseline_scout_on_v4_aligned`
- OFF path: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_063709_h2a_baseline_scout_off_v4_aligned`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| success_rate | 100.0% | 100.0% | +0.0pp |
| avg_latency_ms | 3573.6 | 3403.5 | +170.1 |
| p95_latency_ms | 4066.0 | 4672.0 | -606.0 |

## Backend Evidence
- H2a ON backend start/end: `ScoutRunner` / `ScoutRunner`
- H2a OFF backend start/end: `SchemaCatalog` / `SchemaCatalog`

## Artifacts
- Comparison JSON: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_054125_scout_alignment_audit_v4/comparison.json`
- This report: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260223_054125_scout_alignment_audit_v4/comparison.md`
