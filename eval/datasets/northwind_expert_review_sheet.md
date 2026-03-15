# Northwind Expert Review Sheet (H2a)

Use this file to refine benchmark questions and semantic review criteria before re-running H1/H2a.

## Suggested label set
- `CORRECT`: SQL and result satisfy contract intent.
- `PARTIAL`: mostly correct but missing a key constraint/aggregation/detail.
- `INCORRECT`: wrong logic, wrong aggregation grain, or missing core contract requirement.

## Suggested reason codes
- `MISSING_DISCOUNT_FACTOR`
- `COUNT_NOT_DISTINCT`
- `WRONG_AGGREGATION_GRAIN`
- `MISSING_REQUIRED_TABLE`
- `JOIN_PATH_VIOLATION`
- `MISSING_TIME_GROUPING`
- `TOP_K_NOT_APPLIED`

## NW1
- Question: Show the five products that should be reordered, meaning stock on hand is below the reorder level, sorted by the largest shortage first.
- Required tables: products
- Metric expression target: `units_in_stock < reorder_level`
- Top-K requirement: 5
- Analytic template: `TOP_K_BY_METRIC`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT p.product_id, p.product_name, p.units_in_stock, p.reorder_level
FROM public.products p
WHERE p.units_in_stock < p.reorder_level
ORDER BY (p.reorder_level - p.units_in_stock) DESC, p.product_id
LIMIT 5
```

## NW2
- Question: For each product category, calculate total revenue after discounts, using price times quantity times one minus discount, and identify the category with the highest revenue.
- Required tables: categories, products, order_details
- Metric expression target: `SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount))`
- Analytic template: `AGG_BY_DIMENSION`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT c.category_name,
       SUM(od.unit_price * od.quantity * (1 - od.discount)) AS total_revenue
FROM public.categories c
JOIN public.products p ON p.category_id = c.category_id
JOIN public.order_details od ON od.product_id = p.product_id
GROUP BY c.category_name
ORDER BY total_revenue DESC, c.category_name
```

## NW3
- Question: Which customers have placed more than ten distinct orders, and what is the total value of those orders?
- Required tables: customers, orders, order_details
- Metric expression target: `COUNT(DISTINCT orders.order_id), SUM(order_details.unit_price * order_details.quantity)`
- Analytic template: `FILTER_AND_AGG`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT c.customer_id,
       c.company_name,
       COUNT(DISTINCT o.order_id) AS order_count,
       SUM(od.unit_price * od.quantity) AS total_order_value
FROM public.customers c
JOIN public.orders o ON o.customer_id = c.customer_id
JOIN public.order_details od ON od.order_id = o.order_id
GROUP BY c.customer_id, c.company_name
HAVING COUNT(DISTINCT o.order_id) > 10
ORDER BY total_order_value DESC, c.customer_id
```

## NW4
- Question: For each shipping company, count orders that were shipped later than the required delivery date, and also report total shipped orders.
- Required tables: orders, shippers
- Metric expression target: `COUNT(*) FILTER (WHERE shipped_date > required_date)`
- Analytic template: `AGG_BY_DIMENSION`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT s.shipper_id,
       s.company_name,
       COUNT(*) FILTER (WHERE o.shipped_date > o.required_date) AS late_shipments,
       COUNT(*) AS total_shipments
FROM public.orders o
JOIN public.shippers s ON s.shipper_id = o.ship_via
GROUP BY s.shipper_id, s.company_name
ORDER BY late_shipments DESC, total_shipments DESC, s.shipper_id
```

## NW5
- Question: Which employees generated the highest total revenue from their orders after discounts?
- Required tables: employees, orders, order_details
- Metric expression target: `SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount))`
- Analytic template: `TOP_K_BY_METRIC`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT e.employee_id,
       e.first_name,
       e.last_name,
       SUM(od.unit_price * od.quantity * (1 - od.discount)) AS total_revenue
