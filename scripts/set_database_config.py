#!/usr/bin/env python3
"""
QUICK DATABASE CONFIGURATION SETTER
===================================

This script sets your exact database configuration.
Run this once to configure your system for the mywebshop database.

Usage:
    python set_database_config.py
"""

import os

def set_environment_variables():
    """Set environment variables for the new database."""
    
    # Your new database configuration
    db_settings = {
        'DB_TYPE': 'postgresql',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432', 
        'DB_NAME': 'mywebshop',
        'DB_SCHEMA': 'webshop',
        'DB_USER': 'postgres',  # Change to 'juli' if you prefer
        'DB_PASSWORD': ''  # Add your password here
    }
    
    print("Setting environment variables for your database:")
    print("="*50)
    
    for key, value in db_settings.items():
        os.environ[key] = value
        print(f"{key}={value}")
    
    print("="*50)
    print()
    
    # Test the configuration
    print("Testing configuration...")
    try:
        # Clear any cached modules
        if 'shared_config' in sys.modules:
            del sys.modules['shared_config']
        
        from shared_config import global_db_config
        print(f"✅ Connection String: {global_db_config.connection_string}")
        print(f"✅ JDBC URL: {global_db_config.jdbc_url}")
        print()
        print("Configuration successful! 🎉")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def create_env_file():
    """Create a .env file with the new database configuration."""
    
    env_content = '''# PostgreSQL Database Configuration - mywebshop
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_SCHEMA=webshop
DB_USER=postgres
DB_PASSWORD=

# Alternative user (uncomment if you prefer juli):
# DB_USER=juli
# DB_PASSWORD=juli_password

# Other settings
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT=30
'''
    
    env_file_path = '.env.new'
    
    try:
        with open(env_file_path, 'w') as f:
            f.write(env_content)
        
        print(f"✅ Created {env_file_path}")
        print(f"   → Copy this to .env to use environment variables")
        print(f"   → Or just edit shared_config.py directly")
        
    except Exception as e:
        print(f"❌ Could not create {env_file_path}: {e}")

def main():
    import sys
    
    print("🎯 CONFIGURING YOUR MYWEBSHOP DATABASE")
    print("="*60)
    print()
    
    # Method 1: Set environment variables for this session
    set_environment_variables()
    
    print()
    print("📁 CREATING ENVIRONMENT FILE TEMPLATE")
    print("="*50)
    create_env_file()
    
    print()
    print("🚀 NEXT STEPS:")
    print("="*20)
    print("1. Add your password to shared_config.py or .env file")
    print("2. If you prefer user 'juli', change DB_USER")
    print("3. Test: python shared_config.py")
    print("4. Run your services - they'll use the new database!")
    print()

if __name__ == "__main__":
    main()