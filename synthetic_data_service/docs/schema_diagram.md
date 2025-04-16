# Database Schema Diagram

The following diagram illustrates the relationships between the tables in the synthetic data service database:

```
+-------------+       +-------------+       +-------------+
|  CUSTOMERS  |       |   PRODUCTS  |       |  SUPPLIERS  |
+-------------+       +-------------+       +-------------+
| customer_id |       | product_id  |       | supplier_id |
| name        |       | product_name|<----->| name        |
| email       |       | description |       | contact_name|
| phone       |       | category    |       | email       |
| address     |       | subcategory |       | phone       |
| city        |       | unit_price  |       | address     |
| state       |       | cost_price  |       | city        |
| postal_code |       | supplier_id |       | state       |
| country     |       | created_at  |       | postal_code |
| region      |       | updated_at  |       | country     |
| industry    |       +-------------+       | created_at  |
| company_size|             ^               +-------------+
| created_at  |             |
| updated_at  |             |
+-------------+             |
      ^                     |
      |                     |
      |                     |
      |                     |
+-------------+       +-------------+
|    SALES    |       |  WAREHOUSE  |
+-------------+       +-------------+
| sale_id     |       | id          |
| customer_id |       | product_id  |
| product_id  |       | warehouse_  |
| quantity    |       |   name      |
| unit_price  |       | stock_      |
| discount    |       |   quantity  |
| total_amount|       | reorder_    |
| sale_date   |       |   level     |
| payment_    |       | last_       |
|   method    |       |   restock_  |
| status      |       |   date      |
+-------------+       | updated_at  |
                      +-------------+

+-------------+
|  EMPLOYEES  |
+-------------+
| employee_id |
| first_name  |
| last_name   |
| email       |
| phone       |
| department  |
| position    |
| hire_date   |
| salary      |
| manager_id  |<---+
+-------------+    |
      ^            |
      |            |
      +------------+
```

## Relationship Details

1. **Customers to Sales**: One-to-many relationship
   - A customer can have multiple sales records
   - Each sale belongs to exactly one customer

2. **Products to Sales**: One-to-many relationship
   - A product can appear in multiple sales records
   - Each sale involves exactly one product

3. **Products to Warehouse Items**: One-to-many relationship
   - A product can be stocked in multiple warehouses
   - Each warehouse item entry refers to exactly one product

4. **Suppliers to Products**: One-to-many relationship
   - A supplier can provide multiple products
   - Each product is sourced from exactly one supplier

5. **Employees to Employees**: Self-referential relationship
   - An employee can have one manager (another employee)
   - A manager can have multiple employees reporting to them

## Key Business Entities

This schema represents a simplified but realistic model of a business with:

- **Customer Relationship Management (CRM)**: Customers and sales data
- **Enterprise Resource Planning (ERP)**: Products, suppliers, and inventory management
- **Human Resources**: Employee information and reporting structure

The synthetic data generated for this schema enables testing and development of data fusion, crawling, and analysis algorithms across these business domains.