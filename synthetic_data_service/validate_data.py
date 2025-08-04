"""
Data validation and statistics script for the synthetic ERP database.
"""

import logging
from sqlalchemy import func, text
from synthetic_data_service.db import get_db_session
from synthetic_data_service.models import Customer, Product, Supplier, Employee, Sale, WarehouseItem

logger = logging.getLogger(__name__)


def get_table_counts(session):
    """Get record counts for all tables."""
    counts = {}
    counts['customers'] = session.query(Customer).count()
    counts['products'] = session.query(Product).count()
    counts['suppliers'] = session.query(Supplier).count()
    counts['employees'] = session.query(Employee).count()
    counts['sales'] = session.query(Sale).count()
    counts['warehouse'] = session.query(WarehouseItem).count()
    return counts


def validate_referential_integrity(session):
    """Validate foreign key relationships."""
    issues = []
    
    # Check products without suppliers
    orphaned_products = session.query(Product).filter(
        ~Product.supplier_id.in_(session.query(Supplier.supplier_id))
    ).count()
    if orphaned_products > 0:
        issues.append(f"Found {orphaned_products} products without valid suppliers")
    
    # Check sales without customers
    orphaned_sales_customers = session.query(Sale).filter(
        ~Sale.customer_id.in_(session.query(Customer.customer_id))
    ).count()
    if orphaned_sales_customers > 0:
        issues.append(f"Found {orphaned_sales_customers} sales without valid customers")
    
    # Check sales without products
    orphaned_sales_products = session.query(Sale).filter(
        ~Sale.product_id.in_(session.query(Product.product_id))
    ).count()
    if orphaned_sales_products > 0:
        issues.append(f"Found {orphaned_sales_products} sales without valid products")
    
    # Check warehouse items without products
    orphaned_warehouse = session.query(WarehouseItem).filter(
        ~WarehouseItem.product_id.in_(session.query(Product.product_id))
    ).count()
    if orphaned_warehouse > 0:
        issues.append(f"Found {orphaned_warehouse} warehouse items without valid products")
    
    return issues


def get_business_statistics(session):
    """Generate business intelligence statistics."""
    stats = {}
    
    # Customer statistics
    stats['customers'] = {
        'total': session.query(Customer).count(),
        'active': session.query(Customer).filter(Customer.is_active == True).count(),
        'by_size': dict(session.query(Customer.company_size, func.count(Customer.customer_id)).group_by(Customer.company_size).all()),
        'by_region': dict(session.query(Customer.region, func.count(Customer.customer_id)).group_by(Customer.region).all()),
        'avg_revenue': float(session.query(func.avg(Customer.annual_revenue)).scalar() or 0),
        'total_credit_limit': float(session.query(func.sum(Customer.credit_limit)).scalar() or 0)
    }
    
    # Product statistics
    stats['products'] = {
        'total': session.query(Product).count(),
        'active': session.query(Product).filter(Product.is_active == True).count(),
        'by_category': dict(session.query(Product.category, func.count(Product.product_id)).group_by(Product.category).all()),
        'avg_price': float(session.query(func.avg(Product.unit_price)).scalar() or 0),
        'price_range': {
            'min': float(session.query(func.min(Product.unit_price)).scalar() or 0),
            'max': float(session.query(func.max(Product.unit_price)).scalar() or 0)
        }
    }
    
    # Sales statistics
    completed_sales = session.query(Sale).filter(Sale.status == 'Completed')
    stats['sales'] = {
        'total': session.query(Sale).count(),
        'completed': completed_sales.count(),
        'total_revenue': float(completed_sales.with_entities(func.sum(Sale.total_amount)).scalar() or 0),
        'avg_order_value': float(completed_sales.with_entities(func.avg(Sale.total_amount)).scalar() or 0),
        'by_status': dict(session.query(Sale.status, func.count(Sale.sale_id)).group_by(Sale.status).all()),
        'by_payment_method': dict(session.query(Sale.payment_method, func.count(Sale.sale_id)).group_by(Sale.payment_method).all())
    }
    
    # Employee statistics
    stats['employees'] = {
        'total': session.query(Employee).count(),
        'active': session.query(Employee).filter(Employee.is_active == True).count(),
        'by_department': dict(session.query(Employee.department, func.count(Employee.employee_id)).group_by(Employee.department).all()),
        'avg_salary': float(session.query(func.avg(Employee.salary)).scalar() or 0),
        'with_managers': session.query(Employee).filter(Employee.manager_id.isnot(None)).count()
    }
    
    # Supplier statistics
    stats['suppliers'] = {
        'total': session.query(Supplier).count(),
        'active': session.query(Supplier).filter(Supplier.is_active == True).count(),
        'preferred': session.query(Supplier).filter(Supplier.is_preferred == True).count(),
        'avg_lead_time': float(session.query(func.avg(Supplier.lead_time_days)).scalar() or 0)
    }
    
    # Warehouse statistics
    stats['warehouse'] = {
        'total_items': session.query(WarehouseItem).count(),
        'total_stock': int(session.query(func.sum(WarehouseItem.stock_quantity)).scalar() or 0),
        'low_stock_items': session.query(WarehouseItem).filter(
            WarehouseItem.stock_quantity <= WarehouseItem.reorder_level
        ).count(),
        'out_of_stock': session.query(WarehouseItem).filter(WarehouseItem.stock_quantity == 0).count()
    }
    
    return stats


