# Retrieval-Only Ablation Results — NORTHWIND

**Date:** 2026-04-22 19:30  
**Top-k:** 5  
**Queries:** 84  
**Dataset:** northwind  

## 1. Aggregate Metrics (Primary Search Strategy)

| Metric | sdg_off | sdg_on |
|--------|--------|--------|
| Mean Recall@k | 0.427 | 0.427 |
| Mean Precision@k | 0.340 | 0.311 |
| Mean Hit@k | 0.536 | 0.536 |
| Mean MRR | 0.437 | 0.419 |
| Perfect Recall | 25/84 | 25/84 |
| Zero Recall | 39/84 | 39/84 |
| Mean Latency (ms) | 4 | 3 |

## 2. Per-Query Recall@5

| Query | Required Tables | sdg_off | sdg_on |
|-------|----------------|--------|--------|
| NW1 | products | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW2 | categories, products, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW3 | customers, orders, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW4 | orders, shippers | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW5 | employees, orders, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW6 | products, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW7 | suppliers, products, order_details | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| NW8 | customers, orders, order_details | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| NW9 | orders, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW10 | orders, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL1 | products | 0.00 (MISS) | 0.00 (MISS) |
| NL2 | customers, order_details, orders | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| NL3 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| NL4 | order_details, products | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL5 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| NL6 | order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL7 | order_details, products, suppliers | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| NL8 | orders, shippers | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL9 | employees, orders | 0.00 (MISS) | 0.00 (MISS) |
| NL10 | customers, orders | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| CL1 | order_details, products, suppliers | 1.00 (PERFECT) | 1.00 (PERFECT) |
| CL2 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| CL3 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| CL4 | employees, orders | 0.00 (MISS) | 0.00 (MISS) |
| CL5 | customers, orders | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| CL6 | orders | 0.00 (MISS) | 0.00 (MISS) |
| CL7 | employee_territories, order_details, orders (+2) | 0.40 (PARTIAL) | 0.40 (PARTIAL) |
| CL8 | customers, order_details, orders | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| CL9 | order_details, products, suppliers | 1.00 (PERFECT) | 1.00 (PERFECT) |
| CL10 | customer_customer_demo, customer_demographics, customers (+2) | 0.00 (MISS) | 0.00 (MISS) |
| CL11 | employees, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| CL12 | order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| HX1 | customers, order_details, orders | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| HX3 | orders, shippers | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| HX4 | categories, order_details, products (+1) | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| HX5 | customers, order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| HX7 | categories, order_details, orders (+1) | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| HX8 | order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| HX9 | order_details, products, suppliers | 1.00 (PERFECT) | 1.00 (PERFECT) |
| HX12 | categories, order_details, orders (+1) | 0.00 (MISS) | 0.00 (MISS) |
| US_CL2_U1 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL2_U2 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL2_U3 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL3_U1 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| US_CL3_U2 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| US_CL3_U3 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| US_CL6_U1 | orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL6_U2 | orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL6_U3 | orders | 0.00 (MISS) | 0.00 (MISS) |
| US_CL10_U1 | customer_customer_demo, customer_demographics, customers (+2) | 0.00 (MISS) | 0.00 (MISS) |
| US_CL10_U2 | customer_customer_demo, customer_demographics, customers (+2) | 0.00 (MISS) | 0.00 (MISS) |
| US_CL10_U3 | customer_customer_demo, customer_demographics, customers (+2) | 0.40 (PARTIAL) | 0.40 (PARTIAL) |
| LB_CL2_LX1 | customers, order_details, orders | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| LB_CL2_LX2 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL2_LX3 | customers, order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| LB_CL3_LX1 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL3_LX2 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL3_LX3 | orders, shippers | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| LB_CL6_LX1 | orders | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL6_LX2 | orders | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL6_LX3 | orders | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL10_LX1 | customer_customer_demo, customer_demographics, customers (+2) | 0.40 (PARTIAL) | 0.40 (PARTIAL) |
| LB_CL10_LX2 | customer_customer_demo, customer_demographics, customers (+2) | 0.00 (MISS) | 0.00 (MISS) |
| LB_CL10_LX3 | customer_customer_demo, customer_demographics, customers (+2) | 0.00 (MISS) | 0.00 (MISS) |
| NW_DE_01 | products | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW_DE_02 | categories, products, order_details | 0.00 (MISS) | 0.00 (MISS) |
| NW_DE_03 | customers, orders, order_details | 0.00 (MISS) | 0.00 (MISS) |
| NW_DE_04 | orders, shippers | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| NW_DE_05 | employees, orders, order_details | 0.00 (MISS) | 0.00 (MISS) |
| NW_DE_06 | products, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW_DE_07 | suppliers, products, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NW_DE_08 | customers, orders, order_details | 0.67 (PARTIAL) | 0.67 (PARTIAL) |
| NW_DE_09 | orders, order_details | 0.00 (MISS) | 0.00 (MISS) |
| NW_DE_10 | orders, order_details | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL_DE_01 | products | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL_DE_02 | customers, order_details, orders | 0.00 (MISS) | 0.00 (MISS) |
| NL_DE_03 | orders, shippers | 0.50 (PARTIAL) | 0.50 (PARTIAL) |
| NL_DE_04 | order_details, products | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL_DE_05 | customers, order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL_DE_06 | order_details, orders | 1.00 (PERFECT) | 1.00 (PERFECT) |
| NL_DE_07 | order_details, products, suppliers | 0.33 (PARTIAL) | 0.33 (PARTIAL) |
| NL_DE_08 | orders, shippers | 0.00 (MISS) | 0.00 (MISS) |
| NL_DE_09 | employees, orders | 0.00 (MISS) | 0.00 (MISS) |
| NL_DE_10 | customers, orders | 0.00 (MISS) | 0.00 (MISS) |

