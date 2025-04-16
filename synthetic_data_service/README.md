# Synthetic Data Service

A Python service for generating synthetic CRM and ERP data for testing and development purposes. This service creates realistic mock data and inserts it into a SQL database, providing a foundation for data fusion, crawling, and analysis experiments.

## Project Structure

```
synthetic_data_service/
├── __init__.py         # Package initialization
├── main.py             # Entry point for running the service
├── config.py           # Configuration details (DB URL, etc.)
├── db.py               # Sets up the SQLAlchemy engine & session
├── models.py           # Defines SQLAlchemy ORM models
├── generator.py        # Logic for creating and inserting synthetic data
├── test_generator.py   # Unit tests for the generator
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd synthetic_data_service
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Generate synthetic data with default parameters:

```bash
python -m synthetic_data_service.main
```

This will create:
- 50 customers
- 100 products
- 20 suppliers
- 30 employees
- 200 sales records

### Customizing Data Generation

You can customize the amount of data generated:

```bash
python -m synthetic_data_service.main --customers 100 --products 200 --sales 500
```

To drop existing tables and create new ones:

```bash
python -m synthetic_data_service.main --drop-tables
```

For reproducible data generation, specify a random seed:

```bash
python -m synthetic_data_service.main --seed 42
```

### Command-line Options

```
--customers INT    Number of customer records to generate (default: 50)
--products INT     Number of product records to generate (default: 100)
--suppliers INT    Number of supplier records to generate (default: 20)
--employees INT    Number of employee records to generate (default: 30)
--sales INT        Number of sales records to generate (default: 200)
--seed INT         Random seed for reproducibility
--drop-tables      Drop existing tables before creating new ones
```

## Database Configuration

By default, the service uses SQLite with a local file `synthetic_data.db`. You can configure the database connection using environment variables:

```bash
# For SQLite (default)
export DB_TYPE=sqlite
export DB_NAME=synthetic_data.db

# For PostgreSQL
export DB_TYPE=postgresql
export DB_NAME=synthetic_data
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=password

# For MySQL
export DB_TYPE=mysql
export DB_NAME=synthetic_data
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=password
```

## Data Model

The service generates data for the following entities:

### Database Schema Overview

The synthetic data is organized into six main tables that represent a typical CRM and ERP system:

#### Customers Table (`customers`)

Represents business clients with detailed contact information and company metadata.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `customer_id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `name` | String | Company name | "Joyce, Murray and Campbell", "Moody-Taylor" |
| `email` | String | Primary contact email (unique) | "ashaw@montoya.com" |
| `phone` | String | Contact phone number | "907-458-1814x124" |
| `address` | String | Street address | "37506 Randy Landing Apt. 615" |
| `city` | String | City | "North Lucas" |
| `state` | String | State or province | "Connecticut" |
| `postal_code` | String | Postal or ZIP code | "94178" |
| `country` | String | Country | "Pakistan", "United States" |
| `region` | String | Geographic region | "North", "South", "East", "West", "Central" |
| `industry` | String | Business sector | "Technology", "Healthcare", "Finance", "Retail", "Energy" |
| `company_size` | String | Size classification | "Small", "Medium", "Large", "Enterprise" |
| `created_at` | DateTime | Record creation timestamp | "2020-07-10 00:00:00" |
| `updated_at` | DateTime | Last update timestamp | "2025-04-16 10:19:19" |

#### Products Table (`products`)

Represents items that can be sold, with detailed categorization and pricing information.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `product_id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `product_name` | String | Name of the product | "iterate killer e-commerce", "brand virtual channels" |
| `description` | Text | Detailed product description | "A comprehensive solution for..." |
| `category` | String | Main product category | "Electronics", "Furniture", "Clothing", "Office Supplies" |
| `subcategory` | String | Product subcategory | "Smartphones", "Laptops", "Chairs", "Desks" |
| `unit_price` | Float | Selling price per unit | 368.38, 443.72 |
| `cost_price` | Float | Cost to acquire or produce | 184.19, 221.86 |
| `supplier_id` | Integer | Foreign key to suppliers table | 1, 2, 3 |
| `created_at` | DateTime | Record creation timestamp | "2020-07-10 00:00:00" |
| `updated_at` | DateTime | Last update timestamp | "2025-04-16 10:19:19" |

#### Suppliers Table (`suppliers`)

Represents vendors that provide products to the company.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `supplier_id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `name` | String | Supplier company name | "Smith Inc", "Johnson LLC" |
| `contact_name` | String | Primary contact person | "John Smith", "Jane Johnson" |
| `email` | String | Contact email | "contact@smithinc.com" |
| `phone` | String | Contact phone number | "555-123-4567" |
| `address` | String | Street address | "123 Main St" |
| `city` | String | City | "New York" |
| `state` | String | State or province | "NY" |
| `postal_code` | String | Postal or ZIP code | "10001" |
| `country` | String | Country | "United States", "Canada" |
| `created_at` | DateTime | Record creation timestamp | "2020-07-10 00:00:00" |

