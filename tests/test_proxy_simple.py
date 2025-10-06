#!/usr/bin/env python3
"""
Simple test script to verify proxy connection using existing .env format
"""

import os
import sys
import requests
from pathlib import Path

def load_env():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print("📁 Loading .env file...")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        print("⚠️  No .env file found.")

def test_proxy_direct():
    """Test proxy connection directly using requests."""
    print("🔍 Testing Direct Proxy Connection")
    print("=" * 50)
    
    # Get proxy settings from environment
    proxy_host = os.getenv('PROXY_HOST', '172.20.10.3')
    proxy_port = os.getenv('PROXY_PORT', '5000')
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    
    print(f"\n🎯 Target: {proxy_url}")
    
    try:
        # Test health endpoint
        print("\n🏥 Testing health endpoint...")
        response = requests.get(f"{proxy_url}/health", timeout=10)
        response.raise_for_status()
        health_data = response.json()
        print(f"   ✅ Health check successful!")
        print(f"   📊 Response: {health_data}")
        
        # Test diag endpoint (no auth required in simple mode)
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
        
        print("\n🎉 All tests passed! Proxy is working correctly.")
        return True
        
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure your Windows proxy is running")
        print("   2. Check if Windows IP changed (currently trying 172.20.10.3)")
        print("   3. Verify firewall allows port 5000")
        return False
        
    except requests.exceptions.Timeout as e:
        print(f"\n❌ Request timed out: {e}")
        print("   The proxy might be slow or overloaded")
        return False
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

def test_database_client():
    """Test using the DatabaseClient with manual configuration."""
    print("\n" + "=" * 50)
    print("🔧 Testing DatabaseClient Integration")
    print("=" * 50)
    
    # Set required environment variables for DatabaseClient
    os.environ["DB_MODE"] = "proxy"
    os.environ["PROXY_BASE_URL"] = f"http://{os.getenv('PROXY_HOST', '172.20.10.3')}:{os.getenv('PROXY_PORT', '5000')}"
    os.environ["PROXY_API_KEY"] = "not_required_in_simple_mode"
    os.environ["PROXY_DEFAULT_CONN"] = "corp_sql_erp"
    os.environ["PROXY_TLS_VERIFY"] = "false"
    
    try:
        # Add project root to path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        from app.db.client import DatabaseClient
        
        print(f"\n🔧 Initializing DatabaseClient...")
        client = DatabaseClient()
        print(f"   ✅ Client initialized in {client.mode} mode")
        print(f"   🎯 Target: {client.base_url}")
        
        # Test health check
        print("\n🏥 Testing DatabaseClient health check...")
        healthy = client.health_check()
        if healthy:
            print("   ✅ DatabaseClient health check passed!")
        else:
            print("   ❌ DatabaseClient health check failed")
            return False
        
        # Test query through DatabaseClient
        print("\n🔍 Testing DatabaseClient query...")
        columns, rows = client.query("SELECT 1 as test_value", limit=1)
        print(f"   ✅ DatabaseClient query successful!")
        print(f"   📊 Columns: {columns}")
        print(f"   📋 Rows: {rows}")
        
        print("\n🎉 DatabaseClient integration working!")
        return True
        
    except Exception as e:
        print(f"\n❌ DatabaseClient test failed: {e}")
        return False

if __name__ == "__main__":
    load_env()
    
    # Test direct connection first
    direct_success = test_proxy_direct()
    
    if direct_success:
        # Test DatabaseClient integration
        client_success = test_database_client()
        
        if client_success:
            print("\n" + "🎉" * 20)
            print("✅ COMPLETE SUCCESS!")
            print("✅ Proxy is running and accessible")
            print("✅ DatabaseClient can connect to proxy")
            print("✅ Agent system is ready to use your SQL Server!")
            print("🎉" * 20)
        else:
            print("\n⚠️  Proxy works but DatabaseClient needs configuration")
    
    sys.exit(0 if direct_success else 1)