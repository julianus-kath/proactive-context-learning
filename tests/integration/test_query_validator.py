"""
Tests for SQL Query Validator

Tests the query validation system to ensure only safe, read-only queries are allowed.
"""

import pytest
from app.db.query_validator import (
    QueryValidator,
    validate_query,
    is_read_only,
    ValidationError,
    ValidationResult
)


class TestBasicValidation:
    """Test basic query validation."""
    
    def test_valid_simple_select(self):
        """Valid SELECT query should pass."""
        result = validate_query("SELECT * FROM customers LIMIT 10")
        
        assert result.is_valid
        assert result.sanitized_query is not None
        assert result.error is None
    
    def test_valid_select_with_where(self):
        """SELECT with WHERE clause should pass."""
        result = validate_query("SELECT id, name FROM customers WHERE active = 1 LIMIT 100")
        
        assert result.is_valid
        assert "SELECT" in result.sanitized_query
    
    def test_valid_select_with_join(self):
        """SELECT with JOIN should pass."""
        query = """
        SELECT c.name, o.total
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        LIMIT 50
        """
        result = validate_query(query)
        
        assert result.is_valid
    
    def test_empty_query(self):
        """Empty query should be rejected."""
        result = validate_query("")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.EMPTY_QUERY
    
    def test_whitespace_only_query(self):
        """Whitespace-only query should be rejected."""
        result = validate_query("   \n\t  ")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.EMPTY_QUERY


class TestDangerousStatements:
    """Test rejection of dangerous SQL statements."""
    
    def test_insert_rejected(self):
        """INSERT statement should be rejected."""
        result = validate_query("INSERT INTO customers (name) VALUES ('test')")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_update_rejected(self):
        """UPDATE statement should be rejected."""
        result = validate_query("UPDATE customers SET name = 'test' WHERE id = 1")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_delete_rejected(self):
        """DELETE statement should be rejected."""
        result = validate_query("DELETE FROM customers WHERE id = 1")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_drop_rejected(self):
        """DROP statement should be rejected."""
        result = validate_query("DROP TABLE customers")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_create_rejected(self):
        """CREATE statement should be rejected."""
        result = validate_query("CREATE TABLE test (id INT)")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_alter_rejected(self):
        """ALTER statement should be rejected."""
        result = validate_query("ALTER TABLE customers ADD COLUMN test VARCHAR(50)")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_truncate_rejected(self):
        """TRUNCATE statement should be rejected."""
        result = validate_query("TRUNCATE TABLE customers")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT
    
    def test_exec_rejected(self):
        """EXEC statement should be rejected."""
        result = validate_query("EXEC sp_executesql 'SELECT * FROM customers'")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.NOT_SELECT


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_multiple_statements_rejected(self):
        """Multiple statements (stacked queries) should be rejected."""
        result = validate_query("SELECT * FROM customers; DROP TABLE customers;")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.MULTIPLE_STATEMENTS
    
    def test_comment_injection_rejected(self):
        """SQL comments should be rejected by default."""
        result = validate_query("SELECT * FROM customers -- WHERE id = 1")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.SQL_COMMENTS
    
    def test_multiline_comment_rejected(self):
        """Multi-line comments should be rejected."""
        result = validate_query("SELECT * FROM customers /* comment */ LIMIT 10")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.SQL_COMMENTS
    
    def test_union_injection_rejected(self):
        """UNION-based injection should be rejected by default."""
        result = validate_query("SELECT * FROM customers UNION SELECT * FROM passwords")
        
        assert not result.is_valid
        assert result.error_type == ValidationError.SUSPICIOUS_PATTERN
    
    def test_union_allowed_when_configured(self):
        """UNION should be allowed when explicitly configured."""
        validator = QueryValidator(allow_union=True, enforce_row_limit=False)
        result = validator.validate("SELECT * FROM customers UNION SELECT * FROM archived_customers LIMIT 100")
        
        assert result.is_valid
    
    def test_stacked_query_injection_rejected(self):
        """Stacked query injection should be rejected."""
        queries = [
            "SELECT * FROM customers; INSERT INTO logs VALUES ('hacked');",
            "SELECT * FROM users; UPDATE users SET admin = 1;",
            "SELECT * FROM data; DELETE FROM audit_log;",
        ]
        
        for query in queries:
            result = validate_query(query)
            assert not result.is_valid
    
    def test_xp_cmdshell_rejected(self):
        """SQL Server command execution should be rejected."""
        result = validate_query("SELECT * FROM customers; EXEC xp_cmdshell 'dir';")
        
        assert not result.is_valid


