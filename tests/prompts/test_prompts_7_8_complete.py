#!/usr/bin/env python3
"""
Complete Test Suite for Prompts 7 & 8
Combines end-to-end testing with safety & operability validation
"""

import os
import sys
import subprocess
import time

def run_test_script(script_name, description):
    """Run a test script and return success status"""
    print(f"\n{'='*60}")
    print(f"🧪 Running {description}")
    print(f"{'='*60}")
    
    try:
        # Run the test script
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              cwd=os.path.dirname(os.path.abspath(__file__)))
        
        success = result.returncode == 0
        
        if success:
            print(f"✅ {description} COMPLETED SUCCESSFULLY")
        else:
            print(f"❌ {description} FAILED (exit code: {result.returncode})")
        
        return success
        
    except Exception as e:
        print(f"❌ {description} CRASHED: {e}")
        return False

def check_environment():
    """Check that required environment variables are set"""
    print("🔍 Checking Environment Configuration")
    print("=" * 40)
    
    required_vars = [
        "PROXY_BASE_URL",
        "PROXY_API_KEY"
    ]
    
    optional_vars = [
        "PROXY_CA_BUNDLE",
        "PROXY_DEFAULT_CONN",
        "PROXY_TIMEOUT",
        "PROXY_MAX_RETRIES"
    ]
    
    missing_required = []
    
    print("Required Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            display_value = "*****" if "KEY" in var or "PASSWORD" in var else value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: NOT SET")
            missing_required.append(var)
    
    print("\nOptional Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            display_value = "*****" if "KEY" in var or "PASSWORD" in var else value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ⚪ {var}: not set (using default)")
    
    if missing_required:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_required)}")
        print("\nPlease set the required variables and try again.")
        print("Example:")
        print("  export PROXY_BASE_URL=https://10.255.152.48:5000")
        print("  export PROXY_API_KEY=your_api_key_here")
        return False
    
    print("\n✅ Environment configuration looks good!")
    return True

def check_dependencies():
    """Check that required Python packages are installed"""
    print("\n🔍 Checking Python Dependencies")
    print("=" * 40)
    
    required_packages = [
        ("requests", "HTTP client for proxy communication"),
        ("flask", "Web framework (for proxy server)"),
        ("yaml", "YAML configuration parsing"),
        ("pyodbc", "ODBC database connectivity"),
    ]
    
    optional_packages = [
        ("psycopg2", "PostgreSQL connectivity"),
        ("flask_limiter", "Rate limiting (Prompt 8)"),
    ]
    
    missing_required = []
    
    print("Required Packages:")
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}: installed ({description})")
        except ImportError:
            print(f"  ❌ {package}: NOT INSTALLED ({description})")
            missing_required.append(package)
    
    print("\nOptional Packages:")
    for package, description in optional_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}: installed ({description})")
        except ImportError:
            print(f"  ⚪ {package}: not installed ({description})")
    
    if missing_required:
        print(f"\n❌ Missing required packages: {', '.join(missing_required)}")
        print("\nInstall missing packages:")
        print("  pip install requests flask pyyaml pyodbc")
        return False
    
    print("\n✅ Dependencies look good!")
    return True

def main():
    """Run complete test suite for Prompts 7 & 8"""
    print("🚀 SQL Proxy Complete Test Suite")
    print("Prompts 7 & 8: End-to-End Testing + Safety & Operability")
    print("=" * 70)
    
    start_time = time.time()
    
    # Pre-flight checks
    print("🔧 Pre-flight Checks")
    print("-" * 20)
    
    if not check_environment():
        print("\n❌ Environment check failed. Please fix configuration and try again.")
        return 1
    
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please install missing packages and try again.")
        return 1
    
    print("\n✅ Pre-flight checks passed!")
    
    # Test execution
    print("\n🧪 Test Execution")
    print("-" * 20)
    
    tests = [
        ("test_prompt7_e2e.py", "Prompt 7: End-to-End Testing"),
        ("test_prompt8_safety.py", "Prompt 8: Safety & Operability")
    ]
    
    results = []
    for script, description in tests:
        success = run_test_script(script, description)
        results.append((description, success))
        
        # Brief pause between test suites
        if script != tests[-1][0]:  # Not the last test
            print(f"\n⏸️  Pausing 2 seconds before next test suite...")
            time.sleep(2)
    
    # Final summary
    elapsed = int(time.time() - start_time)
    
    print(f"\n{'='*70}")
    print("🏁 FINAL TEST SUMMARY")
    print(f"{'='*70}")
    
    passed = 0
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {description}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall Results: {passed}/{len(results)} test suites passed")
    print(f"Total execution time: {elapsed} seconds")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Prompt 7: End-to-end functionality verified")
        print("✅ Prompt 8: Safety and operability features working")
        print("\n🚀 SQL Proxy is ready for production deployment!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test suite(s) failed")
        print("❌ Please review the failed tests and fix issues before deployment")
        print("\n🔧 Troubleshooting tips:")
        print("  1. Check proxy server is running on Windows")
        print("  2. Verify network connectivity to proxy")
        print("  3. Confirm API key and certificates are correct")
        print("  4. Review proxy server logs for errors")
        return 1

if __name__ == "__main__":
    sys.exit(main())