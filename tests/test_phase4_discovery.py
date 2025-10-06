"""
Phase 4: Unit tests for discovery tools (list_tables, search_tables, describe_table, list_relations).

Tests cover:
- Pagination logic
- Search and ranking
- Rate limiting
- Response caching
- Error handling
- Integration with catalog
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock
from mcp_server.discovery_tools import (
    DiscoveryTools,
    DiscoveryResponse,
    PageInfo,
    TableSummary,
    ResponseCache,
    RateLimiter
)
from mcp_server.catalog import TableInfo, ColumnInfo, ForeignKeyInfo


class TestResponseCache:
    """Test response cache functionality."""
    
    def test_cache_miss(self):
        """Test cache miss on first access."""
        cache = ResponseCache(ttl_seconds=300)
        result = cache.get("list_tables", {"page": 1})
        assert result is None
        assert cache._misses == 1
        assert cache._hits == 0
    
    def test_cache_hit(self):
        """Test cache hit on second access."""
        cache = ResponseCache(ttl_seconds=300)
        
        # Store response
        response = DiscoveryResponse(ok=True, data={"test": "data"})
        cache.set("list_tables", {"page": 1}, response)
        
        # Retrieve response
        cached = cache.get("list_tables", {"page": 1})
        assert cached is not None
        assert cached.data == {"test": "data"}
        assert cached.cached is True
        assert cache._hits == 1
    
    def test_cache_expiration(self):
        """Test cache expiration after TTL."""
        cache = ResponseCache(ttl_seconds=0.1)  # 100ms TTL
        
        # Store response
        response = DiscoveryResponse(ok=True, data={"test": "data"})
        cache.set("list_tables", {"page": 1}, response)
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should be expired
        cached = cache.get("list_tables", {"page": 1})
        assert cached is None
        assert cache._misses == 1
    
    def test_cache_key_uniqueness(self):
        """Test that different arguments create different cache keys."""
        cache = ResponseCache(ttl_seconds=300)
        
        # Store two different responses
        response1 = DiscoveryResponse(ok=True, data={"page": 1})
        response2 = DiscoveryResponse(ok=True, data={"page": 2})
        
        cache.set("list_tables", {"page": 1}, response1)
        cache.set("list_tables", {"page": 2}, response2)
        
        # Retrieve and verify
        cached1 = cache.get("list_tables", {"page": 1})
        cached2 = cache.get("list_tables", {"page": 2})
        
        assert cached1.data == {"page": 1}
        assert cached2.data == {"page": 2}
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = ResponseCache(ttl_seconds=300)
        
        # Generate some hits and misses
        cache.get("list_tables", {"page": 1})  # miss
        
        response = DiscoveryResponse(ok=True, data={"test": "data"})
        cache.set("list_tables", {"page": 1}, response)
        
        cache.get("list_tables", {"page": 1})  # hit
        cache.get("list_tables", {"page": 1})  # hit
        cache.get("list_tables", {"page": 2})  # miss
        
        stats = cache.get_stats()
        assert stats["cache_hits"] == 2
        assert stats["cache_misses"] == 2
        assert stats["hit_ratio"] == 0.5
        assert stats["cache_size"] == 1


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    def test_allow_request_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=10)
        
        # First request should be allowed
        allowed, retry_after = limiter.allow_request()
        assert allowed is True
        assert retry_after is None
    
    def test_rate_limit_exceeded(self):
        """Test that requests exceeding burst size are throttled."""
        limiter = RateLimiter(requests_per_second=1.0, burst_size=2)
        
        # First two requests should be allowed (burst)
        assert limiter.allow_request()[0] is True
        assert limiter.allow_request()[0] is True
        
        # Third request should be throttled
        allowed, retry_after = limiter.allow_request()
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0
    
    def test_rate_limit_recovery(self):
        """Test that rate limiter recovers over time."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=1)
        
        # Exhaust burst
        assert limiter.allow_request()[0] is True
        assert limiter.allow_request()[0] is False
        
        # Wait for recovery
        time.sleep(0.15)  # 150ms should allow 1.5 tokens
        
        # Should be allowed again
        assert limiter.allow_request()[0] is True
    
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=2)
        
        # Make some requests
        limiter.allow_request()  # allowed
        limiter.allow_request()  # allowed
        limiter.allow_request()  # throttled
        
        stats = limiter.get_stats()
        assert stats["total_requests"] == 3
        assert stats["throttled_requests"] == 1
        assert stats["throttle_ratio"] == 1/3


