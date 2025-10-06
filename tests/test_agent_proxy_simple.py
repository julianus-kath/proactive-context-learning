#!/usr/bin/env python3
"""
Test Agent → Proxy connection in simple mode (no API key required)
"""

import os
import sys
sys.path.append('/')

from app.db.client import DatabaseClient

def test_agent_proxy_simple():
    """Test the agent → proxy connection in simple mode."""
    print("🔍 Testing Agent → Proxy Connection (Simple Mode)")
    print("=" * 60)
    
    # Set up proxy configuration (no API key for simple mode)
    os.environ['DB_MODE'] = 'proxy'
    os.environ['PROXY_BASE_URL'] = 'http://172.20.10.3:5000'
    os.environ['PROXY_DEFAULT_CONN'] = 'corp_sql_erp'
    os.environ['PROXY_API_KEY'] = ''  # Empty for simple mode
    
    print("📋 Configuration:")
    print(f"   DB_MODE: {os.environ.get('DB_MODE')}")
    print(f"   PROXY_BASE_URL: {os.environ.get('PROXY_BASE_URL')}")
    print(f"   PROXY_DEFAULT_CONN: {os.environ.get('PROXY_DEFAULT_CONN')}")
    print(f"   PROXY_API_KEY: {'(empty - simple mode)' if not os.environ.get('PROXY_API_KEY') else '(set)'}")
    print()
    
    try:
        # Initialize DatabaseClient
        print("🔧 Initializing DatabaseClient...")
        db_client = DatabaseClient()
        print("   ✅ DatabaseClient initialized")
        
        # Test simple query
        print("\n🔍 Testing simple query...")
        result = db_client.execute_query("SELECT 1 as test_value, 'Agent → Proxy works!' as message")
        
        if result and result.get('ok'):
            print("   ✅ Query successful!")
            print(f"   📊 Columns: {result.get('columns', [])}")
            print(f"   📋 Rows: {result.get('rows', [])}")
            print(f"   📈 Row count: {result.get('rowcount', 0)}")
            
            # Test database metadata query
            print("\n🔍 Testing database metadata query...")
            result2 = db_client.execute_query(
                "SELECT TOP 5 name, database_id, create_date FROM sys.databases ORDER BY name", 
                limit=10
            )
            
            if result2 and result2.get('ok'):
                print("   ✅ Database metadata query successful!")
                print(f"   📊 Columns: {result2.get('columns', [])}")
                print(f"   📋 Rows: {result2.get('rows', [])}")
                print(f"   📈 Row count: {result2.get('rowcount', 0)}")
                
                # Test with different connection (if available)
                print("\n🔍 Testing execute_query method...")
                result3 = db_client.execute_query("SELECT @@VERSION as sql_server_version")
                
                if result3 and result3.get('ok'):
                    print("   ✅ Version query successful!")
                    print(f"   📊 SQL Server Version: {result3.get('rows', [[]])[0][0] if result3.get('rows') else 'Unknown'}")
                    
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
                    print("🚀 Ready for:")
                    print("   📊 ERP data crawling")
                    print("   🔍 Query processing")
                    print("   🤖 AI-powered analysis")
                    print("   💬 Chatbot interactions")
                    print("   🔧 MCP server integration")
                    
                    return True
                else:
                    print(f"   ❌ Version query failed: {result3.get('error') if result3 else 'No response'}")
            else:
                print(f"   ❌ Metadata query failed: {result2.get('error') if result2 else 'No response'}")
        else:
            print(f"   ❌ Simple query failed: {result.get('error') if result else 'No response'}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def show_next_steps():
    """Show next steps for production setup."""
    print("\n" + "=" * 60)
    print("🔧 NEXT STEPS FOR PRODUCTION")
    print("=" * 60)
    print()
    print("1. 🔐 Set up API key authentication:")
    print("   - On Windows: set PROXY_API_KEY=your-secret-key")
    print("   - In your .env: PROXY_API_KEY=your-secret-key")
    print()
    print("2. 🔒 Enable HTTPS (optional):")
    print("   - Set PROXY_TLS_CERT_FILE and PROXY_TLS_KEY_FILE")
    print("   - Update PROXY_BASE_URL to https://...")
    print()
    print("3. 📝 Update your .env file with:")
    print("   DB_MODE=proxy")
    print("   PROXY_BASE_URL=http://172.20.10.3:5000")
    print("   PROXY_DEFAULT_CONN=corp_sql_erp")
    print("   PROXY_API_KEY=your-secret-key")

if __name__ == "__main__":
    success = test_agent_proxy_simple()
    if success:
        show_next_steps()
    else:
        print("\n❌ Connection test failed. Check proxy and database status.")