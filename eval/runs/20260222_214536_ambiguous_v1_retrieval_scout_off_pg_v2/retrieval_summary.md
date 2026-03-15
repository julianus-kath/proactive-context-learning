# Retrieval Benchmark Summary (scout_off)

- Run ID: `20260222_214536_ambiguous_v1_retrieval_scout_off_pg_v2`
- Total queries: `10`
- Mean Recall@1/3/5/10: `0.425` / `0.8417` / `0.895` / `0.935`
- All-required hit@1/3/5/10: `0.1` / `0.7` / `0.8` / `0.8`
- MRR: `0.92`

| Query | Required Tables | Top-5 Retrieved | Recall@5 |
|---|---|---|---|
| NW1 | products | products, order_details, customer_customer_demo, customer_demographics, customers | 1.00 |
| NW2 | categories, products, order_details | order_details, categories, products, orders | 1.00 |
| NW3 | customers, orders, order_details | order_details, orders, customers, products, customer_customer_demo | 1.00 |
| NW4 | orders, shippers | shippers, orders, us_states, products | 1.00 |
| NW5 | employees, orders, order_details | order_details, orders, employee_territories, employees, products | 1.00 |
| NW6 | products, order_details | order_details, products, employees | 1.00 |
| NW7 | order_details, products, order_suppliers, supplier_pairs, suppliers | customer_customer_demo, customer_demographics, customers, orders, suppliers | 0.20 |
| NW8 | orders, customers, order_details, order_totals | order_details, orders, customers, products, customer_customer_demo | 0.75 |
| NW9 | orders, order_details | orders, order_details, products | 1.00 |
| NW10 | orders, order_details | order_details, products, orders | 1.00 |
