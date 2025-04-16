"""
Synthetic data generation logic.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from faker import Faker
from sqlalchemy.orm import Session

from synthetic_data_service.config import generator_config
from synthetic_data_service.models import (
    Customer, Product, Supplier, WarehouseItem, Sale, Employee
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataGenerator:
    """
    Generator for synthetic CRM and ERP data.
    """
    
    def __init__(self, session: Session, seed: Optional[int] = None):
        """
        Initialize the data generator.
        
        Args:
            session: SQLAlchemy database session
            seed: Random seed for reproducibility (default: from config)
        """
        self.session = session
        self.seed = seed if seed is not None else generator_config.random_seed
        self.faker = Faker()
        self.faker.seed_instance(self.seed)
        random.seed(self.seed)
        
        # Parse date strings from config
        self.start_date = datetime.strptime(generator_config.start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(generator_config.end_date, "%Y-%m-%d")
        
        # Cache for generated entities
        self.customers: List[Customer] = []
        self.products: List[Product] = []
        self.suppliers: List[Supplier] = []
        self.employees: List[Employee] = []
    
    def generate_all(self, num_customers: int, num_products: int, num_suppliers: int, 
                     num_employees: int, num_sales: int):
        """
        Generate all synthetic data entities.
        
        Args:
            num_customers: Number of customer records to generate
            num_products: Number of product records to generate
            num_suppliers: Number of supplier records to generate
            num_employees: Number of employee records to generate
            num_sales: Number of sales records to generate
        """
        logger.info("Starting synthetic data generation...")
        
        # Generate in the correct order to maintain referential integrity
        self.generate_suppliers(num_suppliers)
        self.generate_products(num_products)
        self.generate_warehouse_items()
        self.generate_customers(num_customers)
        self.generate_employees(num_employees)
        self.generate_sales(num_sales)
        
        logger.info("Synthetic data generation completed successfully.")
    
    def generate_random_date(self, start_date=None, end_date=None):
        """
        Generate a random date between start_date and end_date.
        
        Args:
            start_date: Start date (default: from config)
            end_date: End date (default: from config)
            
        Returns:
            Random datetime between start_date and end_date
        """
        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date
            
        time_between_dates = end_date - start_date
        days_between_dates = time_between_dates.days
        random_days = random.randrange(days_between_dates)
        return start_date + timedelta(days=random_days)
    
    def generate_suppliers(self, count: int):
        """
        Generate synthetic supplier data.
        
        Args:
            count: Number of supplier records to generate
        """
        logger.info(f"Generating {count} suppliers...")
        
        for _ in range(count):
            supplier = Supplier(
                name=self.faker.company(),
                contact_name=self.faker.name(),
                email=self.faker.company_email(),
                phone=self.faker.phone_number(),
                address=self.faker.street_address(),
                city=self.faker.city(),
                state=self.faker.state(),
                postal_code=self.faker.postcode(),
                country=self.faker.country(),
                created_at=self.generate_random_date()
            )
            self.session.add(supplier)
        
        self.session.commit()
        self.suppliers = self.session.query(Supplier).all()
        logger.info(f"Generated {len(self.suppliers)} suppliers.")
    
    def generate_products(self, count: int):
        """
        Generate synthetic product data.
        
        Args:
            count: Number of product records to generate
        """
        logger.info(f"Generating {count} products...")
        
        categories = [
            "Electronics", "Furniture", "Clothing", "Office Supplies", 
            "Food & Beverage", "Health & Beauty", "Sports & Outdoors"
        ]
        
        subcategories = {
            "Electronics": ["Smartphones", "Laptops", "Tablets", "Accessories", "Audio"],
            "Furniture": ["Chairs", "Desks", "Tables", "Sofas", "Storage"],
            "Clothing": ["Shirts", "Pants", "Dresses", "Outerwear", "Footwear"],
            "Office Supplies": ["Paper", "Writing Instruments", "Organizers", "Binders"],
            "Food & Beverage": ["Snacks", "Beverages", "Canned Goods", "Dairy"],
            "Health & Beauty": ["Skincare", "Haircare", "Cosmetics", "Personal Hygiene"],
            "Sports & Outdoors": ["Fitness", "Camping", "Team Sports", "Water Sports"]
        }
        
        for _ in range(count):
            category = random.choice(categories)
            subcategory = random.choice(subcategories[category])
            
            unit_price = round(random.uniform(10.0, 1000.0), 2)
            cost_price = round(unit_price * random.uniform(0.4, 0.8), 2)  # Cost is 40-80% of price
            
            product = Product(
                product_name=self.faker.bs(),
                description=self.faker.paragraph(),
                category=category,
                subcategory=subcategory,
                unit_price=unit_price,
                cost_price=cost_price,
                supplier_id=random.choice(self.suppliers).supplier_id,
                created_at=self.generate_random_date()
            )
            self.session.add(product)
        
        self.session.commit()
        self.products = self.session.query(Product).all()
        logger.info(f"Generated {len(self.products)} products.")
    
    def generate_warehouse_items(self):
        """Generate warehouse inventory items for all products."""
        logger.info("Generating warehouse inventory items...")
        
        warehouses = ["Main Warehouse", "East Coast Facility", "West Coast Facility", "Central Distribution"]
        
        for product in self.products:
            # Each product might be in 1-3 warehouses
            num_warehouses = random.randint(1, 3)
            selected_warehouses = random.sample(warehouses, num_warehouses)
            
            for warehouse in selected_warehouses:
                stock_quantity = random.randint(0, 1000)
                reorder_level = random.randint(10, 100)
                
                warehouse_item = WarehouseItem(
                    product_id=product.product_id,
                    warehouse_name=warehouse,
                    stock_quantity=stock_quantity,
                    reorder_level=reorder_level,
                    last_restock_date=self.generate_random_date(
                        end_date=datetime.now() - timedelta(days=random.randint(0, 90))
                    ),
                    updated_at=datetime.now() - timedelta(days=random.randint(0, 30))
                )
                self.session.add(warehouse_item)
        
        self.session.commit()
        logger.info("Generated warehouse inventory items.")
    
    def generate_customers(self, count: int):
        """
        Generate synthetic customer data.
        
        Args:
            count: Number of customer records to generate
        """
        logger.info(f"Generating {count} customers...")
        
        company_sizes = ["Small", "Medium", "Large", "Enterprise"]
        industries = [
            "Technology", "Healthcare", "Finance", "Manufacturing", "Retail", 
            "Education", "Government", "Hospitality", "Construction", "Energy"
        ]
        
        for _ in range(count):
            customer = Customer(
                name=self.faker.company(),
                email=self.faker.company_email(),
                phone=self.faker.phone_number(),
                address=self.faker.street_address(),
                city=self.faker.city(),
                state=self.faker.state(),
                postal_code=self.faker.postcode(),
                country=self.faker.country(),
                region=random.choice(generator_config.regions),
                industry=random.choice(industries),
                company_size=random.choice(company_sizes),
                created_at=self.generate_random_date()
            )
            self.session.add(customer)
        
        self.session.commit()
        self.customers = self.session.query(Customer).all()
        logger.info(f"Generated {len(self.customers)} customers.")
    
    def generate_employees(self, count: int):
        """
        Generate synthetic employee data.
        
        Args:
            count: Number of employee records to generate
        """
        logger.info(f"Generating {count} employees...")
        
        departments = ["Sales", "Marketing", "Engineering", "HR", "Finance", "Operations", "Customer Support"]
        positions = {
            "Sales": ["Sales Representative", "Account Manager", "Sales Manager", "VP of Sales"],
            "Marketing": ["Marketing Specialist", "Marketing Manager", "Content Creator", "CMO"],
            "Engineering": ["Software Engineer", "QA Engineer", "DevOps Engineer", "CTO"],
            "HR": ["HR Specialist", "Recruiter", "HR Manager", "VP of HR"],
            "Finance": ["Accountant", "Financial Analyst", "Controller", "CFO"],
            "Operations": ["Operations Specialist", "Operations Manager", "COO"],
            "Customer Support": ["Support Specialist", "Support Manager", "Customer Success Manager"]
        }
        
        # First, create employees without manager relationships
        for i in range(count):
            department = random.choice(departments)
            position = random.choice(positions[department])
            
            hire_date = self.generate_random_date(
                start_date=datetime(2010, 1, 1),
                end_date=datetime.now() - timedelta(days=30)
            )
            
            # Salary based on position (simple heuristic)
            if "VP" in position or "C" in position and "O" in position:
                salary = random.uniform(120000, 250000)
            elif "Manager" in position:
                salary = random.uniform(80000, 120000)
            else:
                salary = random.uniform(40000, 80000)
                
            employee = Employee(
                first_name=self.faker.first_name(),
                last_name=self.faker.last_name(),
                email=self.faker.email(),
                phone=self.faker.phone_number(),
                department=department,
                position=position,
                hire_date=hire_date,
                salary=round(salary, 2),
                # Manager will be set in the next step
            )
            self.session.add(employee)
        
        self.session.commit()
        self.employees = self.session.query(Employee).all()
        
        # Now assign managers (except for top executives)
        for employee in self.employees:
            if "VP" in employee.position or "C" in employee.position and "O" in employee.position:
                continue  # Top executives don't have managers in this model
                
            # Find potential managers in the same department
            potential_managers = [
                e for e in self.employees 
                if e.department == employee.department 
                and e.employee_id != employee.employee_id
                and ("Manager" in e.position or "VP" in e.position or "C" in e.position)
            ]
            
            if potential_managers:
                employee.manager_id = random.choice(potential_managers).employee_id
        
        self.session.commit()
        logger.info(f"Generated {len(self.employees)} employees.")
    
    def generate_sales(self, count: int):
        """
        Generate synthetic sales data.
        
        Args:
            count: Number of sales records to generate
        """
        logger.info(f"Generating {count} sales records...")
        
        payment_methods = ["Credit Card", "Debit Card", "Bank Transfer", "PayPal", "Cash"]
        statuses = ["Completed", "Pending", "Cancelled", "Refunded"]
        status_weights = [0.8, 0.1, 0.05, 0.05]  # 80% completed, 10% pending, etc.
        
        for _ in range(count):
            customer = random.choice(self.customers)
            product = random.choice(self.products)
            quantity = random.randint(1, 10)
            
            # Apply random discount (0-20%)
            discount_percent = random.uniform(0, 0.2)
            unit_price = product.unit_price
            discount_amount = round(unit_price * discount_percent, 2)
            discounted_price = unit_price - discount_amount
            
            total_amount = round(discounted_price * quantity, 2)
            
            # Generate a sale date after the customer was created
            sale_date = self.generate_random_date(
                start_date=customer.created_at,
                end_date=self.end_date
            )
            
            sale = Sale(
                customer_id=customer.customer_id,
                product_id=product.product_id,
                quantity=quantity,
                unit_price=unit_price,
                discount=discount_amount,
                total_amount=total_amount,
                sale_date=sale_date,
                payment_method=random.choice(payment_methods),
                status=random.choices(statuses, weights=status_weights)[0]
            )
            self.session.add(sale)
            
            # Update inventory for completed sales
            if sale.status == "Completed":
                # Find warehouse items for this product
                warehouse_items = self.session.query(WarehouseItem).filter(
                    WarehouseItem.product_id == product.product_id
                ).all()
                
                if warehouse_items:
                    # Choose a warehouse to fulfill from
                    warehouse_item = random.choice(warehouse_items)
                    # Only reduce stock if there's enough inventory
                    if warehouse_item.stock_quantity >= quantity:
                        warehouse_item.stock_quantity -= quantity
                        warehouse_item.updated_at = sale_date
        
        self.session.commit()
        logger.info(f"Generated {count} sales records.")


def generate_data(session: Session, num_customers: int = 50, num_products: int = 100,
                 num_suppliers: int = 20, num_employees: int = 30, num_sales: int = 200,
                 seed: Optional[int] = None):
    """
    Generate synthetic data and insert it into the database.
    
    Args:
        session: SQLAlchemy database session
        num_customers: Number of customer records to generate
        num_products: Number of product records to generate
        num_suppliers: Number of supplier records to generate
        num_employees: Number of employee records to generate
        num_sales: Number of sales records to generate
        seed: Random seed for reproducibility
    """
    generator = DataGenerator(session, seed)
    generator.generate_all(
        num_customers=num_customers,
        num_products=num_products,
        num_suppliers=num_suppliers,
        num_employees=num_employees,
        num_sales=num_sales
    )