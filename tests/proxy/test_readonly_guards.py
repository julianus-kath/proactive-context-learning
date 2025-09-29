#!/usr/bin/env python3
"""
Test script for enhanced read-only guards and query validation.
Tests the validate_read_only_query and apply_query_limit functions.
"""

import sys
import os

# Add the current directory to Python path to import proxy functions
sys.path.insert(0, os.path.dirname(__file__))

from proxy import validate_read_only_query, apply_query_limit

def test_read_only_validation():
    """Test the enhanced read-only query validation."""
    print("Testing Read-Only Query Validation")
    print("=" * 40)
    
    # Valid SELECT queries
    valid_queries = [
        "SELECT 1",
        "  SELECT * FROM users  ",
        "select name from sys.databases",
        "SELECT TOP 10 * FROM table WHERE id > 5",
        "SELECT a.name, b.value FROM table_a a JOIN table_b b ON a.id = b.id",
        "SELECT COUNT(*) FROM users WHERE active = 1",
        "SELECT * FROM table; -- comment only",
    ]
    
    print("\n✅ Valid SELECT queries:")
    for sql in valid_queries:
        try:
            validate_read_only_query(sql)
            print(f"  ✓ {sql.strip()}")
        except ValueError as e:
            print(f"  ❌ {sql.strip()} - {e}")
    
    # Invalid queries
    invalid_queries = [
        ("", "Empty query"),
        ("INSERT INTO users VALUES (1, 'test')", "INSERT statement"),
        ("UPDATE users SET name = 'test'", "UPDATE statement"),
        ("DELETE FROM users WHERE id = 1", "DELETE statement"),
        ("CREATE TABLE test (id INT)", "CREATE statement"),
        ("DROP TABLE users", "DROP statement"),
        ("SELECT 1; SELECT 2", "Multiple statements"),
        ("SELECT * FROM users; INSERT INTO log VALUES (1)", "SELECT + INSERT"),
        ("SELECT 1; DROP TABLE users", "SELECT + DROP"),
        ("  ; SELECT 1", "Leading semicolon"),
    ]
    
    print("\n❌ Invalid queries (should fail):")
    for sql, reason in invalid_queries:
        try:
            validate_read_only_query(sql)
            print(f"  ❌ FAILED TO REJECT: {sql} ({reason})")
        except ValueError as e:
            print(f"  ✓ Correctly rejected: {sql} - {e}")

def test_query_limits():
    """Test the server-side query limit application."""
    print("\n\nTesting Server-Side Query Limits")
    print("=" * 40)
    
    # Test MSSQL limits
    print("\n📊 MSSQL Limit Tests:")
    mssql_tests = [
        ("SELECT * FROM users", "SELECT TOP 100 * FROM users"),
        ("SELECT name FROM table", "SELECT TOP 100 name FROM table"),
        ("  SELECT  id, name FROM users  ", "  SELECT  TOP 100 id, name FROM users  "),
        ("SELECT TOP 50 * FROM users", "SELECT TOP 50 * FROM users"),  # Already has limit
        ("select count(*) from table", "select TOP 100 count(*) from table"),
    ]
    
    for original, expected in mssql_tests:
        result = apply_query_limit(original, 100, 'mssql')
        if result == expected:
            print(f"  ✓ {original.strip()} → {result}")
        else:
            print(f"  ❌ {original.strip()}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {result}")
    
    # Test PostgreSQL limits
    print("\n🐘 PostgreSQL Limit Tests:")
    postgres_tests = [
        ("SELECT * FROM users", "SELECT * FROM users LIMIT 100"),
        ("SELECT name FROM table", "SELECT name FROM table LIMIT 100"),
        ("SELECT * FROM users;", "SELECT * FROM users LIMIT 100"),  # Remove trailing semicolon
        ("SELECT * FROM users LIMIT 50", "SELECT * FROM users LIMIT 50"),  # Already has limit
        ("select count(*) from table", "select count(*) from table LIMIT 100"),
    ]
    
    for original, expected in postgres_tests:
        result = apply_query_limit(original, 100, 'postgres')
        if result == expected:
            print(f"  ✓ {original.strip()} → {result}")
        else:
            print(f"  ❌ {original.strip()}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {result}")

def main():
    print("Enhanced SQL Proxy - Read-Only Guards Test")
    print("=" * 50)
    
    test_read_only_validation()
    test_query_limits()
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    main()