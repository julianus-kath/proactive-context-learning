#!/usr/bin/env python3
"""
Debug the query issue
"""

import requests
import json

def test_query_debug():
    """Debug the query issue."""
    proxy_url = "http://172.20.10.3:5000"
    
    print("🔍 Debugging Query Issue")
    print("=" * 50)
    
    # Test simple query with detailed error handling
    print("\n🔍 Testing query with debug info...")
    query_payload = {
        "conn": "corp_sql_erp",
        "sql": "SELECT 1 as test_value",
        "limit": 1
    }
    
    print(f"📤 Sending payload: {json.dumps(query_payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{proxy_url}/query",
            json=query_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"📥 Response body: {json.dumps(response_data, indent=2)}")
        except:
            print(f"📥 Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Query successful!")
        else:
            print(f"❌ Query failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_query_debug()