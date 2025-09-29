#!/usr/bin/env python3
"""
Test script for the new POST /query endpoint with JSON request/response format.
Tests read-only guards, parameterized queries, limits, and timeouts.
"""

import requests
import json
import urllib3
import sys

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
PROXY_URL = "https://10.255.152.48:5000"  # Update with your Windows laptop IP
API_KEY = "your-secure-api-key"  # Update with your API key

def test_endpoint(name, method, endpoint, headers=None, json_data=None, expected_status=200):
    """Test an endpoint and return the response."""
    print(f"\n=== {name} ===")
    
    url = f"{PROXY_URL}{endpoint}"
    
    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=json_data, verify=False, timeout=10)
        else:
            response = requests.get(url, headers=headers, verify=False, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"Response: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response (text): {response.text}")
        
        if response.status_code == expected_status:
            print("✅ PASS")
        else:
            print(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
        
        return response
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def main():
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    print("Testing Enhanced SQL Proxy - POST /query endpoint")
    print("=" * 60)
    
    # Test 1: Valid SELECT query
    test_endpoint(
        "Valid SELECT Query",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT 1 as test_column",
            "limit": 100,
            "timeout_s": 10
        }
    )
    
    # Test 2: Query with parameters
    test_endpoint(
        "Parameterized Query",
        "POST", 
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT name FROM sys.databases WHERE name LIKE ?",
            "params": ["%master%"],
            "limit": 10,
            "timeout_s": 15
        }
    )
    
    # Test 3: Query with default limit and timeout
    test_endpoint(
        "Query with Defaults",
        "POST",
        "/query", 
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT TOP 5 name FROM sys.databases"
        }
    )
    
    # Test 4: Invalid query (INSERT) - should fail
    test_endpoint(
        "Invalid INSERT Query (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "INSERT INTO test VALUES (1)"
        },
        expected_status=400
    )
    
    # Test 5: Multiple statements - should fail
    test_endpoint(
        "Multiple Statements (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp", 
            "sql": "SELECT 1; SELECT 2"
        },
        expected_status=400
    )
    
    # Test 6: Missing connection
    test_endpoint(
        "Missing Connection (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "sql": "SELECT 1"
        },
        expected_status=400
    )
    
    # Test 7: Unknown connection
    test_endpoint(
        "Unknown Connection (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "nonexistent",
            "sql": "SELECT 1"
        },
        expected_status=400
    )
    
    # Test 8: Invalid limit
    test_endpoint(
        "Invalid Limit (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT 1",
            "limit": 20000  # Over max limit
        },
        expected_status=400
    )
    
    # Test 9: Invalid timeout
    test_endpoint(
        "Invalid Timeout (should fail)",
        "POST",
        "/query",
        headers=headers,
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT 1",
            "timeout_s": 500  # Over max timeout
        },
        expected_status=400
    )
    
    # Test 10: Missing API key
    test_endpoint(
        "Missing API Key (should fail)",
        "POST",
        "/query",
        headers={"Content-Type": "application/json"},
        json_data={
            "conn": "corp_sql_erp",
            "sql": "SELECT 1"
        },
        expected_status=401
    )
    
    # Test 11: Invalid JSON
    print(f"\n=== Invalid JSON (should fail) ===")
    try:
        response = requests.post(
            f"{PROXY_URL}/query",
            headers=headers,
            data="invalid json",
            verify=False,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        if response.status_code == 400:
            print("✅ PASS")
        else:
            print("❌ FAIL")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test 12: Non-JSON content type
    print(f"\n=== Non-JSON Content Type (should fail) ===")
    try:
        response = requests.post(
            f"{PROXY_URL}/query",
            headers={"X-API-Key": API_KEY, "Content-Type": "text/plain"},
            data="some data",
            verify=False,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        if response.status_code == 400:
            print("✅ PASS")
        else:
            print("❌ FAIL")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        PROXY_URL = f"https://{sys.argv[1]}:5000"
    if len(sys.argv) > 2:
        API_KEY = sys.argv[2]
    
    print(f"Testing proxy at: {PROXY_URL}")
    print(f"Using API key: {API_KEY[:10]}...")
    
    main()