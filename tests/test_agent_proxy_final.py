#!/usr/bin/env python3
"""
Final test of Agent → Proxy connection using DatabaseClient
"""

import os
import sys
sys.path.append('/')

from app.db.client import DatabaseClient

def test_agent_proxy_connection():
    """Test the full agent → proxy → database connection."""
    print("🔍 Testing Agent → Proxy → Database Connection")
    print("=" * 60)
    
    # Set up proxy configuration
    os.environ['DB_MODE'] = 'proxy'
    os.environ['PROXY_BASE_URL'] = 'http://172.20.10.3:5000'
    os.environ['PROXY_DEFAULT_CONN'] = 'corp_sql_erp'
    
    print("📋 Configuration:")
    print(f"   DB_MODE: {os.environ.get('DB_MODE')}")
    print(f"   PROXY_BASE_URL: {os.environ.get('PROXY_BASE_URL')}")
    print(f"   PROXY_DEFAULT_CONN: {os.environ.get('PROXY_DEFAULT_CONN')}")
    print()
    
    try:
        # Initialize DatabaseClient
        print("🔧 Initializing DatabaseClient...")
        db_client = DatabaseClient()
        print("   ✅ DatabaseClient initialized")
        
        # Test simple query
        print("\n🔍 Testing simple query...")
        result = db_client.execute_query("SELECT 1 as test_value, 'Agent works!' as message")
        
        if result and result.get('ok'):
            print("   ✅ Query successful!")
            print(f"   📊 Columns: {result.get('columns', [])}")
            print(f"   📋 Rows: {result.get('rows', [])}")
            print(f"   📈 Row count: {result.get('rowcount', 0)}")
            
            # Test with limit
            print("\n🔍 Testing query with limit...")
            result2 = db_client.execute_query(
                "SELECT TOP 3 name, database_id FROM sys.databases", 
                limit=5
            )
            
            if result2 and result2.get('ok'):
                print("   ✅ Database query successful!")
                print(f"   📊 Columns: {result2.get('columns', [])}")
                print(f"   📋 Rows: {result2.get('rows', [])}")
                print(f"   📈 Row count: {result2.get('rowcount', 0)}")
                
                print("\n" + "🎉" * 20)
                print("🎉 COMPLETE SUCCESS! 🎉")
                print("🎉" * 20)
                print()
                print("✅ Your entire ERP system is now connected:")
                print("   🖥️  Mac Agent (DatabaseClient)")
                print("   ↕️  Network connection")
                print("   🪟 Windows Proxy (proxy.py)")
                print("   ↕️  ODBC Driver 17")
                print("   🗄️  SQL Server Database")
                print()
                print("🚀 Ready for:")
                print("   📊 ERP data crawling")
                print("   🔍 Query processing")
                print("   🤖 AI-powered analysis")
                print("   💬 Chatbot interactions")
                
                return True
            else:
                print(f"   ❌ Database query failed: {result2.get('error') if result2 else 'No response'}")
        else:
            print(f"   ❌ Simple query failed: {result.get('error') if result else 'No response'}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def show_env_update_instructions():
    """Show how to update .env file."""
    print("\n" + "=" * 60)
    print("🔧 TO MAKE THIS PERMANENT")
    print("=" * 60)
    print()
    print("Add these lines to your .env file:")
    print()
    print("# Database proxy configuration")
    print("DB_MODE=proxy")
    print("PROXY_BASE_URL=http://172.20.10.3:5000")
    print("PROXY_DEFAULT_CONN=corp_sql_erp")
    print()
    print("Then your agent will automatically use the proxy!")

if __name__ == "__main__":
    success = test_agent_proxy_connection()
    if success:
        show_env_update_instructions()
    else:
        print("\n❌ Connection test failed. Check proxy and database status.")