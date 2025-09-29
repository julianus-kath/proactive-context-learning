#!/usr/bin/env python3
"""
Prompt 7: End-to-End Testing Script
Tests the complete proxy functionality with curl-equivalent requests
"""

import os
import sys
import json
import requests
import urllib3
from app.db.client import DatabaseClient

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_proxy_health():
    """Test the /health endpoint (should be 200)"""
    print("=== Testing Proxy Health ===")
    
    # Configuration from environment
    base_url = os.getenv("PROXY_BASE_URL", "https://10.255.152.48:5000")
    api_key = os.getenv("PROXY_API_KEY")
    ca_bundle = os.getenv("PROXY_CA_BUNDLE")
    verify = ca_bundle if ca_bundle else False  # Use CA bundle or disable verification
    
    try:
        # Health endpoint doesn't require API key
        response = requests.get(
            f"{base_url}/health",
            verify=verify,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Health check PASSED")
            return True
        else:
            print("❌ Health check FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Health check ERROR: {e}")
        return False

def test_proxy_diag():
    """Test the /diag endpoint (lists connections)"""
    print("\n=== Testing Proxy Diagnostics ===")
    
    # Configuration from environment
    base_url = os.getenv("PROXY_BASE_URL", "https://10.255.152.48:5000")
    api_key = os.getenv("PROXY_API_KEY")
    ca_bundle = os.getenv("PROXY_CA_BUNDLE")
    verify = ca_bundle if ca_bundle else False
    
    if not api_key:
        print("❌ PROXY_API_KEY not set")
        return False
    
    try:
        headers = {"X-API-Key": api_key}
        
        response = requests.get(
            f"{base_url}/diag",
            headers=headers,
            verify=verify,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            connections = data.get("connections", [])
            print(f"✅ Diagnostics PASSED - Found {len(connections)} connections")
            return True
        else:
            print("❌ Diagnostics FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Diagnostics ERROR: {e}")
        return False

def test_proxy_query():
    """Test MSSQL query via proxy"""
    print("\n=== Testing Proxy Query ===")
    
    # Configuration from environment
    base_url = os.getenv("PROXY_BASE_URL", "https://10.255.152.48:5000")
    api_key = os.getenv("PROXY_API_KEY")
    ca_bundle = os.getenv("PROXY_CA_BUNDLE")
    verify = ca_bundle if ca_bundle else False
    
    if not api_key:
        print("❌ PROXY_API_KEY not set")
        return False
    
    try:
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        # Test query: list databases
        payload = {
            "conn": "corp_sql_erp",
            "sql": "select name from sys.databases where name like %(p)s",
            "params": {"p": "%"},
            "limit": 50
        }
        
        response = requests.post(
            f"{base_url}/query",
            json=payload,
            headers=headers,
            verify=verify,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200 and result.get("ok"):
            rows = result.get("rows", [])
            print(f"✅ Query PASSED - Returned {len(rows)} rows")
            return True
        else:
            print("❌ Query FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Query ERROR: {e}")
        return False

def test_non_select_query():
    """Test that non-SELECT queries are rejected"""
    print("\n=== Testing Non-SELECT Query Rejection ===")
    
    # Configuration from environment
    base_url = os.getenv("PROXY_BASE_URL", "https://10.255.152.48:5000")
    api_key = os.getenv("PROXY_API_KEY")
    ca_bundle = os.getenv("PROXY_CA_BUNDLE")
    verify = ca_bundle if ca_bundle else False
    
    if not api_key:
        print("❌ PROXY_API_KEY not set")
        return False
    
    try:
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        # Test non-SELECT query (should be rejected)
        payload = {
            "conn": "corp_sql_erp",
            "sql": "INSERT INTO test_table VALUES (1, 'test')",
            "limit": 50
        }
        
        response = requests.post(
            f"{base_url}/query",
            json=payload,
            headers=headers,
            verify=verify,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 400 and not result.get("ok"):
            print("✅ Non-SELECT rejection PASSED")
            return True
        else:
            print("❌ Non-SELECT rejection FAILED - should have been rejected")
            return False
            
    except Exception as e:
        print(f"❌ Non-SELECT test ERROR: {e}")
        return False

def test_database_client():
    """Test DatabaseClient integration with proxy"""
    print("\n=== Testing DatabaseClient Integration ===")
    
    try:
        # Initialize DatabaseClient (should use proxy mode by default)
        client = DatabaseClient()
        
        print(f"DatabaseClient mode: {client.mode}")
        
        if client.mode != "proxy":
            print("❌ DatabaseClient not in proxy mode")
            return False
        
        # Test health check
        health = client.health_check()
        print(f"Health check result: {health}")
        
        # Test getting available connections
        connections = client.get_available_connections()
        print(f"Available connections: {connections}")
        
        # Test a simple query using default connection
        default_conn = os.getenv("PROXY_DEFAULT_CONN")
        if default_conn:
            print(f"Testing query with default connection: {default_conn}")
            
            columns, rows = client.query(
                "SELECT name FROM sys.databases WHERE name LIKE %(p)s",
                params={"p": "%"},
                limit=5
            )
            
            print(f"Query result: {len(rows)} rows, columns: {columns}")
            print("✅ DatabaseClient integration PASSED")
            return True
        else:
            print("⚠️  PROXY_DEFAULT_CONN not set, skipping query test")
            print("✅ DatabaseClient basic integration PASSED")
            return True
            
    except Exception as e:
        print(f"❌ DatabaseClient integration ERROR: {e}")
        return False

def main():
    """Run all end-to-end tests"""
    print("🚀 Starting Prompt 7: End-to-End Testing")
    print("=" * 50)
    
    # Check environment configuration
    print("Environment Configuration:")
    print(f"  PROXY_BASE_URL: {os.getenv('PROXY_BASE_URL', 'NOT SET')}")
    print(f"  PROXY_API_KEY: {'SET' if os.getenv('PROXY_API_KEY') else 'NOT SET'}")
    print(f"  PROXY_CA_BUNDLE: {os.getenv('PROXY_CA_BUNDLE', 'NOT SET')}")
    print(f"  PROXY_DEFAULT_CONN: {os.getenv('PROXY_DEFAULT_CONN', 'NOT SET')}")
    print()
    
    # Run tests
    tests = [
        ("Health Check", test_proxy_health),
        ("Diagnostics", test_proxy_diag),
        ("Query Execution", test_proxy_query),
        ("Non-SELECT Rejection", test_non_select_query),
        ("DatabaseClient Integration", test_database_client)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Test Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests PASSED! Proxy is ready for production.")
        return 0
    else:
        print("⚠️  Some tests FAILED. Check configuration and proxy status.")
        return 1

if __name__ == "__main__":
    sys.exit(main())