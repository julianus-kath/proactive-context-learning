# Northwind Query Feasibility Review

Generated: 2026-02-15T08:19:09.361474Z

## Summary
- All 10 benchmark intents are supported by available Northwind tables/columns.
- Highest complexity queries are co-occurrence pairing (NW7) and two-stage averaging (NW8).
- Revised NL prompts were made more explicit to improve answerability.

## Per-query feasibility
| Query | Complexity | Required tables present | Key columns present | Reference rows | Feasible |
|---|---|---|---|---:|---|
| NW1 | Low | Yes | Yes | 5 | Yes |
| NW2 | Medium | Yes | Yes | 8 | Yes |
| NW3 | Medium | Yes | Yes | 28 | Yes |
| NW4 | Medium | Yes | Yes | 3 | Yes |
| NW5 | Medium | Yes | Yes | 9 | Yes |
| NW6 | Low | Yes | Yes | 5 | Yes |
| NW7 | High | Yes | Yes | 10 | Yes |
| NW8 | High | Yes | Yes | 21 | Yes |
| NW9 | Medium | Yes | Yes | 1 | Yes |
| NW10 | Medium | Yes | Yes | 23 | Yes |

## Revised NL benchmark questions
- `NW1`: List the 5 products that should be reordered, where units_in_stock is below reorder_level, ordered by the largest shortage first.
- `NW2`: For each product category, compute total discounted revenue using unit_price * quantity * (1 - discount), and show which category has the highest revenue.
- `NW3`: Which customers have placed more than 10 distinct orders, and what is their total order value?
- `NW4`: For each shipper, count late shipments where shipped_date > required_date, and also show total shipments.
- `NW5`: Which employees generated the most discounted revenue from their orders?
- `NW6`: What are the top 5 products by total quantity sold?
- `NW7`: Which pairs of suppliers appear together in the same orders most often? Return supplier_1, supplier_2, and the co-order count.
- `NW8`: Calculate average order value by customer country, where each order value is summed per order before taking the country average.
- `NW9`: How many distinct orders are pending shipment (shipped_date IS NULL), and what is their total discounted value?
- `NW10`: Show the monthly discounted revenue trend by order month.
