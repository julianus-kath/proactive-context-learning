"""
Main entry point for the synthetic data service.
"""

import argparse
import logging
import sys

from synthetic_data_service.config import configure_from_env
from synthetic_data_service.db import init_db, get_db_session
from synthetic_data_service.generator import generate_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate synthetic CRM and ERP data for PostgreSQL")
    
    parser.add_argument("--customers", type=int, default=5000,
                        help="Number of customer records to generate (default: 5000)")
    parser.add_argument("--products", type=int, default=10000,
                        help="Number of product records to generate (default: 10000)")
    parser.add_argument("--suppliers", type=int, default=500,
                        help="Number of supplier records to generate (default: 500)")
    parser.add_argument("--employees", type=int, default=1000,
                        help="Number of employee records to generate (default: 1000)")
    parser.add_argument("--sales", type=int, default=50000,
                        help="Number of sales records to generate (default: 50000)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility (default: from config)")
    parser.add_argument("--drop-tables", action="store_true",
                        help="Drop existing tables before creating new ones")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Batch size for database inserts (default: 1000)")
    
    return parser.parse_args()


def main():
    """Main function to run the synthetic data generator."""
    # Load configuration from environment variables
    configure_from_env()
    
    # Parse command line arguments
    args = parse_args()
    
    try:
        # Initialize the database
        logger.info("Initializing database...")
        init_db(drop_all=args.drop_tables)
        
        # Get a database session
        session = get_db_session()
        
        # Generate synthetic data
        generate_data(
            session=session,
            num_customers=args.customers,
            num_products=args.products,
            num_suppliers=args.suppliers,
            num_employees=args.employees,
            num_sales=args.sales,
            seed=args.seed,
            batch_size=args.batch_size
        )
        
        logger.info("Data generation completed successfully.")
        return 0
    
    except Exception as e:
        logger.error(f"Error generating synthetic data: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())