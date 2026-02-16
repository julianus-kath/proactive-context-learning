# ADR-0002: Synthetic Data Results and Database Access

**Status**: Accepted
**Date**: 2025-04-16
**Author**: Julianus Kath

## Context

After implementing the synthetic data service, we need to document the results of the data generation process and provide instructions for accessing and querying the generated database. This information is crucial for users who want to work with the synthetic data for testing, development, or research purposes.

## Decision

We've decided to document the synthetic data generation results and database access methods to facilitate easier use of the service. This includes:

1. Sample data outputs from each table
2. Example queries for accessing and joining data
3. Instructions for connecting to and working with the SQLite database

## Implementation Details

### Generated Data Overview

The synthetic data service successfully generated the following records:

```
customers|20
employees|30
products|30
sales|50
suppliers|20
warehouse|57
```

### Sample Data

#### Customers Table
```
1|Joyce, Murray and Campbell|ashaw@montoya.com|907-458-1814x124|37506 Randy Landing Apt. 615|North Lucas|Connecticut|94178|Pakistan|Central|Energy|Large|2020-07-10 00:00:00.000000|2025-04-16 10:19:19.630094
2|Moody-Taylor|samantha72@harrison.com|232-589-8614x341|971 Mary Parks Apt. 893|West Ruben|South Carolina|46745|Dominican Republic|South|Retail|Medium|2021-02-11 00:00:00.000000|2025-04-16 10:19:19.630513
3|Butler, Beck and Miller|carlos88@hartman.info|3657405153|58527 Welch Valleys|North Jennifer|New Jersey|05348|French Polynesia|South|Technology|Small|2021-05-16 00:00:00.000000|2025-04-16 10:19:19.630546
```

#### Sales Table
```
1|1|16|6|368.38|13.4|2129.88|2021-09-17 00:00:00.000000|Bank Transfer|Completed
2|9|29|10|443.72|62.23|3814.9|2023-05-01 00:00:00.000000|Cash|Completed
3|3|8|7|867.82|84.8|5481.14|2023-07-01 00:00:00.000000|Debit Card|Completed
```

#### Warehouse Table
```
1|1|Main Warehouse|72|100|2020-04-30 00:00:00.000000|2025-04-09 12:19:19.615560
2|2|Main Warehouse|880|52|2022-11-18 00:00:00.000000|2025-04-09 12:19:19.615612
3|3|Central Distribution|552|26|2023-03-26 00:00:00.000000|2025-04-01 12:19:19.615635
```

### Example Queries

#### Join Query (Recent Sales with Customer and Product Details)
```sql
SELECT c.name as customer_name, p.product_name, s.quantity, s.total_amount, s.sale_date 
FROM sales s 
JOIN customers c ON s.customer_id = c.customer_id 
JOIN products p ON s.product_id = p.product_id 
ORDER BY s.sale_date DESC 
LIMIT 5;
```

Results:
```
Bernard Group|iterate killer e-commerce|8|4382.96|2023-12-30 00:00:00.000000
Bernard Group|brand virtual channels|5|739.55|2023-12-22 00:00:00.000000
Miller Ltd|generate clicks-and-mortar niches|9|2065.86|2023-12-18 00:00:00.000000
Miller Ltd|reinvent back-end markets|1|359.08|2023-12-18 00:00:00.000000
Miller Ltd|harness dynamic action-items|1|335.34|2023-12-16 00:00:00.000000
```

### Database Access Instructions

#### Running the Data Generator

To generate synthetic data with custom parameters:

```bash
python -m synthetic_data_service.main --customers 20 --products 30 --sales 50 --drop-tables
```

Parameters:
- `--customers`: Number of customer records to generate
- `--products`: Number of product records to generate
- `--suppliers`: Number of supplier records to generate (default: 20)
- `--employees`: Number of employee records to generate (default: 30)
- `--sales`: Number of sales records to generate
- `--drop-tables`: Drop existing tables before creating new ones
- `--seed`: Random seed for reproducibility

#### Accessing the SQLite Database

The synthetic data is stored in a SQLite database file named `synthetic_data.db` in the project root directory.

**Using SQLite Command Line**:

1. List all tables:
   ```bash
   sqlite3 synthetic_data.db ".tables"
   ```

2. Count records in each table:
   ```bash
   sqlite3 synthetic_data.db "SELECT 'customers', COUNT(*) FROM customers UNION SELECT 'products', COUNT(*) FROM products UNION SELECT 'suppliers', COUNT(*) FROM suppliers UNION SELECT 'employees', COUNT(*) FROM employees UNION SELECT 'sales', COUNT(*) FROM sales UNION SELECT 'warehouse', COUNT(*) FROM warehouse;"
   ```

3. View sample data:
   ```bash
   sqlite3 synthetic_data.db "SELECT * FROM customers LIMIT 5;"
   ```

4. Run complex queries:
   ```bash
   sqlite3 synthetic_data.db "SELECT c.name as customer_name, p.product_name, s.quantity, s.total_amount, s.sale_date FROM sales s JOIN customers c ON s.customer_id = c.customer_id JOIN products p ON s.product_id = p.product_id ORDER BY s.sale_date DESC LIMIT 5;"
   ```

**Using Python with SQLAlchemy**:

```python
from synthetic_data_service.db import get_db_session
from synthetic_data_service.models import Customer, Product, Sale

# Get a database session
session = get_db_session()

# Query customers
customers = session.query(Customer).limit(5).all()
for customer in customers:
    print(f"Customer: {customer.name}, Region: {customer.region}")

# Query recent sales with joins
recent_sales = session.query(Sale, Customer, Product)\
    .join(Customer, Sale.customer_id == Customer.customer_id)\
    .join(Product, Sale.product_id == Product.product_id)\
    .order_by(Sale.sale_date.desc())\
    .limit(5)\
    .all()

for sale, customer, product in recent_sales:
    print(f"Date: {sale.sale_date}, Customer: {customer.name}, Product: {product.product_name}, Amount: ${sale.total_amount}")

# Close the session
session.close()
```

**Using a GUI Tool**:

For visual exploration of the database, you can use tools like:
- DB Browser for SQLite (https://sqlitebrowser.org/)
- DBeaver (https://dbeaver.io/)
- SQLite Studio (https://sqlitestudio.pl/)

Simply open the `synthetic_data.db` file with your preferred tool.

## Consequences

### Positive

- Users have clear examples of the generated data structure and content
- The documentation provides multiple methods for accessing and querying the database
- Example queries demonstrate how to join tables for data fusion experiments
- Command-line parameters are documented for customizing data generation

### Negative

- The SQLite database is local and not accessible over a network without additional setup
- Large data volumes may require more sophisticated database solutions

### Neutral

- The synthetic data patterns are deterministic when using the same random seed
- The current implementation focuses on data generation rather than analysis

## Future Considerations

1. **Web Interface**
   - Develop a web-based interface for browsing and querying the synthetic data

2. **API Access**
   - Implement a REST API for programmatic access to the synthetic data

3. **Data Export**
   - Add functionality to export data in various formats (CSV, JSON, etc.)

4. **Advanced Analytics**
   - Integrate analytical tools for deriving insights from the synthetic data

5. **Visualization**
   - Add visualization components for exploring data relationships
