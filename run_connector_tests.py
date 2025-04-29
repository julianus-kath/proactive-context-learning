#!/usr/bin/env python
"""
Script to run all connector tests.
"""
import sys
import subprocess
import os

def run_tests():
    """Run all connector tests."""
    print("\n=== Running Connector Tests ===\n")
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the test files
    test_files = [
        os.path.join(script_dir, "tests/test_erp_connector.py"),
        os.path.join(script_dir, "tests/test_document_storage_connector.py"),
        os.path.join(script_dir, "tests/test_knowledge_graph_connector.py"),
        os.path.join(script_dir, "tests/test_integrated_connectors.py")
    ]
    
    # Run each test file
    for test_file in test_files:
        print(f"\n--- Running {os.path.basename(test_file)} ---\n")
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
        else:
            print(f"Test {os.path.basename(test_file)} PASSED")
    
    print("\n=== All Tests Completed ===\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())