def print_validation_report(session):
    """Print a comprehensive validation report."""
    print("=" * 80)
    print("SYNTHETIC ERP DATA VALIDATION REPORT")
    print("=" * 80)
    
    # Table counts
    print("\n📊 TABLE RECORD COUNTS")
    print("-" * 40)
    counts = get_table_counts(session)
    for table, count in counts.items():
        print(f"{table.capitalize():15}: {count:,}")
    
    # Referential integrity
    print("\n🔗 REFERENTIAL INTEGRITY CHECK")
    print("-" * 40)
    issues = validate_referential_integrity(session)
    if issues:
        for issue in issues:
            print(f"❌ {issue}")
    else:
        print("✅ All foreign key relationships are valid")
    
    # Business statistics
    print("\n📈 BUSINESS STATISTICS")
    print("-" * 40)
    stats = get_business_statistics(session)
    
    # Customer insights
    print(f"\n👥 CUSTOMERS ({stats['customers']['total']:,} total)")
    print(f"   Active: {stats['customers']['active']:,} ({stats['customers']['active']/stats['customers']['total']*100:.1f}%)")
    print(f"   Average Annual Revenue: ${stats['customers']['avg_revenue']:,.2f}")
    print(f"   Total Credit Limit: ${stats['customers']['total_credit_limit']:,.2f}")
    print("   By Company Size:")
    for size, count in stats['customers']['by_size'].items():
        print(f"     {size}: {count:,}")
    
    # Product insights
    print(f"\n📦 PRODUCTS ({stats['products']['total']:,} total)")
    print(f"   Active: {stats['products']['active']:,} ({stats['products']['active']/stats['products']['total']*100:.1f}%)")
    print(f"   Average Price: ${stats['products']['avg_price']:.2f}")
    print(f"   Price Range: ${stats['products']['price_range']['min']:.2f} - ${stats['products']['price_range']['max']:.2f}")
    print("   Top Categories:")
    sorted_categories = sorted(stats['products']['by_category'].items(), key=lambda x: x[1], reverse=True)
    for category, count in sorted_categories[:5]:
        print(f"     {category}: {count:,}")
    
    # Sales insights
    print(f"\n💰 SALES ({stats['sales']['total']:,} total)")
    print(f"   Completed: {stats['sales']['completed']:,} ({stats['sales']['completed']/stats['sales']['total']*100:.1f}%)")
    print(f"   Total Revenue: ${stats['sales']['total_revenue']:,.2f}")
    print(f"   Average Order Value: ${stats['sales']['avg_order_value']:.2f}")
    print("   By Status:")
    for status, count in stats['sales']['by_status'].items():
        print(f"     {status}: {count:,}")
    
    # Employee insights
    print(f"\n👨‍💼 EMPLOYEES ({stats['employees']['total']:,} total)")
    print(f"   Active: {stats['employees']['active']:,} ({stats['employees']['active']/stats['employees']['total']*100:.1f}%)")
    print(f"   Average Salary: ${stats['employees']['avg_salary']:,.2f}")
    print(f"   With Managers: {stats['employees']['with_managers']:,}")
    print("   By Department:")
    sorted_departments = sorted(stats['employees']['by_department'].items(), key=lambda x: x[1], reverse=True)
    for dept, count in sorted_departments:
        print(f"     {dept}: {count:,}")
    
    # Supplier insights
    print(f"\n🏭 SUPPLIERS ({stats['suppliers']['total']:,} total)")
    print(f"   Active: {stats['suppliers']['active']:,} ({stats['suppliers']['active']/stats['suppliers']['total']*100:.1f}%)")
    print(f"   Preferred: {stats['suppliers']['preferred']:,}")
    print(f"   Average Lead Time: {stats['suppliers']['avg_lead_time']:.1f} days")
    
    # Warehouse insights
    print(f"\n📦 WAREHOUSE ({stats['warehouse']['total_items']:,} items)")
    print(f"   Total Stock Units: {stats['warehouse']['total_stock']:,}")
    print(f"   Low Stock Items: {stats['warehouse']['low_stock_items']:,}")
    print(f"   Out of Stock: {stats['warehouse']['out_of_stock']:,}")
    
    print("\n" + "=" * 80)


def main():
    """Main validation function."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        session = get_db_session()
        print_validation_report(session)
        session.close()
        
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        raise


if __name__ == "__main__":
    main()