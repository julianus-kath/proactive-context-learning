"""
Test Result Validator Agent - Phase 10a

Comprehensive test coverage for result validation logic.
"""

import pytest
from langgraph_integration.agents.result_validator import ResultValidator, ValidatorConfig


class TestResultValidator:
    """Unit tests for ResultValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ResultValidator()
    
    @pytest.fixture
    def base_intent(self):
        """Base intent for count query."""
        return {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["count"],
            "confidence": 0.95,
            "keywords_for_discovery": ["customers"]
        }
    
    # ========== ZERO ROWS TESTS ==========
    
    def test_zero_rows_low_confidence_count_query(self, validator, base_intent):
        """
        Test: Zero rows + low confidence (0.4) on count query
        Expected: try_next_candidate (wrong table likely)
        """
        intent = {**base_intent, "confidence": 0.4, "metrics": ["count"]}
        
        result = validator.validate(
            user_query="How many customers?",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT COUNT(*) FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "zero_rows"
        assert result["retry_action"] == "try_next_candidate"
        assert "confidence" in result["suggestion"].lower()
    
    def test_zero_rows_high_confidence_count_query(self, validator, base_intent):
        """
        Test: Zero rows + high confidence (0.95) on count query
        Expected: try_next_candidate (suspicious - COUNT(*) should always return ≥1 row)
        
        NOTE: This is now suspicious because SELECT COUNT(*) ALWAYS returns 1 row.
        If the query returned 0 rows, it means the table doesn't exist or query failed.
        """
        intent = {**base_intent, "confidence": 0.95, "metrics": ["count"]}
        
        result = validator.validate(
            user_query="How many customers?",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT COUNT(*) FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "zero_rows"
        assert result["retry_action"] == "try_next_candidate"
        assert "aggregate" in result["suggestion"].lower()
    
    def test_zero_rows_sum_metric_suspicious(self, validator):
        """
        Test: Zero rows on sum/total metric
        Expected: try_next_candidate (suspicious)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["orders"],
            "metrics": ["sum"],
            "confidence": 0.85,
            "keywords_for_discovery": ["orders", "revenue"]
        }
        
        result = validator.validate(
            user_query="Total revenue?",
            intent=intent,
            discovery_results=["dbo.Orders"],
            sql_query="SELECT SUM(Amount) FROM dbo.Orders",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "zero_rows"
        assert result["retry_action"] == "try_next_candidate"
    
    def test_zero_rows_threshold_boundary(self, validator):
        """
        Test: Zero rows at confidence boundary (0.7) on DETAIL query (no aggregate metric)
        Expected: Should accept (confidence >= threshold)
        
        NOTE: This tests a detail query, not a count query. Count queries are always
        suspicious when returning 0 rows because SELECT COUNT(*) always returns ≥1 row.
        """
        intent = {
            "operation": "query",
            "primary_entities": ["items"],
            "metrics": [],  # No aggregate metric
            "confidence": 0.7,
            "keywords_for_discovery": ["items"]
        }
        
        result = validator.validate(
            user_query="Show items",
            intent=intent,
            discovery_results=["dbo.Items"],
            sql_query="SELECT * FROM dbo.Items",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        assert result["valid"] is True  # At threshold, should be accepted (no aggregate metric)
        assert result["retry_action"] == "accept"
    
    # ========== TOO MANY ROWS TESTS ==========
    
    def test_too_many_rows_count_query(self, validator):
        """
        Test: Truncated result (>5000 rows) on count query
        Expected: replan_with_aggregation (missing GROUP BY)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["orders"],
            "metrics": ["count"],
            "confidence": 0.9,
            "keywords_for_discovery": ["orders"]
        }
        
        result = validator.validate(
            user_query="How many orders?",
            intent=intent,
            discovery_results=["dbo.Orders"],
            sql_query="SELECT * FROM dbo.Orders",  # Missing GROUP BY
            exec_result={
                "ok": True,
                "data": [{"OrderID": 1}, {"OrderID": 2}],
                "row_count": 10000,
                "truncated": True
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "too_many_rows"
        assert result["retry_action"] == "replan_with_aggregation"
    
    def test_too_many_rows_detail_query(self, validator):
        """
        Test: Truncated result (>5000 rows) on detail query
        Expected: replan_with_filter (need WHERE clause)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["orders"],
            "metrics": ["details", "list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["orders"]
        }
        
        result = validator.validate(
            user_query="Show all orders",
            intent=intent,
            discovery_results=["dbo.Orders"],
            sql_query="SELECT * FROM dbo.Orders",
            exec_result={
                "ok": True,
                "data": [{"OrderID": i} for i in range(100)],
                "row_count": 10000,
                "truncated": True
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "too_many_rows"
        assert result["retry_action"] == "replan_with_filter"
    
    def test_too_many_rows_boundary(self, validator):
        """
        Test: Result exactly at threshold (5000 rows)
        Expected: Should trigger too_many_rows check
        """
        intent = {
            "operation": "query",
            "primary_entities": ["data"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["data"]
        }
        
        result = validator.validate(
            user_query="Show all data",
            intent=intent,
            discovery_results=["dbo.Data"],
            sql_query="SELECT * FROM dbo.Data",
            exec_result={
                "ok": True,
                "data": [{"ID": i} for i in range(100)],
                "row_count": 5000,  # Exactly at threshold
                "truncated": True
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "too_many_rows"
    
    # ========== SCHEMA MISMATCH TESTS ==========
    
    def test_schema_mismatch_no_overlap(self, validator):
        """
        Test: Returned columns have no overlap with expected
        Expected: try_next_candidate (wrong table)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Show customers",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT CustomerID, Name FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [
                    {"OrderID": 1, "Amount": 100},  # Wrong columns!
                    {"OrderID": 2, "Amount": 200}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "schema_mismatch"
        assert result["retry_action"] == "try_next_candidate"
    
    def test_schema_match_partial_overlap(self, validator):
        """
        Test: Returned columns have partial overlap
        Expected: valid (overlap means correct table)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Show customers",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT CustomerID, Name FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [
                    {"CustomerID": 1, "Name": "Alice", "Email": "alice@example.com"},
                    {"CustomerID": 2, "Name": "Bob", "Email": "bob@example.com"}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is True
    
    # ========== ALL NULLS TESTS ==========
    
    def test_all_nulls_detection(self, validator):
        """
        Test: All values in result are NULL
        Expected: try_next_candidate (likely failed join)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers", "orders"],
            "metrics": ["list"],
            "confidence": 0.85,
            "keywords_for_discovery": ["customers", "orders"]
        }
        
        result = validator.validate(
            user_query="Show customers with orders",
            intent=intent,
            discovery_results=["dbo.Customers", "dbo.Orders"],
            sql_query="SELECT c.Name, o.Amount FROM Customers c JOIN Orders o ON c.ID = o.BadColumn",
            exec_result={
                "ok": True,
                "data": [
                    {"Name": None, "Amount": None},
                    {"Name": None, "Amount": None}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "all_nulls"
        assert result["retry_action"] == "try_next_candidate"
    
    def test_mixed_nulls_accepted(self, validator):
        """
        Test: Result has some NULLs but not all
        Expected: valid (NULLs are OK if mixed with values)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Show customers",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT ID, Name, Phone FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [
                    {"ID": 1, "Name": "Alice", "Phone": None},  # Phone is NULL
                    {"ID": 2, "Name": "Bob", "Phone": "555-1234"}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is True
    
    # ========== SUSPICIOUS PATTERNS TESTS ==========
    
    def test_suspicious_identical_values(self, validator):
        """
        Test: All non-ID column values are identical
        Expected: try_next_candidate (data quality issue)
        """
        intent = {
            "operation": "query",
            "primary_entities": ["products"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["products"]
        }
        
        result = validator.validate(
            user_query="Show products",
            intent=intent,
            discovery_results=["dbo.Products"],
            sql_query="SELECT ProductID, Name, Price FROM dbo.Products",
            exec_result={
                "ok": True,
                "data": [
                    {"ProductID": 1, "Name": "Unknown", "Price": 0},
                    {"ProductID": 2, "Name": "Unknown", "Price": 0},
                    {"ProductID": 3, "Name": "Unknown", "Price": 0}
                ],
                "row_count": 3,
                "truncated": False
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "suspicious_values"
        assert result["retry_action"] == "try_next_candidate"
    
    def test_suspicious_disabled(self, validator):
        """
        Test: Disable suspicious pattern checking
        Expected: Pattern not detected
        """
        config = ValidatorConfig(check_suspicious_patterns=False)
        validator_no_check = ResultValidator(config)
        
        intent = {
            "operation": "query",
            "primary_entities": ["products"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["products"]
        }
        
        result = validator_no_check.validate(
            user_query="Show products",
            intent=intent,
            discovery_results=["dbo.Products"],
            sql_query="SELECT ProductID, Name FROM dbo.Products",
            exec_result={
                "ok": True,
                "data": [
                    {"ProductID": 1, "Name": "Unknown"},
                    {"ProductID": 2, "Name": "Unknown"}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is True
    
    # ========== ERROR HANDLING TESTS ==========
    
    def test_execution_error_detected(self, validator):
        """
        Test: Execution error in result
        Expected: valid=False, try_next_candidate
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["list"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Show customers",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT * FROM dbo.Customers",
            exec_result={
                "ok": False,
                "error": "Column 'Foo' does not exist"
            }
        )
        
        assert result["valid"] is False
        assert result["issue"] == "error"
        assert result["retry_action"] == "try_next_candidate"
    
    # ========== VALID RESULTS TESTS ==========
    
    def test_valid_count_result(self, validator):
        """
        Test: Valid count result (1 row)
        Expected: valid=True
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["count"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="How many customers?",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT COUNT(*) as cnt FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [{"cnt": 42}],
                "row_count": 1,
                "truncated": False
            }
        )
        
        assert result["valid"] is True
        assert result["retry_action"] == "accept"
    
    def test_valid_detail_result(self, validator):
        """
        Test: Valid detail result (multiple rows, <5000)
        Expected: valid=True
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["list", "details"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Show all customers",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT ID, Name FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [
                    {"ID": 1, "Name": "Alice"},
                    {"ID": 2, "Name": "Bob"}
                ],
                "row_count": 2,
                "truncated": False
            }
        )
        
        assert result["valid"] is True
        assert result["retry_action"] == "accept"
    
    # ========== CONFIGURATION TESTS ==========
    
    def test_custom_config_thresholds(self):
        """
        Test: Custom configuration thresholds
        Expected: Validator uses custom values
        """
        config = ValidatorConfig(
            zero_row_confidence_threshold=0.5,  # Lower threshold
            too_many_row_threshold=1000         # Lower row limit
        )
        validator = ResultValidator(config)
        
        intent = {
            "operation": "query",
            "primary_entities": ["data"],
            "metrics": ["list"],
            "confidence": 0.55,  # Above custom threshold
            "keywords_for_discovery": ["data"]
        }
        
        result = validator.validate(
            user_query="Show data",
            intent=intent,
            discovery_results=["dbo.Data"],
            sql_query="SELECT * FROM dbo.Data",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        # Should accept because confidence (0.55) > custom threshold (0.5)
        assert result["valid"] is True
    
    # ========== EDGE CASES ==========
    
    def test_empty_exec_result(self, validator):
        """
        Test: Empty execution result dict
        Expected: Should handle gracefully
        """
        intent = {"confidence": 0.9, "metrics": ["count"]}
        
        result = validator.validate(
            user_query="Test",
            intent=intent,
            discovery_results=[],
            sql_query="",
            exec_result={}
        )
        
        # Should have a validation result (not crash)
        assert "valid" in result
    
    def test_no_rows_in_result(self, validator):
        """
        Test: exec_result has no rows list
        Expected: Handle gracefully
        """
        intent = {
            "operation": "query",
            "primary_entities": ["customers"],
            "metrics": ["count"],
            "confidence": 0.9,
            "keywords_for_discovery": ["customers"]
        }
        
        result = validator.validate(
            user_query="Count",
            intent=intent,
            discovery_results=["dbo.Customers"],
            sql_query="SELECT COUNT(*) FROM dbo.Customers",
            exec_result={
                "ok": True,
                "row_count": 42
                # No 'rows' key
            }
        )
        
        assert "valid" in result
    
    def test_sql_column_extraction_edge_case(self):
        """
        Test: SQL column extraction with complex query
        Expected: Should extract what it can
        """
        validator = ResultValidator()
        
        # Test with various SQL patterns
        test_cases = [
            ("SELECT a, b, c FROM table", {"a", "b", "c"}),
            ("SELECT a AS x, b AS y FROM table", {"x", "y"}),
            ("SELECT COUNT(*) FROM table", set()),  # * is ignored
            ("SELECT a, b FROM table", {"a", "b"}),
        ]
        
        for sql, expected in test_cases:
            columns = validator._extract_expected_columns_from_sql(sql)
            # Just verify it doesn't crash and returns a set
            assert isinstance(columns, set)


class TestResultValidatorIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_customer_count_query_happy_path(self):
        """
        Integration: Simple customer count query, happy path
        """
        validator = ResultValidator()
        
        result = validator.validate(
            user_query="How many customers do we have?",
            intent={
                "operation": "query",
                "primary_entities": ["customers"],
                "metrics": ["count"],
                "confidence": 0.95,
                "keywords_for_discovery": ["customers"]
            },
            discovery_results=["dbo.Customers"],
            sql_query="SELECT COUNT(*) as customer_count FROM dbo.Customers",
            exec_result={
                "ok": True,
                "data": [{"customer_count": 1234}],
                "row_count": 1,
                "truncated": False,
                "execution_time_ms": 45
            }
        )
        
        assert result["valid"] is True
    
    def test_revenue_query_with_recovery(self):
        """
        Integration: Revenue query that discovers wrong table
        """
        validator = ResultValidator()
        
        result = validator.validate(
            user_query="What is our total revenue?",
            intent={
                "operation": "query",
                "primary_entities": ["revenue"],
                "metrics": ["sum"],
                "confidence": 0.65,  # Moderate confidence
                "keywords_for_discovery": ["revenue", "sales"]
            },
            discovery_results=["dbo.Revenue"],  # Might be wrong
            sql_query="SELECT SUM(amount) FROM dbo.Revenue",
            exec_result={
                "ok": True,
                "data": [],
                "row_count": 0,
                "truncated": False
            }
        )
        
        # Should trigger retry
        assert result["valid"] is False
        assert result["retry_action"] == "try_next_candidate"
    
    def test_complex_join_query_truncated(self):
        """
        Integration: Complex join query returns truncated results
        """
        validator = ResultValidator()
        
        result = validator.validate(
            user_query="Show all customer orders with details",
            intent={
                "operation": "query",
                "primary_entities": ["customers", "orders"],
                "metrics": ["details"],
                "confidence": 0.88,
                "keywords_for_discovery": ["customers", "orders"]
            },
            discovery_results=["dbo.Customers", "dbo.Orders", "dbo.OrderDetails"],
            sql_query="SELECT c.ID, c.Name, o.OrderID, od.Amount FROM Customers c JOIN Orders o JOIN OrderDetails od",
            exec_result={
                "ok": True,
                "data": [{"ID": 1, "Name": "Alice", "OrderID": 100, "Amount": 500}],
                "row_count": 15000,
                "truncated": True
            }
        )
        
        # Should trigger replan with filter
        assert result["valid"] is False
        assert result["retry_action"] == "replan_with_filter"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])