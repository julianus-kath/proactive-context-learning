#!/usr/bin/env python3
"""
Test script for new IP address 172.20.10.3:5000
"""

import requests
import sys

def test_new_proxy():
    """Test the proxy at the new IP address."""
    proxy_url = "http://172.20.10.3:5000"
    
    print("🔍 Testing New Proxy IP: 172.20.10.3:5000")
    print("=" * 50)
    
    try:
        # Test health endpoint
        print("\n🏥 Testing health endpoint...")
        response = requests.get(f"{proxy_url}/health", timeout=10)
        response.raise_for_status()
        health_data = response.json()
        print(f"   ✅ Health check successful!")
        print(f"   📊 Response: {health_data}")
        
        # Test diag endpoint
        print("\n🔍 Testing diagnostics endpoint...")
        response = requests.get(f"{proxy_url}/diag", timeout=10)
        response.raise_for_status()
        diag_data = response.json()
        print(f"   ✅ Diagnostics successful!")
        print(f"   📊 Connections: {len(diag_data.get('connections', []))}")
        for conn in diag_data.get('connections', []):
            print(f"      - {conn.get('name', 'unknown')}: {conn.get('type', 'unknown')}")
        
        # Test simple query
        print("\n🔍 Testing simple query...")
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
        response.raise_for_status()
        query_data = response.json()
        
        if query_data.get("ok"):
            print(f"   ✅ Query successful!")
            print(f"   📊 Columns: {query_data.get('columns', [])}")
            print(f"   📋 Rows: {query_data.get('rows', [])}")
        else:
            print(f"   ❌ Query failed: {query_data.get('error', 'Unknown error')}")
            return False
        
        print("\n🎉 SUCCESS! Proxy at 172.20.10.3:5000 is working!")
        print("\n📋 Next Steps:")
        print("   1. Update PROXY_HOST=172.20.10.3 in your .env file")
        print("   2. Add DatabaseClient configuration to .env")
        print("   3. Test agent integration")
        
        return True
        
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure your Windows proxy is running")
        print("   2. Verify the IP address is correct: 172.20.10.3")
        print("   3. Check firewall allows port 5000")
        print("   4. Try: curl http://172.20.10.3:5000/health")
        return False
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_new_proxy()
    sys.exit(0 if success else 1)