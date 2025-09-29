#!/usr/bin/env python3
"""
Simple test for secret redaction patterns.
"""

import re

def test_redact_secrets(text):
    """Test version of redact_secrets function."""
    if not isinstance(text, str):
        return str(text)
    
    # Redact connection string passwords first (most specific)
    text = re.sub(r'(PWD=)([^;]+)', r'\1*****', text, flags=re.IGNORECASE)
    
    # Redact password-like patterns with quotes (handle each quote type separately)
    text = re.sub(r'(password\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(password\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(pwd\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(pwd\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(api[_-]?key\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(api[_-]?key\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    
    # Redact password-like patterns without quotes (avoid already redacted ones)
    text = re.sub(r'(password\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    text = re.sub(r'(pwd\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    text = re.sub(r'(api[_-]?key\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    
    return text

def main():
    test_cases = [
        ("password=secret123", "password=*****"),
        ("PWD=mypassword", "PWD=*****"),
        ("api_key=abc123def", "api_key=*****"),
        ('password: "secret"', 'password: "*****"'),
        ('pwd="test123"', 'pwd="*****"'),
        ("normal text without secrets", "normal text without secrets"),
        ("SERVER=localhost;PWD=secret;DATABASE=test", "SERVER=localhost;PWD=*****;DATABASE=test"),
    ]
    
    print("Testing secret redaction patterns:")
    all_passed = True
    
    for original, expected in test_cases:
        result = test_redact_secrets(original)
        if result == expected:
            print(f"  ✅ '{original}' → '{result}'")
        else:
            print(f"  ❌ '{original}' → '{result}' (expected: '{expected}')")
            all_passed = False
    
    if all_passed:
        print("✅ All secret redaction tests passed")
        return 0
    else:
        print("❌ Some secret redaction tests failed")
        return 1

if __name__ == "__main__":
    exit(main())