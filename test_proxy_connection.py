#!/usr/bin/env python3
"""
Test script to verify agent-proxy connection
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.client import DatabaseClient

def test_proxy_connection():
    """Test connection to the Windows proxy."""
    print("🔍 Testing Agent → Proxy Connection")
    print("=" * 50)
    
    # Check environment configuration
    print("\n📋 Environment Configuration:")
    print(f"   DB_MODE: {os.getenv('DB_MODE', 'NOT SET')}")
    print(f"   PROXY_BASE_URL: {os.getenv('PROXY_BASE_URL', 'NOT SET')}")
    print(f"   PROXY_DEFAULT_CONN: {os.getenv('PROXY_DEFAULT_CONN', 'NOT SET')}")
    
    if not os.getenv('PROXY_BASE_URL'):
        print("\n❌ PROXY_BASE_URL not set!")
        print("   Please copy .env.proxy_setup to .env and configure your Windows IP")
        return False
    
    try:
        # Initialize DatabaseClient
        print("\n🔧 Initializing DatabaseClient...")
        client = DatabaseClient()
        print(f"   ✅ Client initialized in {client.mode} mode")
        print(f"   🎯 Target: {client.base_url}")
        
        # Test health check
        print("\n🏥 Testing health check...")
        healthy = client.health_check()
        if healthy:
            print("   ✅ Proxy is healthy!")
        else:
            print("   ❌ Proxy health check failed")
            return False
        
        # Get available connections
        print("\n🔗 Getting available connections...")
        connections = client.get_available_connections()
        print(f"   📊 Found {len(connections)} connections:")
        for conn in connections:
            print(f"      - {conn.get('name', 'unknown')}: {conn.get('type', 'unknown')}")
        
        # Test a simple query
        print("\n🔍 Testing simple query...")
        try:
            columns, rows = client.query("SELECT 1 as test_value", limit=1)
            print(f"   ✅ Query successful!")
            print(f"   📊 Columns: {columns}")
            print(f"   📋 Rows: {rows}")
        except Exception as e:
            print(f"   ❌ Query failed: {e}")
            return False
        
        print("\n🎉 All tests passed! Agent is connected to proxy.")
        return True
        
    except Exception as e:
        print(f"\n❌ Connection test failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure your Windows proxy is running")
        print("   2. Check your Windows IP address")
        print("   3. Verify firewall allows port 5000")
        print("   4. Update PROXY_BASE_URL in .env file")
        return False

if __name__ == "__main__":
    # Load environment variables from .env file if it exists
    env_file = project_root / ".env"
    if env_file.exists():
        print("📁 Loading .env file...")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        print("⚠️  No .env file found. Using environment variables only.")
    
    success = test_proxy_connection()
    sys.exit(0 if success else 1)