"""
Unit tests for Phase 2: Column Redactor

Tests sensitive column identification and data redaction.
"""

import pytest
from mcp_server.column_redactor import (
    ColumnRedactor,
    RedactionConfig,
    redact_sensitive_data
)


class TestColumnRedactor:
    """Test column redactor functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.redactor = ColumnRedactor()
    
    def test_identify_password_column(self):
        """Test password column is identified as sensitive."""
        columns = ["id", "username", "password", "email"]
        sensitive = self.redactor.identify_sensitive_columns(columns)
        
        assert "password" in sensitive
        assert "id" not in sensitive
        assert "username" not in sensitive
    
    def test_identify_multiple_sensitive_columns(self):
        """Test multiple sensitive columns are identified."""
        columns = ["id", "password", "api_key", "secret_token", "email"]
        sensitive = self.redactor.identify_sensitive_columns(columns)
        
        assert "password" in sensitive
        assert "api_key" in sensitive
        assert "secret_token" in sensitive
        assert "email" not in sensitive
    
    def test_case_insensitive_matching(self):
        """Test pattern matching is case-insensitive."""
        columns = ["ID", "PASSWORD", "ApiKey", "SECRET_TOKEN"]
        sensitive = self.redactor.identify_sensitive_columns(columns)
        
        assert "PASSWORD" in sensitive
        assert "ApiKey" in sensitive
        assert "SECRET_TOKEN" in sensitive
    
    def test_pattern_variations(self):
        """Test various pattern variations are matched."""
        columns = [
            "user_password",
            "passwd",
            "pwd",
            "password_hash",
            "hashed_password",
            "api_key",
            "apikey",
            "secret",
            "token",
            "ssn",
            "social_security_number",
            "credit_card",
            "card_number",
            "cvv",
            "pin",
            "private_key"
        ]
        sensitive = self.redactor.identify_sensitive_columns(columns)
        
        # All should be identified as sensitive
        assert len(sensitive) == len(columns)
    
    def test_redact_rows(self):
        """Test row data is redacted correctly."""
        rows = [
            {"id": 1, "username": "john", "password": "secret123"},
            {"id": 2, "username": "jane", "password": "pass456"}
        ]
        
        redacted_rows, redacted_cols = self.redactor.redact_rows(rows)
        
        assert len(redacted_rows) == 2
        assert "password" in redacted_cols
        assert redacted_rows[0]["password"] == "[REDACTED]"
        assert redacted_rows[1]["password"] == "[REDACTED]"
        assert redacted_rows[0]["username"] == "john"
        assert redacted_rows[1]["username"] == "jane"
    
    def test_redact_multiple_columns(self):
        """Test multiple columns are redacted."""
        rows = [
            {
                "id": 1,
                "username": "john",
                "password": "secret123",
                "api_key": "key123",
                "email": "john@example.com"
            }
        ]
        
        redacted_rows, redacted_cols = self.redactor.redact_rows(rows)
        
        assert "password" in redacted_cols
        assert "api_key" in redacted_cols
        assert "email" not in redacted_cols
        assert redacted_rows[0]["password"] == "[REDACTED]"
        assert redacted_rows[0]["api_key"] == "[REDACTED]"
        assert redacted_rows[0]["email"] == "john@example.com"
    
    def test_empty_rows(self):
        """Test empty rows are handled correctly."""
        rows = []
        redacted_rows, redacted_cols = self.redactor.redact_rows(rows)
        
        assert len(redacted_rows) == 0
        assert len(redacted_cols) == 0
    
    def test_no_sensitive_columns(self):
        """Test rows with no sensitive columns."""
        rows = [
            {"id": 1, "name": "John", "email": "john@example.com"}
        ]
        
        redacted_rows, redacted_cols = self.redactor.redact_rows(rows)
        
        assert len(redacted_cols) == 0
        assert redacted_rows[0]["name"] == "John"
        assert redacted_rows[0]["email"] == "john@example.com"
    
    def test_redaction_disabled(self):
        """Test redaction can be disabled."""
        config = RedactionConfig(enabled=False)
        redactor = ColumnRedactor(config)
        
        rows = [
            {"id": 1, "username": "john", "password": "secret123"}
        ]
        
        redacted_rows, redacted_cols = redactor.redact_rows(rows)
        
        assert len(redacted_cols) == 0
        assert redacted_rows[0]["password"] == "secret123"
    
    def test_custom_redaction_text(self):
        """Test custom redaction text."""
        config = RedactionConfig(redaction_text="***HIDDEN***")
        redactor = ColumnRedactor(config)
        
        rows = [
            {"id": 1, "password": "secret123"}
        ]
        
        redacted_rows, redacted_cols = redactor.redact_rows(rows)
        
        assert redacted_rows[0]["password"] == "***HIDDEN***"
    
    def test_custom_patterns(self):
        """Test custom redaction patterns."""
        config = RedactionConfig(patterns=[r'.*email.*', r'.*phone.*'])
        redactor = ColumnRedactor(config)
        
        rows = [
            {"id": 1, "email": "test@example.com", "phone": "123-456-7890", "name": "John"}
        ]
        
        redacted_rows, redacted_cols = redactor.redact_rows(rows)
        
        assert "email" in redacted_cols
        assert "phone" in redacted_cols
        assert "name" not in redacted_cols
        assert redacted_rows[0]["email"] == "[REDACTED]"
        assert redacted_rows[0]["phone"] == "[REDACTED]"
        assert redacted_rows[0]["name"] == "John"
    
    def test_add_pattern(self):
        """Test adding a new pattern."""
        redactor = ColumnRedactor()
        redactor.add_pattern(r'.*custom.*')
        
        columns = ["id", "custom_field", "name"]
        sensitive = redactor.identify_sensitive_columns(columns)
        
        assert "custom_field" in sensitive
    
    def test_remove_pattern(self):
        """Test removing a pattern."""
        config = RedactionConfig(patterns=[r'.*password.*', r'.*secret.*'])
        redactor = ColumnRedactor(config)
        
        redactor.remove_pattern(r'.*password.*')
        
        columns = ["password", "secret"]
        sensitive = redactor.identify_sensitive_columns(columns)
        
        assert "password" not in sensitive
        assert "secret" in sensitive


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_redact_sensitive_data(self):
        """Test redact_sensitive_data convenience function."""
        rows = [
            {"id": 1, "username": "john", "password": "secret123"}
        ]
        
        redacted_rows, redacted_cols = redact_sensitive_data(rows)
        
        assert "password" in redacted_cols
        assert redacted_rows[0]["password"] == "[REDACTED]"
    
    def test_redact_with_custom_patterns(self):
        """Test redact_sensitive_data with custom patterns."""
        rows = [
            {"id": 1, "email": "test@example.com", "name": "John"}
        ]
        
        redacted_rows, redacted_cols = redact_sensitive_data(
            rows,
            patterns=[r'.*email.*']
        )
        
        assert "email" in redacted_cols
        assert redacted_rows[0]["email"] == "[REDACTED]"
        assert redacted_rows[0]["name"] == "John"
    
    def test_redact_disabled(self):
        """Test redact_sensitive_data with redaction disabled."""
        rows = [
            {"id": 1, "password": "secret123"}
        ]
        
        redacted_rows, redacted_cols = redact_sensitive_data(rows, enabled=False)
        
        assert len(redacted_cols) == 0
        assert redacted_rows[0]["password"] == "secret123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])