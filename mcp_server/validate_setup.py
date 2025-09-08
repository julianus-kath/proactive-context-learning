#!/usr/bin/env python3
"""
Validation script to check MCP server setup.
"""

import sys
import os
import asyncio
import asyncpg
from pathlib import Path
from dotenv import load_dotenv

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("🔍 Checking Dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'asyncpg',
        'pydantic',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies installed")
    return True

def check_configuration():
    """Check configuration files."""
    print("\n⚙️ Checking Configuration...")
    
    env_file = Path(__file__).parent / '.env'
    env_example = Path(__file__).parent / '.env.example'
    
    if not env_file.exists():
        if env_example.exists():
            print("  ⚠️ .env file not found, but .env.example exists")
            print("  💡 Copy .env.example to .env and configure your settings")
        else:
            print("  ❌ No configuration files found")
        return False
    
    print("  ✅ .env file found")
    
    # Load and check environment variables
    load_dotenv(env_file)
    
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'API_KEY']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Don't print sensitive values
            display_value = value if var not in ['DB_PASSWORD', 'API_KEY'] else '***'
            print(f"    ✅ {var}: {display_value}")
        else:
            print(f"    ❌ {var}: NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"  ❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

async def check_database_connection():
    """Check database connection."""
    print("\n🗄️ Checking Database Connection...")
    
    load_dotenv()
    
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'synthetic_erp_data'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        conn = await asyncpg.connect(**db_config)
        print(f"  ✅ Connected to database: {db_config['database']}")
        
        # Check for expected tables
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """
        
        tables = await conn.fetch(tables_query)
        table_names = [row['table_name'] for row in tables]
        
        expected_tables = ['customers', 'products', 'suppliers', 'employees', 'sales', 'warehouse']
        found_tables = []
        missing_tables = []
        
        for table in expected_tables:
            if table in table_names:
                # Get row count
                count_result = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                found_tables.append(table)
                print(f"    ✅ {table}: {count_result:,} rows")
            else:
                missing_tables.append(table)
                print(f"    ❌ {table}: MISSING")
        
        await conn.close()
        
        if missing_tables:
            print(f"\n⚠️ Missing tables: {', '.join(missing_tables)}")
            print("Run: python ../synthetic_data_service/main.py --drop-tables")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        print("  💡 Check your database configuration and ensure PostgreSQL is running")
        return False

def check_file_structure():
    """Check if all required files exist."""
    print("\n📁 Checking File Structure...")
    
    required_files = [
        'server.py',
        'tools.py',
        'db.py',
        'models.py',
        'requirements.txt',
        '.env.example',
        'start_server.py',
        'test_client.py'
    ]
    
    missing_files = []
    
    for file in required_files:
        file_path = Path(__file__).parent / file
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    
    return True

async def main():
    """Main validation function."""
    print("🧪 MCP Server Setup Validation")
    print("=" * 50)
    
    checks = [
        ("File Structure", check_file_structure),
        ("Dependencies", check_dependencies),
        ("Configuration", check_configuration),
        ("Database Connection", check_database_connection)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            if not result:
                all_passed = False
        except Exception as e:
            print(f"  ❌ {check_name} check failed with error: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("🎉 All checks passed! MCP server is ready to use.")
        print("\nNext steps:")
        print("  1. Start the server: python start_server.py")
        print("  2. Test the server: python test_client.py")
        print("  3. Access API docs: http://localhost:8000/docs")
        print("  4. Integrate with LangGraph agents")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nCommon solutions:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Configure database: cp .env.example .env (then edit)")
        print("  3. Generate data: python ../synthetic_data_service/main.py")
        print("  4. Start PostgreSQL: brew services start postgresql")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))