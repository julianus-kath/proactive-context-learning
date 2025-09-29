#!/usr/bin/env python3
"""
Script to set up the webshop schema with sample tables for testing.
This creates the schema structure mentioned in the chat log.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

from mcp_server.db import db_manager

async def setup_webshop_schema():
    """Set up the webshop schema with sample tables."""
    try:
        await db_manager.initialize()
        
        # Create webshop schema
        print("Creating webshop schema...")
        await db_manager.execute("CREATE SCHEMA IF NOT EXISTS webshop")
        
        # Create tables mentioned in the chat log
        tables = [
            """
            CREATE TABLE IF NOT EXISTS webshop.labels (
                label_id SERIAL PRIMARY KEY,
                label_name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.products (
                product_id SERIAL PRIMARY KEY,
                product_name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10,2),
                category VARCHAR(100),
                brand VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.articles (
                article_id SERIAL PRIMARY KEY,
                article_code VARCHAR(50) UNIQUE NOT NULL,
                product_id INTEGER REFERENCES webshop.products(product_id),
                title VARCHAR(255),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.colors (
                color_id SERIAL PRIMARY KEY,
                color_name VARCHAR(50) NOT NULL,
                hex_code VARCHAR(7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.sizes (
                size_id SERIAL PRIMARY KEY,
                size_name VARCHAR(20) NOT NULL,
                size_category VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.customer (
                customer_id SERIAL PRIMARY KEY,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(20),
                date_of_birth DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.address (
                address_id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES webshop.customer(customer_id),
                street VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(50),
                postal_code VARCHAR(20),
                country VARCHAR(50),
                address_type VARCHAR(20) DEFAULT 'shipping',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.stock (
                stock_id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES webshop.products(product_id),
                color_id INTEGER REFERENCES webshop.colors(color_id),
                size_id INTEGER REFERENCES webshop.sizes(size_id),
                quantity INTEGER DEFAULT 0,
                reserved_quantity INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.order (
                order_id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES webshop.customer(customer_id),
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending',
                total_amount DECIMAL(10,2),
                shipping_address_id INTEGER REFERENCES webshop.address(address_id),
                billing_address_id INTEGER REFERENCES webshop.address(address_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webshop.order_positions (
                position_id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES webshop.order(order_id),
                product_id INTEGER REFERENCES webshop.products(product_id),
                color_id INTEGER REFERENCES webshop.colors(color_id),
                size_id INTEGER REFERENCES webshop.sizes(size_id),
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10,2),
                total_price DECIMAL(10,2)
            )
            """
        ]
        
        for table_sql in tables:
            print(f"Creating table...")
            await db_manager.execute(table_sql)
        
        print("✅ All tables created successfully!")
        
        # Insert some sample data
        print("\nInserting sample data...")
        
        # Sample customers
        await db_manager.execute("""
            INSERT INTO webshop.customer (first_name, last_name, email, phone) VALUES
            ('John', 'Doe', 'john.doe@email.com', '+1234567890'),
            ('Jane', 'Smith', 'jane.smith@email.com', '+1234567891'),
            ('Bob', 'Johnson', 'bob.johnson@email.com', '+1234567892'),
            ('Alice', 'Brown', 'alice.brown@email.com', '+1234567893'),
            ('Charlie', 'Wilson', 'charlie.wilson@email.com', '+1234567894'),
            ('Diana', 'Davis', 'diana.davis@email.com', '+1234567895'),
            ('Eve', 'Miller', 'eve.miller@email.com', '+1234567896'),
            ('Frank', 'Garcia', 'frank.garcia@email.com', '+1234567897'),
            ('Grace', 'Martinez', 'grace.martinez@email.com', '+1234567898'),
            ('Henry', 'Anderson', 'henry.anderson@email.com', '+1234567899'),
            ('Ivy', 'Taylor', 'ivy.taylor@email.com', '+1234567800'),
            ('Jack', 'Thomas', 'jack.thomas@email.com', '+1234567801'),
            ('Kate', 'Jackson', 'kate.jackson@email.com', '+1234567802'),
            ('Leo', 'White', 'leo.white@email.com', '+1234567803'),
            ('Mia', 'Harris', 'mia.harris@email.com', '+1234567804'),
            ('Noah', 'Clark', 'noah.clark@email.com', '+1234567805'),
            ('Olivia', 'Lewis', 'olivia.lewis@email.com', '+1234567806'),
            ('Paul', 'Robinson', 'paul.robinson@email.com', '+1234567807'),
            ('Quinn', 'Walker', 'quinn.walker@email.com', '+1234567808'),
            ('Ruby', 'Hall', 'ruby.hall@email.com', '+1234567809'),
            ('Sam', 'Allen', 'sam.allen@email.com', '+1234567810'),
            ('Tina', 'Young', 'tina.young@email.com', '+1234567811'),
            ('Uma', 'King', 'uma.king@email.com', '+1234567812'),
            ('Victor', 'Wright', 'victor.wright@email.com', '+1234567813')
            ON CONFLICT (email) DO NOTHING
        """)
        
        # Sample products
        await db_manager.execute("""
            INSERT INTO webshop.products (product_name, description, price, category, brand) VALUES
            ('T-Shirt Basic', 'Comfortable cotton t-shirt', 19.99, 'Clothing', 'BasicWear'),
            ('Jeans Classic', 'Classic blue jeans', 49.99, 'Clothing', 'DenimCo'),
            ('Sneakers Sport', 'Athletic sneakers', 79.99, 'Footwear', 'SportBrand'),
            ('Hoodie Warm', 'Warm hoodie for winter', 39.99, 'Clothing', 'WarmWear'),
            ('Cap Baseball', 'Baseball cap', 14.99, 'Accessories', 'CapCo'),
            ('Backpack Travel', 'Travel backpack', 89.99, 'Accessories', 'TravelGear'),
            ('Watch Digital', 'Digital sports watch', 129.99, 'Electronics', 'TimeTech'),
            ('Sunglasses Cool', 'Stylish sunglasses', 59.99, 'Accessories', 'EyeWear')
            ON CONFLICT DO NOTHING
        """)
        
        # Sample colors
        await db_manager.execute("""
            INSERT INTO webshop.colors (color_name, hex_code) VALUES
            ('Black', '#000000'),
            ('White', '#FFFFFF'),
            ('Red', '#FF0000'),
            ('Blue', '#0000FF'),
            ('Green', '#00FF00'),
            ('Yellow', '#FFFF00'),
            ('Purple', '#800080'),
            ('Orange', '#FFA500')
            ON CONFLICT DO NOTHING
        """)
        
        # Sample sizes
        await db_manager.execute("""
            INSERT INTO webshop.sizes (size_name, size_category) VALUES
            ('XS', 'Clothing'),
            ('S', 'Clothing'),
            ('M', 'Clothing'),
            ('L', 'Clothing'),
            ('XL', 'Clothing'),
            ('XXL', 'Clothing'),
            ('36', 'Footwear'),
            ('37', 'Footwear'),
            ('38', 'Footwear'),
            ('39', 'Footwear'),
            ('40', 'Footwear'),
            ('41', 'Footwear'),
            ('42', 'Footwear'),
            ('43', 'Footwear'),
            ('44', 'Footwear'),
            ('45', 'Footwear')
            ON CONFLICT DO NOTHING
        """)
        
        # Sample orders (including some in May)
        await db_manager.execute("""
            INSERT INTO webshop.order (customer_id, order_date, status, total_amount) VALUES
            (1, '2024-05-15 10:30:00', 'completed', 69.98),
            (2, '2024-05-20 14:15:00', 'completed', 129.99),
            (3, '2024-05-25 09:45:00', 'completed', 89.99),
            (4, '2024-06-01 16:20:00', 'completed', 49.99),
            (5, '2024-06-05 11:10:00', 'completed', 159.98),
            (6, '2024-06-10 13:30:00', 'pending', 79.99),
            (7, '2024-05-28 08:45:00', 'completed', 34.98),
            (8, '2024-05-12 17:20:00', 'completed', 199.97)
            ON CONFLICT DO NOTHING
        """)
        
        # Sample order positions
        await db_manager.execute("""
            INSERT INTO webshop.order_positions (order_id, product_id, color_id, size_id, quantity, unit_price, total_price) VALUES
            (1, 1, 1, 3, 2, 19.99, 39.98),
            (1, 5, 2, 3, 1, 14.99, 14.99),
            (1, 5, 4, 3, 1, 14.99, 14.99),
            (2, 7, 1, 3, 1, 129.99, 129.99),
            (3, 6, 3, 3, 1, 89.99, 89.99),
            (4, 2, 4, 3, 1, 49.99, 49.99),
            (5, 3, 1, 10, 1, 79.99, 79.99),
            (5, 4, 2, 4, 2, 39.99, 79.99),
            (6, 8, 1, 3, 1, 79.99, 79.99),
            (7, 1, 3, 2, 1, 19.99, 19.99),
            (7, 5, 1, 3, 1, 14.99, 14.99),
            (8, 1, 1, 4, 3, 19.99, 59.97),
            (8, 2, 4, 4, 1, 49.99, 49.99),
            (8, 3, 2, 11, 1, 79.99, 79.99),
            (8, 5, 4, 4, 1, 14.99, 14.99)
            ON CONFLICT DO NOTHING
        """)
        
        print("✅ Sample data inserted successfully!")
        
        # Verify the setup
        print("\nVerifying setup...")
        
        # Count customers
        result = await db_manager.fetch("SELECT COUNT(*) as count FROM webshop.customer")
        print(f"Customers: {result[0]['count']}")
        
        # Count orders
        result = await db_manager.fetch("SELECT COUNT(*) as count FROM webshop.order")
        print(f"Orders: {result[0]['count']}")
        
        # Count orders in May
        result = await db_manager.fetch("""
            SELECT COUNT(*) as count 
            FROM webshop.order 
            WHERE EXTRACT(MONTH FROM order_date) = 5
        """)
        print(f"Orders in May: {result[0]['count']}")
        
        # Most popular product
        result = await db_manager.fetch("""
            SELECT p.product_name, SUM(op.quantity) as total_quantity
            FROM webshop.order_positions op
            JOIN webshop.products p ON op.product_id = p.product_id
            GROUP BY p.product_id, p.product_name
            ORDER BY total_quantity DESC
            LIMIT 1
        """)
        if result:
            print(f"Most popular product: {result[0]['product_name']} ({result[0]['total_quantity']} units)")
        
        print("\n🎉 Webshop schema setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error setting up webshop schema: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(setup_webshop_schema())