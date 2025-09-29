#!/usr/bin/env python3
"""
Test after ODBC driver installation
"""

import requests
import json

def test_after_driver_install():
    """Test the connection after driver installation."""
    proxy_url = "http://172.20.10.3:5000"
    
    print("🔍 Testing After ODBC Driver Installation")
    print("=" * 50)
    
    try:
        # Test health first
        print("\n🏥 Testing health...")
        response = requests.get(f"{proxy_url}/health", timeout=10)
        response.raise_for_status()
        print("   ✅ Health check passed")
        
        # Test query
        print("\n🔍 Testing query...")
        query_payload = {
            "conn": "corp_sql_erp",
            "sql": "SELECT 1 as test_value",
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
                print(f"   ✅ Query successful!")
                print(f"   📊 Columns: {data.get('columns', [])}")
                print(f"   📋 Rows: {data.get('rows', [])}")
                
                print("\n🎉 SUCCESS! Everything is working!")
                print("✅ Proxy is accessible at 172.20.10.3:5000")
                print("✅ ODBC driver is working")
                print("✅ SQL Server connection is established")
                print("✅ Agent system can now connect to your database!")
                
                return True
            else:
                print(f"   ❌ Query failed: {data.get('error', 'Unknown error')}")
        else:
            try:
                error_data = response.json()
                print(f"   ❌ Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   ❌ HTTP {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    return False

if __name__ == "__main__":
    test_after_driver_install()