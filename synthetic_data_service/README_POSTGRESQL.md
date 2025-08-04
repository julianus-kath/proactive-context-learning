# Enhanced Synthetic ERP Data Service - PostgreSQL Edition

This enhanced version of the synthetic data service generates comprehensive ERP/CRM data in a PostgreSQL database, designed for MCP (Model Context Protocol) and LangGraph integration.

## Features

### Enhanced Data Model
- **Customers**: 5,000+ records with detailed company information, credit ratings, and financial data
- **Products**: 10,000+ records with SKUs, barcodes, detailed specifications, and inventory tracking
- **Suppliers**: 500+ records with payment terms, credit ratings, and lead times
- **Employees**: 1,000+ records with hierarchical relationships, departments, and compensation
- **Sales**: 50,000+ records with order tracking, payment processing, and shipping details
- **Warehouse**: Comprehensive inventory management across multiple locations

### PostgreSQL Optimizations
- Proper indexing for query performance
- Batch processing for large data sets
- Connection pooling and optimization
- Decimal precision for financial data
- Foreign key relationships and constraints

### Realistic Data Generation
- Industry-specific product categories and pricing
- Company size-based customer segmentation
- Hierarchical employee structures with managers
- Seasonal sales patterns and trends
- Geographic distribution across regions

## Prerequisites

### PostgreSQL Installation

