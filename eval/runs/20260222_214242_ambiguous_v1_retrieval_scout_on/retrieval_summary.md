# Retrieval Benchmark Summary (scout_on)

- Run ID: `20260222_214242_ambiguous_v1_retrieval_scout_on`
- Total queries: `10`
- Mean Recall@1/3/5/10: `0.2833` / `0.4667` / `0.5` / `0.5`
- All-required hit@1/3/5/10: `0.1` / `0.4` / `0.5` / `0.5`
- MRR: `0.5`

| Query | Required Tables | Top-5 Retrieved | Recall@5 |
|---|---|---|---|
| NW1 | products | products, order_details, customer_customer_demo, customer_demographics, customers | 1.00 |
| NW2 | categories, products, order_details |  | 0.00 |
| NW3 | customers, orders, order_details |  | 0.00 |
| NW4 | orders, shippers | shippers, orders, us_states, products | 1.00 |
| NW5 | employees, orders, order_details | order_details, orders, employee_territories, employees, products | 1.00 |
| NW6 | products, order_details |  | 0.00 |
| NW7 | order_details, products, order_suppliers, supplier_pairs, suppliers |  | 0.00 |
| NW8 | orders, customers, order_details, order_totals |  | 0.00 |
| NW9 | orders, order_details | orders, order_details, products | 1.00 |
| NW10 | orders, order_details | order_details, products, orders | 1.00 |