## 4. Keyword Strategy Analysis

Shows whether alternative search strategies improve recall over the primary strategy.

### sdg_off

| Query | Primary | Best Alt | Delta |
|-------|---------|----------|-------|
| NW1 | 1.00 | 1.00 | +0.00 |
| NW2 | 1.00 | 0.67 | -0.33 |
| NW3 | 1.00 | 0.67 | -0.33 |
| NW4 | 1.00 | 1.00 | +0.00 |
| NW5 | 1.00 | 0.67 | -0.33 |
| NW6 | 1.00 | 1.00 | +0.00 |
| NW7 | 0.67 | 0.67 | +0.00 |
| NW8 | 0.67 | 0.67 | +0.00 |
| NW9 | 1.00 | 1.00 | +0.00 |
| NW10 | 1.00 | 1.00 | +0.00 |
| NL1 | 0.00 | 1.00 | +1.00 |
| NL2 | 0.67 | 0.67 | +0.00 |
| NL3 | 0.00 | 1.00 | +1.00 |
| NL4 | 1.00 | 1.00 | +0.00 |
| NL5 | 0.00 | 0.67 | +0.67 |
| NL6 | 1.00 | 1.00 | +0.00 |
| NL7 | 0.67 | 0.67 | +0.00 |
| NL8 | 1.00 | 1.00 | +0.00 |
| NL9 | 0.00 | 1.00 | +1.00 |
| NL10 | 0.50 | 1.00 | +0.50 |
| CL1 | 1.00 | 0.67 | -0.33 |
| CL2 | 0.00 | 0.00 | +0.00 |
| CL3 | 0.00 | 0.00 | +0.00 |
| CL4 | 0.00 | 0.00 | +0.00 |
| CL5 | 0.50 | 0.50 | +0.00 |
| CL6 | 0.00 | 0.00 | +0.00 |
| CL7 | 0.40 | 0.60 | +0.20 |
| CL8 | 0.67 | 0.67 | +0.00 |
| CL9 | 1.00 | 1.00 | +0.00 |
| CL10 | 0.00 | 0.00 | +0.00 |
| CL11 | 0.00 | 0.00 | +0.00 |
| CL12 | 1.00 | 1.00 | +0.00 |
| HX1 | 0.67 | 0.67 | +0.00 |
| HX3 | 0.50 | 0.00 | -0.50 |
| HX4 | 0.50 | 0.50 | +0.00 |
| HX5 | 1.00 | 0.67 | -0.33 |
| HX7 | 0.50 | 0.50 | +0.00 |
| HX8 | 0.00 | 0.00 | +0.00 |
| HX9 | 1.00 | 1.00 | +0.00 |
| HX12 | 0.00 | 0.00 | +0.00 |
| US_CL2_U1 | 0.00 | 0.00 | +0.00 |
| US_CL2_U2 | 0.00 | 0.00 | +0.00 |
| US_CL2_U3 | 0.00 | 0.00 | +0.00 |
| US_CL3_U1 | 0.00 | 0.00 | +0.00 |
| US_CL3_U2 | 0.00 | 0.00 | +0.00 |
| US_CL3_U3 | 0.00 | 0.00 | +0.00 |
| US_CL6_U1 | 0.00 | 0.00 | +0.00 |
| US_CL6_U2 | 0.00 | 0.00 | +0.00 |
| US_CL6_U3 | 0.00 | 0.00 | +0.00 |
| US_CL10_U1 | 0.00 | 0.00 | +0.00 |
| US_CL10_U2 | 0.00 | 0.00 | +0.00 |
| US_CL10_U3 | 0.40 | 0.00 | -0.40 |
| LB_CL2_LX1 | 0.67 | 0.67 | +0.00 |
| LB_CL2_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL2_LX3 | 1.00 | 0.33 | -0.67 |
| LB_CL3_LX1 | 0.00 | 0.00 | +0.00 |
| LB_CL3_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL3_LX3 | 0.50 | 0.00 | -0.50 |
| LB_CL6_LX1 | 0.00 | 0.00 | +0.00 |
| LB_CL6_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL6_LX3 | 0.00 | 0.00 | +0.00 |
| LB_CL10_LX1 | 0.40 | 0.40 | +0.00 |
| LB_CL10_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL10_LX3 | 0.00 | 0.00 | +0.00 |
| NW_DE_01 | 1.00 | 1.00 | +0.00 |
| NW_DE_02 | 0.00 | 0.00 | +0.00 |
| NW_DE_03 | 0.00 | 0.00 | +0.00 |
| NW_DE_04 | 0.50 | 0.00 | -0.50 |
| NW_DE_05 | 0.00 | 0.00 | +0.00 |
| NW_DE_06 | 1.00 | 1.00 | +0.00 |
| NW_DE_07 | 1.00 | 0.67 | -0.33 |
| NW_DE_08 | 0.67 | 0.00 | -0.67 |
| NW_DE_09 | 0.00 | 0.00 | +0.00 |
| NW_DE_10 | 1.00 | 0.00 | -1.00 |
| NL_DE_01 | 1.00 | 1.00 | +0.00 |
| NL_DE_02 | 0.00 | 0.00 | +0.00 |
| NL_DE_03 | 0.50 | 0.00 | -0.50 |
| NL_DE_04 | 1.00 | 1.00 | +0.00 |
| NL_DE_05 | 1.00 | 0.33 | -0.67 |
| NL_DE_06 | 1.00 | 0.00 | -1.00 |
| NL_DE_07 | 0.33 | 0.00 | -0.33 |
| NL_DE_08 | 0.00 | 0.00 | +0.00 |
| NL_DE_09 | 0.00 | 0.00 | +0.00 |
| NL_DE_10 | 0.00 | 0.00 | +0.00 |

