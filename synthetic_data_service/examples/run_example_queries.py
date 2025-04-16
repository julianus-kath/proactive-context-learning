"""
Example script to run the SQL queries from the README.
This script demonstrates how to execute the example queries and display the results.
"""

import os
import sys
import sqlite3
from tabulate import tabulate

# Add the parent directory to the path so we can import the synthetic_data_service package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def execute_query(conn, query, title):
    """Execute a SQL query and print the results in a formatted table."""
    print(f"\n=== {title} ===\n")
    cursor = conn.cursor()
    cursor.execute(query)
    
    # Get column names from cursor description
    columns = [desc[0] for desc in cursor.description]
    
    # Fetch all rows
    rows = cursor.fetchall()
    
    # Print results in a table format
    print(tabulate(rows, headers=columns, tablefmt="grid"))
    print(f"\nTotal rows: {len(rows)}\n")
    
    return rows


def main():
    """Run example queries from the README."""
    # Connect to the SQLite database
    db_path = os.path.join(os.path.dirname(__file__), '../../synthetic_data.db')
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print("Please run the data generator first:")
        print("python -m synthetic_data_service.main")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Example 1: List all customers in a specific region and industry
        query1 = """
        SELECT customer_id, name, city, state, country, industry, company_size
        FROM customers
        WHERE region = 'North' AND industry = 'Technology';
        """
        execute_query(conn, query1, "Customers in North Region in Technology Industry")
        
        # Example 2: Find products with low inventory
        query2 = """
        SELECT p.product_id, p.product_name, p.category, w.warehouse_name, 
               w.stock_quantity, w.reorder_level
        FROM products p
        JOIN warehouse w ON p.product_id = w.product_id
        WHERE w.stock_quantity < w.reorder_level
        ORDER BY (w.reorder_level - w.stock_quantity) DESC
        LIMIT 10;
        """
        execute_query(conn, query2, "Products with Low Inventory")
        
        # Example 3: List employees by department with their managers
        query3 = """
        SELECT e.employee_id, e.first_name, e.last_name, e.department, e.position,
               m.first_name || ' ' || m.last_name AS manager_name
        FROM employees e
        LEFT JOIN employees m ON e.manager_id = m.employee_id
        ORDER BY e.department, e.position
        LIMIT 10;
        """
        execute_query(conn, query3, "Employees with Their Managers")
        
        # Example 4: Sales performance by region and product category
        query4 = """
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
        """
        execute_query(conn, query4, "Sales Performance by Region and Product Category")
        
        # Example 5: Customer purchase history
        query5 = """
        SELECT c.name AS customer_name, c.industry, c.company_size,
               p.product_name, p.category, p.subcategory,
               s.quantity, s.total_amount, s.sale_date
        FROM customers c
        JOIN sales s ON c.customer_id = s.customer_id
        JOIN products p ON s.product_id = p.product_id
        WHERE c.customer_id = 1
        ORDER BY s.sale_date DESC;
        """
        execute_query(conn, query5, "Purchase History for Customer ID 1")
        
        # Example 6: Inventory valuation by warehouse
        query6 = """
        SELECT w.warehouse_name,
               SUM(w.stock_quantity * p.cost_price) AS inventory_value,
               COUNT(DISTINCT p.product_id) AS unique_products,
               SUM(w.stock_quantity) AS total_items
        FROM warehouse w
        JOIN products p ON w.product_id = p.product_id
        GROUP BY w.warehouse_name
        ORDER BY inventory_value DESC;
        """
        execute_query(conn, query6, "Inventory Valuation by Warehouse")
        
        # Example 7: Sales trends over time
        query7 = """
        SELECT 
            strftime('%Y-%m', s.sale_date) AS month,
            COUNT(s.sale_id) AS num_sales,
            SUM(s.total_amount) AS monthly_revenue
        FROM sales s
        WHERE s.status = 'Completed'
        GROUP BY month
        ORDER BY month;
        """
        execute_query(conn, query7, "Sales Trends Over Time")
        
    finally:
        # Close the connection
        conn.close()


if __name__ == "__main__":
    main()