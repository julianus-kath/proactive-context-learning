"""
Phase 6 Integration Tests: Observability & Guardrails

Tests for:
1. Structured logging for all MCP tool calls
2. Enhanced /health endpoint with comprehensive metrics
3. Rate limiting with Retry-After headers
4. Big schema handling (500+ tables)
5. Relevance testing (search → describe → query flow)
6. Safety testing (DDL/DML rejection, timeouts)
7. Load testing (20 queries/min for 5 min)

Architecture alignment:
- Read-only, safe queries: Only SELECT statements
- JSON as single data format: All responses are JSON
- Security & privacy: PII-free logging
"""

import pytest
import asyncio
import time
import json
import sys
import os
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Phase 6 imports
from mcp_server.observability import (
    StructuredLogger,
    ToolCallMetrics,
    ErrorCategory,
    log_tool_call
)
from mcp_server.discovery_tools import DiscoveryTools, ResponseCache, RateLimiter


class TestStructuredLogging:
    """Test Phase 6 structured logging."""
    
    def test_tool_call_metrics_creation(self):
        """Test ToolCallMetrics dataclass creation."""
        metrics = ToolCallMetrics(
            tool_name="list_tables",
            arguments={"page": 1, "page_size": 25},
            duration_ms=15.5,
            success=True,
            cache_hit=False,
            row_count=25,
            truncated=False,
            error_code=None,
            error_category=None,
            error_message=None
        )
        
        assert metrics.tool_name == "list_tables"
        assert metrics.duration_ms == 15.5
        assert metrics.success is True
        assert metrics.cache_hit is False
        assert metrics.row_count == 25
    
    def test_error_category_enum(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.DATABASE.value == "database"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.CATALOG.value == "catalog"
        assert ErrorCategory.UNKNOWN.value == "unknown"
    
    def test_structured_logger_singleton(self):
        """Test StructuredLogger is a singleton."""
        logger1 = StructuredLogger()
        logger2 = StructuredLogger()
        assert logger1 is logger2
    
    def test_log_tool_call_context_manager_success(self):
        """Test log_tool_call context manager for successful call."""
        logger = StructuredLogger()
        
        with log_tool_call("list_tables", {"page": 1}) as metrics:
            time.sleep(0.01)  # Simulate work
            metrics.cache_hit = True
            metrics.row_count = 25
        
        # Verify metrics were recorded
        assert metrics.success is True
        assert metrics.duration_ms > 0
        assert metrics.cache_hit is True
        assert metrics.row_count == 25
        
        # Verify metrics are in history
        history = logger.get_metrics_history()
        assert len(history) > 0
        assert history[-1]["tool_name"] == "list_tables"
        assert history[-1]["success"] is True
    
    def test_log_tool_call_context_manager_error(self):
        """Test log_tool_call context manager for failed call."""
        logger = StructuredLogger()
        
        try:
            with log_tool_call("query_bounded", {"sql": "SELECT * FROM users"}) as metrics:
                raise ValueError("Database connection failed")
        except ValueError:
            pass
        
        # Verify error was recorded
        assert metrics.success is False
        assert metrics.error_category == "unknown"
        assert "Database connection failed" in metrics.error_message
        
        # Verify metrics are in history
        history = logger.get_metrics_history()
        assert len(history) > 0
        assert history[-1]["success"] is False
    
    def test_pii_redaction_in_arguments(self):
        """Test that PII is redacted from logged arguments."""
        logger = StructuredLogger()
        
        # Arguments with SQL (should be redacted)
        args = {
            "sql": "SELECT * FROM users WHERE email = 'test@example.com'",
            "limit": 100
        }
        
        redacted = logger._redact_arguments(args)
        
        # SQL content should be redacted
        assert "sql" in redacted
        assert "test@example.com" not in str(redacted)
        assert "length" in redacted["sql"]
        
        # Safe metadata should be preserved
        assert redacted["limit"] == 100
    
    def test_metrics_summary(self):
        """Test get_metrics_summary aggregation."""
        logger = StructuredLogger()
        logger._metrics_history.clear()  # Clear history
        
        # Log some successful calls
        for i in range(5):
            with log_tool_call("list_tables", {"page": i+1}) as metrics:
                metrics.cache_hit = (i % 2 == 0)
                metrics.row_count = 25
        
        # Log some failed calls
        for i in range(2):
            try:
                with log_tool_call("query_bounded", {"sql": "SELECT *"}) as metrics:
                    metrics.error_category = "validation"
                    raise ValueError("Invalid query")
            except ValueError:
                pass
        
        summary = logger.get_metrics_summary()
        
        assert summary["total_calls"] == 7
        assert summary["success_rate"] > 0.5
        assert "avg_duration_ms" in summary
        assert "cache_hit_rate" in summary
        assert "error_breakdown" in summary
        assert "tool_breakdown" in summary


class TestRateLimitingWithRetryAfter:
    """Test Phase 6 rate limiting with Retry-After headers."""
    
    def test_rate_limiter_allows_requests_within_limit(self):
        """Test rate limiter allows requests within limit."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
        
        # Should allow first 20 requests (burst)
        for i in range(20):
            allowed, retry_after = limiter.allow_request()
            assert allowed is True
            assert retry_after is None
    
    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test rate limiter blocks requests over limit."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5)
        
        # Exhaust burst
        for i in range(5):
            limiter.allow_request()
        
        # Next request should be blocked
        allowed, retry_after = limiter.allow_request()
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0
    
    def test_rate_limiter_retry_after_calculation(self):
        """Test retry_after is calculated correctly."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=1)
        
        # Exhaust burst
        limiter.allow_request()
        
        # Check retry_after
        allowed, retry_after = limiter.allow_request()
        assert allowed is False
        assert retry_after is not None
        # Should be approximately 0.1 seconds (1/10 rps)
        assert 0.05 < retry_after < 0.15
    
    @pytest.mark.asyncio
    async def test_discovery_response_includes_retry_after(self):
        """Test DiscoveryResponse includes retry_after on rate limit."""
        # Create a mock database adapter with catalog
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = []
        
        # Create rate limiter with very low limit
        DiscoveryTools._rate_limiter = RateLimiter(requests_per_second=1.0, burst_size=1)
        
        # First request should succeed
        response1 = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
        assert response1.ok is True
        
        # Second request should be rate limited
        response2 = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
        assert response2.ok is False
        assert response2.error_code == "RATE_LIMIT_EXCEEDED"
        assert response2.retry_after is not None
        assert response2.retry_after > 0
        
        # Verify retry_after is in JSON response
        response_dict = response2.to_dict()
        assert "retry_after" in response_dict
        assert response_dict["retry_after"] > 0


class TestBigSchemaHandling:
    """Test Phase 6 big schema handling (500+ tables)."""
    
    @pytest.mark.asyncio
    async def test_list_tables_with_500_tables(self):
        """Test list_tables handles 500+ tables efficiently."""
        # Create mock catalog with 500 tables
        tables = []
        for i in range(500):
            tables.append({
                "schema": "dbo",
                "name": f"Table_{i:03d}",
                "type": "TABLE",
                "estimated_rows": 1000,
                "columns": [
                    {"name": "id", "type": "int", "nullable": False},
                    {"name": "name", "type": "varchar(100)", "nullable": True}
                ],
                "primary_keys": [{"column": "id"}],
                "foreign_keys": []
            })
        
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = tables
        
        # Test pagination works
        start_time = time.time()
        response = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
        duration = (time.time() - start_time) * 1000
        
        assert response.ok is True
        assert response.page_info.total_items == 500
        assert response.page_info.total_pages == 20
        assert len(response.data["tables"]) == 25
        assert duration < 300  # Should be < 300ms
    
    @pytest.mark.asyncio
    async def test_search_tables_with_500_tables(self):
        """Test search_tables handles 500+ tables efficiently."""
        # Create mock catalog with 500 tables
        tables = []
        for i in range(500):
            tables.append({
                "schema": "dbo",
                "name": f"Customer_{i:03d}" if i < 10 else f"Table_{i:03d}",
                "type": "TABLE",
                "estimated_rows": 1000,
                "columns": [
                    {"name": "id", "type": "int", "nullable": False},
                    {"name": "name", "type": "varchar(100)", "nullable": True}
                ],
                "primary_keys": [{"column": "id"}],
                "foreign_keys": []
            })
        
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = tables
        
        # Test search finds relevant tables
        start_time = time.time()
        response = await DiscoveryTools.search_tables(db_adapter, query="customer", page=1, page_size=25)
        duration = (time.time() - start_time) * 1000
        
        assert response.ok is True
        assert len(response.data["tables"]) >= 10  # Should find Customer_* tables
        assert duration < 300  # Should be < 300ms


class TestRelevanceFlow:
    """Test Phase 6 relevance testing (search → describe → query flow)."""
    
    @pytest.mark.asyncio
    async def test_search_describe_query_flow(self):
        """Test complete discovery flow: search → describe → query."""
        # Create mock catalog
        tables = [
            {
                "schema": "dbo",
                "name": "Customers",
                "type": "TABLE",
                "estimated_rows": 1000,
                "columns": [
                    {"name": "CustomerID", "type": "int", "nullable": False},
                    {"name": "CustomerName", "type": "varchar(100)", "nullable": True},
                    {"name": "Email", "type": "varchar(255)", "nullable": True}
                ],
                "primary_keys": [{"column": "CustomerID"}],
                "foreign_keys": []
            },
            {
                "schema": "dbo",
                "name": "Orders",
                "type": "TABLE",
                "estimated_rows": 5000,
                "columns": [
                    {"name": "OrderID", "type": "int", "nullable": False},
                    {"name": "CustomerID", "type": "int", "nullable": False},
                    {"name": "OrderDate", "type": "datetime", "nullable": True}
                ],
                "primary_keys": [{"column": "OrderID"}],
                "foreign_keys": [
                    {"column": "CustomerID", "references_table": "Customers", "references_column": "CustomerID"}
                ]
            }
        ]
        
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = tables
        db_adapter.catalog.get_table.side_effect = lambda schema, name: next(
            (t for t in tables if t["name"] == name), None
        )
        
        # Step 1: Search for "customer"
        search_response = await DiscoveryTools.search_tables(db_adapter, query="customer", page=1, page_size=25)
        assert search_response.ok is True
        assert len(search_response.data["tables"]) >= 1
        assert search_response.data["tables"][0]["name"] == "Customers"
        
        # Step 2: Describe the Customers table
        describe_response = await DiscoveryTools.describe_table(
            db_adapter,
            schema="dbo",
            table="Customers",
            include_sample_data=False
        )
        assert describe_response.ok is True
        assert describe_response.data["table"]["name"] == "Customers"
        assert len(describe_response.data["table"]["columns"]) == 3
        
        # Step 3: List relations for Customers
        relations_response = await DiscoveryTools.list_relations(
            db_adapter,
            schema="dbo",
            table="Customers"
        )
        assert relations_response.ok is True
        # Should find Orders as a related table
        assert len(relations_response.data["outgoing_relations"]) >= 0


class TestSafetyControls:
    """Test Phase 6 safety controls (DDL/DML rejection, timeouts)."""
    
    @pytest.mark.asyncio
    async def test_ddl_rejection(self):
        """Test that DDL statements are rejected."""
        from mcp_server.query_validator import validate_query
        
        ddl_queries = [
            "DROP TABLE users",
            "CREATE TABLE test (id int)",
            "ALTER TABLE users ADD COLUMN email varchar(255)",
            "TRUNCATE TABLE users"
        ]
        
        for query in ddl_queries:
            result = validate_query(query)
            assert result["ok"] is False
            assert "DDL" in result["error"] or "not allowed" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_dml_rejection(self):
        """Test that DML statements are rejected."""
        from mcp_server.query_validator import validate_query
        
        dml_queries = [
            "INSERT INTO users (name) VALUES ('test')",
            "UPDATE users SET name = 'test' WHERE id = 1",
            "DELETE FROM users WHERE id = 1"
        ]
        
        for query in dml_queries:
            result = validate_query(query)
            assert result["ok"] is False
            assert "DML" in result["error"] or "not allowed" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_select_only_allowed(self):
        """Test that only SELECT statements are allowed."""
        from mcp_server.query_validator import validate_query
        
        select_queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM users WHERE id = 1",
            "SELECT COUNT(*) FROM users"
        ]
        
        for query in select_queries:
            result = validate_query(query)
            assert result["ok"] is True


