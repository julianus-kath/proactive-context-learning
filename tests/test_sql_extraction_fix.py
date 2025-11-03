"""
Unit tests for robust SQL extraction from LLM responses.

Tests the Phase 9 multi-statement validation fix.
"""

import pytest
import logging
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent

logger = logging.getLogger(__name__)


class TestSQLExtraction:
    """Test suite for _extract_sql and related methods."""

    @pytest.fixture
    def agent(self):
        """Create an ExecAndRecoveryAgent instance for testing."""
        return ExecAndRecoveryAgent(llm_model="gpt-4o", llm_temp=0.0)

    # ============================================================================
    # Test 1: Code Fence Extraction (Standard Case)
    # ============================================================================

    def test_extract_sql_from_code_fence_standard(self, agent):
        """Test extracting clean SQL from markdown code fence."""
        response = """Here's the fixed query:

```sql
SELECT id, name FROM dbo.customers WHERE status = 'active'
```

This removes the expensive joins."""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "WHERE status = 'active'" in extracted
        assert "This removes" not in extracted  # No explanation leaked
        assert "```" not in extracted  # No fence markers
        assert extracted.count("SELECT") == 1  # Single statement


    def test_extract_sql_from_code_fence_with_comments(self, agent):
        """Test extraction with SQL comments."""
        response = """```sql
-- Get top customers
SELECT TOP 100 id, total_sales FROM dbo.customers ORDER BY total_sales DESC
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted


    def test_extract_sql_from_code_fence_multiline(self, agent):
        """Test extraction of multi-line SQL query."""
        response = """```sql
SELECT 
    a.id,
    a.name,
    b.total_sales
FROM 
    dbo.customers a
JOIN 
    dbo.orders b ON a.id = b.customer_id
WHERE 
    a.status = 'active'
ORDER BY 
    b.total_sales DESC
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT" in extracted
        assert "dbo.customers" in extracted
        assert "dbo.orders" in extracted
        # Should have multiple lines
        assert extracted.count("\n") > 0


    # ============================================================================
    # Test 2: Code Fence with Explanations (Problem Case)
    # ============================================================================

    def test_extract_sql_fence_with_trailing_explanation(self, agent):
        """Test extraction when explanation follows the code fence."""
        response = """```sql