### sdg_on

| Query | Primary | Best Alt | Delta |
|-------|---------|----------|-------|
| NW1 | 1.00 | 1.00 | +0.00 |
| NW2 | 1.00 | 0.67 | -0.33 |
| NW3 | 1.00 | 1.00 | +0.00 |
| NW4 | 1.00 | 1.00 | +0.00 |
| NW5 | 1.00 | 0.67 | -0.33 |
| NW6 | 1.00 | 1.00 | +0.00 |
| NW7 | 0.67 | 1.00 | +0.33 |
| NW8 | 0.67 | 1.00 | +0.33 |
| NW9 | 1.00 | 1.00 | +0.00 |
| NW10 | 1.00 | 1.00 | +0.00 |
| NL1 | 0.00 | 1.00 | +1.00 |
| NL2 | 0.67 | 1.00 | +0.33 |
| NL3 | 0.00 | 1.00 | +1.00 |
| NL4 | 1.00 | 1.00 | +0.00 |
| NL5 | 0.00 | 1.00 | +1.00 |
| NL6 | 1.00 | 1.00 | +0.00 |
| NL7 | 0.67 | 1.00 | +0.33 |
| NL8 | 1.00 | 1.00 | +0.00 |
| NL9 | 0.00 | 1.00 | +1.00 |
| NL10 | 0.50 | 1.00 | +0.50 |
| CL1 | 1.00 | 1.00 | +0.00 |
| CL2 | 0.00 | 0.00 | +0.00 |
| CL3 | 0.00 | 0.00 | +0.00 |
| CL4 | 0.00 | 0.00 | +0.00 |
| CL5 | 0.50 | 0.50 | +0.00 |
| CL6 | 0.00 | 1.00 | +1.00 |
| CL7 | 0.40 | 0.60 | +0.20 |
| CL8 | 0.67 | 0.67 | +0.00 |
| CL9 | 1.00 | 1.00 | +0.00 |
| CL10 | 0.00 | 0.00 | +0.00 |
| CL11 | 0.00 | 0.00 | +0.00 |
| CL12 | 1.00 | 1.00 | +0.00 |
| HX1 | 0.67 | 0.67 | +0.00 |
| HX3 | 0.50 | 0.00 | -0.50 |
| HX4 | 0.50 | 0.75 | +0.25 |
| HX5 | 1.00 | 0.67 | -0.33 |
| HX7 | 0.50 | 0.50 | +0.00 |
| HX8 | 0.00 | 0.00 | +0.00 |
| HX9 | 1.00 | 1.00 | +0.00 |
| HX12 | 0.00 | 0.25 | +0.25 |
| US_CL2_U1 | 0.00 | 0.00 | +0.00 |
| US_CL2_U2 | 0.00 | 0.00 | +0.00 |
| US_CL2_U3 | 0.00 | 0.00 | +0.00 |
| US_CL3_U1 | 0.00 | 0.00 | +0.00 |
| US_CL3_U2 | 0.00 | 0.50 | +0.50 |
| US_CL3_U3 | 0.00 | 0.00 | +0.00 |
| US_CL6_U1 | 0.00 | 0.00 | +0.00 |
| US_CL6_U2 | 0.00 | 0.00 | +0.00 |
| US_CL6_U3 | 0.00 | 0.00 | +0.00 |
| US_CL10_U1 | 0.00 | 0.00 | +0.00 |
| US_CL10_U2 | 0.00 | 0.00 | +0.00 |
| US_CL10_U3 | 0.40 | 0.40 | +0.00 |
| LB_CL2_LX1 | 0.67 | 0.67 | +0.00 |
| LB_CL2_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL2_LX3 | 1.00 | 0.33 | -0.67 |
| LB_CL3_LX1 | 0.00 | 0.50 | +0.50 |
| LB_CL3_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL3_LX3 | 0.50 | 0.00 | -0.50 |
| LB_CL6_LX1 | 0.00 | 1.00 | +1.00 |
| LB_CL6_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL6_LX3 | 0.00 | 0.00 | +0.00 |
| LB_CL10_LX1 | 0.40 | 0.40 | +0.00 |
| LB_CL10_LX2 | 0.00 | 0.00 | +0.00 |
| LB_CL10_LX3 | 0.00 | 0.20 | +0.20 |
| NW_DE_01 | 1.00 | 1.00 | +0.00 |
| NW_DE_02 | 0.00 | 0.00 | +0.00 |
| NW_DE_03 | 0.00 | 0.00 | +0.00 |
| NW_DE_04 | 0.50 | 0.50 | +0.00 |
| NW_DE_05 | 0.00 | 0.33 | +0.33 |
| NW_DE_06 | 1.00 | 1.00 | +0.00 |
| NW_DE_07 | 1.00 | 0.67 | -0.33 |
| NW_DE_08 | 0.67 | 0.00 | -0.67 |
| NW_DE_09 | 0.00 | 0.50 | +0.50 |
| NW_DE_10 | 1.00 | 0.00 | -1.00 |
| NL_DE_01 | 1.00 | 1.00 | +0.00 |
| NL_DE_02 | 0.00 | 0.00 | +0.00 |
| NL_DE_03 | 0.50 | 0.00 | -0.50 |
| NL_DE_04 | 1.00 | 1.00 | +0.00 |
| NL_DE_05 | 1.00 | 0.33 | -0.67 |
| NL_DE_06 | 1.00 | 0.00 | -1.00 |
| NL_DE_07 | 0.33 | 0.00 | -0.33 |
| NL_DE_08 | 0.00 | 0.00 | +0.00 |
| NL_DE_09 | 0.00 | 0.00 | +0.00 |
| NL_DE_10 | 0.00 | 0.00 | +0.00 |

