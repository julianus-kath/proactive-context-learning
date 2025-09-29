#!/usr/bin/env python3
"""
Test different ODBC driver configurations
"""

import requests
import json
import yaml
import tempfile
import os

def test_driver_config(driver_name):
    """Test a specific driver configuration."""
    proxy_url = "http://172.20.10.3:5000"
    
    print(f"\n🔍 Testing driver: {driver_name}")
    print("-" * 50)
    
    # Create temporary connections.yaml with this driver
    config = {
        'connections': {
            'corp_sql_erp': {
                'type': 'mssql',
                'driver': driver_name,
                'host': '192.168.200.16',
                'port': 1433,
                'database': 'master',
                'user': 'SimonM',
                'password': '%Si!Mon!Ma1',
                'encrypt': True,
                'trust_server_certificate': True
            }
        }
    }
    
    # Note: This test shows what to try, but you'll need to update 
    # the actual connections.yaml file on your Windows machine
    
    query_payload = {
        "conn": "corp_sql_erp",
        "sql": "SELECT 1 as test_value",
        "limit": 1
    }
    
    try:
        response = requests.post(
            f"{proxy_url}/query",
            json=query_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"   ✅ SUCCESS with {driver_name}!")
                return True
            else:
                print(f"   ❌ Query failed: {data.get('error', 'Unknown error')}")
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                if 'IM002' in error_msg or 'nicht gefunden' in error_msg:
                    print(f"   ❌ Driver not found: {driver_name}")
                else:
                    print(f"   ❌ Other error: {error_msg}")
            except:
                print(f"   ❌ HTTP {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
    
    return False

def main():
    """Test common ODBC driver names."""
    print("🔍 Testing Common ODBC Driver Names")
    print("=" * 60)
    print("Note: You'll need to update connections.yaml on Windows with the working driver")
    
    # Common ODBC driver names to try
    drivers_to_test = [
        "ODBC Driver 18 for SQL Server",  # Current (not working)
        "ODBC Driver 17 for SQL Server",  # Very common
        "ODBC Driver 13 for SQL Server",  # Older but common
        "ODBC Driver 11 for SQL Server",  # Legacy
        "SQL Server Native Client 11.0",  # Legacy
        "SQL Server",                     # Basic driver
    ]
    
    working_drivers = []
    
    for driver in drivers_to_test:
        if test_driver_config(driver):
            working_drivers.append(driver)
    
    print("\n" + "=" * 60)
    if working_drivers:
        print("✅ Working drivers found:")
        for driver in working_drivers:
            print(f"   - {driver}")
        print(f"\n🔧 Update your connections.yaml with: driver: \"{working_drivers[0]}\"")
    else:
        print("❌ No working drivers found with current test")
        print("\n🔧 Manual steps needed:")
        print("   1. Check available drivers on Windows:")
        print("      Get-OdbcDriver | Where-Object {$_.Name -like '*SQL Server*'}")
        print("   2. Update connections.yaml with correct driver name")
        print("   3. Restart proxy.py")

if __name__ == "__main__":
    main()