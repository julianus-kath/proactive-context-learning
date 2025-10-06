"""
Integration Tests for Schema Cache

Tests the schema caching functionality to ensure:
1. Cache hits on second query (no extra schema calls)
2. TTL expiration works correctly
3. Concurrent access is thread-safe
4. Cache invalidation works

Run with: pytest tests/integration/test_schema_cache.py -v
"""

import pytest
import time
import os
import sys
from threading import Thread
from typing import Dict, Any

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

from app.db.schema_cache import (
    get_schema_cache,
    reset_cache,
    InMemorySchemaCache,
    TableInfo
)


@pytest.fixture
def sample_schema_index() -> Dict[str, TableInfo]:
    """Create a sample schema index for testing."""
    return {
        'dbo.customers': TableInfo(
            schema_name='dbo',
            table_name='customers',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'customer_id', 'data_type': 'int', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': None},
                {'column_name': 'customer_name', 'data_type': 'varchar', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': 100},
                {'column_name': 'email', 'data_type': 'varchar', 'is_nullable': 'YES', 'column_default': None, 'character_maximum_length': 255},
            ],
            primary_keys=['customer_id'],
            foreign_keys=[],
            row_count=1000
        ),
        'dbo.sales': TableInfo(
            schema_name='dbo',
            table_name='sales',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'sale_id', 'data_type': 'int', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': None},
                {'column_name': 'customer_id', 'data_type': 'int', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': None},
                {'column_name': 'sale_date', 'data_type': 'date', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': None},
                {'column_name': 'total_amount', 'data_type': 'decimal', 'is_nullable': 'NO', 'column_default': None, 'character_maximum_length': None},
            ],
            primary_keys=['sale_id'],
            foreign_keys=[
                {'column_name': 'customer_id', 'referenced_table': 'customers', 'referenced_column': 'customer_id'}
            ],
            row_count=5000
        )
    }


@pytest.fixture(autouse=True)
def reset_cache_before_test():
    """Reset cache before each test."""
    reset_cache()
    yield
    reset_cache()


def test_cache_initialization():
    """Test that cache initializes correctly."""
    cache = get_schema_cache()
    assert cache is not None
    assert isinstance(cache, InMemorySchemaCache)
    assert not cache.is_cached()


def test_cache_set_and_get(sample_schema_index):
    """Test basic cache set and get operations."""
    cache = get_schema_cache()
    
    schema_text = "Test schema text"
    
    # Set schema
    cache.set_schema(schema_text, sample_schema_index)
    
    # Verify it's cached
    assert cache.is_cached()
    
    # Get schema
    retrieved_text, retrieved_index = cache.get_schema()
    
    assert retrieved_text == schema_text
    assert retrieved_index == sample_schema_index
    assert len(retrieved_index) == 2


def test_cache_hit_on_second_query(sample_schema_index):
    """
    MILESTONE 1 ACCEPTANCE CRITERIA:
    First query indexes once, next queries use cache.
    """
    cache = get_schema_cache()
    
    schema_text = "Full database schema"
    
    # First query - cache miss
    assert not cache.is_cached()
    cache.set_schema(schema_text, sample_schema_index)
    
    # Second query - cache hit
    assert cache.is_cached()
    text1, index1 = cache.get_schema()
    
    # Third query - still cache hit
    assert cache.is_cached()
    text2, index2 = cache.get_schema()
    
    # Verify same data returned
    assert text1 == text2 == schema_text
    assert index1 == index2 == sample_schema_index


def test_cache_ttl_expiration(sample_schema_index):
    """Test that cache expires after TTL."""
    # Create cache with 1 second TTL
    cache = InMemorySchemaCache(ttl_seconds=1)
    
    schema_text = "Test schema"
    cache.set_schema(schema_text, sample_schema_index)
    
    # Should be cached immediately
    assert cache.is_cached()
    
    # Wait for TTL to expire
    time.sleep(1.1)
    
    # Should no longer be cached
    assert not cache.is_cached()
    
    # Get should return None
    text, index = cache.get_schema()
    assert text is None
    assert index is None


def test_cache_invalidation(sample_schema_index):
    """Test manual cache invalidation."""
    cache = get_schema_cache()
    
    schema_text = "Test schema"
    cache.set_schema(schema_text, sample_schema_index)
    
    assert cache.is_cached()
    
    # Invalidate cache
    cache.invalidate()
    
    assert not cache.is_cached()
    
    # Get should return None
    text, index = cache.get_schema()
    assert text is None
    assert index is None


def test_get_table_info(sample_schema_index):
    """Test retrieving specific table information."""
    cache = get_schema_cache()
    cache.set_schema("schema text", sample_schema_index)
    
    # Test exact match
    table_info = cache.get_table_info('dbo.customers')
    assert table_info is not None
    assert table_info.table_name == 'customers'
    assert table_info.schema_name == 'dbo'
    assert len(table_info.columns) == 3
    
    # Test case-insensitive match
    table_info = cache.get_table_info('DBO.CUSTOMERS')
    assert table_info is not None
    
    # Test without schema prefix
    table_info = cache.get_table_info('sales')
    assert table_info is not None
    assert table_info.table_name == 'sales'
    
    # Test non-existent table
    table_info = cache.get_table_info('nonexistent')
    assert table_info is None


def test_concurrent_access(sample_schema_index):
    """Test thread-safe concurrent access to cache."""
    cache = get_schema_cache()
    cache.set_schema("initial schema", sample_schema_index)
    
    results = []
    errors = []
    
    def read_cache():
        try:
            for _ in range(10):
                text, index = cache.get_schema()
                if text:
                    results.append(text)
        except Exception as e:
            errors.append(e)
    
    # Create multiple threads
    threads = [Thread(target=read_cache) for _ in range(5)]
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join()
    
    # Verify no errors
    assert len(errors) == 0
    
    # Verify all reads succeeded
    assert len(results) == 50  # 5 threads * 10 reads each
    assert all(r == "initial schema" for r in results)


def test_singleton_pattern():
    """Test that get_schema_cache returns the same instance."""
    cache1 = get_schema_cache()
    cache2 = get_schema_cache()
    
    assert cache1 is cache2


def test_cache_with_empty_index():
    """Test cache behavior with empty schema index."""
    cache = get_schema_cache()
    
    cache.set_schema("empty schema", {})
    
    assert cache.is_cached()
    text, index = cache.get_schema()
    assert text == "empty schema"
    assert index == {}


def test_cache_performance():
    """Test that cache provides significant performance benefit."""
    cache = get_schema_cache()
    
    # Large schema text
    large_schema = "Table: " + "\n".join([f"column_{i} int" for i in range(1000)])
    large_index = {f"table_{i}": TableInfo(
        schema_name='dbo',
        table_name=f'table_{i}',
        table_type='BASE TABLE',
        columns=[],
        primary_keys=[],
        foreign_keys=[]
    ) for i in range(100)}
    
    # Set cache
    start = time.time()
    cache.set_schema(large_schema, large_index)
    set_time = time.time() - start
    
    # Get from cache (should be much faster)
    start = time.time()
    for _ in range(100):
        cache.get_schema()
    get_time = time.time() - start
    
    # Cache retrieval should be very fast
    assert get_time < 0.1  # 100 retrievals in < 100ms
    print(f"\nCache performance: set={set_time*1000:.2f}ms, 100 gets={get_time*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])