#### Warehouse Items Table (`warehouse`)

Represents inventory stock for products across different warehouse locations.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `product_id` | Integer | Foreign key to products table | 1, 2, 3 |
| `warehouse_name` | String | Name of the warehouse | "Main Warehouse", "East Coast Facility", "Central Distribution" |
| `stock_quantity` | Integer | Current inventory quantity | 72, 880, 552 |
| `reorder_level` | Integer | Minimum stock before reordering | 100, 52, 26 |
| `last_restock_date` | DateTime | Date of last inventory restock | "2020-04-30 00:00:00" |
| `updated_at` | DateTime | Last update timestamp | "2025-04-09 12:19:19" |

#### Sales Table (`sales`)

Represents transactions between customers and products.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `sale_id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `customer_id` | Integer | Foreign key to customers table | 1, 9, 3 |
| `product_id` | Integer | Foreign key to products table | 16, 29, 8 |
| `quantity` | Integer | Number of units sold | 6, 10, 7 |
| `unit_price` | Float | Price per unit at time of sale | 368.38, 443.72, 867.82 |
| `discount` | Float | Discount amount applied | 13.4, 62.23, 84.8 |
| `total_amount` | Float | Total sale amount after discount | 2129.88, 3814.9, 5481.14 |
| `sale_date` | DateTime | Date and time of the sale | "2021-09-17 00:00:00", "2023-05-01 00:00:00" |
| `payment_method` | String | Method of payment | "Credit Card", "Bank Transfer", "Cash", "PayPal" |
| `status` | String | Current status of the sale | "Completed", "Pending", "Cancelled", "Refunded" |

#### Employees Table (`employees`)

Represents staff members with department information and reporting structure.

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `employee_id` | Integer | Primary key, auto-incrementing | 1, 2, 3 |
| `first_name` | String | Employee's first name | "John", "Jane" |
| `last_name` | String | Employee's last name | "Smith", "Johnson" |
| `email` | String | Work email (unique) | "john.smith@company.com" |
| `phone` | String | Contact phone number | "555-123-4567" |
| `department` | String | Department name | "Sales", "Marketing", "Engineering", "HR", "Finance" |
| `position` | String | Job title | "Sales Representative", "Marketing Manager", "Software Engineer" |
| `hire_date` | DateTime | Date employee was hired | "2020-07-10 00:00:00" |
| `salary` | Float | Annual salary | 75000.00, 120000.00 |
| `manager_id` | Integer | Foreign key to employees table (self-referential) | 1, 2, NULL |

### Data Relationships

The database schema includes the following relationships:

1. **Products to Suppliers**: Many-to-one relationship (each product has one supplier, each supplier can provide many products)
2. **Products to Warehouse Items**: One-to-many relationship (each product can be stocked in multiple warehouses)
3. **Customers to Sales**: One-to-many relationship (each customer can have multiple sales)
4. **Products to Sales**: One-to-many relationship (each product can be sold multiple times)
5. **Employees to Employees**: Self-referential relationship (each employee can have one manager, each manager can have multiple subordinates)

A visual representation of the database schema and relationships is available in the [schema diagram](docs/schema_diagram.md).

### Data Generation Patterns

The synthetic data follows these patterns:

1. **Customer Data**: 
   - Company names use realistic business naming patterns
   - Contact information includes properly formatted emails and phone numbers
   - Geographic distribution across regions is balanced
   - Industry and company size distributions reflect realistic market segments

2. **Product Data**:
   - Products are categorized into main categories and subcategories
   - Pricing follows realistic patterns with cost typically 40-80% of selling price
   - Product names reflect business jargon and industry terminology

3. **Sales Data**:
   - Sales dates are distributed across the configured time range
   - Quantities follow typical purchasing patterns (1-10 units per transaction)
   - Discounts range from 0-20% of the unit price
   - Payment methods and statuses follow realistic distribution patterns

4. **Employee Data**:
   - Hierarchical reporting structure with executives, managers, and staff
   - Salaries correlate with position levels
   - Departments have appropriate position titles
   - Hire dates are distributed realistically over time

5. **Warehouse Data**:
   - Products are distributed across multiple warehouse locations
   - Stock quantities and reorder levels vary by product
   - Inventory is updated based on completed sales

## Running Tests

Run the unit tests to verify the data generator:

```bash
python -m unittest synthetic_data_service.test_generator
```

## Example Queries and Analysis

The synthetic data is designed to support complex queries and analysis. Here are some example SQL queries that demonstrate the types of insights that can be derived:

### Basic Queries

**1. List all customers in a specific region and industry:**

```sql
SELECT customer_id, name, city, state, country, industry, company_size
FROM customers
WHERE region = 'North' AND industry = 'Technology';
```

**2. Find products with low inventory (below reorder level):**

```sql
SELECT p.product_id, p.product_name, p.category, w.warehouse_name, 
       w.stock_quantity, w.reorder_level
