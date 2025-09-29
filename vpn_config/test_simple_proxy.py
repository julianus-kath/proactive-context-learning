#!/usr/bin/env python3
"""
Simple test script for the development proxy.
Tests basic functionality without requiring database access.
"""

import requests
import json
import sys

def test_proxy(base_url="http://localhost:5000"):
    """Test the proxy endpoints."""
    print(f"Testing proxy at {base_url}")
    print("=" * 50)
    
    # Test 1: Health endpoint
    print("1. Testing /health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {data['status']}")
            print(f"   ✅ Connections: {data['connections']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Diagnostic endpoint
    print("\n2. Testing /diag endpoint...")
    try:
        response = requests.get(f"{base_url}/diag", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Proxy version: {data['version']['proxy']}")
            print(f"   ✅ Python version: {data['version']['python']}")
            print(f"   ✅ Connections: {len(data['connections'])}")
            print(f"   ✅ MSSQL drivers: {len(data['drivers']['mssql']) if isinstance(data['drivers']['mssql'], list) else 'Error'}")
            print(f"   ✅ PostgreSQL: {data['drivers']['postgres']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 3: Query endpoint (will fail without database, but should validate request)
    print("\n3. Testing /query endpoint validation...")
    try:
        test_query = {
            "conn": "corp_sql_erp",
            "sql": "SELECT 1 as test",
            "limit": 10
        }
        response = requests.post(
            f"{base_url}/query",
            headers={"Content-Type": "application/json"},
            data=json.dumps(test_query),
            timeout=5
        )
        
        if response.status_code in [200, 400]:  # 400 is expected if database not accessible
            data = response.json()
            if response.status_code == 200:
                print(f"   ✅ Query executed successfully")
                print(f"   ✅ Rows returned: {data.get('rowcount', 0)}")
            else:
                print(f"   ⚠️  Query validation works (database not accessible): {data.get('error', 'Unknown error')}")
        else:
            print(f"   ❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All tests passed! Proxy is working correctly.")
    print("\nNext steps:")
    print("1. Update connections.yaml with your database details")
    print("2. Set SQLSERVER_PASSWORD environment variable")
    print("3. Test with real database queries")
    return True

if __name__ == "__main__":
    # Allow custom URL as command line argument
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    success = test_proxy(url)
    sys.exit(0 if success else 1)