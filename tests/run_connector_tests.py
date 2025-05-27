#!/usr/bin/env python
"""
Script to run all connector tests.
"""
import sys
import subprocess
import os

def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = ["pandas", "pyyaml", "requests", "pymongo"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("\n=== Missing Dependencies ===")
        print("The following packages are required but not installed:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nYou can install them with:")
        print(f"pip install {' '.join(missing_packages)}")
        print("\nRunning tests anyway, but some tests may be skipped...\n")
    
    return len(missing_packages) == 0

def run_tests():
    """Run all connector tests."""
    print("\n=== Running Connector Tests ===\n")
    
    # Check dependencies
    all_deps_installed = check_dependencies()
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the test files
    test_files = [
        os.path.join(script_dir, "tests/test_erp_connector.py"),
        os.path.join(script_dir, "tests/test_document_storage_connector.py"),
        os.path.join(script_dir, "tests/test_knowledge_graph_connector.py"),
        os.path.join(script_dir, "tests/test_simple_integration.py"),
        os.path.join(script_dir, "tests/test_integrated_connectors.py")
    ]
    
    # Run each test file
    all_passed = True
    for test_file in test_files:
        print(f"\n--- Running {os.path.basename(test_file)} ---\n")
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v"],
                cwd=script_dir,
                capture_output=True,
                text=True
            )
            
            # Print the output
            print(result.stdout)
            
            # Print any errors
            if result.stderr:
                print("ERRORS:")
                print(result.stderr)
            
            # Check if the test passed
            if result.returncode != 0:
                print(f"Test {os.path.basename(test_file)} FAILED with return code {result.returncode}")
                all_passed = False
            else:
                print(f"Test {os.path.basename(test_file)} PASSED")
        except Exception as e:
            print(f"Error running test {os.path.basename(test_file)}: {e}")
            all_passed = False
    
    print("\n=== All Tests Completed ===\n")
    
    if not all_deps_installed:
        print("Note: Some dependencies were missing. Install them for full test coverage.")
    
    if all_passed:
        print("All tests passed successfully!")
        return 0
    else:
        print("Some tests failed. See output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())