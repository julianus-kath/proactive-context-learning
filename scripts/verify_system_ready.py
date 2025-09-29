#!/usr/bin/env python3
"""
System Readiness Verification Script
Checks if all components are ready for the enhanced Phase 4 system.
"""

import os
import sys
import subprocess
import psycopg2
from dotenv import load_dotenv

def check_python_dependencies():
    """Check if required Python packages are installed."""
    print("🔍 Checking Python dependencies...")
    
    required_packages = [
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('langgraph', 'langgraph'),
        ('langchain', 'langchain'),
        ('langchain-openai', 'langchain_openai'),
        ('psycopg2-binary', 'psycopg2'),
        ('requests', 'requests'),
        ('python-dotenv', 'dotenv'),
        ('aiofiles', 'aiofiles')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            print(f"  ❌ {package_name}")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All Python dependencies are installed")
    return True

def check_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔍 Checking environment variables...")
    
    load_dotenv()
    
    required_vars = [
        'OPENAI_API_KEY',
        'LANGGRAPH_URL',
        'API_KEY',
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_USER'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value == "your_openai_api_key_here":
            print(f"  ❌ {var}")
            missing_vars.append(var)
        else:
            # Mask sensitive values
            if 'KEY' in var:
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"  ✅ {var} = {display_value}")
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        return False
    
    print("✅ All environment variables are set")
    return True

def check_postgresql():
    """Check if PostgreSQL is running and database exists."""
    print("\n🔍 Checking PostgreSQL...")
    
    # Check if PostgreSQL is running
    try:
        result = subprocess.run(['pg_isready', '-h', 'localhost', '-p', '5432'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("  ❌ PostgreSQL is not running")
            return False
        print("  ✅ PostgreSQL is running")
    except FileNotFoundError:
        print("  ❌ PostgreSQL tools not found (pg_isready)")
        return False
    
    # Check database connection and data
    try:
        load_dotenv()
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'synthetic_erp_data'),
            user=os.getenv('DB_USER', 'juli'),
            password=os.getenv('DB_PASSWORD', '')
        )
        
        cursor = conn.cursor()
        
        # Check if tables exist and have data
        tables = ['customers', 'products', 'sales', 'suppliers', 'warehouse', 'employees']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"  ✅ {table}: {count} records")
        
        cursor.close()
        conn.close()
        
        print("✅ Database is ready with data")
        return True
        
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def check_file_structure():
    """Check if required files exist."""
    print("\n🔍 Checking file structure...")
    
    required_files = [
        'start_all_services.sh',
        'restore_database.py',
        '.env',
        'chatbot_ui/app.py',
        'chatbot_ui/langgraph_service.py',
        'langgraph_integration/graph_definition.py',
        'mcp_server/tools.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ All required files are present")
    return True

def check_ports():
    """Check if required ports are available."""
    print("\n🔍 Checking port availability...")
    
    import socket
    
    ports = {
        3000: "Modern Web UI",
        5001: "LangGraph Service", 
        8000: "MCP Server",
        5432: "PostgreSQL"
    }
    
    occupied_ports = []
    
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            if port == 5432:  # PostgreSQL should be running
                print(f"  ✅ Port {port} ({service}) - Running")
            else:
                print(f"  ⚠️  Port {port} ({service}) - Occupied")
                occupied_ports.append(f"{port} ({service})")
        else:
            if port == 5432:  # PostgreSQL should be running
                print(f"  ❌ Port {port} ({service}) - Not running")
                return False
            else:
                print(f"  ✅ Port {port} ({service}) - Available")
    
    if occupied_ports and len(occupied_ports) > 1:  # More than just PostgreSQL
        print(f"\n⚠️  Some service ports are occupied: {', '.join(occupied_ports)}")
        print("The startup script will attempt to stop existing services")
    
    print("✅ Port check completed")
    return True

def main():
    """Run all system checks."""
    print("🚀 System Readiness Verification for Phase 4")
    print("=" * 50)
    
    checks = [
        check_file_structure,
        check_environment_variables,
        check_python_dependencies,
        check_postgresql,
        check_ports
    ]
    
    all_passed = True
    
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("🎉 System is ready! You can run:")
        print("   ./start_all_services.sh")
        print("\n📋 What will happen:")
        print("   1. MCP Server will start on port 8000")
        print("   2. LangGraph Service will start on port 5001")
        print("   3. Modern Web UI will start on port 3000")
        print("   4. All services will be connected and ready for Phase 4 multi-turn dialogue")
        print("\n🌐 Access URLs:")
        print("   • Modern Web UI: http://localhost:3000")
        print("   • LangGraph API: http://localhost:5001/docs")
        print("   • MCP Server: http://localhost:8000/docs")
        return True
    else:
        print("❌ System is not ready. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)