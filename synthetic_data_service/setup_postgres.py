"""
PostgreSQL database setup script for the synthetic ERP data service.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
import sys
from synthetic_data_service.config import db_config

logger = logging.getLogger(__name__)


def create_database():
    """Create the PostgreSQL database if it doesn't exist."""
    try:
        # Connect to PostgreSQL server (not to a specific database)
        conn = psycopg2.connect(
            host=db_config.db_host,
            port=db_config.db_port,
            user=db_config.db_user,
            password=db_config.db_password,
            database='postgres'  # Connect to default postgres database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (db_config.db_name,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            # Create the database
            cursor.execute(f'CREATE DATABASE "{db_config.db_name}"')
            logger.info(f"Created database: {db_config.db_name}")
        else:
            logger.info(f"Database {db_config.db_name} already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"Error creating database: {e}")
        return False


def test_connection():
    """Test connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=db_config.db_host,
            port=db_config.db_port,
            user=db_config.db_user,
            password=db_config.db_password,
            database=db_config.db_name
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        logger.info(f"Successfully connected to PostgreSQL: {version[0]}")
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"Error connecting to database: {e}")
        return False


def main():
    """Main setup function."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("Setting up PostgreSQL database for synthetic ERP data...")
    
    # Create database
    if not create_database():
        logger.error("Failed to create database")
        sys.exit(1)
    
    # Test connection
    if not test_connection():
        logger.error("Failed to connect to database")
        sys.exit(1)
    
    logger.info("PostgreSQL setup completed successfully!")
    logger.info(f"Database: {db_config.db_name}")
    logger.info(f"Host: {db_config.db_host}:{db_config.db_port}")
    logger.info(f"User: {db_config.db_user}")


if __name__ == "__main__":
    main()