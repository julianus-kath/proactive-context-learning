"""
Tests for Query Executor - Safe Query Execution with Validation

Tests cover:
- Successful query execution
- Validation integration
- Result formatting
- Error handling
- Timeout behavior (mocked)
- Empty results
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.db.query_executor import (
    QueryExecutor,
    QueryResult,
    ExecutionStatus,
    execute_safe_query
)


class TestBasicExecution:
    """Test basic query execution functionality."""
    
    def test_successful_query_execution(self):
        """Test successful query execution with results."""
        # Mock database client
        mock_client = Mock()
        mock_client.query.return_value = (
            ['id', 'name', 'email'],
            [
                [1, 'Alice', 'alice@example.com'],
                [2, 'Bob', 'bob@example.com']
            ]
        )
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM customers LIMIT 2")
        
        assert result.success is True
        assert result.status == ExecutionStatus.SUCCESS
        assert result.row_count == 2
        assert result.columns == ['id', 'name', 'email']
        assert len(result.rows) == 2
        assert result.execution_time_ms > 0
        assert result.formatted_result is not None
        assert 'Alice' in result.formatted_result
    
    def test_empty_result_set(self):
        """Test query that returns no rows."""
        mock_client = Mock()
        mock_client.query.return_value = (['id', 'name'], [])
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM customers WHERE id = 999")
        
        assert result.success is True
        assert result.status == ExecutionStatus.EMPTY_RESULT
        assert result.row_count == 0
        assert result.formatted_result == "Query executed successfully but returned no rows."
    
    def test_query_with_limit(self):
        """Test query execution respects row limits."""
        mock_client = Mock()
        mock_client.query.return_value = (
            ['id'],
            [[i] for i in range(100)]
        )
        
        executor = QueryExecutor(max_rows=50)
        result = executor.execute(mock_client, "SELECT * FROM large_table")
        
        # Verify limit was passed to client
        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args
        assert call_args.kwargs['limit'] == 50


class TestValidationIntegration:
    """Test integration with query validator."""
    
    def test_invalid_query_rejected(self):
        """Test that invalid queries are rejected before execution."""
        mock_client = Mock()
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "DELETE FROM customers")
        
        assert result.success is False
        assert result.status == ExecutionStatus.VALIDATION_FAILED
        # Validator rejects non-SELECT statements
        assert "select" in result.error.lower() or "read-only" in result.error.lower()
        
        # Verify query was never executed
        mock_client.query.assert_not_called()
    
    def test_empty_query_rejected(self):
        """Test that empty queries are rejected."""
        mock_client = Mock()
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "")
        
        assert result.success is False
        assert result.status == ExecutionStatus.VALIDATION_FAILED
        assert "empty" in result.error.lower()
        mock_client.query.assert_not_called()
    
    def test_sql_injection_rejected(self):
        """Test that SQL injection attempts are rejected."""
        mock_client = Mock()
        
        executor = QueryExecutor()
        result = executor.execute(
            mock_client,
            "SELECT * FROM users; DROP TABLE users;"
        )
        
        assert result.success is False
        assert result.status == ExecutionStatus.VALIDATION_FAILED
        mock_client.query.assert_not_called()
    
    def test_validation_warnings_included(self):
        """Test that validation warnings are included in result."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        executor = QueryExecutor()
        # Query without LIMIT will get auto-added
        result = executor.execute(mock_client, "SELECT * FROM customers")
        
        assert result.success is True
        assert len(result.validation_warnings) > 0
        # Should have warning about auto-added limit
        assert any('limit' in w.lower() for w in result.validation_warnings)


