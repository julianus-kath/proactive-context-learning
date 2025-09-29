#!/usr/bin/env python3
"""
Test script for the enhanced proxy.py with API key auth and HTTPS.
This script demonstrates the expected behavior for Prompt 1 acceptance criteria.
"""

import requests
import urllib3
import os

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_proxy_auth(base_url, api_key):
    """Test the proxy authentication and HTTPS functionality."""
    
    print(f"Testing proxy at: {base_url}")
    print("=" * 50)
    
    # Test 1: Health endpoint without API key (should return 401)
    print("1. Testing /health without API key (should return 401):")
    try:
        response = requests.get(f"{base_url}/health", verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 2: Health endpoint with API key (should return 200)
    print("2. Testing /health with API key (should return 200):")
    headers = {"X-API-Key": api_key}
    try:
        response = requests.get(f"{base_url}/health", headers=headers, verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 3: Query endpoint without API key (should return 401)
    print("3. Testing /query without API key (should return 401):")
    try:
        response = requests.get(f"{base_url}/query?sql=SELECT 1", verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 4: Query endpoint without connection parameter (should return 400)
    print("4. Testing /query without connection parameter (should return 400):")
    try:
        response = requests.get(f"{base_url}/query?sql=SELECT 1 as test_column", headers=headers, verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 5: Query endpoint with connection parameter (should work if DB is available)
    print("5. Testing /query with connection parameter:")
    try:
        response = requests.get(f"{base_url}/query?sql=SELECT 1 as test_column&connection=corp_sql_erp", headers=headers, verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 6: Query endpoint with invalid connection (should return 400)
    print("6. Testing /query with invalid connection (should return 400):")
    try:
        response = requests.get(f"{base_url}/query?sql=SELECT 1&connection=invalid_connection", headers=headers, verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 7: Diag endpoint with API key
    print("7. Testing /diag with API key:")
    try:
        response = requests.get(f"{base_url}/diag", headers=headers, verify=False, timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    # Configuration - update these for your environment
    WINDOWS_LAN_IP = "10.255.152.48"  # Replace with actual Windows laptop IP
    PORT = "5000"
    API_KEY = "test-api-key-123"  # Replace with your actual API key
    
    base_url = f"https://{WINDOWS_LAN_IP}:{PORT}"
    
    print("Proxy Authentication Test")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print(f"API Key: {API_KEY}")
    print()
    
    test_proxy_auth(base_url, API_KEY)