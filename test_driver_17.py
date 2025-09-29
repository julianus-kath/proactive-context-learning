#!/usr/bin/env python3
"""
Test with ODBC Driver 17 for SQL Server
"""

import requests
import json

def test_driver_17():
    """Test if Driver 17 works by making a query."""
    proxy_url = "http://172.20.10.3:5000"
    
    print("🔍 Testing ODBC Driver 17 for SQL Server")
    print("=" * 50)
    print("📝 This assumes you've updated connections.yaml to use Driver 17")
    print()
    
    try:
        # Test health first
        print("🏥 Testing health...")
        response = requests.get(f"{proxy_url}/health", timeout=10)
        response.raise_for_status()
        print("   ✅ Health check passed")
        
        # Test query
        print("\n🔍 Testing query with Driver 17...")
        query_payload = {
            "conn": "corp_sql_erp",
            "sql": "SELECT 1 as test_value, 'Driver 17 works!' as message",
            "limit": 1
        }
        
        response = requests.post(
            f"{proxy_url}/query",
            json=query_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"   ✅ SUCCESS! Driver 17 is working!")
                print(f"   📊 Columns: {data.get('columns', [])}")
                print(f"   📋 Rows: {data.get('rows', [])}")
                
                print("\n🎉 PERFECT! Your system is now fully connected!")
                print("✅ Windows Proxy ↔ SQL Server (Driver 17)")
                print("✅ Mac Agent ↔ Windows Proxy")
                print("✅ Complete pipeline ready!")
                
                return True
            else:
                error_msg = data.get('error', 'Unknown error')
                print(f"   ❌ Query failed: {error_msg}")
                
                if 'IM002' in error_msg or 'nicht gefunden' in error_msg:
                    print("\n💡 Still getting driver not found error.")
                    print("   This means connections.yaml still has Driver 18")
                    print("   Please update it to use Driver 17")
                
        else:
            try:
                error_data = response.json()
                print(f"   ❌ Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   ❌ HTTP {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    return False

def show_fix_instructions():
    """Show how to fix the driver issue."""
    print("\n" + "=" * 60)
    print("🔧 HOW TO FIX THE DRIVER ISSUE")
    print("=" * 60)
    print()
    print("1. 📝 On your Windows machine, edit vpn_config/connections.yaml")
    print("2. 🔄 Change line 4 from:")
    print('     driver: "ODBC Driver 18 for SQL Server"')
    print("   To:")
    print('     driver: "ODBC Driver 17 for SQL Server"')
    print()
    print("3. 🔄 Restart proxy.py")
    print("4. ✅ Run this test again")
    print()
    print("That's it! No need to install anything new.")

if __name__ == "__main__":
    success = test_driver_17()
    if not success:
        show_fix_instructions()