**macOS (using Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
Download and install from [PostgreSQL official website](https://www.postgresql.org/download/windows/)

### Python Dependencies
```bash
pip install -r requirements.txt
```

## Setup

### 1. Configure Environment
Copy the example environment file and customize:
```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL credentials:
```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=postgres
DB_PASSWORD=your_password
```

### 2. Setup PostgreSQL Database
```bash
python setup_postgres.py
```

This script will:
- Create the database if it doesn't exist
- Test the connection
- Verify PostgreSQL version compatibility

### 3. Generate Synthetic Data

**Quick Start (Default volumes):**
```bash
python -m synthetic_data_service.main --drop-tables
```

**Custom Data Volumes:**
```bash
python -m synthetic_data_service.main \
    --customers 10000 \
    --products 20000 \
    --suppliers 1000 \
    --employees 2000 \
    --sales 100000 \
    --batch-size 2000 \
    --drop-tables
```

**Production Scale:**
```bash
python -m synthetic_data_service.main \
    --customers 50000 \
    --products 100000 \
    --suppliers 5000 \
    --employees 10000 \
    --sales 1000000 \
    --batch-size 5000 \
    --drop-tables
```

## Data Model Details

### Customers Table
- **Primary Key**: customer_id
- **Unique Fields**: email, tax_id
- **Key Relationships**: → sales
- **Business Logic**: Credit limits based on company size, industry-specific revenue ranges

### Products Table
- **Primary Key**: product_id
- **Unique Fields**: sku, barcode
- **Key Relationships**: → suppliers, → warehouse, → sales
- **Business Logic**: Category-based pricing, realistic specifications

### Sales Table
- **Primary Key**: sale_id
- **Unique Fields**: order_number
- **Key Relationships**: → customers, → products, → employees
- **Business Logic**: Tax calculations, shipping costs, order lifecycle tracking

### Employees Table
- **Primary Key**: employee_id
- **Unique Fields**: employee_number, email
- **Self-Referential**: manager_id → employee_id
- **Business Logic**: Department-based hierarchies, position-based compensation

## Performance Considerations

### Indexing Strategy
- Primary keys and foreign keys are automatically indexed
- Additional indexes on frequently queried fields:
  - Customer region, industry, company size
  - Product category, brand, active status
  - Sale date, status, customer
  - Employee department, active status

### Batch Processing
- Default batch size: 1,000 records
- Configurable via `--batch-size` parameter
- Optimized for PostgreSQL's bulk insert performance

### Memory Usage
- Generator uses lazy loading and batch processing
- Memory usage scales with batch size, not total record count
- Recommended: 8GB RAM for 1M+ sales records

## Database Queries

### Sample Analytical Queries

**Top Customers by Revenue:**
```sql
SELECT 
    c.name,
    c.industry,
    c.company_size,
    SUM(s.total_amount) as total_revenue,
    COUNT(s.sale_id) as order_count
FROM customers c
JOIN sales s ON c.customer_id = s.customer_id
WHERE s.status = 'Completed'
GROUP BY c.customer_id, c.name, c.industry, c.company_size
ORDER BY total_revenue DESC
LIMIT 10;
```

**Product Performance by Category:**
```sql
SELECT 
    p.category,
    p.subcategory,
    COUNT(s.sale_id) as units_sold,
    SUM(s.quantity) as total_quantity,
    SUM(s.total_amount) as revenue,
    AVG(s.unit_price) as avg_price
FROM products p
JOIN sales s ON p.product_id = s.product_id
WHERE s.status = 'Completed'
GROUP BY p.category, p.subcategory
ORDER BY revenue DESC;
```

**Sales Performance by Employee:**
```sql
SELECT 
    e.first_name || ' ' || e.last_name as employee_name,
    e.department,
    e.position,
    COUNT(s.sale_id) as sales_count,
    SUM(s.total_amount) as total_sales,
    AVG(s.total_amount) as avg_sale_amount
FROM employees e
JOIN sales s ON e.employee_id = s.employee_id
WHERE s.status = 'Completed'
GROUP BY e.employee_id, employee_name, e.department, e.position
ORDER BY total_sales DESC
LIMIT 20;
```

**Inventory Status:**
```sql
SELECT 
    p.product_name,
    p.sku,
    p.category,
    w.warehouse_name,
    w.stock_quantity,
    w.reorder_level,
    CASE 
        WHEN w.stock_quantity <= w.reorder_level THEN 'REORDER'
        WHEN w.stock_quantity = 0 THEN 'OUT_OF_STOCK'
        ELSE 'IN_STOCK'
    END as stock_status
FROM products p
JOIN warehouse w ON p.product_id = w.product_id
WHERE p.is_active = true
ORDER BY w.stock_quantity ASC;
```

## MCP Integration Ready

This database is designed for MCP (Model Context Protocol) integration with the following considerations:

### Schema Documentation
- All tables have comprehensive column descriptions
- Foreign key relationships are clearly defined
- Business rules are documented in constraints

### Query Optimization
- Indexes on commonly filtered columns
- Efficient join paths between related tables
- Optimized for both OLTP and analytical queries

### Data Quality
- Referential integrity enforced
- Realistic data distributions
- Consistent data formats and patterns

## LangGraph Integration

The database structure supports LangGraph workflows:

### Multi-Agent Queries
- **Customer Agent**: Focus on customer-related tables and relationships
- **Product Agent**: Handle inventory, catalog, and supplier queries
- **Sales Agent**: Process transaction and performance analytics
- **Employee Agent**: Manage organizational and HR-related queries

### Cross-Domain Analysis
- Customer-Product relationships for recommendation systems
- Sales-Employee relationships for performance tracking
- Supplier-Product relationships for procurement optimization
- Geographic analysis across customers and warehouses

## Troubleshooting

### Common Issues

**Connection Refused:**
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql
# or
sudo systemctl status postgresql
```

**Permission Denied:**
```bash
# Create PostgreSQL user if needed
sudo -u postgres createuser --interactive
```

**Memory Issues with Large Datasets:**
```bash
# Reduce batch size
python -m synthetic_data_service.main --batch-size 500
```

**Slow Performance:**
```bash
# Check PostgreSQL configuration
# Increase shared_buffers and work_mem in postgresql.conf
```

### Performance Tuning

**PostgreSQL Configuration (postgresql.conf):**
```
shared_buffers = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
```

**Connection Pooling:**
The service includes connection pooling configuration in `db.py`:
- Pool size: 20 connections
- Max overflow: 30 connections
- Connection recycling: 1 hour

## Next Steps

1. **MCP Server Implementation**: Use this database as the backend for an MCP server
2. **LangGraph Integration**: Create specialized agents for different data domains
3. **API Development**: Build REST/GraphQL APIs on top of the data
4. **Analytics Dashboard**: Create visualization tools for the synthetic data
5. **Machine Learning**: Use the data for training recommendation systems or predictive models

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify PostgreSQL installation and configuration
3. Ensure all Python dependencies are installed
4. Check database connection parameters in `.env`