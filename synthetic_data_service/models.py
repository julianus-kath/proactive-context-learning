"""
SQLAlchemy ORM models for the synthetic data service.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = relationship("Sale", back_populates="customer")
    
    def __repr__(self):
        return f"<Customer(id={self.customer_id}, name='{self.name}')>"


class Product(Base):
    """Product entity representing items in the inventory."""
    __tablename__ = "products"
    
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))
    subcategory = Column(String(50))
    unit_price = Column(Float, nullable=False)
    cost_price = Column(Float)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    warehouse_items = relationship("WarehouseItem", back_populates="product")
    sales = relationship("Sale", back_populates="product")
    
    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.product_name}')>"


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
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)  # Price at time of sale
    discount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    sale_date = Column(DateTime, nullable=False)
    payment_method = Column(String(50))
    status = Column(String(20))  # Pending, Completed, Cancelled, etc.
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_positive_quantity'),
        CheckConstraint('total_amount >= 0', name='check_positive_amount'),
    )
    
    # Relationships
    customer = relationship("Customer", back_populates="sales")
    product = relationship("Product", back_populates="sales")
    
    def __repr__(self):
        return f"<Sale(id={self.sale_id}, customer_id={self.customer_id}, amount={self.total_amount})>"


class Employee(Base):
    """Employee entity representing staff members."""
    __tablename__ = "employees"
    
    employee_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    phone = Column(String(20))
    department = Column(String(50))
    position = Column(String(50))
    hire_date = Column(DateTime, nullable=False)
    salary = Column(Float)
    manager_id = Column(Integer, ForeignKey("employees.employee_id"))
    
    # Self-referential relationship for manager
    reports_to = relationship("Employee", remote_side=[employee_id], backref="subordinates")
    
    def __repr__(self):
        return f"<Employee(id={self.employee_id}, name='{self.first_name} {self.last_name}')>"