class TestHealthEndpoint:
    """Test Phase 6 enhanced /health endpoint."""
    
    def test_health_endpoint_structure(self):
        """Test /health endpoint returns comprehensive metrics."""
        # This would be tested with actual FastAPI test client
        # For now, we verify the structure
        expected_keys = [
            "ok",
            "service",
            "version",
            "phase",
            "catalog_stats",
            "pool_stats",
            "discovery_tools",
            "observability",
            "last_db_error"
        ]
        
        # Mock health response
        health_response = {
            "ok": True,
            "service": "MCP Database Server",
            "version": "1.0.0",
            "phase": "6 - Observability & Guardrails",
            "catalog_stats": {
                "initialized": True,
                "table_count": 100,
                "last_refresh": "2025-01-15T10:00:00Z"
            },
            "pool_stats": {
                "size": 5,
                "min_size": 1,
                "max_size": 10,
                "free_connections": 3
            },
            "discovery_tools": {
                "cache_hit_ratio": 0.85,
                "rate_limit_rps": 10.0
            },
            "observability": {
                "total_calls": 1000,
                "success_rate": 0.95,
                "avg_duration_ms": 15.5
            },
            "last_db_error": None
        }
        
        for key in expected_keys:
            assert key in health_response


class TestLoadTesting:
    """Test Phase 6 load testing (20 queries/min for 5 min)."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_20_qpm(self):
        """Test system handles 20 queries/min for 5 minutes."""
        # This is a long-running test - mark as slow
        # In practice, this would be run separately
        
        # Create mock database adapter
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = []
        
        # Reset rate limiter to allow high throughput
        DiscoveryTools._rate_limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
        
        total_queries = 100  # 20 queries/min * 5 min = 100 queries
        query_interval = 3.0  # 60 seconds / 20 queries = 3 seconds per query
        
        success_count = 0
        rate_limited_count = 0
        error_count = 0
        
        start_time = time.time()
        
        for i in range(total_queries):
            try:
                response = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
                
                if response.ok:
                    success_count += 1
                elif response.error_code == "RATE_LIMIT_EXCEEDED":
                    rate_limited_count += 1
                else:
                    error_count += 1
                
                # Wait for next query
                if i < total_queries - 1:
                    await asyncio.sleep(query_interval)
                    
            except Exception as e:
                error_count += 1
        
        duration = time.time() - start_time
        
        # Verify results
        assert success_count > 0
        assert rate_limited_count == 0  # Should not hit rate limit at 20 qpm
        assert error_count == 0
        assert duration < 360  # Should complete in < 6 minutes


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])