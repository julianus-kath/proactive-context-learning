"""
Example script demonstrating how to query the synthetic database using SQLAlchemy.
"""

import os
import sys
from datetime import datetime
from tabulate import tabulate

# Add the parent directory to the path so we can import the synthetic_data_service package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from synthetic_data_service.db import get_db_session
from synthetic_data_service.models import Customer, Product, Supplier, Sale, Employee, WarehouseItem


def print_table(headers, rows):
    """Print data in a nicely formatted table."""
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print()


def main():
    """Query and display data from the synthetic database."""
    # Get a database session
    session = get_db_session()
    
    try:
        # Example 1: List all customers
        print("\n=== CUSTOMERS ===")
        customers = session.query(Customer).all()
        customer_rows = [
            (c.customer_id, c.name, c.region, c.industry, c.company_size)
            for c in customers
        ]
        print_table(["ID", "Name", "Region", "Industry", "Size"], customer_rows)
        
        # Example 2: List products by category
        print("\n=== PRODUCTS BY CATEGORY ===")
        products_by_category = {}
        for product in session.query(Product).all():
            if product.category not in products_by_category:
                products_by_category[product.category] = []
            products_by_category[product.category].append(product)
        
        for category, products in products_by_category.items():
            print(f"\nCategory: {category}")
            product_rows = [
                (p.product_id, p.product_name, p.subcategory, f"${p.unit_price:.2f}")
                for p in products
            ]
            print_table(["ID", "Name", "Subcategory", "Price"], product_rows)
        
        # Example 3: Recent sales with customer and product details
        print("\n=== RECENT SALES ===")
        recent_sales = session.query(Sale, Customer, Product)\
            .join(Customer, Sale.customer_id == Customer.customer_id)\
            .join(Product, Sale.product_id == Product.product_id)\
            .order_by(Sale.sale_date.desc())\
            .limit(10)\
            .all()
        
        sale_rows = [
            (
                s.sale_date.strftime("%Y-%m-%d"),
                c.name,
                p.product_name,
                s.quantity,
                f"${s.total_amount:.2f}",
                s.payment_method,
                s.status
            )
            for s, c, p in recent_sales
        ]
        print_table(
            ["Date", "Customer", "Product", "Qty", "Amount", "Payment", "Status"],
            sale_rows
        )
        
        # Example 4: Inventory status
        print("\n=== INVENTORY STATUS ===")
        inventory = session.query(WarehouseItem, Product)\
            .join(Product, WarehouseItem.product_id == Product.product_id)\
            .all()
        
        inventory_rows = [
            (
                w.warehouse_name,
                p.product_name,
                w.stock_quantity,
                w.reorder_level,
                "Low" if w.stock_quantity < w.reorder_level else "OK"
            )
            for w, p in inventory
        ]
        print_table(
            ["Warehouse", "Product", "Stock", "Reorder Level", "Status"],
            inventory_rows
        )
        
        # Example 5: Sales by region
        print("\n=== SALES BY REGION ===")
        sales_by_region = session.query(
            Customer.region,
            session.query(Sale).filter(Sale.customer_id == Customer.customer_id).count().label('sale_count'),
            session.query(Sale.total_amount).filter(Sale.customer_id == Customer.customer_id).with_entities(
                session.func.sum(Sale.total_amount)
            ).scalar_subquery().label('total_amount')
        ).group_by(Customer.region).all()
        
        region_rows = [
            (region, count, f"${amount:.2f}" if amount else "$0.00")
            for region, count, amount in sales_by_region
        ]
        print_table(["Region", "Number of Sales", "Total Amount"], region_rows)
        
    finally:
        # Always close the session
        session.close()


if __name__ == "__main__":
    main()