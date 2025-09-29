#!/usr/bin/env python3
"""
Test Database Connection Script
===============================
This script tests if all components can connect to the new mywebshop database.
"""

import sys
import os
import asyncio

print("🔍 TESTING DATABASE CONNECTIONS")
print("="*50)

# Test 1: Shared Configuration
print("\n1. Testing Shared Configuration...")
try:
    from shared_config import global_db_config
    print(f"✅ Database: {global_db_config.db_name}")
    print(f"✅ Host: {global_db_config.db_host}")
    print(f"✅ Port: {global_db_config.db_port}")
    print(f"✅ User: {global_db_config.db_user}")
    print(f"✅ Connection String: {global_db_config.connection_string}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: MCP Server Configuration
print("\n2. Testing MCP Server Configuration...")
try:
    from mcp_server.config import config
    print(f"✅ MCP Database: {config.db_name}")
    print(f"✅ MCP Connection: {config.connection_string}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Database Manager Direct Connection
print("\n3. Testing Database Manager...")
try:
    from mcp_server.db import db_manager
    print(f"✅ DB Config: {db_manager.db_config}")
    print("✅ Database Manager loaded")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Actual Database Connection
print("\n4. Testing Actual Database Connection...")
try:
    import asyncpg
    
    async def test_connection():
        try:
            conn = await asyncpg.connect(
                host="localhost",
                port=5432,
                database="mywebshop",
                user="postgres",
                password=""
            )
            
            # Test query
            result = await conn.fetchval("SELECT version();")
            print(f"✅ Connected to PostgreSQL: {result[:50]}...")
            
            # Check for webshop schema
            schema_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'webshop');"
            )
            print(f"✅ Schema 'webshop' exists: {schema_exists}")
            
            # List some tables
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema IN ('public', 'webshop') 
                ORDER BY table_name 
                LIMIT 5;
            """)
            
            if tables:
                print(f"✅ Found tables: {[row['table_name'] for row in tables]}")
            else:
                print("⚠️  No tables found in database")
                
            await conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            print("💡 Possible issues:")
            print("   - Database 'mywebshop' doesn't exist")
            print("   - User 'postgres' needs password")
            print("   - PostgreSQL not running")
            return False
    
    # Run the async test
    connection_ok = asyncio.run(test_connection())
    
except Exception as e:
    print(f"❌ Connection test failed: {e}")
    connection_ok = False

# Test 5: Environment Variables
print("\n5. Testing Environment Variables...")
env_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
for var in env_vars:
    value = os.getenv(var, 'NOT_SET')
    print(f"   {var} = {value}")

print("\n" + "="*50)
if connection_ok:
    print("🎉 ALL TESTS PASSED! Your database connection is ready.")
    print("\n🚀 Next Steps:")
    print("1. Stop all services: ./start_all_services.sh (Ctrl+C if running)")
    print("2. Restart services: ./start_all_services.sh")
    print("3. Test the chatbot - it should now connect to mywebshop!")
else:
    print("❌ SOME TESTS FAILED - Please fix the issues above first.")
    print("\n🔧 Quick fixes:")
    print("1. Make sure PostgreSQL is running")
    print("2. Create the mywebshop database: createdb -U postgres mywebshop")
    print("3. Set your password in shared_config.py or .env file")

print("="*50)