class TestRowLimitEnforcement:
    """Test row limit enforcement."""
    
    def test_query_with_limit_accepted(self):
        """Query with LIMIT should be accepted."""
        result = validate_query("SELECT * FROM customers LIMIT 100")
        
        assert result.is_valid
        assert "LIMIT" in result.sanitized_query
    
    def test_query_without_limit_gets_auto_limit(self):
        """Query without LIMIT should get auto-added limit."""
        result = validate_query("SELECT * FROM customers")
        
        assert result.is_valid
        assert "LIMIT" in result.sanitized_query
        assert any("Auto-added row limit" in w for w in result.warnings)
    
    def test_query_with_top_accepted(self):
        """Query with TOP (SQL Server) should be accepted."""
        result = validate_query("SELECT TOP 100 * FROM customers")
        
        assert result.is_valid
    
    def test_custom_max_rows(self):
        """Custom max_rows should be respected."""
        result = validate_query("SELECT * FROM customers", max_rows=500)
        
        assert result.is_valid
        assert "LIMIT 500" in result.sanitized_query
    
    def test_row_limit_not_enforced_when_disabled(self):
        """Row limit should not be enforced when disabled."""
        validator = QueryValidator(enforce_row_limit=False)
        result = validator.validate("SELECT * FROM customers")
        
        assert result.is_valid
        assert "LIMIT" not in result.sanitized_query


class TestQuerySanitization:
    """Test query sanitization."""
    
    def test_trailing_semicolon_removed(self):
        """Trailing semicolon should be removed."""
        result = validate_query("SELECT * FROM customers LIMIT 10;")
        
        assert result.is_valid
        assert not result.sanitized_query.endswith(';')
        assert any("semicolon" in w.lower() for w in result.warnings)
    
    def test_whitespace_normalized(self):
        """Excessive whitespace should be normalized."""
        result = validate_query("SELECT  *   FROM    customers   LIMIT  10")
        
        assert result.is_valid
        # Should have single spaces
        assert "  " not in result.sanitized_query
    
    def test_multiline_query_normalized(self):
        """Multi-line query should be normalized."""
        query = """
        SELECT
            id,
            name,
            email
        FROM
            customers
        LIMIT 10
        """
        result = validate_query(query)
        
        assert result.is_valid
        assert result.sanitized_query is not None


class TestIsReadOnlyHelper:
    """Test is_read_only() helper function."""
    
    def test_select_is_read_only(self):
        """SELECT query should be read-only."""
        assert is_read_only("SELECT * FROM customers")
    
    def test_insert_not_read_only(self):
        """INSERT query should not be read-only."""
        assert not is_read_only("INSERT INTO customers VALUES (1, 'test')")
    
    def test_update_not_read_only(self):
        """UPDATE query should not be read-only."""
        assert not is_read_only("UPDATE customers SET name = 'test'")
    
    def test_delete_not_read_only(self):
        """DELETE query should not be read-only."""
        assert not is_read_only("DELETE FROM customers")
    
    def test_empty_not_read_only(self):
        """Empty query should not be read-only."""
        assert not is_read_only("")
    
    def test_select_with_dangerous_keywords_not_read_only(self):
        """SELECT with dangerous keywords should not be read-only."""
        assert not is_read_only("SELECT * FROM customers; DROP TABLE customers;")


