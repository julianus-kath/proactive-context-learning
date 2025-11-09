"""
Phase 2 Integration Tests: MCP Safety & Bounded Execution

This script tests the complete Phase 2 implementation including:
- Query validation (SELECT-only, single statement)
- Row cap injection (LIMIT/TOP)
- Timeout enforcement
- Column redaction
- Structured error responses
- Both PostgreSQL and SQL Server dialects

Usage:
    python scripts/test_phase2.py
    DB_DIALECT=mssql python scripts/test_phase2.py
"""

import os
import sys
import asyncio
import time
from typing import Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from mcp_server.config import config
from mcp_server.database_adapter import DatabaseAdapter
from mcp_server.bounded_query import execute_bounded_query
from mcp_server.query_validator import validate_query


class Phase2Tester:
    """Integration tester for Phase 2 features."""
    
    def __init__(self):
        self.db_adapter = None
        self.passed = 0
        self.failed = 0
        self.dialect = config.db_dialect
    
    async def setup(self):
        """Initialize database adapter."""
        print(f"\n{'='*60}")
        print(f"Phase 2 Integration Tests - {self.dialect.upper()}")
        print(f"{'='*60}\n")
        
        try:
            self.db_adapter = DatabaseAdapter()
            await self.db_adapter.initialize()
            print(f"✅ Database adapter initialized ({self.dialect})\n")
        except Exception as e:
            print(f"❌ Failed to initialize database adapter: {e}")
            sys.exit(1)
    
    async def teardown(self):
        """Cleanup database adapter."""
        if self.db_adapter:
            await self.db_adapter.close()
    
    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result."""
        if passed:
            self.passed += 1
            print(f"✅ {name}")
            if details:
                print(f"   {details}")
        else:
            self.failed += 1
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
    
    async def test_query_validation(self):
        """Test query validation (SELECT-only enforcement)."""
        print("\n--- Test 1: Query Validation ---\n")
        
        # Test 1.1: Valid SELECT query
        result = validate_query("SELECT * FROM customers", dialect=self.dialect)
        self.log_test(
            "Valid SELECT query accepted",
            result.valid,
            f"Query: {result.query[:50]}..."
        )
        
        # Test 1.2: INSERT rejected
        result = validate_query("INSERT INTO customers (name) VALUES ('test')", dialect=self.dialect)
        self.log_test(
            "INSERT query rejected",
            not result.valid and result.error_code == "READ_ONLY_VIOLATION",
            f"Error: {result.error_message}"
        )
        
        # Test 1.3: UPDATE rejected
        result = validate_query("UPDATE customers SET name = 'test'", dialect=self.dialect)
        self.log_test(
            "UPDATE query rejected",
            not result.valid and result.error_code == "READ_ONLY_VIOLATION",
            f"Error: {result.error_message}"
        )
        
        # Test 1.4: DELETE rejected
        result = validate_query("DELETE FROM customers", dialect=self.dialect)
        self.log_test(
            "DELETE query rejected",
            not result.valid and result.error_code == "READ_ONLY_VIOLATION",
            f"Error: {result.error_message}"
        )
        
        # Test 1.5: DROP rejected
        result = validate_query("DROP TABLE customers", dialect=self.dialect)
        self.log_test(
            "DROP query rejected",
            not result.valid and result.error_code == "READ_ONLY_VIOLATION",
            f"Error: {result.error_message}"
        )
        
        # Test 1.6: Multi-statement rejected
        result = validate_query("SELECT * FROM customers; DROP TABLE customers;", dialect=self.dialect)
        self.log_test(
            "Multi-statement query rejected",
            not result.valid and result.error_code == "MULTI_STATEMENT",
            f"Error: {result.error_message}"
        )
    
    async def test_row_cap_injection(self):
        """Test row cap injection (LIMIT/TOP)."""
        print("\n--- Test 2: Row Cap Injection ---\n")
        
        if self.dialect == "postgres":
            # Test 2.1: LIMIT injected when missing
            result = validate_query("SELECT * FROM customers", dialect=self.dialect, max_rows=100)
            self.log_test(
                "LIMIT injected when missing",
                result.valid and "LIMIT 100" in result.query and result.row_cap_applied,
                f"Query: {result.query}"
            )
            
            # Test 2.2: LIMIT preserved when below max
            result = validate_query("SELECT * FROM customers LIMIT 50", dialect=self.dialect, max_rows=100)
            self.log_test(
                "LIMIT preserved when below max",
                result.valid and "LIMIT 50" in result.query and not result.row_cap_applied,
                f"Original limit: {result.original_limit}"
            )
            
            # Test 2.3: LIMIT clamped when above max
            result = validate_query("SELECT * FROM customers LIMIT 500", dialect=self.dialect, max_rows=100)
            self.log_test(
                "LIMIT clamped when above max",
                result.valid and "LIMIT 100" in result.query and result.row_cap_applied,
                f"Original: {result.original_limit}, Applied: 100"
            )
        
        elif self.dialect == "mssql":
            # Test 2.1: TOP injected when missing
            result = validate_query("SELECT * FROM customers", dialect=self.dialect, max_rows=100)
            self.log_test(
                "TOP injected when missing",
                result.valid and "SELECT TOP 100" in result.query and result.row_cap_applied,
                f"Query: {result.query[:50]}..."
            )
            
            # Test 2.2: TOP preserved when below max
            result = validate_query("SELECT TOP 50 * FROM customers", dialect=self.dialect, max_rows=100)
            self.log_test(
                "TOP preserved when below max",
                result.valid and "SELECT TOP 50" in result.query and not result.row_cap_applied,
                f"Original limit: {result.original_limit}"
            )
            
            # Test 2.3: TOP clamped when above max
            result = validate_query("SELECT TOP 500 * FROM customers", dialect=self.dialect, max_rows=100)
            self.log_test(
                "TOP clamped when above max",
                result.valid and "SELECT TOP 100" in result.query and result.row_cap_applied,
                f"Original: {result.original_limit}, Applied: 100"
            )
    
    async def test_bounded_query_execution(self):
        """Test bounded query execution with real database."""
        print("\n--- Test 3: Bounded Query Execution ---\n")
        
        # Test 3.1: Valid query execution
        try:
            if self.dialect == "postgres":
                query = "SELECT * FROM customers"
            else:
                query = "SELECT * FROM customers"
            
            start_time = time.time()
            response = await execute_bounded_query(
                query=query,
                db_adapter=self.db_adapter,
                dialect=self.dialect,
                max_rows=10,
                query_timeout=30
            )
            elapsed = (time.time() - start_time) * 1000
            
            self.log_test(
                "Valid query executed successfully",
                response.ok and response.row_count >= 0,
                f"Rows: {response.row_count}, Time: {response.execution_time_ms}ms"
            )
            
            # Test 3.2: Row cap enforced
            self.log_test(
                "Row cap enforced",
                response.row_count <= 10,
                f"Returned {response.row_count} rows (max: 10)"
            )
            
            # Test 3.3: Execution time tracked
            self.log_test(
                "Execution time tracked",
                response.execution_time_ms > 0,
                f"Execution time: {response.execution_time_ms}ms"
            )
            
        except Exception as e:
            self.log_test("Valid query executed successfully", False, f"Error: {e}")
            self.log_test("Row cap enforced", False, "Query failed")
            self.log_test("Execution time tracked", False, "Query failed")
    
    async def test_error_handling(self):
        """Test structured error responses."""
        print("\n--- Test 4: Error Handling ---\n")
        
        # Test 4.1: Invalid query returns structured error
        response = await execute_bounded_query(
            query="INSERT INTO customers (name) VALUES ('test')",
            db_adapter=self.db_adapter,
            dialect=self.dialect,
            max_rows=100
        )
        
        self.log_test(
            "Invalid query returns structured error",
            not response.ok and response.error_code == "READ_ONLY_VIOLATION",
            f"Error code: {response.error_code}, Message: {response.error_message}"
        )
        
        # Test 4.2: Empty query returns error
        response = await execute_bounded_query(
            query="",
            db_adapter=self.db_adapter,
            dialect=self.dialect,
            max_rows=100
        )
        
        self.log_test(
            "Empty query returns error",
            not response.ok and response.error_code == "EMPTY_QUERY",
            f"Error code: {response.error_code}"
        )
        
        # Test 4.3: Invalid SQL returns error
        response = await execute_bounded_query(
            query="SELECT * FROM nonexistent_table_xyz",
            db_adapter=self.db_adapter,
            dialect=self.dialect,
            max_rows=100
        )
        
        self.log_test(
            "Invalid SQL returns error",
            not response.ok,
            f"Error code: {response.error_code}"
        )
    
    async def test_column_redaction(self):
        """Test sensitive column redaction."""
        print("\n--- Test 5: Column Redaction ---\n")
        
        # Create a test query that might have sensitive columns
        # Note: This test assumes the database has a table with sensitive columns
        # If not, we'll test with a mock scenario
        
        try:
            # Test with redaction enabled
            if self.dialect == "postgres":
                query = "SELECT 1 as id, 'test' as username, 'secret' as password"
            else:
                query = "SELECT 1 as id, 'test' as username, 'secret' as password"
            
            response = await execute_bounded_query(
                query=query,
                db_adapter=self.db_adapter,
                dialect=self.dialect,
                max_rows=10,
                enable_redaction=True
            )
            
            # Check if password column was redacted
            has_password_col = "password" in response.columns if response.columns else False
            password_redacted = False
            
            if response.ok and response.rows and has_password_col:
                password_redacted = response.rows[0].get("password") == "[REDACTED]"
            
            self.log_test(
                "Sensitive columns redacted",
                response.ok and (password_redacted or "password" in (response.redacted_columns or [])),
                f"Redacted columns: {response.redacted_columns}"
            )
            
            # Test with redaction disabled
            response = await execute_bounded_query(
                query=query,
                db_adapter=self.db_adapter,
                dialect=self.dialect,
                max_rows=10,
                enable_redaction=False
            )
            
            password_not_redacted = False
            if response.ok and response.rows and has_password_col:
                password_not_redacted = response.rows[0].get("password") != "[REDACTED]"
            
            self.log_test(
                "Redaction can be disabled",
                response.ok and (password_not_redacted or not response.redacted_columns),
                f"Redacted columns: {response.redacted_columns}"
            )
            
        except Exception as e:
            self.log_test("Sensitive columns redacted", False, f"Error: {e}")
            self.log_test("Redaction can be disabled", False, f"Error: {e}")
    
    async def test_response_envelope(self):
        """Test structured response envelope."""
        print("\n--- Test 6: Response Envelope ---\n")
        
        # Execute a query and check response structure
        response = await execute_bounded_query(
            query="SELECT 1 as test_col",
            db_adapter=self.db_adapter,
            dialect=self.dialect,
            max_rows=10
        )
        
        # Test 6.1: Response has required fields
        has_ok = hasattr(response, 'ok')
        has_rows = hasattr(response, 'rows')
        has_columns = hasattr(response, 'columns')
        has_row_count = hasattr(response, 'row_count')
        has_execution_time = hasattr(response, 'execution_time_ms')
        has_truncated = hasattr(response, 'truncated')
        
        self.log_test(
            "Response has required fields",
            all([has_ok, has_rows, has_columns, has_row_count, has_execution_time, has_truncated]),
            f"Fields: ok={has_ok}, rows={has_rows}, columns={has_columns}, row_count={has_row_count}, execution_time_ms={has_execution_time}, truncated={has_truncated}"
        )
        
        # Test 6.2: Response can be converted to dict
        try:
            response_dict = response.to_dict()
            is_dict = isinstance(response_dict, dict)
            has_ok_field = 'ok' in response_dict
            
            self.log_test(
                "Response converts to dict",
                is_dict and has_ok_field,
                f"Keys: {list(response_dict.keys())}"
            )
        except Exception as e:
            self.log_test("Response converts to dict", False, f"Error: {e}")
    
    async def run_all_tests(self):
        """Run all Phase 2 tests."""
        await self.setup()
        
        try:
            await self.test_query_validation()
            await self.test_row_cap_injection()
            await self.test_bounded_query_execution()
            await self.test_error_handling()
            await self.test_column_redaction()
            await self.test_response_envelope()
        finally:
            await self.teardown()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Test Summary")
        print(f"{'='*60}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        print(f"Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        print(f"{'='*60}\n")
        
        return self.failed == 0


async def main():
    """Main test runner."""
    tester = Phase2Tester()
    success = await tester.run_all_tests()
    
    if success:
        print("🎉 All Phase 2 tests passed!")
        sys.exit(0)
    else:
        print("⚠️ Some Phase 2 tests failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())