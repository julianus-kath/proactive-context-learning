"""
Tests for the synthetic data generator.
"""

import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from synthetic_data_service.db import Base
from synthetic_data_service.models import Customer, Product, Supplier, Sale, WarehouseItem, Employee
from synthetic_data_service.generator import generate_data


class TestDataGenerator(unittest.TestCase):
    """Test cases for the synthetic data generator."""
    
    def setUp(self):
        """Set up test database."""
        # Use an in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        
        # Create a session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def tearDown(self):
        """Clean up after tests."""
        self.session.close()
    
    def test_data_generation(self):
        """Test that the correct number of records are generated."""
        # Define test parameters
        num_customers = 10
        num_products = 20
        num_suppliers = 5
        num_employees = 8
        num_sales = 30
        
        # Generate data
        generate_data(
            session=self.session,
            num_customers=num_customers,
            num_products=num_products,
            num_suppliers=num_suppliers,
            num_employees=num_employees,
            num_sales=num_sales,
            seed=42  # Fixed seed for reproducibility
        )
        
        # Verify counts
        self.assertEqual(self.session.query(Customer).count(), num_customers)
        self.assertEqual(self.session.query(Product).count(), num_products)
        self.assertEqual(self.session.query(Supplier).count(), num_suppliers)
        self.assertEqual(self.session.query(Employee).count(), num_employees)
        self.assertEqual(self.session.query(Sale).count(), num_sales)
        
        # Verify warehouse items were created for products
        self.assertGreater(self.session.query(WarehouseItem).count(), 0)
    
    def test_referential_integrity(self):
        """Test that foreign key relationships are maintained."""
        # Generate a small dataset
        generate_data(
            session=self.session,
            num_customers=5,
            num_products=10,
            num_suppliers=3,
            num_employees=5,
            num_sales=15,
            seed=42
        )
        
        # Check that all sales reference valid customers and products
        for sale in self.session.query(Sale).all():
            customer = self.session.query(Customer).filter_by(customer_id=sale.customer_id).first()
            product = self.session.query(Product).filter_by(product_id=sale.product_id).first()
            
            self.assertIsNotNone(customer, f"Sale {sale.sale_id} references non-existent customer {sale.customer_id}")
            self.assertIsNotNone(product, f"Sale {sale.sale_id} references non-existent product {sale.product_id}")
        
        # Check that all products reference valid suppliers
        for product in self.session.query(Product).all():
            supplier = self.session.query(Supplier).filter_by(supplier_id=product.supplier_id).first()
            self.assertIsNotNone(supplier, f"Product {product.product_id} references non-existent supplier {product.supplier_id}")


if __name__ == "__main__":
    unittest.main()