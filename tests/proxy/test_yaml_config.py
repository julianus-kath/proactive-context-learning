#!/usr/bin/env python3
"""
Test script to validate YAML configuration loading for proxy.py
This helps debug configuration issues before starting the full proxy.
"""

import os
import sys
import yaml
import string

def expand_env_vars(text):
    """Expand ${VAR} environment variables in text."""
    if not isinstance(text, str):
        return text
    
    template = string.Template(text)
    try:
        return template.substitute(os.environ)
    except KeyError as e:
        raise RuntimeError(f"Environment variable not found: {e}")

def test_yaml_config():
    """Test loading and validating the connections.yaml configuration."""
    
    print("Testing YAML Configuration Loading")
    print("=" * 40)
    
    # Set test environment variables
    os.environ['SQLSERVER_PASSWORD'] = 'test-sql-password'
    os.environ['PG_PASSWORD'] = 'test-pg-password'
    
    config_path = os.path.join(os.path.dirname(__file__), 'connections.yaml')
    
    print(f"Looking for config at: {config_path}")
    
    if not os.path.exists(config_path):
        print(f"❌ connections.yaml not found at: {config_path}")
        return False
    
    print("✅ connections.yaml found")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✅ YAML parsed successfully")
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML: {e}")
        return False
    
    if not config or 'connections' not in config:
        print("❌ YAML must contain a 'connections' section")
        return False
    
    print("✅ 'connections' section found")
    
    connections = {}
    for name, conn_config in config['connections'].items():
        print(f"\n📋 Processing connection: {name}")
        
        # Validate required fields
        if 'type' not in conn_config:
            print(f"❌ Connection '{name}' missing required 'type' field")
            return False
        
        print(f"   Type: {conn_config['type']}")
        
        # Expand environment variables
        try:
            expanded_config = {}
            for key, value in conn_config.items():
                expanded_config[key] = expand_env_vars(value)
            print(f"✅ Environment variables expanded successfully")
        except RuntimeError as e:
            print(f"❌ Environment variable expansion failed: {e}")
            return False
        
        # Validate type-specific requirements
        conn_type = expanded_config['type']
        if conn_type == 'mssql':
            required_fields = ['host', 'port', 'database', 'user', 'password']
            for field in required_fields:
                if field not in expanded_config:
                    print(f"❌ MSSQL connection '{name}' missing required field: {field}")
                    return False
            print(f"✅ All required MSSQL fields present")
        elif conn_type == 'postgres':
            required_fields = ['host', 'port', 'database', 'user', 'password']
            for field in required_fields:
                if field not in expanded_config:
                    print(f"❌ PostgreSQL connection '{name}' missing required field: {field}")
                    return False
            print(f"✅ All required PostgreSQL fields present")
        else:
            print(f"❌ Unsupported connection type '{conn_type}' for connection '{name}'")
            return False
        
        # Show redacted config
        redacted_config = expanded_config.copy()
        if 'password' in redacted_config:
            redacted_config['password'] = "*****"
        print(f"   Config: {redacted_config}")
        
        connections[name] = expanded_config
    
    print(f"\n🎉 Configuration validation successful!")
    print(f"   Found {len(connections)} connections: {list(connections.keys())}")
    
    return True

if __name__ == "__main__":
    success = test_yaml_config()
    sys.exit(0 if success else 1)