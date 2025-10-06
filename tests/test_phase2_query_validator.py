"""
Unit tests for Phase 2: Query Validator

Tests query validation, row cap injection, and error handling
for both PostgreSQL and SQL Server dialects.
"""

import pytest
from mcp_server.query_validator import (
    QueryValidator,
    ValidationResult,
    ValidationErrorCode,
    validate_query
)


class TestQueryValidatorPostgres:
    """Test query validator with PostgreSQL dialect."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = QueryValidator(dialect="postgres", max_rows=1000)
    
    def test_valid_select_query(self):
        """Test valid SELECT query passes validation."""
        query = "SELECT * FROM customers"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert result.error_code is None
        assert "LIMIT 1000" in result.query
        assert result.row_cap_applied is True
    
    def test_select_with_existing_limit_below_max(self):
        """Test SELECT with LIMIT below max is preserved."""
        query = "SELECT * FROM customers LIMIT 100"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "LIMIT 100" in result.query
        assert result.row_cap_applied is False
        assert result.original_limit == 100
    
    def test_select_with_existing_limit_above_max(self):
        """Test SELECT with LIMIT above max is clamped."""
        query = "SELECT * FROM customers LIMIT 5000"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "LIMIT 1000" in result.query
        assert result.row_cap_applied is True
        assert result.original_limit == 5000
    
    def test_requested_limit_honored(self):
        """Test requested limit is honored if below max."""
        query = "SELECT * FROM customers"
        result = self.validator.validate_and_cap(query, requested_limit=50)
        
        assert result.valid is True
        assert "LIMIT 50" in result.query
        assert result.row_cap_applied is True
    
    def test_requested_limit_clamped(self):
        """Test requested limit is clamped if above max."""
        query = "SELECT * FROM customers"
        result = self.validator.validate_and_cap(query, requested_limit=5000)
        
        assert result.valid is True
        assert "LIMIT 1000" in result.query
        assert result.row_cap_applied is True
    
    def test_insert_rejected(self):
        """Test INSERT statement is rejected."""
        query = "INSERT INTO customers (name) VALUES ('test')"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
        assert "INSERT" in result.error_message
    
    def test_update_rejected(self):
        """Test UPDATE statement is rejected."""
        query = "UPDATE customers SET name = 'test' WHERE id = 1"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_delete_rejected(self):
        """Test DELETE statement is rejected."""
        query = "DELETE FROM customers WHERE id = 1"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_drop_rejected(self):
        """Test DROP statement is rejected."""
        query = "DROP TABLE customers"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_create_rejected(self):
        """Test CREATE statement is rejected."""
        query = "CREATE TABLE test (id INT)"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_alter_rejected(self):
        """Test ALTER statement is rejected."""
        query = "ALTER TABLE customers ADD COLUMN test VARCHAR(100)"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_exec_rejected(self):
        """Test EXEC statement is rejected."""
        query = "EXEC sp_executesql N'SELECT * FROM customers'"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_multi_statement_rejected(self):
        """Test multiple statements are rejected."""
        query = "SELECT * FROM customers; DROP TABLE customers;"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.MULTI_STATEMENT
    
    def test_empty_query_rejected(self):
        """Test empty query is rejected."""
        query = ""
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.EMPTY_QUERY
    
    def test_whitespace_query_rejected(self):
        """Test whitespace-only query is rejected."""
        query = "   \n\t  "
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.EMPTY_QUERY
    
    def test_comments_stripped(self):
        """Test SQL comments are stripped."""
        query = """
        -- This is a comment
        SELECT * FROM customers
        /* Multi-line
           comment */
        WHERE id = 1
        """
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "--" not in result.query
        assert "/*" not in result.query
    
    def test_with_cte_allowed(self):
        """Test WITH (CTE) queries are allowed."""
        query = """
        WITH active_customers AS (
            SELECT * FROM customers WHERE active = true
        )
        SELECT * FROM active_customers
        """
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "LIMIT 1000" in result.query
    
    def test_trailing_semicolon_allowed(self):
        """Test trailing semicolon is allowed."""
        query = "SELECT * FROM customers;"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True


class TestQueryValidatorMSSQL:
    """Test query validator with SQL Server dialect."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = QueryValidator(dialect="mssql", max_rows=1000)
    
    def test_valid_select_query(self):
        """Test valid SELECT query passes validation."""
        query = "SELECT * FROM customers"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert result.error_code is None
        assert "SELECT TOP 1000" in result.query
        assert result.row_cap_applied is True
    
    def test_select_with_existing_top_below_max(self):
        """Test SELECT with TOP below max is preserved."""
        query = "SELECT TOP 100 * FROM customers"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "SELECT TOP 100" in result.query
        assert result.row_cap_applied is False
        assert result.original_limit == 100
    
    def test_select_with_existing_top_above_max(self):
        """Test SELECT with TOP above max is clamped."""
        query = "SELECT TOP 5000 * FROM customers"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is True
        assert "SELECT TOP 1000" in result.query
        assert result.row_cap_applied is True
        assert result.original_limit == 5000
    
    def test_requested_limit_honored(self):
        """Test requested limit is honored if below max."""
        query = "SELECT * FROM customers"
        result = self.validator.validate_and_cap(query, requested_limit=50)
        
        assert result.valid is True
        assert "SELECT TOP 50" in result.query
        assert result.row_cap_applied is True
    
    def test_insert_rejected(self):
        """Test INSERT statement is rejected."""
        query = "INSERT INTO customers (name) VALUES ('test')"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.READ_ONLY_VIOLATION
    
    def test_multi_statement_rejected(self):
        """Test multiple statements are rejected."""
        query = "SELECT * FROM customers; DROP TABLE customers;"
        result = self.validator.validate_and_cap(query)
        
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.MULTI_STATEMENT


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_validate_query_postgres(self):
        """Test validate_query convenience function for PostgreSQL."""
        result = validate_query(
            "SELECT * FROM customers",
            dialect="postgres",
            max_rows=500
        )
        
        assert result.valid is True
        assert "LIMIT 500" in result.query
    
    def test_validate_query_mssql(self):
        """Test validate_query convenience function for SQL Server."""
        result = validate_query(
            "SELECT * FROM customers",
            dialect="mssql",
            max_rows=500
        )
        
        assert result.valid is True
        assert "SELECT TOP 500" in result.query
    
    def test_validate_query_with_requested_limit(self):
        """Test validate_query with requested limit."""
        result = validate_query(
            "SELECT * FROM customers",
            dialect="postgres",
            max_rows=1000,
            requested_limit=100
        )
        
        assert result.valid is True
        assert "LIMIT 100" in result.query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])