class TestResultFormatting:
    """Test result formatting for LLM consumption."""
    
    def test_formatted_output_structure(self):
        """Test that formatted output has proper structure."""
        mock_client = Mock()
        mock_client.query.return_value = (
            ['id', 'name', 'status'],
            [
                [1, 'Product A', 'active'],
                [2, 'Product B', 'inactive']
            ]
        )
        
        executor = QueryExecutor(format_results=True)
        result = executor.execute(mock_client, "SELECT * FROM products LIMIT 2")
        
        assert result.success is True
        assert result.formatted_result is not None
        
        # Check structure
        formatted = result.formatted_result
        assert 'id' in formatted
        assert 'name' in formatted
        assert 'status' in formatted
        assert 'Product A' in formatted
        assert 'Product B' in formatted
        assert '2 row(s)' in formatted
    
    def test_formatting_disabled(self):
        """Test execution without result formatting."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        executor = QueryExecutor(format_results=False)
        result = executor.execute(mock_client, "SELECT * FROM test LIMIT 1")
        
        assert result.success is True
        assert result.formatted_result is None
        assert result.rows is not None
    
    def test_large_result_truncation(self):
        """Test that large results are truncated in formatted output."""
        mock_client = Mock()
        # Return 200 rows
        mock_client.query.return_value = (
            ['id'],
            [[i] for i in range(200)]
        )
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM large_table LIMIT 200")
        
        assert result.success is True
        assert result.row_count == 200
        # Formatted output should mention truncation
        assert 'more row(s)' in result.formatted_result
    
    def test_null_values_formatted(self):
        """Test that NULL values are properly formatted."""
        mock_client = Mock()
        mock_client.query.return_value = (
            ['id', 'optional_field'],
            [
                [1, 'value'],
                [2, None]
            ]
        )
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM test LIMIT 2")
        
        assert result.success is True
        assert 'NULL' in result.formatted_result


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_database_error_handled(self):
        """Test that database errors are caught and reported."""
        mock_client = Mock()
        mock_client.query.side_effect = RuntimeError("Database connection failed")
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM customers LIMIT 10")
        
        assert result.success is False
        assert result.status == ExecutionStatus.EXECUTION_FAILED
        assert "Database connection failed" in result.error
    
    def test_timeout_error_handled(self):
        """Test that timeout errors are caught and reported."""
        mock_client = Mock()
        mock_client.query.side_effect = TimeoutError("Query timeout")
        
        executor = QueryExecutor(timeout_seconds=5)
        result = executor.execute(mock_client, "SELECT * FROM slow_table")
        
        assert result.success is False
        assert result.status == ExecutionStatus.TIMEOUT
        assert "timeout" in result.error.lower()
    
    def test_execution_time_recorded_on_error(self):
        """Test that execution time is recorded even on errors."""
        mock_client = Mock()
        mock_client.query.side_effect = RuntimeError("Error")
        
        executor = QueryExecutor()
        result = executor.execute(mock_client, "SELECT * FROM test LIMIT 1")
        
        assert result.success is False
        assert result.execution_time_ms > 0


class TestConvenienceFunction:
    """Test the execute_safe_query convenience function."""
    
    def test_execute_safe_query_success(self):
        """Test convenience function with successful query."""
        mock_client = Mock()
        mock_client.query.return_value = (
            ['count'],
            [[42]]
        )
        
        result = execute_safe_query(
            mock_client,
            "SELECT COUNT(*) as count FROM orders"
        )
        
        assert result.success is True
        assert result.row_count == 1
        assert result.rows[0][0] == 42
    
    def test_execute_safe_query_with_params(self):
        """Test convenience function with parameters."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        result = execute_safe_query(
            mock_client,
            "SELECT * FROM users WHERE id = :id LIMIT 1",
            params={'id': 1}
        )
        
        assert result.success is True
        # Verify params were passed
        call_args = mock_client.query.call_args
        assert call_args.kwargs['params'] == {'id': 1}
    
    def test_execute_safe_query_custom_limits(self):
        """Test convenience function with custom limits."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        result = execute_safe_query(
            mock_client,
            "SELECT * FROM test",
            max_rows=500,
            timeout_seconds=60
        )
        
        assert result.success is True
        # Verify custom limits were used
        call_args = mock_client.query.call_args
        assert call_args.kwargs['limit'] == 500
        assert call_args.kwargs['timeout_s'] == 60


class TestQueryResultDataclass:
    """Test QueryResult dataclass structure."""
    
    def test_result_structure(self):
        """Test that QueryResult has expected structure."""
        result = QueryResult(
            success=True,
            status=ExecutionStatus.SUCCESS,
            columns=['id', 'name'],
            rows=[[1, 'test']],
            row_count=1,
            execution_time_ms=10.5,
            formatted_result="test output"
        )
        
        assert result.success is True
        assert result.status == ExecutionStatus.SUCCESS
        assert result.columns == ['id', 'name']
        assert result.rows == [[1, 'test']]
        assert result.row_count == 1
        assert result.execution_time_ms == 10.5
        assert result.formatted_result == "test output"
        assert result.error is None
        assert result.validation_warnings == []
    
    def test_failed_result_structure(self):
        """Test QueryResult for failed execution."""
        result = QueryResult(
            success=False,
            status=ExecutionStatus.EXECUTION_FAILED,
            error="Database error"
        )
        
        assert result.success is False
        assert result.status == ExecutionStatus.EXECUTION_FAILED
        assert result.error == "Database error"
        assert result.columns is None
        assert result.rows is None


class TestCustomConfiguration:
    """Test custom executor configuration."""
    
    def test_custom_max_rows(self):
        """Test executor with custom max_rows."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        executor = QueryExecutor(max_rows=2000)
        result = executor.execute(mock_client, "SELECT * FROM test")
        
        # Verify custom limit was used
        call_args = mock_client.query.call_args
        assert call_args.kwargs['limit'] == 2000
    
    def test_custom_timeout(self):
        """Test executor with custom timeout."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        executor = QueryExecutor(timeout_seconds=120)
        result = executor.execute(mock_client, "SELECT * FROM test LIMIT 1")
        
        # Verify custom timeout was used
        call_args = mock_client.query.call_args
        assert call_args.kwargs['timeout_s'] == 120
    
    def test_row_limit_enforcement_disabled(self):
        """Test executor with row limit enforcement disabled."""
        mock_client = Mock()
        mock_client.query.return_value = (['id'], [[1]])
        
        executor = QueryExecutor(enforce_row_limit=False)
        result = executor.execute(mock_client, "SELECT * FROM test")
        
        # Query should succeed without auto-added LIMIT
        assert result.success is True
        # Should have no warnings about missing limit
        assert not any('limit' in w.lower() for w in result.validation_warnings)