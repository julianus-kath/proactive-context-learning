"""
Query Safety Demo - Demonstrates Phase 2 Implementation

This script demonstrates the complete query safety pipeline:
1. Query Validation - Ensures only safe, read-only queries
2. Query Execution - Executes validated queries with timeout
3. Result Formatting - Formats results for LLM consumption

Usage:
    python examples/query_safety_demo.py
"""

import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from app.db.query_validator import validate_query, is_read_only
from app.db.query_executor import QueryExecutor, execute_safe_query
from unittest.mock import Mock


def demo_validation():
    """Demonstrate query validation."""
    print("=" * 80)
    print("DEMO 1: Query Validation")
    print("=" * 80)
    print()
    
    # Test cases
    test_queries = [
        ("SELECT * FROM customers LIMIT 10", "Valid SELECT query"),
        ("SELECT COUNT(*) FROM orders WHERE status = 'pending'", "Valid aggregate query"),
        ("DELETE FROM customers WHERE id = 1", "Invalid: DELETE statement"),
        ("SELECT * FROM users; DROP TABLE users;", "Invalid: SQL injection attempt"),
        ("SELECT * FROM products", "Valid but missing LIMIT (will be auto-added)"),
    ]
    
    for query, description in test_queries:
        print(f"Query: {query}")
        print(f"Description: {description}")
        
        # Validate
        result = validate_query(query)
        
        if result.is_valid:
            print(f"✅ VALID")
            print(f"   Sanitized: {result.sanitized_query}")
            if result.warnings:
                print(f"   Warnings: {', '.join(result.warnings)}")
        else:
            print(f"❌ INVALID")
            print(f"   Error: {result.error}")
        
        print()


def demo_quick_check():
    """Demonstrate quick read-only check."""
    print("=" * 80)
    print("DEMO 2: Quick Read-Only Check")
    print("=" * 80)
    print()
    
    queries = [
        "SELECT * FROM customers",
        "INSERT INTO customers VALUES (1, 'test')",
        "UPDATE customers SET name = 'test'",
        "WITH cte AS (SELECT * FROM orders) SELECT * FROM cte",
    ]
    
    for query in queries:
        is_safe = is_read_only(query)
        status = "✅ READ-ONLY" if is_safe else "❌ NOT READ-ONLY"
        print(f"{status}: {query}")
    
    print()


def demo_execution():
    """Demonstrate query execution with mock database."""
    print("=" * 80)
    print("DEMO 3: Safe Query Execution")
    print("=" * 80)
    print()
    
    # Create mock database client
    mock_db = Mock()
    mock_db.query.return_value = (
        ['id', 'name', 'email', 'status'],
        [
            [1, 'Alice Johnson', 'alice@example.com', 'active'],
            [2, 'Bob Smith', 'bob@example.com', 'active'],
            [3, 'Charlie Brown', 'charlie@example.com', 'inactive'],
        ]
    )
    
    # Execute safe query
    print("Executing: SELECT * FROM customers WHERE status = 'active' LIMIT 10")
    result = execute_safe_query(
        mock_db,
        "SELECT * FROM customers WHERE status = 'active' LIMIT 10"
    )
    
    if result.success:
        print(f"✅ Query executed successfully")
        print(f"   Rows returned: {result.row_count}")
        print(f"   Execution time: {result.execution_time_ms:.2f}ms")
        print()
        print("Formatted Results:")
        print("-" * 80)
        print(result.formatted_result)
    else:
        print(f"❌ Query failed: {result.error}")
    
    print()


def demo_execution_with_validation_failure():
    """Demonstrate execution with validation failure."""
    print("=" * 80)
    print("DEMO 4: Execution with Validation Failure")
    print("=" * 80)
    print()
    
    # Create mock database client (won't be called)
    mock_db = Mock()
    
    # Try to execute dangerous query
    print("Attempting: DELETE FROM customers WHERE id = 1")
    result = execute_safe_query(mock_db, "DELETE FROM customers WHERE id = 1")
    
    if result.success:
        print(f"✅ Query executed (this shouldn't happen!)")
    else:
        print(f"❌ Query blocked by validator")
        print(f"   Status: {result.status.value}")
        print(f"   Error: {result.error}")
        print(f"   Database was never called: {not mock_db.query.called}")
    
    print()


def demo_custom_executor():
    """Demonstrate custom executor configuration."""
    print("=" * 80)
    print("DEMO 5: Custom Executor Configuration")
    print("=" * 80)
    print()
    
    # Create mock database with large result set
    mock_db = Mock()
    mock_db.query.return_value = (
        ['id', 'value'],
        [[i, f'value_{i}'] for i in range(150)]
    )
    
    # Create executor with custom settings
    executor = QueryExecutor(
        max_rows=500,
        timeout_seconds=60,
        format_results=True
    )
    
    print("Custom Executor Settings:")
    print(f"  - Max rows: 500")
    print(f"  - Timeout: 60 seconds")
    print(f"  - Format results: True")
    print()
    
    print("Executing: SELECT * FROM large_table")
    result = executor.execute(mock_db, "SELECT * FROM large_table")
    
    if result.success:
        print(f"✅ Query executed successfully")
        print(f"   Rows returned: {result.row_count}")
        print(f"   Formatted output length: {len(result.formatted_result)} characters")
        print()
        print("First 500 characters of formatted output:")
        print("-" * 80)
        print(result.formatted_result[:500])
        print("...")
    
    print()


def main():
    """Run all demos."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "QUERY SAFETY SYSTEM DEMO" + " " * 34 + "║")
    print("║" + " " * 25 + "Phase 2 Complete" + " " * 37 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    demo_validation()
    demo_quick_check()
    demo_execution()
    demo_execution_with_validation_failure()
    demo_custom_executor()
    
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("Key Features Demonstrated:")
    print("  ✅ Query validation with multiple security layers")
    print("  ✅ SQL injection prevention")
    print("  ✅ Read-only enforcement")
    print("  ✅ Automatic row limit enforcement")
    print("  ✅ Safe query execution with timeout")
    print("  ✅ Result formatting for LLM consumption")
    print("  ✅ Comprehensive error handling")
    print()


if __name__ == "__main__":
    main()