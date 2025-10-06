"""
Test script for connecting to actual database through Windows proxy.

This script tests the complete Phase 2 implementation with a real database:
1. Proxy connection health check
2. Schema discovery
3. Query validation
4. Safe query execution
5. Result formatting

Prerequisites:
- Windows proxy.py running on VPN-connected machine
- .env file configured with PROXY_BASE_URL and PROXY_API_KEY
- Database connection configured in connections.yaml on Windows
"""

import os
import sys
import logging
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.client import DatabaseClient
from app.db.query_validator import validate_query
from app.db.query_executor import execute_safe_query, QueryExecutor
from app.db.schema_cache import SchemaCache
from app.db.table_selector import TableSelector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")


def print_info(message: str):
    """Print an info message."""
    print(f"ℹ️  {message}")


def test_environment_config():
    """Test 1: Verify environment configuration."""
    print_section("Test 1: Environment Configuration")
    
    required_vars = {
        'DB_MODE': os.getenv('DB_MODE'),
        'PROXY_BASE_URL': os.getenv('PROXY_BASE_URL'),
        'PROXY_API_KEY': os.getenv('PROXY_API_KEY'),
    }
    
    optional_vars = {
        'PROXY_DEFAULT_CONN': os.getenv('PROXY_DEFAULT_CONN'),
        'PROXY_TLS_VERIFY': os.getenv('PROXY_TLS_VERIFY', 'true'),
        'PROXY_CA_BUNDLE': os.getenv('PROXY_CA_BUNDLE'),
        'PROXY_TIMEOUT': os.getenv('PROXY_TIMEOUT', '30'),
    }
    
    all_configured = True
    
    print("Required Configuration:")
    for key, value in required_vars.items():
        if value:
            # Redact sensitive values
            display_value = value if key != 'PROXY_API_KEY' else '*' * 20
            print_success(f"{key} = {display_value}")
        else:
            print_error(f"{key} is not set")
            all_configured = False
    
    print("\nOptional Configuration:")
    for key, value in optional_vars.items():
        display_value = value if value else "(not set)"
        print_info(f"{key} = {display_value}")
    
    if all_configured:
        print_success("\nAll required environment variables are configured!")
        return True
    else:
        print_error("\nSome required environment variables are missing!")
        print_info("Please configure your .env file based on .env.template")
        return False


def test_proxy_health():
    """Test 2: Check proxy health and available connections."""
    print_section("Test 2: Proxy Health Check")
    
    try:
        client = DatabaseClient()
        print_info(f"Database client initialized in {client.mode} mode")
        print_info(f"Proxy URL: {client.base_url}")
        
        # Health check
        print("\nChecking proxy health...")
        is_healthy = client.health_check()
        
        if is_healthy:
            print_success("Proxy is healthy and responding!")
        else:
            print_error("Proxy health check failed!")
            return False
        
        # Get available connections
        print("\nFetching available connections...")
        connections = client.get_available_connections()
        
        if connections:
            print_success(f"Found {len(connections)} available connection(s):")
            for conn in connections:
                print(f"  - {conn.get('name', 'unknown')} ({conn.get('type', 'unknown')})")
        else:
            print_error("No connections available!")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Proxy health check failed: {e}")
        logger.exception("Proxy health check error")
        return False


def test_simple_query():
    """Test 3: Execute a simple query."""
    print_section("Test 3: Simple Query Execution")
    
    try:
        client = DatabaseClient()
        
        # Try a simple query (adjust based on your database)
        test_queries = [
            "SELECT 1 AS test_value",
            "SELECT GETDATE() AS current_time",  # SQL Server
            "SELECT NOW() AS current_time",       # PostgreSQL
        ]
        
        for sql in test_queries:
            print(f"\nTrying query: {sql}")
            try:
                columns, rows = client.query(sql, limit=1, timeout_s=10)
                print_success(f"Query successful!")
                print(f"  Columns: {columns}")
                print(f"  Rows: {rows}")
                return True
            except Exception as e:
                print_info(f"Query failed (trying next): {e}")
                continue
        
        print_error("All test queries failed!")
        return False
        
    except Exception as e:
        print_error(f"Simple query test failed: {e}")
        logger.exception("Simple query error")
        return False


def test_schema_discovery():
    """Test 4: Discover database schema."""
    print_section("Test 4: Schema Discovery")
    
    try:
        client = DatabaseClient()
        cache = SchemaCache(client)
        
        print("Fetching database schema...")
        schema = cache.get_schema()
        
        if schema:
            print_success(f"Schema discovered! Found {len(schema)} tables:")
            
            # Show first 10 tables
            for i, (table_name, columns) in enumerate(list(schema.items())[:10]):
                print(f"\n  Table: {table_name}")
                print(f"    Columns: {', '.join(columns[:5])}")
                if len(columns) > 5:
                    print(f"    ... and {len(columns) - 5} more columns")
            
            if len(schema) > 10:
                print(f"\n  ... and {len(schema) - 10} more tables")
            
            return True
        else:
            print_error("No schema found!")
            return False
        
    except Exception as e:
        print_error(f"Schema discovery failed: {e}")
        logger.exception("Schema discovery error")
        return False


