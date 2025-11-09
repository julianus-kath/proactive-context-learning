#!/usr/bin/env python3
"""
Quick proxy connection diagnostic tool.

Usage:
    python scripts/test_proxy_quick.py
    
This script performs a rapid health check of the proxy connection.
"""

import os
import sys
import requests
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print('=' * 60)


def print_ok(text):
    """Print success message."""
    print(f"✅ {text}")


def print_fail(text):
    """Print failure message."""
    print(f"❌ {text}")


def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")


def check_environment():
    """Check environment configuration."""
    print_header("Environment Configuration")
    
    db_mode = os.getenv('DB_MODE')
    proxy_url = os.getenv('PROXY_BASE_URL')
    api_key = os.getenv('PROXY_API_KEY')
    default_conn = os.getenv('PROXY_DEFAULT_CONN')
    tls_verify = os.getenv('PROXY_TLS_VERIFY', 'true')
    
    if not db_mode:
        print_info("DB_MODE not set (defaulting to 'proxy')")
    else:
        print_ok(f"DB_MODE = {db_mode}")
    
    if not proxy_url:
        print_fail("PROXY_BASE_URL not set")
        return False
    print_ok(f"PROXY_BASE_URL = {proxy_url}")
    
    if not api_key:
        print_info("PROXY_API_KEY not set (proxy may have authentication disabled)")
    else:
        print_ok(f"PROXY_API_KEY = {'*' * 20}")
    
    if default_conn:
        print_ok(f"PROXY_DEFAULT_CONN = {default_conn}")
    else:
        print_info("PROXY_DEFAULT_CONN not set (optional)")
    
    print_info(f"PROXY_TLS_VERIFY = {tls_verify}")
    
    return True


def check_network_connectivity():
    """Check if proxy is reachable."""
    print_header("Network Connectivity")
    
    proxy_url = os.getenv('PROXY_BASE_URL')
    if not proxy_url:
        print_fail("PROXY_BASE_URL not configured")
        return False
    
    # Parse URL
    parsed = urlparse(proxy_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    
    print_info(f"Testing connection to {host}:{port}...")
    
    # Try to connect
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print_ok(f"Port {port} is reachable")
            return True
        else:
            print_fail(f"Cannot connect to port {port}")
            print_info("Check if proxy is running on Windows")
            print_info("Check Windows firewall settings")
            return False
    except socket.gaierror:
        print_fail(f"Cannot resolve hostname: {host}")
        print_info("Check if IP address is correct")
        return False
    except Exception as e:
        print_fail(f"Connection test failed: {e}")
        return False


def check_proxy_health():
    """Check proxy health endpoint."""
    print_header("Proxy Health Check")
    
    proxy_url = os.getenv('PROXY_BASE_URL')
    api_key = os.getenv('PROXY_API_KEY')
    tls_verify = os.getenv('PROXY_TLS_VERIFY', 'true').lower() == 'true'
    
    if not proxy_url:
        print_fail("Missing PROXY_BASE_URL")
        return False
    
    try:
        print_info(f"Calling {proxy_url}/diag...")
        
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
        else:
            print_info("No API key provided (testing without authentication)")
        
        response = requests.get(
            f"{proxy_url}/diag",
            headers=headers,
            verify=tls_verify,
            timeout=10
        )
        
        if response.status_code == 200:
            print_ok("Proxy is responding")
            
            data = response.json()
            
            # Show proxy info
            if 'version' in data:
                print_info(f"Proxy version: {data['version']}")
            
            # Show connections
            connections = data.get('connections', [])
            if connections:
                print_ok(f"Found {len(connections)} connection(s):")
                for conn in connections:
                    print(f"    - {conn.get('name', 'unknown')} ({conn.get('type', 'unknown')})")
            else:
                print_fail("No connections configured")
                print_info("Check connections.yaml on Windows")
                return False
            
            return True
            
        elif response.status_code == 401:
            print_fail("Authentication failed")
            print_info("Check if PROXY_API_KEY matches Windows configuration")
            return False
        else:
            print_fail(f"Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.SSLError as e:
        print_fail("SSL certificate verification failed")
        print_info("Set PROXY_TLS_VERIFY=false in .env for self-signed certs")
        return False
    except requests.exceptions.ConnectionError as e:
        print_fail("Connection refused")
        print_info("Check if proxy is running on Windows")
        return False
    except requests.exceptions.Timeout:
        print_fail("Request timeout")
        print_info("Check network connectivity and proxy status")
        return False
    except Exception as e:
        print_fail(f"Health check failed: {e}")
        return False


def check_simple_query():
    """Test a simple query."""
    print_header("Simple Query Test")
    
    try:
        from app.db.client import DatabaseClient
        
        client = DatabaseClient()
        print_info("Executing: SELECT 1 AS test")
        
        columns, rows = client.query("SELECT 1 AS test", limit=1, timeout_s=10)
        
        print_ok("Query executed successfully")
        print_info(f"Columns: {columns}")
        print_info(f"Rows: {rows}")
        
        return True
        
    except Exception as e:
        print_fail(f"Query failed: {e}")
        return False


def main():
    """Run quick diagnostics."""
    print("\n" + "=" * 60)
    print("  PROXY CONNECTION QUICK DIAGNOSTIC")
    print("=" * 60)
    
    # Check environment
    if not check_environment():
        print("\n" + "=" * 60)
        print_fail("Environment configuration incomplete")
        print_info("Please configure your .env file")
        print_info("See: PROXY_SETUP_CHECKLIST.md")
        print("=" * 60 + "\n")
        return 1
    
    # Check network
    if not check_network_connectivity():
        print("\n" + "=" * 60)
        print_fail("Cannot reach proxy server")
        print_info("1. Verify proxy is running on Windows")
        print_info("2. Check Windows firewall settings")
        print_info("3. Verify IP address is correct")
        print("=" * 60 + "\n")
        return 1
    
    # Check proxy health
    if not check_proxy_health():
        print("\n" + "=" * 60)
        print_fail("Proxy health check failed")
        print_info("See error messages above for details")
        print("=" * 60 + "\n")
        return 1
    
    # Test query
    if not check_simple_query():
        print("\n" + "=" * 60)
        print_fail("Query execution failed")
        print_info("Check database configuration on Windows")
        print("=" * 60 + "\n")
        return 1
    
    # Success!
    print("\n" + "=" * 60)
    print_ok("All checks passed!")
    print_info("Proxy connection is working correctly")
    print_info("Run full test suite: python tests/test_proxy_connection.py")
    print("=" * 60 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())