FROM products p
JOIN warehouse w ON p.product_id = w.product_id
WHERE w.stock_quantity < w.reorder_level
ORDER BY (w.reorder_level - w.stock_quantity) DESC;
```

**3. List employees by department with their managers:**

```sql
SELECT e.employee_id, e.first_name, e.last_name, e.department, e.position,
       m.first_name || ' ' || m.last_name AS manager_name
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.employee_id
ORDER BY e.department, e.position;
```

### Data Fusion Queries

**1. Sales performance by region and product category:**

```sql
SELECT c.region, p.category, 
       COUNT(s.sale_id) AS num_sales,
       SUM(s.total_amount) AS total_revenue,
       AVG(s.total_amount) AS avg_sale_value
FROM sales s
JOIN customers c ON s.customer_id = c.customer_id
JOIN products p ON s.product_id = p.product_id
WHERE s.status = 'Completed'
GROUP BY c.region, p.category
ORDER BY total_revenue DESC;
```

**2. Customer purchase history with product details:**

```sql
SELECT c.name AS customer_name, c.industry, c.company_size,
       p.product_name, p.category, p.subcategory,
       s.quantity, s.total_amount, s.sale_date
FROM customers c
JOIN sales s ON c.customer_id = s.customer_id
JOIN products p ON s.product_id = p.product_id
WHERE c.customer_id = 1
ORDER BY s.sale_date DESC;
```

**3. Supplier performance analysis:**

```sql
SELECT sup.name AS supplier_name, sup.country,
       COUNT(p.product_id) AS num_products,
       COUNT(DISTINCT s.sale_id) AS num_sales,
       SUM(s.total_amount) AS total_revenue
FROM suppliers sup
JOIN products p ON sup.supplier_id = p.supplier_id
JOIN sales s ON p.product_id = s.product_id
WHERE s.status = 'Completed'
GROUP BY sup.supplier_id
ORDER BY total_revenue DESC;
```

**4. Inventory valuation by warehouse:**

```sql
SELECT w.warehouse_name,
       SUM(w.stock_quantity * p.cost_price) AS inventory_value,
       COUNT(DISTINCT p.product_id) AS unique_products,
       SUM(w.stock_quantity) AS total_items
FROM warehouse w
JOIN products p ON w.product_id = p.product_id
GROUP BY w.warehouse_name
ORDER BY inventory_value DESC;
```

**5. Sales trends over time by product category:**

```sql
SELECT 
    strftime('%Y-%m', s.sale_date) AS month,
    p.category,
    COUNT(s.sale_id) AS num_sales,
    SUM(s.total_amount) AS monthly_revenue
FROM sales s
JOIN products p ON s.product_id = p.product_id
WHERE s.status = 'Completed'
GROUP BY month, p.category
ORDER BY month, monthly_revenue DESC;
```

## Extended Data Models

In addition to the relational database, this service can generate synthetic data in other formats to simulate a more realistic business environment:

### Document Store

JSON documents organized into collections that represent unstructured or semi-structured business data:

- **Product Details**: Rich, detailed product information beyond what's in the relational database
- **Customer Feedback**: Reviews and ratings from customers about products
- **Marketing Campaigns**: Information about marketing initiatives, target audiences, and performance
- **Support Tickets**: Customer support interactions with conversation history
- **Knowledge Base**: Internal knowledge articles and documentation

### Graph Database

Graph data representing relationships between business entities:

- **Employee Network**: Organizational relationships including management, collaboration, and mentorship
- **Product Network**: Relationships between products such as similarities, accessories, and purchase patterns
- **Customer-Product Network**: Interactions between customers and products beyond just purchases
- **Supply Chain Network**: Flow of products from suppliers through warehouses to distribution centers

### Generating Extended Data

To generate the extended data models:

```bash
python -m synthetic_data_service.extended_data_generator --db-path synthetic_data.db --output-dir extended_data
```

For more details on the extended data models, see the [extended data documentation](docs/extended_data.md).

## Extending the Service

This service is designed to be extended for data fusion, crawling, and analysis experiments:

1. **Data Crawling**: Implement crawlers that extract data from the synthetic database based on specific criteria.

2. **Data Fusion**: Create modules that combine data across different models (relational, document, graph) to derive comprehensive insights.

3. **Analysis**: Build analytical queries and visualizations on top of the synthetic data.

4. **Machine Learning**: Use the synthetic data to train and test machine learning models for:
   - Customer segmentation
   - Sales forecasting
   - Product recommendation
   - Anomaly detection in sales patterns

## License

[MIT License](LICENSE)