def test_query_validation():
    """Test 5: Test query validation."""
    print_section("Test 5: Query Validation")
    
    test_cases = [
        ("SELECT * FROM customers LIMIT 10", True, "Valid SELECT query"),
        ("SELECT id, name FROM products WHERE active = 1", True, "Valid filtered query"),
        ("DELETE FROM customers WHERE id = 1", False, "Dangerous DELETE statement"),
        ("SELECT * FROM users; DROP TABLE users;", False, "SQL injection attempt"),
        ("SELECT * FROM orders -- comment", False, "Comment injection"),
    ]
    
    all_passed = True
    
    for sql, should_pass, description in test_cases:
        print(f"\nTest: {description}")
        print(f"  Query: {sql}")
        
        result = validate_query(sql)
        
        if result.is_valid == should_pass:
            print_success(f"Validation correct: {'PASS' if should_pass else 'BLOCKED'}")
            if result.is_valid:
                print(f"    Sanitized: {result.sanitized_query}")
        else:
            print_error(f"Validation incorrect! Expected {'PASS' if should_pass else 'BLOCKED'}, got {'PASS' if result.is_valid else 'BLOCKED'}")
            if not result.is_valid:
                print(f"    Error: {result.error}")
            all_passed = False
    
    return all_passed


def test_safe_execution():
    """Test 6: Execute safe queries with validation."""
    print_section("Test 6: Safe Query Execution")
    
    try:
        client = DatabaseClient()
        
        # First, get schema to find a real table
        print("Discovering schema to find a table...")
        cache = SchemaCache(client)
        schema = cache.get_schema()
        
        if not schema:
            print_error("No schema available for testing!")
            return False
        
        # Get first table
        table_name = list(schema.keys())[0]
        print_success(f"Using table: {table_name}")
        
        # Execute safe query
        sql = f"SELECT * FROM {table_name}"
        print(f"\nExecuting query: {sql}")
        
        result = execute_safe_query(
            client,
            sql,
            max_rows=10,
            timeout_seconds=30
        )
        
        if result.success:
            print_success("Query executed successfully!")
            print(f"  Status: {result.status.value}")
            print(f"  Rows returned: {result.row_count}")
            print(f"  Execution time: {result.execution_time_ms}ms")
            print(f"\nFormatted result (first 500 chars):")
            print(result.formatted_result[:500])
            if len(result.formatted_result) > 500:
                print("  ... (truncated)")
            return True
        else:
            print_error(f"Query execution failed: {result.error}")
            return False
        
    except Exception as e:
        print_error(f"Safe execution test failed: {e}")
        logger.exception("Safe execution error")
        return False


def test_table_selection():
    """Test 7: Test intelligent table selection."""
    print_section("Test 7: Intelligent Table Selection")
    
    try:
        client = DatabaseClient()
        cache = SchemaCache(client)
        selector = TableSelector(cache)
        
        test_queries = [
            "Show me all customers",
            "What are the recent orders?",
            "List all products",
            "Show me sales data",
        ]
        
        for query in test_queries:
            print(f"\nUser query: '{query}'")
            tables = selector.select_relevant_tables(query, top_k=3)
            
            if tables:
                print_success(f"Selected {len(tables)} relevant table(s):")
                for table in tables:
                    print(f"  - {table}")
            else:
                print_info("No specific tables selected (will use all)")
        
        return True
        
    except Exception as e:
        print_error(f"Table selection test failed: {e}")
        logger.exception("Table selection error")
        return False


def test_end_to_end():
    """Test 8: Complete end-to-end workflow."""
    print_section("Test 8: End-to-End Workflow")
    
    try:
        # Initialize components
        client = DatabaseClient()
        cache = SchemaCache(client)
        selector = TableSelector(cache)
        executor = QueryExecutor(max_rows=10, timeout_seconds=30)
        
        # Simulate user query
        user_query = "Show me the first 5 records from any table"
        print(f"User query: '{user_query}'")
        
        # Step 1: Get schema
        print("\n1. Discovering schema...")
        schema = cache.get_schema()
        print_success(f"Found {len(schema)} tables")
        
        # Step 2: Select relevant tables
        print("\n2. Selecting relevant tables...")
        tables = selector.select_relevant_tables(user_query, top_k=1)
        if not tables:
            tables = [list(schema.keys())[0]]
        print_success(f"Selected table: {tables[0]}")
        
        # Step 3: Generate SQL
        print("\n3. Generating SQL query...")
        sql = f"SELECT * FROM {tables[0]}"
        print_info(f"SQL: {sql}")
        
        # Step 4: Validate query
        print("\n4. Validating query...")
        validation = validate_query(sql)
        if validation.is_valid:
            print_success("Query is valid and safe")
        else:
            print_error(f"Query validation failed: {validation.error}")
            return False
        
        # Step 5: Execute query
        print("\n5. Executing query...")
        result = executor.execute(client, validation.sanitized_query)
        
        if result.success:
            print_success("Query executed successfully!")
            print(f"  Rows: {result.row_count}")
            print(f"  Time: {result.execution_time_ms}ms")
            print(f"\nResult preview:")
            print(result.formatted_result[:300])
            return True
        else:
            print_error(f"Execution failed: {result.error}")
            return False
        
    except Exception as e:
        print_error(f"End-to-end test failed: {e}")
        logger.exception("End-to-end error")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  PHASE 2 - PROXY CONNECTION TEST SUITE")
    print("  Testing Query Safety & Validation with Real Database")
    print("=" * 80)
    
    tests = [
        ("Environment Configuration", test_environment_config),
        ("Proxy Health Check", test_proxy_health),
        ("Simple Query", test_simple_query),
        ("Schema Discovery", test_schema_discovery),
        ("Query Validation", test_query_validation),
        ("Safe Execution", test_safe_execution),
        ("Table Selection", test_table_selection),
        ("End-to-End Workflow", test_end_to_end),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            logger.exception(f"Test {test_name} crashed")
            results[test_name] = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print(f"\n{'=' * 80}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'=' * 80}\n")
    
    if passed == total:
        print_success("🎉 All tests passed! Phase 2 is working with real database!")
        return 0
    else:
        print_error(f"⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())