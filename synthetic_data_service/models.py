"""
SQLAlchemy ORM models for the synthetic data service.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint, Boolean, Numeric, Index
from sqlalchemy.orm import relationship

from synthetic_data_service.db import Base


class Customer(Base):
    """Customer entity representing a client in the CRM system."""
    __tablename__ = "customers"
    
    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    phone = Column(String(20))
    address = Column(String(200))
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50))
    region = Column(String(50))
    industry = Column(String(50))
    company_size = Column(String(20))  # Small, Medium, Large, Enterprise
    annual_revenue = Column(Numeric(15, 2))
    employee_count = Column(Integer)
    credit_limit = Column(Numeric(12, 2))
    credit_rating = Column(String(10))  # AAA, AA, A, BBB, BB, B, CCC, CC, C, D
    is_active = Column(Boolean, default=True)
    website = Column(String(200))
    tax_id = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_customer_region', 'region'),
        Index('idx_customer_industry', 'industry'),
        Index('idx_customer_size', 'company_size'),
        Index('idx_customer_active', 'is_active'),
        Index('idx_customer_created', 'created_at'),
    )
    
    # Relationships
    sales = relationship("Sale", back_populates="customer")
    
    def __repr__(self):
        return f"<Customer(id={self.customer_id}, name='{self.name}')>"


class Product(Base):
    """Product entity representing items in the inventory."""
    __tablename__ = "products"
    
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(100), nullable=False)
    sku = Column(String(50), unique=True, nullable=False)
    barcode = Column(String(50))
    description = Column(Text)
    category = Column(String(50))
    subcategory = Column(String(50))
    brand = Column(String(50))
    unit_price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2))
    weight = Column(Numeric(8, 3))  # in kg
    dimensions = Column(String(50))  # LxWxH in cm
    color = Column(String(30))
    size = Column(String(20))
    material = Column(String(50))
    warranty_months = Column(Integer)
    is_active = Column(Boolean, default=True)
    is_digital = Column(Boolean, default=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_product_category', 'category'),
        Index('idx_product_subcategory', 'subcategory'),
        Index('idx_product_brand', 'brand'),
        Index('idx_product_active', 'is_active'),
        Index('idx_product_supplier', 'supplier_id'),
        Index('idx_product_sku', 'sku'),
    )
    
    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    warehouse_items = relationship("WarehouseItem", back_populates="product")
    sales = relationship("Sale", back_populates="product")
    
    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.product_name}', sku='{self.sku}')>"


class Supplier(Base):
    """Supplier entity representing vendors that provide products."""
    __tablename__ = "suppliers"
    
    supplier_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    contact_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    address = Column(String(200))
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50))
    website = Column(String(200))
    tax_id = Column(String(50))
    payment_terms = Column(String(50))  # Net 30, Net 60, etc.
    credit_rating = Column(String(10))
    is_active = Column(Boolean, default=True)
    is_preferred = Column(Boolean, default=False)
    lead_time_days = Column(Integer)
    minimum_order_amount = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_supplier_country', 'country'),
        Index('idx_supplier_active', 'is_active'),
        Index('idx_supplier_preferred', 'is_preferred'),
    )
    
    # Relationships
    products = relationship("Product", back_populates="supplier")
    
    def __repr__(self):
        return f"<Supplier(id={self.supplier_id}, name='{self.name}')>"


class WarehouseItem(Base):
    """Warehouse item representing inventory stock."""
    __tablename__ = "warehouse"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    warehouse_name = Column(String(100), nullable=False)
    stock_quantity = Column(Integer, nullable=False)
    reorder_level = Column(Integer)
    last_restock_date = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('stock_quantity >= 0', name='check_positive_stock'),
    )
    
    # Relationships
    product = relationship("Product", back_populates="warehouse_items")
    
    def __repr__(self):
        return f"<WarehouseItem(product_id={self.product_id}, quantity={self.stock_quantity})>"


class Sale(Base):
    """Sale entity representing a transaction."""
    __tablename__ = "sales"
    
    sale_id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(50), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"))  # Sales rep
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # Price at time of sale
    discount_percent = Column(Numeric(5, 2), default=0.0)
    discount_amount = Column(Numeric(10, 2), default=0.0)
    tax_amount = Column(Numeric(10, 2), default=0.0)
    shipping_cost = Column(Numeric(10, 2), default=0.0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    sale_date = Column(DateTime, nullable=False)
    shipped_date = Column(DateTime)
    delivered_date = Column(DateTime)
    payment_method = Column(String(50))
    payment_status = Column(String(20))  # Pending, Paid, Failed, Refunded
    status = Column(String(20))  # Pending, Processing, Shipped, Delivered, Cancelled
    notes = Column(Text)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_positive_quantity'),
        CheckConstraint('total_amount >= 0', name='check_positive_amount'),
        CheckConstraint('discount_percent >= 0 AND discount_percent <= 100', name='check_discount_percent'),
        Index('idx_sale_date', 'sale_date'),
        Index('idx_sale_status', 'status'),
        Index('idx_sale_customer', 'customer_id'),
        Index('idx_sale_product', 'product_id'),
        Index('idx_sale_employee', 'employee_id'),
        Index('idx_sale_order_number', 'order_number'),
    )
    
    # Relationships
    customer = relationship("Customer", back_populates="sales")
    product = relationship("Product", back_populates="sales")
    employee = relationship("Employee", back_populates="sales")
    
    def __repr__(self):
        return f"<Sale(id={self.sale_id}, order={self.order_number}, amount={self.total_amount})>"


class Employee(Base):
    """Employee entity representing staff members."""
    __tablename__ = "employees"
    
    employee_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_number = Column(String(20), unique=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    phone = Column(String(20))
    address = Column(String(200))
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50))
    department = Column(String(50))
    position = Column(String(50))
    employment_type = Column(String(20))  # Full-time, Part-time, Contract, Intern
    hire_date = Column(DateTime, nullable=False)
    termination_date = Column(DateTime)
    salary = Column(Numeric(10, 2))
    commission_rate = Column(Numeric(5, 2))  # For sales staff
    is_active = Column(Boolean, default=True)
    manager_id = Column(Integer, ForeignKey("employees.employee_id"))
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_employee_department', 'department'),
        Index('idx_employee_position', 'position'),
        Index('idx_employee_active', 'is_active'),
        Index('idx_employee_manager', 'manager_id'),
        Index('idx_employee_number', 'employee_number'),
    )
    
    # Self-referential relationship for manager
    reports_to = relationship("Employee", remote_side=[employee_id], backref="subordinates")
    
    # Relationships
    sales = relationship("Sale", back_populates="employee")
    
    def __repr__(self):
        return f"<Employee(id={self.employee_id}, number='{self.employee_number}', name='{self.first_name} {self.last_name}')>"