#!/usr/bin/env python3
"""
Test Agent → Proxy connection with dummy API key
"""

import os
import sys
sys.path.append('/')

from app.db.client import DatabaseClient

def test_agent_proxy_with_key():
    """Test the agent → proxy connection with dummy API key."""
    print("🔍 Testing Agent → Proxy Connection (With API Key)")
    print("=" * 60)
    
    # Set up proxy configuration with dummy API key
    os.environ['DB_MODE'] = 'proxy'
    os.environ['PROXY_BASE_URL'] = 'http://172.20.10.3:5000'
    os.environ['PROXY_DEFAULT_CONN'] = 'corp_sql_erp'
    os.environ['PROXY_API_KEY'] = 'dummy-key-for-testing'  # Dummy key since proxy doesn't require auth
    
    print("📋 Configuration:")
    print(f"   DB_MODE: {os.environ.get('DB_MODE')}")
    print(f"   PROXY_BASE_URL: {os.environ.get('PROXY_BASE_URL')}")
    print(f"   PROXY_DEFAULT_CONN: {os.environ.get('PROXY_DEFAULT_CONN')}")
    print(f"   PROXY_API_KEY: {'(set - dummy for testing)' if os.environ.get('PROXY_API_KEY') else '(not set)'}")
    print()
    
    try:
        # Initialize DatabaseClient
        print("🔧 Initializing DatabaseClient...")
        db_client = DatabaseClient()
        print("   ✅ DatabaseClient initialized")
        
        # Test simple query
        print("\n🔍 Testing simple query...")
        columns, rows = db_client.query("SELECT 1 as test_value, 'Agent → Proxy works!' as message")
        
        if columns and rows:
            print("   ✅ Query successful!")
            print(f"   📊 Columns: {columns}")
            print(f"   📋 Rows: {rows}")
            print(f"   📈 Row count: {len(rows)}")
            
            # Test database metadata query
            print("\n🔍 Testing database metadata query...")
            columns2, rows2 = db_client.query(
                "SELECT TOP 5 name, database_id, create_date FROM sys.databases ORDER BY name", 
                limit=10
            )
            
            if columns2 and rows2:
                print("   ✅ Database metadata query successful!")
                print(f"   📊 Columns: {columns2}")
                print(f"   📋 Rows: {rows2}")
                print(f"   📈 Row count: {len(rows2)}")
                
                # Test SQL Server version
                print("\n🔍 Testing SQL Server version query...")
                columns3, rows3 = db_client.query("SELECT @@VERSION as sql_server_version")
                
                if columns3 and rows3:
                    version_info = rows3[0][0] if rows3 else 'Unknown'
                    print("   ✅ Version query successful!")
                    print(f"   📊 SQL Server: {version_info[:100]}...")  # Truncate long version string
                    
                    # Test table listing (if we have access)
                    print("\n🔍 Testing table listing...")
                    columns4, rows4 = db_client.query(
                        "SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'",
                        limit=10
                    )
                    
                    if columns4 and rows4:
                        print("   ✅ Table listing successful!")
                        print(f"   📊 Found {len(rows4)} tables")
                        for row in rows4[:5]:  # Show first 5 tables
                            print(f"      - {row[0]}.{row[1]}")
                    else:
                        print(f"   ⚠️  Table listing limited: No access or no tables found")
                    
                    print("\n" + "🎉" * 20)
                    print("🎉 COMPLETE SUCCESS! 🎉")
                    print("🎉" * 20)
                    print()
                    print("✅ Your entire ERP system is now connected:")
                    print("   🖥️  Mac Agent (DatabaseClient)")
                    print("   ↕️  HTTP connection")
                    print("   🪟 Windows Proxy (proxy.py)")
                    print("   ↕️  ODBC Driver 17 for SQL Server")
                    print("   🗄️  SQL Server Database")
                    print()
                    print("🚀 System is ready for:")
                    print("   📊 ERP data crawling and analysis")
                    print("   🔍 Complex query processing")
                    print("   🤖 AI-powered data insights")
                    print("   💬 Chatbot interactions")
                    print("   🔧 MCP server integration")
                    print("   📈 Business intelligence workflows")
                    
                    return True
                else:
                    print(f"   ❌ Version query failed")
            else:
                print(f"   ❌ Metadata query failed")
        else:
            print(f"   ❌ Simple query failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def show_production_setup():
    """Show how to set up for production."""
    print("\n" + "=" * 60)
    print("🔧 PRODUCTION SETUP")
    print("=" * 60)
    print()
    print("Your system is working! For production use:")
    print()
    print("1. 📝 Update your .env file with:")
    print("   DB_MODE=proxy")
    print("   PROXY_BASE_URL=http://172.20.10.3:5000")
    print("   PROXY_DEFAULT_CONN=corp_sql_erp")
    print("   PROXY_API_KEY=dummy-key-for-testing  # or set a real key")
    print()
    print("2. 🔐 For real security (optional):")
    print("   - Set a strong PROXY_API_KEY on both Windows and Mac")
    print("   - Enable HTTPS with TLS certificates")
    print()
    print("3. 🚀 Your agent can now:")
    print("   - Access ERP data through the proxy")
    print("   - Process queries safely with limits")
    print("   - Integrate with MCP server")
    print("   - Power the chatbot UI")

if __name__ == "__main__":
    success = test_agent_proxy_with_key()
    if success:
        show_production_setup()
    else:
        print("\n❌ Connection test failed. Check proxy and database status.")