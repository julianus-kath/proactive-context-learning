"""
Enhanced synthetic data generation logic for PostgreSQL ERP system.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from decimal import Decimal

from faker import Faker
from sqlalchemy.orm import Session

from synthetic_data_service.config import generator_config
from synthetic_data_service.models import (
    Customer, Product, Supplier, WarehouseItem, Sale, Employee
)

# Configure logging
logger = logging.getLogger(__name__)


class EnhancedDataGenerator:
    """
    Enhanced generator for synthetic CRM and ERP data with PostgreSQL support.
    """
    
    def __init__(self, session: Session, seed: Optional[int] = None, batch_size: int = 1000):
        """
        Initialize the data generator.
        
        Args:
            session: SQLAlchemy database session
            seed: Random seed for reproducibility (default: from config)
            batch_size: Number of records to insert in each batch
        """
        self.session = session
        self.seed = seed if seed is not None else generator_config.random_seed
        self.batch_size = batch_size
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
        
        # Enhanced data for realistic generation
        self.brands = [
            "TechCorp", "InnovatePro", "GlobalTech", "NextGen", "SmartSolutions",
            "EliteProducts", "PremiumBrand", "QualityFirst", "ReliableTech", "ModernDesign",
            "FutureTech", "ProSeries", "UltraMax", "PowerCore", "FlexiTech"
        ]
        
        self.colors = [
            "Black", "White", "Silver", "Gray", "Blue", "Red", "Green", "Yellow",
            "Orange", "Purple", "Pink", "Brown", "Gold", "Rose Gold", "Space Gray"
        ]
        
        self.sizes = ["XS", "S", "M", "L", "XL", "XXL", "One Size", "Mini", "Standard", "Large"]
        
        self.materials = [
            "Plastic", "Metal", "Wood", "Glass", "Fabric", "Leather", "Rubber",
            "Ceramic", "Carbon Fiber", "Aluminum", "Steel", "Bamboo", "Silicone"
        ]
        
        self.payment_terms = ["Net 15", "Net 30", "Net 45", "Net 60", "COD", "Prepaid", "2/10 Net 30"]
        self.credit_ratings = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
        
    def generate_all(self, num_customers: int, num_products: int, num_suppliers: int, 
                     num_employees: int, num_sales: int):
        """
        Generate all synthetic data entities with batch processing.
        
        Args:
            num_customers: Number of customer records to generate
            num_products: Number of product records to generate
            num_suppliers: Number of supplier records to generate
            num_employees: Number of employee records to generate
            num_sales: Number of sales records to generate
        """
        logger.info("Starting enhanced synthetic data generation...")
        
        # Generate in the correct order to maintain referential integrity
        self.generate_suppliers(num_suppliers)
        self.generate_products(num_products)
        self.generate_warehouse_items()
        self.generate_customers(num_customers)
        self.generate_employees(num_employees)
        self.generate_sales(num_sales)
        
        logger.info("Enhanced synthetic data generation completed successfully.")
    
    def generate_random_date(self, start_date=None, end_date=None):
        """Generate a random date between start_date and end_date."""
        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date
            
        time_between_dates = end_date - start_date
        days_between_dates = time_between_dates.days
        random_days = random.randrange(days_between_dates)
        return start_date + timedelta(days=random_days)
    
    def generate_sku(self, category: str, subcategory: str, product_id: int) -> str:
        """Generate a realistic SKU."""
        cat_code = category[:3].upper()
        subcat_code = subcategory[:2].upper()
        return f"{cat_code}-{subcat_code}-{product_id:06d}"
    
    def generate_barcode(self) -> str:
        """Generate a realistic barcode."""
        return ''.join([str(random.randint(0, 9)) for _ in range(13)])
    
    def generate_order_number(self, sale_id: int) -> str:
        """Generate a realistic order number."""
        year = datetime.now().year
        return f"ORD-{year}-{sale_id:08d}"
    
    def generate_employee_number(self, employee_id: int) -> str:
        """Generate a realistic employee number."""
        return f"EMP{employee_id:06d}"
    
    def batch_insert(self, objects: List[Any], entity_name: str):
        """Insert objects in batches for better performance."""
        total = len(objects)
        for i in range(0, total, self.batch_size):
            batch = objects[i:i + self.batch_size]
            self.session.add_all(batch)
            self.session.commit()
            logger.info(f"Inserted batch {i//self.batch_size + 1} of {entity_name} ({len(batch)} records)")
    
    def generate_suppliers(self, count: int):
        """Generate enhanced supplier data."""
        logger.info(f"Generating {count} suppliers...")
        
        suppliers = []
        for i in range(count):
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
                website=f"https://www.{self.faker.domain_name()}",
                tax_id=self.faker.ssn(),
                payment_terms=random.choice(self.payment_terms),
                credit_rating=random.choice(self.credit_ratings),
                is_active=random.choice([True, True, True, False]),  # 75% active
                is_preferred=random.choice([True, False, False, False]),  # 25% preferred
                lead_time_days=random.randint(1, 30),
                minimum_order_amount=Decimal(str(random.uniform(100, 5000))).quantize(Decimal('0.01')),
                created_at=self.generate_random_date()
            )
            suppliers.append(supplier)
        
        self.batch_insert(suppliers, "suppliers")
        self.suppliers = self.session.query(Supplier).all()
        logger.info(f"Generated {len(self.suppliers)} suppliers.")
    
    def generate_products(self, count: int):
        """Generate enhanced product data."""
        logger.info(f"Generating {count} products...")
        
        categories = {
            "Electronics": {
                "subcategories": ["Smartphones", "Laptops", "Tablets", "Accessories", "Audio", "Gaming"],
                "materials": ["Plastic", "Metal", "Glass", "Carbon Fiber", "Aluminum"],
                "price_range": (50, 2000)
            },
            "Furniture": {
                "subcategories": ["Chairs", "Desks", "Tables", "Sofas", "Storage", "Lighting"],
                "materials": ["Wood", "Metal", "Fabric", "Leather", "Glass"],
                "price_range": (100, 3000)
            },
            "Clothing": {
                "subcategories": ["Shirts", "Pants", "Dresses", "Outerwear", "Footwear", "Accessories"],
                "materials": ["Cotton", "Polyester", "Wool", "Leather", "Denim"],
                "price_range": (20, 500)
            },
            "Office Supplies": {
                "subcategories": ["Paper", "Writing", "Organizers", "Binders", "Technology", "Furniture"],
                "materials": ["Paper", "Plastic", "Metal", "Wood", "Fabric"],
                "price_range": (5, 200)
            },
            "Food & Beverage": {
                "subcategories": ["Snacks", "Beverages", "Canned Goods", "Dairy", "Frozen", "Fresh"],
                "materials": ["Organic", "Natural", "Processed"],
                "price_range": (1, 50)
            },
            "Health & Beauty": {
                "subcategories": ["Skincare", "Haircare", "Cosmetics", "Personal Care", "Supplements"],
                "materials": ["Natural", "Organic", "Synthetic", "Mineral"],
                "price_range": (10, 300)
            },
            "Sports & Outdoors": {
                "subcategories": ["Fitness", "Camping", "Team Sports", "Water Sports", "Winter Sports"],
                "materials": ["Plastic", "Metal", "Fabric", "Rubber", "Composite"],
                "price_range": (15, 1000)
            }
        }
        
        products = []
        for i in range(count):
            category = random.choice(list(categories.keys()))
            category_info = categories[category]
            subcategory = random.choice(category_info["subcategories"])
            
            unit_price = Decimal(str(random.uniform(*category_info["price_range"]))).quantize(Decimal('0.01'))
            cost_price = unit_price * Decimal(str(random.uniform(0.4, 0.8))).quantize(Decimal('0.01'))
            
            product = Product(
                product_name=self.faker.catch_phrase(),
                sku=self.generate_sku(category, subcategory, i + 1),
                barcode=self.generate_barcode(),
                description=self.faker.paragraph(nb_sentences=3),
                category=category,
                subcategory=subcategory,
                brand=random.choice(self.brands),
                unit_price=unit_price,
                cost_price=cost_price,
                weight=Decimal(str(random.uniform(0.1, 50.0))).quantize(Decimal('0.001')),
                dimensions=f"{random.randint(5, 100)}x{random.randint(5, 100)}x{random.randint(5, 100)}",
                color=random.choice(self.colors),
                size=random.choice(self.sizes),
                material=random.choice(category_info["materials"]),
                warranty_months=random.choice([0, 6, 12, 24, 36, 60]),
                is_active=random.choice([True, True, True, False]),  # 75% active
                is_digital=category == "Electronics" and random.choice([True, False, False]),
                supplier_id=random.choice(self.suppliers).supplier_id,
                created_at=self.generate_random_date()
            )
            products.append(product)
        
        self.batch_insert(products, "products")
        self.products = self.session.query(Product).all()
        logger.info(f"Generated {len(self.products)} products.")
    
    def generate_warehouse_items(self):
        """Generate warehouse inventory items for all products."""
        logger.info("Generating warehouse inventory items...")
        
        warehouses = [
            "Main Warehouse", "East Coast Facility", "West Coast Facility", 
            "Central Distribution", "North Regional", "South Regional"
        ]
        
        warehouse_items = []
        for product in self.products:
            # Each product might be in 1-4 warehouses
            num_warehouses = random.randint(1, 4)
            selected_warehouses = random.sample(warehouses, num_warehouses)
            
            for warehouse in selected_warehouses:
                stock_quantity = random.randint(0, 2000)
                reorder_level = random.randint(10, 200)
                
                warehouse_item = WarehouseItem(
                    product_id=product.product_id,
                    warehouse_name=warehouse,
                    stock_quantity=stock_quantity,
                    reorder_level=reorder_level,
                    last_restock_date=self.generate_random_date(
                        end_date=datetime.now() - timedelta(days=random.randint(0, 180))
                    ),
                    updated_at=datetime.now() - timedelta(days=random.randint(0, 30))
                )
                warehouse_items.append(warehouse_item)
        
        self.batch_insert(warehouse_items, "warehouse items")
        logger.info(f"Generated {len(warehouse_items)} warehouse inventory items.")
    
    def generate_customers(self, count: int):
        """Generate enhanced customer data."""
        logger.info(f"Generating {count} customers...")
        
        company_sizes = ["Small", "Medium", "Large", "Enterprise"]
        industries = [
            "Technology", "Healthcare", "Finance", "Manufacturing", "Retail", 
            "Education", "Government", "Hospitality", "Construction", "Energy",
            "Transportation", "Media", "Telecommunications", "Agriculture", "Real Estate"
        ]
        
        customers = []
        for i in range(count):
            company_size = random.choice(company_sizes)
            
            # Generate realistic data based on company size
            if company_size == "Small":
                employee_count = random.randint(1, 50)
                annual_revenue = Decimal(str(random.uniform(100000, 2000000))).quantize(Decimal('0.01'))
                credit_limit = Decimal(str(random.uniform(5000, 50000))).quantize(Decimal('0.01'))
            elif company_size == "Medium":
                employee_count = random.randint(51, 500)
                annual_revenue = Decimal(str(random.uniform(2000000, 50000000))).quantize(Decimal('0.01'))
                credit_limit = Decimal(str(random.uniform(50000, 200000))).quantize(Decimal('0.01'))
            elif company_size == "Large":
                employee_count = random.randint(501, 5000)
                annual_revenue = Decimal(str(random.uniform(50000000, 500000000))).quantize(Decimal('0.01'))
                credit_limit = Decimal(str(random.uniform(200000, 1000000))).quantize(Decimal('0.01'))
            else:  # Enterprise
                employee_count = random.randint(5001, 100000)
                annual_revenue = Decimal(str(random.uniform(500000000, 10000000000))).quantize(Decimal('0.01'))
                credit_limit = Decimal(str(random.uniform(1000000, 10000000))).quantize(Decimal('0.01'))
            
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
                company_size=company_size,
                annual_revenue=annual_revenue,
                employee_count=employee_count,
                credit_limit=credit_limit,
                credit_rating=random.choice(self.credit_ratings),
                is_active=random.choice([True, True, True, False]),  # 75% active
                website=f"https://www.{self.faker.domain_name()}",
                tax_id=self.faker.ssn(),
                created_at=self.generate_random_date()
            )
            customers.append(customer)
        
        self.batch_insert(customers, "customers")
        self.customers = self.session.query(Customer).all()
        logger.info(f"Generated {len(self.customers)} customers.")
    
    def generate_employees(self, count: int):
        """Generate enhanced employee data."""
        logger.info(f"Generating {count} employees...")
        
        departments = [
            "Sales", "Marketing", "Engineering", "HR", "Finance", "Operations", 
            "Customer Support", "Legal", "IT", "Procurement", "Quality Assurance"
        ]
        
        positions = {
            "Sales": ["Sales Representative", "Account Manager", "Sales Manager", "VP of Sales", "Sales Director"],
            "Marketing": ["Marketing Specialist", "Marketing Manager", "Content Creator", "CMO", "Brand Manager"],
            "Engineering": ["Software Engineer", "QA Engineer", "DevOps Engineer", "CTO", "Engineering Manager"],
            "HR": ["HR Specialist", "Recruiter", "HR Manager", "VP of HR", "HR Director"],
            "Finance": ["Accountant", "Financial Analyst", "Controller", "CFO", "Finance Manager"],
            "Operations": ["Operations Specialist", "Operations Manager", "COO", "Process Manager"],
            "Customer Support": ["Support Specialist", "Support Manager", "Customer Success Manager"],
            "Legal": ["Legal Counsel", "Paralegal", "Legal Manager", "Chief Legal Officer"],
            "IT": ["IT Specialist", "System Administrator", "IT Manager", "CIO"],
            "Procurement": ["Procurement Specialist", "Buyer", "Procurement Manager"],
            "Quality Assurance": ["QA Specialist", "QA Manager", "Quality Director"]
        }
        
        employment_types = ["Full-time", "Part-time", "Contract", "Intern"]
        
        employees = []
        for i in range(count):
            department = random.choice(departments)
            position = random.choice(positions[department])
            employment_type = random.choice(employment_types)
            
            hire_date = self.generate_random_date(
                start_date=datetime(2010, 1, 1),
                end_date=datetime.now() - timedelta(days=30)
            )
            
            # Salary based on position and employment type
            if "C" in position and "O" in position:  # C-level
                base_salary = random.uniform(150000, 400000)
            elif "VP" in position or "Director" in position:
                base_salary = random.uniform(120000, 250000)
            elif "Manager" in position:
                base_salary = random.uniform(80000, 150000)
            else:
                base_salary = random.uniform(40000, 100000)
            
            # Adjust for employment type
            if employment_type == "Part-time":
                base_salary *= 0.6
            elif employment_type == "Contract":
                base_salary *= 1.2  # Higher hourly rate
            elif employment_type == "Intern":
                base_salary = random.uniform(30000, 50000)
            
            # Commission rate for sales staff
            commission_rate = None
            if department == "Sales":
                commission_rate = Decimal(str(random.uniform(2, 10))).quantize(Decimal('0.01'))
            
            employee = Employee(
                employee_number=self.generate_employee_number(i + 1),
                first_name=self.faker.first_name(),
                last_name=self.faker.last_name(),
                email=self.faker.email(),
                phone=self.faker.phone_number(),
                address=self.faker.street_address(),
                city=self.faker.city(),
                state=self.faker.state(),
                postal_code=self.faker.postcode(),
                country=self.faker.country(),
                department=department,
                position=position,
                employment_type=employment_type,
                hire_date=hire_date,
                salary=Decimal(str(base_salary)).quantize(Decimal('0.01')),
                commission_rate=commission_rate,
                is_active=random.choice([True, True, True, False])  # 75% active
            )
            employees.append(employee)
        
        self.batch_insert(employees, "employees")
        self.employees = self.session.query(Employee).all()
        
        # Assign managers after all employees are created
        logger.info("Assigning managers to employees...")
        for employee in self.employees:
            if "C" in employee.position and "O" in employee.position:
                continue  # C-level executives don't have managers
                
            # Find potential managers in the same department
            potential_managers = [
                e for e in self.employees 
                if e.department == employee.department 
                and e.employee_id != employee.employee_id
                and ("Manager" in e.position or "VP" in e.position or "Director" in e.position or ("C" in e.position and "O" in e.position))
                and e.is_active
            ]
            
            if potential_managers:
                employee.manager_id = random.choice(potential_managers).employee_id
        
        self.session.commit()
        logger.info(f"Generated {len(self.employees)} employees with manager relationships.")
    
    def generate_sales(self, count: int):
        """Generate enhanced sales data."""
        logger.info(f"Generating {count} sales records...")
        
        payment_methods = ["Credit Card", "Debit Card", "Bank Transfer", "PayPal", "Cash", "Check", "Wire Transfer"]
        payment_statuses = ["Paid", "Pending", "Failed", "Refunded", "Partial"]
        statuses = ["Completed", "Processing", "Shipped", "Delivered", "Cancelled", "Returned"]
        
        # Weight distributions for realistic data
        payment_status_weights = [0.7, 0.15, 0.05, 0.05, 0.05]
        status_weights = [0.6, 0.1, 0.1, 0.15, 0.03, 0.02]
        
        # Get active customers, products, and sales employees
        active_customers = [c for c in self.customers if c.is_active]
        active_products = [p for p in self.products if p.is_active]
        sales_employees = [e for e in self.employees if e.department == "Sales" and e.is_active]
        
        sales = []
        for i in range(count):
            customer = random.choice(active_customers)
            product = random.choice(active_products)
            sales_rep = random.choice(sales_employees) if sales_employees else None
            
            quantity = random.randint(1, 20)
            unit_price = product.unit_price
            
            # Apply discount
            discount_percent = Decimal(str(random.uniform(0, 25))).quantize(Decimal('0.01'))
            discount_amount = (unit_price * discount_percent / 100).quantize(Decimal('0.01'))
            discounted_price = unit_price - discount_amount
            
            # Calculate amounts
            subtotal = discounted_price * quantity
            tax_rate = Decimal('0.08')  # 8% tax
            tax_amount = (subtotal * tax_rate).quantize(Decimal('0.01'))
            shipping_cost = Decimal(str(random.uniform(0, 50))).quantize(Decimal('0.01'))
            total_amount = subtotal + tax_amount + shipping_cost
            
            # Generate dates
            sale_date = self.generate_random_date(
                start_date=max(customer.created_at, product.created_at),
                end_date=self.end_date
            )
            
            status = random.choices(statuses, weights=status_weights)[0]
            payment_status = random.choices(payment_statuses, weights=payment_status_weights)[0]
            
            # Set shipped and delivered dates based on status
            shipped_date = None
            delivered_date = None
            if status in ["Shipped", "Delivered"]:
                shipped_date = sale_date + timedelta(days=random.randint(1, 3))
                if status == "Delivered":
                    delivered_date = shipped_date + timedelta(days=random.randint(1, 7))
            
            sale = Sale(
                order_number=self.generate_order_number(i + 1),
                customer_id=customer.customer_id,
                product_id=product.product_id,
                employee_id=sales_rep.employee_id if sales_rep else None,
                quantity=quantity,
                unit_price=unit_price,
                discount_percent=discount_percent,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                shipping_cost=shipping_cost,
                total_amount=total_amount,
                sale_date=sale_date,
                shipped_date=shipped_date,
                delivered_date=delivered_date,
                payment_method=random.choice(payment_methods),
                payment_status=payment_status,
                status=status,
                notes=self.faker.sentence() if random.choice([True, False, False]) else None
            )
            sales.append(sale)
        
        self.batch_insert(sales, "sales")
        logger.info(f"Generated {count} sales records.")


def generate_data(session: Session, num_customers: int = 5000, num_products: int = 10000,
                 num_suppliers: int = 500, num_employees: int = 1000, num_sales: int = 50000,
                 seed: Optional[int] = None, batch_size: int = 1000):
    """
    Generate enhanced synthetic data and insert it into PostgreSQL database.
    
    Args:
        session: SQLAlchemy database session
        num_customers: Number of customer records to generate
        num_products: Number of product records to generate
        num_suppliers: Number of supplier records to generate
        num_employees: Number of employee records to generate
        num_sales: Number of sales records to generate
        seed: Random seed for reproducibility
        batch_size: Batch size for database inserts
    """
    generator = EnhancedDataGenerator(session, seed, batch_size)
    generator.generate_all(
        num_customers=num_customers,
        num_products=num_products,
        num_suppliers=num_suppliers,
        num_employees=num_employees,
        num_sales=num_sales
    )