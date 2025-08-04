#!/usr/bin/env python3
"""
Quick setup script for PostgreSQL synthetic ERP data generation.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from synthetic_data_service.config import configure_from_env, db_config
from synthetic_data_service.setup_postgres import create_database, test_connection
from synthetic_data_service.db import init_db, get_db_session
from synthetic_data_service.generator import generate_data
from synthetic_data_service.validate_data import print_validation_report

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_postgresql():
    """Check if PostgreSQL is installed and running."""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"PostgreSQL found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    logger.error("PostgreSQL not found. Please install PostgreSQL first.")
    logger.info("macOS: brew install postgresql && brew services start postgresql")
    logger.info("Ubuntu: sudo apt install postgresql postgresql-contrib")
    return False


def setup_environment():
    """Setup environment variables."""
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        logger.info("Creating .env file from template...")
        example_file = Path(__file__).parent / '.env.example'
        if example_file.exists():
            import shutil
            shutil.copy(example_file, env_file)
            logger.info("Created .env file. Please edit it with your PostgreSQL credentials.")
            return False
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        configure_from_env()
        logger.info("Environment variables loaded successfully.")
        return True
    except ImportError:
        logger.warning("python-dotenv not installed. Using default configuration.")
        return True


def main():
    """Main setup function."""
    logger.info("🚀 Starting PostgreSQL Synthetic ERP Data Setup")
    
    # Check PostgreSQL installation
    if not check_postgresql():
        return 1
    
    # Setup environment
    if not setup_environment():
        logger.info("Please edit the .env file and run this script again.")
        return 1
    
    try:
        # Create database
        logger.info("📊 Setting up PostgreSQL database...")
        if not create_database():
            logger.error("Failed to create database")
            return 1
        
        if not test_connection():
            logger.error("Failed to connect to database")
            return 1
        
        # Initialize database schema
        logger.info("🏗️  Creating database tables...")
        init_db(drop_all=True)
        
        # Generate sample data (smaller set for quick testing)
        logger.info("🎲 Generating synthetic data...")
        session = get_db_session()
        
        generate_data(
            session=session,
            num_customers=1000,
            num_products=2000,
            num_suppliers=100,
            num_employees=200,
            num_sales=5000,
            batch_size=500
        )
        
        # Validate the generated data
        logger.info("✅ Validating generated data...")
        print_validation_report(session)
        
        session.close()
        
        logger.info("🎉 Setup completed successfully!")
        logger.info(f"Database: {db_config.db_name}")
        logger.info(f"Host: {db_config.db_host}:{db_config.db_port}")
        logger.info(f"Connection string: {db_config.connection_string}")
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. For larger datasets, run:")
        print("   python -m synthetic_data_service.main --customers 10000 --products 20000 --sales 100000")
        print("\n2. To validate data:")
        print("   python -m synthetic_data_service.validate_data")
        print("\n3. Ready for MCP server and LangGraph integration!")
        print("="*60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())