class TestListTables:
    """Test list_tables discovery tool."""
    
    def setup_method(self):
        """Clear cache before each test."""
        DiscoveryTools.clear_cache()
    
    @pytest.mark.asyncio
    async def test_list_tables_basic(self):
        """Test basic table listing."""
        # Mock database adapter with catalog
        db_adapter = Mock()
        catalog = Mock()
        
        # Create mock tables
        table1 = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[
                ColumnInfo("id", "int", False, None, True, False),
                ColumnInfo("name", "varchar", False, None, False, False)
            ],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        table2 = TableInfo(
            schema="public",
            name="orders",
            type="BASE TABLE",
            columns=[
                ColumnInfo("id", "int", False, None, True, False),
                ColumnInfo("customer_id", "int", False, None, False, True)
            ],
            foreign_keys=[
                ForeignKeyInfo("customer_id", "customers", "public", "id")
            ],
            estimated_rows=5000,
            primary_keys=["id"]
        )
        
        catalog.get_table_list.return_value = [table1, table2]
        db_adapter.catalog = catalog
        
        # Call list_tables
        response = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
        
        assert response.ok is True
        assert len(response.data["tables"]) == 2
        assert response.page_info.total_items == 2
        assert response.page_info.page == 1
        assert response.page_info.has_next is False
    
    @pytest.mark.asyncio
    async def test_list_tables_pagination(self):
        """Test table listing with pagination."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create 30 mock tables
        tables = []
        for i in range(30):
            table = TableInfo(
                schema="public",
                name=f"table_{i}",
                type="BASE TABLE",
                columns=[ColumnInfo("id", "int", False, None, True, False)],
                foreign_keys=[],
                estimated_rows=100,
                primary_keys=["id"]
            )
            tables.append(table)
        
        catalog.get_table_list.return_value = tables
        db_adapter.catalog = catalog
        
        # Get page 1 (25 items)
        response1 = await DiscoveryTools.list_tables(db_adapter, page=1, page_size=25)
        assert response1.ok is True
        assert len(response1.data["tables"]) == 25
        assert response1.page_info.total_items == 30
        assert response1.page_info.total_pages == 2
        assert response1.page_info.has_next is True
        assert response1.page_info.has_prev is False
        
        # Get page 2 (5 items)
        response2 = await DiscoveryTools.list_tables(db_adapter, page=2, page_size=25)
        assert response2.ok is True
        assert len(response2.data["tables"]) == 5
        assert response2.page_info.has_next is False
        assert response2.page_info.has_prev is True
    
    @pytest.mark.asyncio
    async def test_list_tables_schema_filter(self):
        """Test table listing with schema filter."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create tables in different schemas
        table1 = TableInfo(
            schema="public",
            name="table1",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=["id"]
        )
        
        table2 = TableInfo(
            schema="private",
            name="table2",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=["id"]
        )
        
        catalog.get_table_list.return_value = [table1, table2]
        db_adapter.catalog = catalog
        
        # Filter by schema
        response = await DiscoveryTools.list_tables(db_adapter, schema="public")
        
        assert response.ok is True
        assert len(response.data["tables"]) == 1
        assert response.data["tables"][0]["schema"] == "public"
    
    @pytest.mark.asyncio
    async def test_list_tables_pattern_filter(self):
        """Test table listing with pattern filter."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create tables with different names
        table1 = TableInfo(
            schema="public",
            name="customer_orders",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=["id"]
        )
        
        table2 = TableInfo(
            schema="public",
            name="products",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=["id"]
        )
        
        catalog.get_table_list.return_value = [table1, table2]
        db_adapter.catalog = catalog
        
        # Filter by pattern
        response = await DiscoveryTools.list_tables(db_adapter, pattern="customer")
        
        assert response.ok is True
        assert len(response.data["tables"]) == 1
        assert "customer" in response.data["tables"][0]["name"].lower()


class TestSearchTables:
    """Test search_tables discovery tool."""
    
    def setup_method(self):
        """Clear cache before each test."""
        DiscoveryTools.clear_cache()
    
    @pytest.mark.asyncio
    async def test_search_tables_basic(self):
        """Test basic table search."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create mock tables
        table1 = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[
                ColumnInfo("id", "int", False, None, True, False),
                ColumnInfo("email", "varchar", False, None, False, False)
            ],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        catalog.search_tables.return_value = [table1]
        db_adapter.catalog = catalog
        
        # Search for "customer"
        response = await DiscoveryTools.search_tables(db_adapter, query="customer")
        
        assert response.ok is True
        assert len(response.data["results"]) == 1
        assert response.data["query"] == "customer"
    
    @pytest.mark.asyncio
    async def test_search_tables_relevance_scoring(self):
        """Test search relevance scoring."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create tables with different relevance
        table1 = TableInfo(
            schema="public",
            name="customer",  # Exact match
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        table2 = TableInfo(
            schema="public",
            name="customer_orders",  # Partial match
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=5000,
            primary_keys=["id"]
        )
        
        table3 = TableInfo(
            schema="public",
            name="orders",  # No match in name
            type="BASE TABLE",
            columns=[ColumnInfo("customer_id", "int", False, None, False, True)],  # Match in column
            foreign_keys=[],
            estimated_rows=3000,
            primary_keys=["id"]
        )
        
        catalog.search_tables.return_value = [table1, table2, table3]
        db_adapter.catalog = catalog
        
        # Search for "customer"
        response = await DiscoveryTools.search_tables(db_adapter, query="customer")
        
        assert response.ok is True
        results = response.data["results"]
        
        # Results should be sorted by relevance
        assert results[0]["name"] == "customer"  # Exact match first
        assert results[0]["relevance_score"] > results[1]["relevance_score"]
    
    @pytest.mark.asyncio
    async def test_search_tables_empty_query(self):
        """Test search with empty query."""
        db_adapter = Mock()
        
        response = await DiscoveryTools.search_tables(db_adapter, query="")
        
        assert response.ok is False
        assert response.error_code == "EMPTY_QUERY"


class TestDescribeTable:
    """Test describe_table discovery tool."""
    
    def setup_method(self):
        """Clear cache before each test."""
        DiscoveryTools.clear_cache()
    
    @pytest.mark.asyncio
    async def test_describe_table_basic(self):
        """Test basic table description."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create mock table
        table = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[
                ColumnInfo("id", "int", False, None, True, False),
                ColumnInfo("name", "varchar", False, None, False, False),
                ColumnInfo("email", "varchar", True, None, False, False)
            ],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        catalog.get_table.return_value = table
        db_adapter.catalog = catalog
        
        # Describe table
        response = await DiscoveryTools.describe_table(db_adapter, table_name="public.customers")
        
        assert response.ok is True
        assert response.data["full_name"] == "public.customers"
        assert len(response.data["columns"]) == 3
        assert response.data["primary_keys"] == ["id"]
    
    @pytest.mark.asyncio
    async def test_describe_table_with_foreign_keys(self):
        """Test table description with foreign keys."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create mock table with foreign keys
        table = TableInfo(
            schema="public",
            name="orders",
            type="BASE TABLE",
            columns=[
                ColumnInfo("id", "int", False, None, True, False),
                ColumnInfo("customer_id", "int", False, None, False, True)
            ],
            foreign_keys=[
                ForeignKeyInfo("customer_id", "customers", "public", "id")
            ],
            estimated_rows=5000,
            primary_keys=["id"]
        )
        
        catalog.get_table.return_value = table
        db_adapter.catalog = catalog
        
        # Describe table
        response = await DiscoveryTools.describe_table(db_adapter, table_name="public.orders")
        
        assert response.ok is True
        assert len(response.data["foreign_keys"]) == 1
        assert response.data["foreign_keys"][0]["column"] == "customer_id"
        assert response.data["foreign_keys"][0]["referenced_table"] == "customers"
    
    @pytest.mark.asyncio
    async def test_describe_table_not_found(self):
        """Test describing non-existent table."""
        db_adapter = Mock()
        catalog = Mock()
        
        catalog.get_table.return_value = None
        catalog.get_table_list.return_value = []
        db_adapter.catalog = catalog
        
        # Try to describe non-existent table
        response = await DiscoveryTools.describe_table(db_adapter, table_name="nonexistent")
        
        assert response.ok is False
        assert response.error_code == "TABLE_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_describe_table_ambiguous_name(self):
        """Test describing table with ambiguous name."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Create tables with same name in different schemas
        table1 = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        table2 = TableInfo(
            schema="private",
            name="customers",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=500,
            primary_keys=["id"]
        )
        
        catalog.get_table_list.return_value = [table1, table2]
        db_adapter.catalog = catalog
        
        # Try to describe without schema
        response = await DiscoveryTools.describe_table(db_adapter, table_name="customers")
        
        assert response.ok is False
        assert response.error_code == "AMBIGUOUS_TABLE_NAME"


