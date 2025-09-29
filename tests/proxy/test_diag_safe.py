#!/usr/bin/env python3
"""
Test the /diag endpoint to ensure it returns safe information without secrets.
"""

import json
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

def test_diag_endpoint():
    """Test that /diag endpoint returns safe information without secrets."""
    try:
        # Import the Flask app
        from proxy import app, CONNECTIONS, PROXY_VERSION, PYTHON_VERSION, POSTGRES_AVAILABLE
        
        # Create test client
        with app.test_client() as client:
            # Mock API key for testing
            headers = {'X-API-Key': 'test-key'}
            
            # Make request to /diag endpoint
            response = client.get('/diag', headers=headers)
            
            # Check response status
            if response.status_code != 200:
                print(f"❌ /diag endpoint returned status {response.status_code}")
                return False
            
            # Parse JSON response
            try:
                diag_data = response.get_json()
            except Exception as e:
                print(f"❌ Failed to parse /diag JSON response: {e}")
                return False
            
            # Verify response structure
            required_keys = ['version', 'connections', 'drivers']
            for key in required_keys:
                if key not in diag_data:
                    print(f"❌ Missing required key '{key}' in /diag response")
                    return False
            
            # Check version information
            version_info = diag_data['version']
            if 'proxy' not in version_info or 'python' not in version_info:
                print("❌ Missing version information in /diag response")
                return False
            
            if version_info['proxy'] != PROXY_VERSION:
                print(f"❌ Proxy version mismatch: expected {PROXY_VERSION}, got {version_info['proxy']}")
                return False
            
            if version_info['python'] != PYTHON_VERSION:
                print(f"❌ Python version mismatch: expected {PYTHON_VERSION}, got {version_info['python']}")
                return False
            
            # Check connections information (should only contain name and type)
            connections = diag_data['connections']
            if not isinstance(connections, list):
                print("❌ Connections should be a list")
                return False
            
            for conn in connections:
                if not isinstance(conn, dict):
                    print("❌ Each connection should be a dictionary")
                    return False
                
                # Should only have 'name' and 'type' keys
                if set(conn.keys()) != {'name', 'type'}:
                    print(f"❌ Connection should only have 'name' and 'type' keys, got: {list(conn.keys())}")
                    return False
                
                # Check for any secret-like values
                for key, value in conn.items():
                    if any(secret in str(value).lower() for secret in ['password', 'pwd', 'secret', 'key', 'host', 'server', 'port']):
                        if key not in ['name', 'type']:  # These are allowed
                            print(f"❌ Connection contains potential secret in {key}: {value}")
                            return False
            
            # Check drivers information
            drivers = diag_data['drivers']
            if not isinstance(drivers, dict):
                print("❌ Drivers should be a dictionary")
                return False
            
            # Should have mssql and postgres keys
            if 'mssql' not in drivers or 'postgres' not in drivers:
                print("❌ Drivers should contain 'mssql' and 'postgres' keys")
                return False
            
            # Verify no secrets in the entire response
            response_str = json.dumps(diag_data, indent=2)
            secret_patterns = ['password', 'pwd=', 'secret', 'api_key', 'host=', 'server=', 'database=', 'uid=']
            
            for pattern in secret_patterns:
                if pattern.lower() in response_str.lower():
                    # Allow some exceptions
                    if pattern in ['password', 'secret'] and 'password' not in response_str.lower():
                        continue
                    print(f"❌ Response contains potential secret pattern: {pattern}")
                    print(f"Response: {response_str}")
                    return False
            
            print("✅ /diag endpoint test passed")
            print(f"✅ Response structure is correct")
            print(f"✅ Version info: proxy={version_info['proxy']}, python={version_info['python']}")
            print(f"✅ Found {len(connections)} connections (safe info only)")
            print(f"✅ Driver info included without secrets")
            print(f"✅ No secret patterns detected in response")
            
            return True
            
    except ImportError as e:
        print(f"❌ Failed to import proxy module: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error testing /diag endpoint: {e}")
        return False


def test_startup_logging():
    """Test that startup logging doesn't expose secrets."""
    try:
        # Capture startup output by importing proxy module
        import io
        import contextlib
        
        # Redirect stdout to capture print statements
        captured_output = io.StringIO()
        
        with contextlib.redirect_stdout(captured_output):
            # Re-import to trigger startup logging
            import importlib
            import proxy
            importlib.reload(proxy)
        
        startup_log = captured_output.getvalue()
        
        # Check for secret patterns in startup log
        secret_patterns = ['password=', 'pwd=', 'secret=', 'api_key=']
        
        for pattern in secret_patterns:
            if pattern.lower() in startup_log.lower():
                print(f"❌ Startup log contains potential secret pattern: {pattern}")
                print(f"Log excerpt: {startup_log}")
                return False
        
        print("✅ Startup logging test passed")
        print("✅ No secret patterns detected in startup logs")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing startup logging: {e}")
        return False


def main():
    """Run all diagnostic safety tests."""
    print("Testing /diag endpoint and startup logging safety...")
    print()
    
    all_passed = True
    
    # Test /diag endpoint
    print("1. Testing /diag endpoint:")
    if not test_diag_endpoint():
        all_passed = False
    print()
    
    # Test startup logging
    print("2. Testing startup logging:")
    if not test_startup_logging():
        all_passed = False
    print()
    
    if all_passed:
        print("✅ All diagnostic safety tests passed!")
        return 0
    else:
        print("❌ Some diagnostic safety tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())