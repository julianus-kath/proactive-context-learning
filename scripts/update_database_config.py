#!/usr/bin/env python3
"""
EASY DATABASE CONFIGURATION UPDATER
===================================

This script makes it super easy to update your database configuration.
Just run it and follow the prompts, or edit the shared_config.py file directly.

Usage:
    python update_database_config.py

Or to see current settings:
    python update_database_config.py --show
"""

import sys
import argparse
from shared_config import print_connection_info

def update_shared_config():
    """Interactive function to update the shared configuration."""
    print("="*60)
    print("DATABASE CONFIGURATION UPDATER")
    print("="*60)
    print()
    print("Current settings:")
    print_connection_info()
    print()
    
    print("To update your database configuration:")
    print("1. Edit the file: shared_config.py")
    print("2. Update these values in the GlobalDatabaseConfig class:")
    print("   - db_host (currently: localhost)")
    print("   - db_port (currently: 5432)")
    print("   - db_name (currently: mywebshop)")
    print("   - db_schema (currently: webshop)")
    print("   - db_user (currently: postgres)")
    print("   - db_password (currently: your_password_here)")
    print()
    print("3. OR create a .env file in the root directory with:")
    print("""
# Copy this to .env file:
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_SCHEMA=webshop
DB_USER=postgres
DB_PASSWORD=your_actual_password_here
""")
    print()
    print("4. Restart your services after making changes")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Update database configuration")
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    
    args = parser.parse_args()
    
    if args.show:
        print_connection_info()
    else:
        update_shared_config()

if __name__ == "__main__":
    main()