class TestCustomValidatorConfiguration:
    """Test custom validator configuration."""
    
    def test_custom_max_rows(self):
        """Custom max_rows should be applied."""
        validator = QueryValidator(max_rows=5000)
        result = validator.validate("SELECT * FROM customers")
        
        assert result.is_valid
        assert "LIMIT 5000" in result.sanitized_query
    
    def test_comments_allowed_when_configured(self):
        """Comments should be allowed when configured."""
        validator = QueryValidator(allow_comments=True, enforce_row_limit=False)
        result = validator.validate("SELECT * FROM customers -- get all customers LIMIT 10")
        
        assert result.is_valid
    
    def test_multiple_validators_independent(self):
        """Multiple validator instances should be independent."""
        validator1 = QueryValidator(max_rows=100)
        validator2 = QueryValidator(max_rows=500)
        
        result1 = validator1.validate("SELECT * FROM customers")
        result2 = validator2.validate("SELECT * FROM customers")
        
        assert "LIMIT 100" in result1.sanitized_query
        assert "LIMIT 500" in result2.sanitized_query


class TestEdgeCases:
    """Test edge cases and corner scenarios."""
    
    def test_select_in_string_literal(self):
        """SELECT keyword in string literal should not cause issues."""
        result = validate_query("SELECT * FROM customers WHERE note = 'SELECT this' LIMIT 10")
        
        assert result.is_valid
    
    def test_case_insensitive_validation(self):
        """Validation should be case-insensitive."""
        queries = [
            "select * from customers limit 10",
            "SELECT * FROM customers LIMIT 10",
            "SeLeCt * FrOm customers LiMiT 10",
        ]
        
        for query in queries:
            result = validate_query(query)
            assert result.is_valid
    
    def test_complex_select_with_subquery(self):
        """Complex SELECT with subquery should be allowed."""
        query = """
        SELECT c.name, (SELECT COUNT(*) FROM orders WHERE customer_id = c.id) as order_count
        FROM customers c
        LIMIT 100
        """
        result = validate_query(query)
        
        assert result.is_valid
    
    def test_select_with_cte(self):
        """SELECT with CTE (Common Table Expression) should be allowed."""
        query = """
        WITH active_customers AS (
            SELECT * FROM customers WHERE active = 1
        )
        SELECT * FROM active_customers LIMIT 50
        """
        result = validate_query(query)
        
        assert result.is_valid
    
    def test_semicolon_in_string_literal(self):
        """Semicolon in string literal should not trigger multiple statement error."""
        result = validate_query("SELECT * FROM customers WHERE note = 'test;data' LIMIT 10")
        
        assert result.is_valid
    
    def test_very_long_query(self):
        """Very long query should be handled."""
        columns = ", ".join([f"col{i}" for i in range(100)])
        query = f"SELECT {columns} FROM customers LIMIT 10"
        
        result = validate_query(query)
        assert result.is_valid


class TestValidationResult:
    """Test ValidationResult dataclass."""
    
    def test_validation_result_structure(self):
        """ValidationResult should have correct structure."""
        result = validate_query("SELECT * FROM customers LIMIT 10")
        
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'sanitized_query')
        assert hasattr(result, 'error')
        assert hasattr(result, 'error_type')
        assert hasattr(result, 'warnings')
    
    def test_successful_validation_result(self):
        """Successful validation should have correct fields."""
        result = validate_query("SELECT * FROM customers LIMIT 10")
        
        assert result.is_valid is True
        assert result.sanitized_query is not None
        assert result.error is None
        assert result.error_type is None
        assert isinstance(result.warnings, list)
    
    def test_failed_validation_result(self):
        """Failed validation should have error information."""
        result = validate_query("DROP TABLE customers")
        
        assert result.is_valid is False
        assert result.sanitized_query is None
        assert result.error is not None
        assert result.error_type is not None