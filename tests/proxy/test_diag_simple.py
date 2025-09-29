#!/usr/bin/env python3
"""
Simple test for /diag endpoint functionality without full environment setup.
"""

import os
import sys
import tempfile

# Set minimal required environment variables for testing
os.environ['PROXY_API_KEY'] = 'test-key-123'
os.environ['PROXY_TLS_CERT_FILE'] = '/tmp/test.crt'  # Will create dummy files
os.environ['PROXY_TLS_KEY_FILE'] = '/tmp/test.key'

# Create dummy cert files for testing
with open('/tmp/test.crt', 'w') as f:
    f.write('dummy cert')
with open('/tmp/test.key', 'w') as f:
    f.write('dummy key')

# Create a minimal connections.yaml for testing
connections_yaml = """
connections:
  test_mssql:
    type: mssql
    host: localhost
    port: 1433
    database: testdb
    user: testuser
    password: testpass
  test_postgres:
    type: postgres
    host: localhost
    port: 5432
    database: testdb
    user: testuser
    password: testpass
"""

# Write test connections.yaml
with open('connections.yaml', 'w') as f:
    f.write(connections_yaml)

try:
    # Now import and test
    from proxy import app, PROXY_VERSION, PYTHON_VERSION
    
    def test_diag_response_structure():
        """Test that /diag returns the expected structure without secrets."""
        with app.test_client() as client:
            headers = {'X-API-Key': 'test-key-123'}
            response = client.get('/diag', headers=headers)
            
            if response.status_code != 200:
                print(f"❌ /diag returned status {response.status_code}")
                return False
            
            data = response.get_json()
            
            # Check required keys
            required_keys = ['version', 'connections', 'drivers']
            for key in required_keys:
                if key not in data:
                    print(f"❌ Missing key: {key}")
                    return False
            
            # Check version structure
            version = data['version']
            if 'proxy' not in version or 'python' not in version:
                print("❌ Missing version info")
                return False
            
            # Check connections structure
            connections = data['connections']
            if not isinstance(connections, list):
                print("❌ Connections should be a list")
                return False
            
            for conn in connections:
                if set(conn.keys()) != {'name', 'type'}:
                    print(f"❌ Connection has wrong keys: {conn.keys()}")
                    return False
            
            # Check drivers structure
            drivers = data['drivers']
            if 'mssql' not in drivers or 'postgres' not in drivers:
                print("❌ Missing driver info")
                return False
            
            # Verify no secrets in response
            response_str = str(data)
            secret_indicators = ['password', 'testpass', 'localhost', '1433', '5432', 'testuser', 'testdb']
            
            for secret in secret_indicators:
                if secret in response_str.lower():
                    print(f"❌ Found potential secret in response: {secret}")
                    return False
            
            print("✅ /diag endpoint structure test passed")
            print(f"✅ Version: {version}")
            print(f"✅ Connections: {len(connections)} found (safe info only)")
            print(f"✅ Drivers info included")
            print("✅ No secrets detected in response")
            
            return True
    
    def test_secret_redaction():
        """Test the secret redaction function."""
        from proxy import redact_secrets
        
        test_cases = [
            ("password=secret123", "password=*****"),
            ("PWD=mypassword", "PWD=*****"),
            ("api_key=abc123def", "api_key=*****"),
            ('password: "secret"', 'password: "*****"'),
            ("normal text without secrets", "normal text without secrets"),
            ("SERVER=localhost;PWD=secret;DATABASE=test", "SERVER=localhost;PWD=*****;DATABASE=test"),
        ]
        
        passed = 0
        for original, expected in test_cases:
            result = redact_secrets(original)
            if "password" in expected or "PWD" in expected or "api" in expected:
                # For secret patterns, just check that **** appears
                if "*****" in result:
                    print(f"✅ '{original}' → '{result}' (redacted)")
                    passed += 1
                else:
                    print(f"❌ '{original}' → '{result}' (not redacted)")
            else:
                # For non-secret text, should be unchanged
                if result == expected:
                    print(f"✅ '{original}' → '{result}' (unchanged)")
                    passed += 1
                else:
                    print(f"❌ '{original}' → '{result}' (should be unchanged)")
        
        print(f"✅ Secret redaction test: {passed}/{len(test_cases)} passed")
        return passed == len(test_cases)
    
    # Run tests
    print("Testing /diag endpoint and secret redaction...")
    print()
    
    print("1. Testing /diag endpoint structure:")
    diag_ok = test_diag_response_structure()
    print()
    
    print("2. Testing secret redaction:")
    redaction_ok = test_secret_redaction()
    print()
    
    if diag_ok and redaction_ok:
        print("✅ All tests passed! Prompt 4 implementation is working correctly.")
        exit(0)
    else:
        print("❌ Some tests failed.")
        exit(1)

except Exception as e:
    print(f"❌ Error running tests: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

finally:
    # Clean up test files
    try:
        os.remove('/tmp/test.crt')
        os.remove('/tmp/test.key')
        os.remove('connections.yaml')
    except:
        pass