SELECT TOP 100 id, total_sales FROM dbo.customers
```

This is better because it:
- Removes the expensive join
- Limits to 100 rows"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted
        assert "removes the" not in extracted  # No explanation


    def test_extract_sql_fence_with_leading_explanation(self, agent):
        """Test extraction when explanation precedes the code fence."""
        response = """Here's the fixed query (I changed it to use TOP instead of LIMIT):

```sql
SELECT TOP 100 id, name FROM dbo.customers
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted
        assert "I changed" not in extracted


    # ============================================================================
    # Test 3: Multiple SELECT Statements (Reject Case)
    # ============================================================================

    def test_extract_sql_rejects_multiple_statements(self, agent):
        """Test that extraction rejects responses with multiple SELECTs."""
        response = """The original query:
```sql
SELECT * FROM dbo.orders
```

Should be simplified to:
```sql
SELECT TOP 100 id, total FROM dbo.orders
```
"""

        extracted = agent._extract_sql(response)
        
        # Should return empty because of ambiguity
        assert extracted == "", "Should reject multiple SELECTs"


    def test_extract_sql_rejects_select_plus_markdown(self, agent):
        """Test that extraction rejects code fence with markdown headers inside."""
        response = """```sql
SELECT TOP 100 id FROM dbo.customers

### Important Note
This assumes the database is online
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted
        # Should stop at markdown marker
        assert "Important Note" not in extracted


    # ============================================================================
    # Test 4: Fallback to SELECT...Semicolon
    # ============================================================================

    def test_extract_sql_fallback_select_to_semicolon(self, agent):
        """Test fallback extraction when no code fence present."""
        response = "The fix is: SELECT TOP 100 id FROM dbo.customers WHERE id > 0;"

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted
        assert "fix is:" not in extracted


    def test_extract_sql_fallback_multistatement_rejected(self, agent):
        """Test that fallback rejects multiple statements."""
        response = "SELECT * FROM dbo.orders; SELECT * FROM dbo.customers;"

        extracted = agent._extract_sql(response)
        
        # Should detect multiple SELECTs and reject
        assert extracted == ""


    # ============================================================================
    # Test 5: Special Tokens (CANNOT_FIX, CANNOT_SIMPLIFY)
    # ============================================================================

    def test_extract_sql_rejects_cannot_fix_token(self, agent):
        """Test that extraction recognizes CANNOT_FIX token."""
        response = "CANNOT_FIX: This query requires database-specific context"

        extracted = agent._extract_sql(response)
        
        assert extracted == "", "Should return empty for CANNOT_FIX"


    def test_extract_sql_rejects_cannot_simplify_token(self, agent):
        """Test that extraction recognizes CANNOT_SIMPLIFY token."""
        response = "CANNOT_SIMPLIFY: Query is already minimal"

        extracted = agent._extract_sql(response)
        
        assert extracted == "", "Should return empty for CANNOT_SIMPLIFY"


    # ============================================================================
    # Test 6: Edge Cases
    # ============================================================================

    def test_extract_sql_empty_input(self, agent):
        """Test extraction with empty input."""
        extracted = agent._extract_sql("")
        assert extracted == ""


    def test_extract_sql_no_select(self, agent):
        """Test extraction when no SELECT keyword present."""
        response = "I'm sorry, I cannot help with this query."

        extracted = agent._extract_sql(response)
        assert extracted == ""


    def test_extract_sql_case_insensitive_sql_keyword(self, agent):
        """Test that SQL keyword matching is case-insensitive."""
        response = "```SQL\nselect id from dbo.customers\n```"

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "select" in extracted.lower()


    def test_extract_sql_with_semicolon_in_fence(self, agent):
        """Test that semicolon is properly handled in code fence."""
        response = """```sql
SELECT id FROM dbo.customers;
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT id FROM dbo.customers" in extracted
        # Semicolon should be stripped
        assert not extracted.endswith(";")


    # ============================================================================
    # Test 7: Validation Method
    # ============================================================================

    def test_validate_extracted_sql_valid(self, agent):
        """Test validation of valid SQL."""
        sql = "SELECT id, name FROM dbo.customers"
        assert agent._validate_extracted_sql(sql) is True


    def test_validate_extracted_sql_not_select(self, agent):
        """Test validation rejects non-SELECT statements."""
        sql = "UPDATE dbo.customers SET status = 'active'"
        assert agent._validate_extracted_sql(sql) is False


    def test_validate_extracted_sql_insert(self, agent):
        """Test validation rejects INSERT statements."""
        sql = "INSERT INTO dbo.customers (id, name) VALUES (1, 'John')"
        assert agent._validate_extracted_sql(sql) is False


    def test_validate_extracted_sql_delete(self, agent):
        """Test validation rejects DELETE statements."""
        sql = "DELETE FROM dbo.customers WHERE id = 1"
        assert agent._validate_extracted_sql(sql) is False


    def test_validate_extracted_sql_drop(self, agent):
        """Test validation rejects DROP statements."""
        sql = "DROP TABLE dbo.customers"
        assert agent._validate_extracted_sql(sql) is False


    def test_validate_extracted_sql_exec(self, agent):
        """Test validation rejects EXEC statements."""
        sql = "EXEC sp_executesql N'SELECT * FROM dbo.customers'"
        assert agent._validate_extracted_sql(sql) is False


    def test_validate_extracted_sql_multiple_selects(self, agent):
        """Test validation rejects multiple SELECT statements."""
        sql = "SELECT id FROM dbo.customers; SELECT id FROM dbo.orders"
        assert agent._validate_extracted_sql(sql) is False


    # ============================================================================
    # Test 8: Real-World LLM Responses (Integration Style)
    # ============================================================================

    def test_extract_from_real_world_response_1(self, agent):
        """
        Real-world: LLM returns markdown-formatted explanation with SQL.
        
        This was the original bug: LLM returning formatted response with
        multiple SQL statements.
        """
        response = """The original query had several issues. Here's the corrected version:

```sql
SELECT id, name, total_sales FROM dbo.customers WHERE status = 'active'
```

Key changes:
- Removed expensive joins
- Added status filter
- Limited column selection for performance"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT id, name, total_sales" in extracted
        assert "Key changes:" not in extracted
        # Should be valid
        assert agent._validate_extracted_sql(extracted)


    def test_extract_from_real_world_response_2(self, agent):
        """
        Real-world: LLM returns comparison of original and fixed versions.
        This is the multi-statement case that was causing the error.
        """
        response = """### Original Query (problematic):
```sql
SELECT a.id, a.name, b.total_sales, c.region_name, d.manager_name
FROM customers a
JOIN sales b ON a.id = b.customer_id
JOIN regions c ON a.region_id = c.id
JOIN managers d ON c.manager_id = d.id
WHERE b.sale_date BETWEEN '2023-01-01' AND '2023-12-31'
ORDER BY b.total_sales DESC;
```

### Simplified Version:
```sql
SELECT TOP 100 a.id, a.name, b.total_sales
FROM customers a
JOIN sales b ON a.id = b.customer_id
WHERE b.total_sales > 1000
ORDER BY b.total_sales DESC
```

The simplified version removes unnecessary joins and limits results to top 100."""

        extracted = agent._extract_sql(response)
        
        # Should return empty because multiple SELECTs
        assert extracted == "", "Should reject response with multiple query examples"


    def test_extract_from_real_world_response_3(self, agent):
        """
        Real-world: LLM returns simple code fence format (ideal).
        This is what we want the prompts to enforce.
        """
        response = """```sql
SELECT TOP 100 id, name, total_sales
FROM dbo.customers
WHERE status = 'active'
ORDER BY total_sales DESC
```"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT TOP 100" in extracted
        assert agent._validate_extracted_sql(extracted)


    # ============================================================================
    # Test 9: Helper Methods
    # ============================================================================

    def test_extract_from_code_fence_method(self, agent):
        """Test the _extract_from_code_fence helper method directly."""
        text = """```sql
SELECT id FROM dbo.customers
```
"""
        result = agent._extract_from_code_fence(text)
        assert result is not None
        assert "SELECT id" in result


    def test_extract_select_to_semicolon_method(self, agent):
        """Test the _extract_select_to_semicolon helper method directly."""
        text = "Some text SELECT id FROM dbo.customers; more text"
        result = agent._extract_select_to_semicolon(text)
        assert result is not None
        assert "SELECT id FROM dbo.customers" in result


    # ============================================================================
    # Test 10: Robustness (Weird But Valid Input)
    # ============================================================================

    def test_extract_sql_with_extra_whitespace(self, agent):
        """Test extraction with excessive whitespace."""
        response = """
        
```sql


SELECT    id,    name
FROM      dbo.customers


```

        """

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SELECT" in extracted
        # Whitespace should be normalized
        assert "SELECT    id" in extracted or "SELECT" in extracted


    def test_extract_sql_mixed_case_keywords(self, agent):
        """Test extraction with mixed-case keywords."""
        response = """```sql
SeLeCt id FROM dbo.customers WhErE status = 'active'
```
"""

        extracted = agent._extract_sql(response)
        
        assert extracted is not None
        assert "SeLeCt" in extracted  # Case preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])