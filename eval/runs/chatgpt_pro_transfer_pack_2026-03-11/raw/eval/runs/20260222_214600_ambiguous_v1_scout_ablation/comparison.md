# Scout ON vs OFF Retrieval Ablation (Ambiguous v1)

## Runs
- Scout ON: `20260222_214527_ambiguous_v1_retrieval_scout_on_pg_v2`
- Scout OFF: `20260222_214536_ambiguous_v1_retrieval_scout_off_pg_v2`

## Aggregate Metrics
| Metric | Scout ON | Scout OFF | Delta (OFF-ON) |
|---|---:|---:|---:|
| mean_recall_at_1 | 0.3750 | 0.4250 | +0.0500 |
| mean_recall_at_3 | 0.6750 | 0.8417 | +0.1667 |
| mean_recall_at_5 | 0.7083 | 0.8950 | +0.1867 |
| mean_recall_at_10 | 0.7083 | 0.9350 | +0.2267 |
| mrr | 0.8000 | 0.9200 | +0.1200 |

## Per-Query (Recall@5)
| Query | ON | OFF | Delta | ON Top-5 | OFF Top-5 |
|---|---:|---:|---:|---|---|
| NW1 | 1.00 | 1.00 | +0.00 | products, order_details, customer_customer_demo, customer_demographics, customers | products, order_details, customer_customer_demo, customer_demographics, customers |
| NW2 | 0.67 | 1.00 | +0.33 | order_details, products | order_details, categories, products, orders |
| NW3 | 0.67 | 1.00 | +0.33 | order_details, orders, products | order_details, orders, customers, products, customer_customer_demo |
| NW4 | 1.00 | 1.00 | +0.00 | shippers, orders, us_states, products | shippers, orders, us_states, products |
| NW5 | 1.00 | 1.00 | +0.00 | order_details, orders, employee_territories, employees, products | order_details, orders, employee_territories, employees, products |
| NW6 | 0.00 | 1.00 | +1.00 | employees | order_details, products, employees |
| NW7 | 0.00 | 0.20 | +0.20 | orders, customers, customer_customer_demo, customer_demographics | customer_customer_demo, customer_demographics, customers, orders, suppliers |
| NW8 | 0.75 | 0.75 | +0.00 | order_details, orders, customers, products, customer_customer_demo | order_details, orders, customers, products, customer_customer_demo |
| NW9 | 1.00 | 1.00 | +0.00 | orders, order_details, products | orders, order_details, products |
| NW10 | 1.00 | 1.00 | +0.00 | order_details, products, orders | order_details, products, orders |