FROM public.employees e
JOIN public.orders o ON o.employee_id = e.employee_id
JOIN public.order_details od ON od.order_id = o.order_id
GROUP BY e.employee_id, e.first_name, e.last_name
ORDER BY total_revenue DESC, e.employee_id
```

## NW6
- Question: Which five products sold the highest total quantity?
- Required tables: products, order_details
- Metric expression target: `SUM(order_details.quantity)`
- Top-K requirement: 5
- Analytic template: `TOP_K_BY_METRIC`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT p.product_id,
       p.product_name,
       SUM(od.quantity) AS quantity_sold
FROM public.products p
JOIN public.order_details od ON od.product_id = p.product_id
GROUP BY p.product_id, p.product_name
ORDER BY quantity_sold DESC, p.product_id
LIMIT 5
```

## NW7
- Question: Which pairs of suppliers most frequently appear together within the same order? Return both supplier names and the co-order frequency.
- Required tables: suppliers, products, order_details
- Metric expression target: `COUNT(DISTINCT order_id)`
- Analytic template: `COMPLEX_ANALYSIS`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
WITH order_suppliers AS (
    SELECT DISTINCT od.order_id, p.supplier_id
    FROM public.order_details od
    JOIN public.products p ON p.product_id = od.product_id
),
supplier_pairs AS (
    SELECT os1.supplier_id AS supplier_id_1,
           os2.supplier_id AS supplier_id_2,
           COUNT(*) AS co_order_count
    FROM order_suppliers os1
    JOIN order_suppliers os2
      ON os1.order_id = os2.order_id
     AND os1.supplier_id < os2.supplier_id
    GROUP BY os1.supplier_id, os2.supplier_id
)
SELECT s1.company_name AS supplier_1,
       s2.company_name AS supplier_2,
       sp.co_order_count
FROM supplier_pairs sp
JOIN public.suppliers s1 ON s1.supplier_id = sp.supplier_id_1
JOIN public.suppliers s2 ON s2.supplier_id = sp.supplier_id_2
ORDER BY sp.co_order_count DESC, supplier_1, supplier_2
LIMIT 10
```

## NW8
- Question: By customer country, compute the average order value where each order is totaled first and then averaged at the country level.
- Required tables: customers, orders, order_details
- Metric expression target: `AVG(order_total)`
- Analytic template: `AGG_BY_DIMENSION`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
WITH order_totals AS (
    SELECT o.order_id,
           c.country,
           SUM(od.unit_price * od.quantity * (1 - od.discount)) AS order_total
    FROM public.orders o
    JOIN public.customers c ON c.customer_id = o.customer_id
    JOIN public.order_details od ON od.order_id = o.order_id
    GROUP BY o.order_id, c.country
)
SELECT country,
       AVG(order_total) AS avg_order_value
FROM order_totals
GROUP BY country
ORDER BY avg_order_value DESC, country
```

## NW9
- Question: How many distinct orders have not been shipped yet, and what is their total value after discounts?
- Required tables: orders, order_details
- Metric expression target: `COUNT(DISTINCT orders.order_id), SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount))`
- Analytic template: `FILTER_AND_AGG`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT COUNT(DISTINCT o.order_id) AS pending_orders,
       SUM(od.unit_price * od.quantity * (1 - od.discount)) AS total_value
FROM public.orders o
JOIN public.order_details od ON od.order_id = o.order_id
WHERE o.shipped_date IS NULL
```

## NW10
- Question: Show the month-by-month revenue trend after discounts based on order date.
- Required tables: orders, order_details
- Metric expression target: `SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount))`
- Analytic template: `AGG_OVER_PERIOD`
- Expert review fields to fill:
  - Label: `CORRECT | PARTIAL | INCORRECT`
  - Reason code(s):
  - Reviewer notes:
- Reference SQL:
```sql
SELECT DATE_TRUNC('month', o.order_date)::date AS month,
       SUM(od.unit_price * od.quantity * (1 - od.discount)) AS revenue
FROM public.orders o
JOIN public.order_details od ON od.order_id = o.order_id
GROUP BY DATE_TRUNC('month', o.order_date)::date
ORDER BY month
```

