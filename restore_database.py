#!/usr/bin/env python3
"""
Simple script to restore the PostgreSQL database with essential ERP data
without using the problematic synthetic_data_service.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

def create_connection():
    """Create PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="synthetic_erp_data",
            user="juli",
            password=""
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def create_tables(conn):
    """Create the essential ERP tables."""
    cursor = conn.cursor()
    
    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            price DECIMAL(10,2),
            cost DECIMAL(10,2),
            sku VARCHAR(50) UNIQUE,
            stock_quantity INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 10,
            supplier_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create suppliers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            contact_person VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            city VARCHAR(100),
            state VARCHAR(50),
            postal_code VARCHAR(20),
            country VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create employees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id SERIAL PRIMARY KEY,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(50),
            department VARCHAR(100),
            position VARCHAR(100),
            salary DECIMAL(10,2),
            hire_date DATE,
            manager_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            sale_id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            employee_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            sale_date DATE NOT NULL,
            status VARCHAR(50) DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create warehouse table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warehouse (
            warehouse_id SERIAL PRIMARY KEY,
            product_id INTEGER,
            location VARCHAR(100),
            quantity INTEGER DEFAULT 0,
            reserved_quantity INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    print("✅ Tables created successfully")

def insert_sample_data(conn):
    """Insert sample data into the tables."""
    cursor = conn.cursor()
    
    # Insert suppliers
    suppliers_data = [
        ("TechSupply Corp", "John Smith", "john@techsupply.com", "+1-555-1001", "123 Tech St", "San Francisco", "CA", "94105", "USA"),
        ("Global Parts Ltd", "Sarah Johnson", "sarah@globalparts.com", "+1-555-1002", "456 Industrial Ave", "Chicago", "IL", "60601", "USA"),
        ("Premium Components", "Mike Wilson", "mike@premium.com", "+1-555-1003", "789 Quality Blvd", "Austin", "TX", "73301", "USA"),
    ]
    
    cursor.executemany("""
        INSERT INTO suppliers (name, contact_person, email, phone, address, city, state, postal_code, country)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, suppliers_data)
    
    # Insert products
    products_data = [
        ("Laptop Pro 15", "High-performance laptop for professionals", "Electronics", 1299.99, 899.99, "LAP-PRO-15", 25, 5, 1),
        ("Wireless Mouse", "Ergonomic wireless mouse", "Electronics", 49.99, 25.99, "WM-ERG-01", 150, 20, 1),
        ("Office Chair", "Comfortable ergonomic office chair", "Furniture", 299.99, 199.99, "OFC-CHR-01", 12, 3, 2),
        ("Desk Lamp", "LED desk lamp with adjustable brightness", "Furniture", 79.99, 45.99, "DSK-LMP-01", 35, 10, 2),
        ("Smartphone X", "Latest smartphone with advanced features", "Electronics", 899.99, 599.99, "SPH-X-01", 40, 8, 3),
        ("Tablet Pro", "Professional tablet for creative work", "Electronics", 649.99, 449.99, "TAB-PRO-01", 20, 5, 3),
        ("Keyboard Mechanical", "Mechanical keyboard for gaming and typing", "Electronics", 129.99, 79.99, "KBD-MECH-01", 60, 15, 1),
        ("Monitor 27inch", "4K monitor for professional use", "Electronics", 399.99, 279.99, "MON-27-4K", 18, 4, 1),
    ]
    
    cursor.executemany("""
        INSERT INTO products (name, description, category, price, cost, sku, stock_quantity, reorder_level, supplier_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sku) DO NOTHING
    """, products_data)
    
    # Insert employees
    employees_data = [
        ("Alice", "Johnson", "alice.johnson@company.com", "+1-555-2001", "Sales", "Sales Manager", 75000.00, "2022-01-15", None),
        ("Bob", "Smith", "bob.smith@company.com", "+1-555-2002", "Sales", "Sales Representative", 55000.00, "2022-03-01", 1),
        ("Carol", "Davis", "carol.davis@company.com", "+1-555-2003", "Marketing", "Marketing Manager", 70000.00, "2021-11-10", None),
        ("David", "Wilson", "david.wilson@company.com", "+1-555-2004", "IT", "IT Manager", 85000.00, "2021-08-20", None),
        ("Emma", "Brown", "emma.brown@company.com", "+1-555-2005", "Sales", "Sales Representative", 52000.00, "2023-02-14", 1),
    ]
    
    cursor.executemany("""
        INSERT INTO employees (first_name, last_name, email, phone, department, position, salary, hire_date, manager_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
    """, employees_data)
    
    # Insert warehouse data
    warehouse_data = [
        (1, "Main Warehouse", 25, 2),
        (2, "Main Warehouse", 150, 10),
        (3, "Main Warehouse", 12, 1),
        (4, "Main Warehouse", 35, 5),
        (5, "Main Warehouse", 40, 3),
        (6, "Main Warehouse", 20, 2),
        (7, "Main Warehouse", 60, 8),
        (8, "Main Warehouse", 18, 1),
    ]
    
    cursor.executemany("""
        INSERT INTO warehouse (product_id, location, quantity, reserved_quantity)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, warehouse_data)
    
    # Insert sales data
    sales_data = [
        (1, 1, 1, 2, 1299.99, 2599.98, "2024-01-15"),
        (2, 2, 2, 1, 49.99, 49.99, "2024-01-16"),
        (3, 1, 3, 1, 299.99, 299.99, "2024-01-17"),
        (1, 5, 5, 3, 899.99, 2699.97, "2024-01-18"),
        (2, 2, 7, 2, 129.99, 259.98, "2024-01-19"),
        (3, 1, 8, 1, 399.99, 399.99, "2024-01-20"),
        (1, 5, 6, 1, 649.99, 649.99, "2024-01-21"),
        (2, 2, 4, 3, 79.99, 239.97, "2024-01-22"),
    ]
    
    cursor.executemany("""
        INSERT INTO sales (customer_id, employee_id, product_id, quantity, unit_price, total_amount, sale_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, sales_data)
    
    conn.commit()
    print("✅ Sample data inserted successfully")

def verify_data(conn):
    """Verify that data was inserted correctly."""
    cursor = conn.cursor()
    
    tables = ['customers', 'products', 'suppliers', 'employees', 'sales', 'warehouse']
    
    print("\n📊 Database Status:")
    print("=" * 40)
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table:12}: {count:4} records")
    
    print("=" * 40)

def main():
    """Main function."""
    print("🔧 Restoring PostgreSQL Database")
    print("=" * 40)
    
    # Connect to database
    conn = create_connection()
    if not conn:
        sys.exit(1)
    
    try:
        # Create tables
        create_tables(conn)
        
        # Insert sample data
        insert_sample_data(conn)
        
        # Verify data
        verify_data(conn)
        
        print("\n🎉 Database restored successfully!")
        print("\n📋 Available tables:")
        print("   - customers (existing data preserved)")
        print("   - products (8 sample products)")
        print("   - suppliers (3 suppliers)")
        print("   - employees (5 employees)")
        print("   - sales (8 sales records)")
        print("   - warehouse (8 inventory records)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()