class TestListRelations:
    """Test list_relations discovery tool."""
    
    def setup_method(self):
        """Clear cache before each test."""
        DiscoveryTools.clear_cache()
    
    @pytest.mark.asyncio
    async def test_list_relations_basic(self):
        """Test basic relationship listing."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Mock neighbors
        neighbors = ["public.orders", "public.addresses"]
        catalog.get_neighbors.return_value = neighbors
        
        # Mock table list for name resolution
        table = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        catalog.get_table_list.return_value = [table]
        
        db_adapter.catalog = catalog
        
        # List relations
        response = await DiscoveryTools.list_relations(db_adapter, table_name="public.customers")
        
        assert response.ok is True
        assert response.data["neighbor_count"] == 2
        assert "public.orders" in response.data["neighbors"]
        assert "public.addresses" in response.data["neighbors"]
    
    @pytest.mark.asyncio
    async def test_list_relations_no_neighbors(self):
        """Test listing relations for table with no neighbors."""
        db_adapter = Mock()
        catalog = Mock()
        
        # Mock empty neighbors
        catalog.get_neighbors.return_value = []
        
        # Mock table list
        table = TableInfo(
            schema="public",
            name="standalone",
            type="BASE TABLE",
            columns=[ColumnInfo("id", "int", False, None, True, False)],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=["id"]
        )
        catalog.get_table_list.return_value = [table]
        
        db_adapter.catalog = catalog
        
        # List relations
        response = await DiscoveryTools.list_relations(db_adapter, table_name="public.standalone")
        
        assert response.ok is True
        assert response.data["neighbor_count"] == 0
    
    @pytest.mark.asyncio
    async def test_list_relations_table_not_found(self):
        """Test listing relations for non-existent table."""
        db_adapter = Mock()
        catalog = Mock()
        
        catalog.get_neighbors.return_value = None
        catalog.get_table_list.return_value = []
        db_adapter.catalog = catalog
        
        # Try to list relations for non-existent table
        response = await DiscoveryTools.list_relations(db_adapter, table_name="nonexistent")
        
        assert response.ok is False
        assert response.error_code == "TABLE_NOT_FOUND"


class TestCatalogNotInitialized:
    """Test error handling when catalog is not initialized."""
    
    def setup_method(self):
        """Clear cache before each test."""
        DiscoveryTools.clear_cache()
    
    @pytest.mark.asyncio
    async def test_list_tables_no_catalog(self):
        """Test list_tables when catalog is not initialized."""
        db_adapter = Mock()
        db_adapter.catalog = None
        
        response = await DiscoveryTools.list_tables(db_adapter)
        
        assert response.ok is False
        assert response.error_code == "CATALOG_NOT_INITIALIZED"
    
    @pytest.mark.asyncio
    async def test_search_tables_no_catalog(self):
        """Test search_tables when catalog is not initialized."""
        db_adapter = Mock()
        db_adapter.catalog = None
        
        response = await DiscoveryTools.search_tables(db_adapter, query="test")
        
        assert response.ok is False
        assert response.error_code == "CATALOG_NOT_INITIALIZED"
    
    @pytest.mark.asyncio
    async def test_describe_table_no_catalog(self):
        """Test describe_table when catalog is not initialized."""
        db_adapter = Mock()
        db_adapter.catalog = None
        
        response = await DiscoveryTools.describe_table(db_adapter, table_name="test")
        
        assert response.ok is False
        assert response.error_code == "CATALOG_NOT_INITIALIZED"
    
    @pytest.mark.asyncio
    async def test_list_relations_no_catalog(self):
        """Test list_relations when catalog is not initialized."""
        db_adapter = Mock()
        db_adapter.catalog = None
        
        response = await DiscoveryTools.list_relations(db_adapter, table_name="test")
        
        assert response.ok is False
        assert response.error_code == "CATALOG_NOT_INITIALIZED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])