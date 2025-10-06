"""
Schema Cache Module - In-Memory Caching with Redis-Ready Interface

This module provides schema caching to eliminate redundant schema discovery calls.
It stores both full schema text and a structured schema index for fast lookups.

Design Decisions:
-----------------
1. **In-Memory First**: Uses Python dict with threading.Lock for simplicity
   - PRO: Zero external dependencies, instant setup
   - CON: Not shared across processes
   - DECISION: Start simple, add Redis later when needed

2. **TTL-Based Expiration**: Configurable cache lifetime (default: 1 hour)
   - PRO: Balances performance with schema freshness
   - CON: May serve stale data if schema changes frequently
   - DECISION: 1 hour is reasonable for ERP databases (schema rarely changes)

3. **Pluggable Backend**: Interface designed for easy Redis integration
   - PRO: Can swap to Redis without changing calling code
   - CON: Slightly more complex interface
   - DECISION: Worth it for future-proofing

4. **Schema Index Structure**: Stores tables → {columns, types, keys, row_count}
   - PRO: Enables fast table lookups without parsing full schema text
   - CON: Requires more memory
   - DECISION: Memory is cheap, speed is critical

Environment Variables:
----------------------
- SCHEMA_CACHE_TTL: Cache TTL in seconds (default: 3600)
- SCHEMA_CACHE_BACKEND: 'memory' or 'redis' (default: 'memory')
- REDIS_URL: Redis connection URL (required if backend=redis)

Usage:
------
    from app.db.schema_cache import get_schema_cache
    
    cache = get_schema_cache()
    
    # Store schema
    cache.set_schema("full_schema_text", schema_index)
    
    # Retrieve schema
    schema_text, schema_index = cache.get_schema()
    
    # Check if cached
    if cache.is_cached():
        print("Using cached schema")
"""

import os
import time
import json
import logging
import threading
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class TableInfo:
    """Structured information about a database table."""
    schema_name: str
    table_name: str
    table_type: str  # 'BASE TABLE', 'VIEW', etc.
    columns: List[Dict[str, Any]]  # List of column definitions
    primary_keys: List[str]  # List of primary key column names
    foreign_keys: List[Dict[str, str]]  # List of foreign key relationships
    row_count: Optional[int] = None  # Approximate row count (if available)
    last_updated: Optional[str] = None  # Last update timestamp (if available)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TableInfo':
        """Create from dictionary."""
        return cls(**data)


class SchemaCache:
    """
    Base class for schema caching implementations.
    
    This defines the interface that all cache backends must implement.
    """
    
    def set_schema(self, schema_text: str, schema_index: Dict[str, TableInfo]) -> None:
        """
        Store schema in cache.
        
        Args:
            schema_text: Full schema as formatted text
            schema_index: Structured index of tables and columns
        """
        raise NotImplementedError
    
    def get_schema(self) -> Tuple[Optional[str], Optional[Dict[str, TableInfo]]]:
        """
        Retrieve schema from cache.
        
        Returns:
            Tuple of (schema_text, schema_index) or (None, None) if not cached
        """
        raise NotImplementedError
    
    def is_cached(self) -> bool:
        """Check if schema is currently cached and valid."""
        raise NotImplementedError
    
    def invalidate(self) -> None:
        """Invalidate (clear) the cache."""
        raise NotImplementedError
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """
        Get information about a specific table.
        
        Args:
            table_name: Name of the table (can be schema-qualified: 'schema.table')
        
        Returns:
            TableInfo object or None if not found
        """
        raise NotImplementedError


class InMemorySchemaCache(SchemaCache):
    """
    In-memory schema cache using Python dict with TTL support.
    
    Thread-safe implementation suitable for single-process applications.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize in-memory cache.
        
        Args:
            ttl_seconds: Time-to-live for cached data in seconds (default: 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._schema_text: Optional[str] = None
        self._schema_index: Optional[Dict[str, TableInfo]] = None
        self._cached_at: Optional[float] = None
        
        logger.info(f"InMemorySchemaCache initialized with TTL={ttl_seconds}s")
    
    def set_schema(self, schema_text: str, schema_index: Dict[str, TableInfo]) -> None:
        """Store schema in memory."""
        with self._lock:
            self._schema_text = schema_text
            self._schema_index = schema_index
            self._cached_at = time.time()
            
            table_count = len(schema_index)
            logger.info(f"Schema cached: {table_count} tables indexed at {datetime.now().isoformat()}")
    
    def get_schema(self) -> Tuple[Optional[str], Optional[Dict[str, TableInfo]]]:
        """Retrieve schema from memory if not expired."""
        with self._lock:
            if not self._is_valid():
                return None, None
            
            logger.debug(f"Schema cache hit (age: {self._get_age():.1f}s)")
            return self._schema_text, self._schema_index
    
    def is_cached(self) -> bool:
        """Check if schema is cached and valid."""
        with self._lock:
            return self._is_valid()
    
    def invalidate(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._schema_text = None
            self._schema_index = None
            self._cached_at = None
            logger.info("Schema cache invalidated")
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get information about a specific table."""
        with self._lock:
            if not self._is_valid() or not self._schema_index:
                return None
            
            # Try exact match first
            if table_name in self._schema_index:
                return self._schema_index[table_name]
            
            # Try case-insensitive match
            table_name_lower = table_name.lower()
            for key, value in self._schema_index.items():
                if key.lower() == table_name_lower:
                    return value
            
            # Try matching without schema prefix
            if '.' not in table_name:
                for key, value in self._schema_index.items():
                    if '.' in key:
                        _, tbl = key.rsplit('.', 1)
                        if tbl.lower() == table_name_lower:
                            return value
            
            return None
    
    def _is_valid(self) -> bool:
        """Check if cached data is still valid (not expired)."""
        if self._cached_at is None or self._schema_text is None:
            return False
        
        age = time.time() - self._cached_at
        return age < self.ttl_seconds
    
    def _get_age(self) -> float:
        """Get age of cached data in seconds."""
        if self._cached_at is None:
            return float('inf')
        return time.time() - self._cached_at


class RedisSchemaCache(SchemaCache):
    """
    Redis-based schema cache for multi-process applications.
    
    NOTE: This is a placeholder for future implementation.
    Requires redis-py package: pip install redis
    """
    
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL (e.g., 'redis://localhost:6379/0')
            ttl_seconds: Time-to-live for cached data in seconds
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        
        # TODO: Initialize Redis connection
        # import redis
        # self.client = redis.from_url(redis_url)
        
        raise NotImplementedError(
            "Redis cache backend not yet implemented. "
            "Use SCHEMA_CACHE_BACKEND=memory for now."
        )
    
    def set_schema(self, schema_text: str, schema_index: Dict[str, TableInfo]) -> None:
        """Store schema in Redis."""
        # TODO: Implement Redis storage
        # self.client.setex('schema_text', self.ttl_seconds, schema_text)
        # self.client.setex('schema_index', self.ttl_seconds, json.dumps(...))
        raise NotImplementedError
    
    def get_schema(self) -> Tuple[Optional[str], Optional[Dict[str, TableInfo]]]:
        """Retrieve schema from Redis."""
        # TODO: Implement Redis retrieval
        raise NotImplementedError
    
    def is_cached(self) -> bool:
        """Check if schema exists in Redis."""
        # TODO: Implement Redis check
        raise NotImplementedError
    
    def invalidate(self) -> None:
        """Clear schema from Redis."""
        # TODO: Implement Redis invalidation
        raise NotImplementedError
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get table info from Redis."""
        # TODO: Implement Redis table lookup
        raise NotImplementedError


# Global cache instance (singleton pattern)
_cache_instance: Optional[SchemaCache] = None
_cache_lock = threading.Lock()


def get_schema_cache() -> SchemaCache:
    """
    Get the global schema cache instance (singleton).
    
    The cache backend is determined by the SCHEMA_CACHE_BACKEND environment variable:
    - 'memory' (default): In-memory cache
    - 'redis': Redis cache (requires REDIS_URL)
    
    Returns:
        SchemaCache instance
    """
    global _cache_instance
    
    if _cache_instance is not None:
        return _cache_instance
    
    with _cache_lock:
        # Double-check pattern
        if _cache_instance is not None:
            return _cache_instance
        
        # Read configuration from environment
        backend = os.getenv('SCHEMA_CACHE_BACKEND', 'memory').lower()
        ttl_seconds = int(os.getenv('SCHEMA_CACHE_TTL', '3600'))
        
        if backend == 'memory':
            _cache_instance = InMemorySchemaCache(ttl_seconds=ttl_seconds)
            logger.info(f"Schema cache initialized: backend=memory, ttl={ttl_seconds}s")
        
        elif backend == 'redis':
            redis_url = os.getenv('REDIS_URL')
            if not redis_url:
                logger.warning("REDIS_URL not set, falling back to in-memory cache")
                _cache_instance = InMemorySchemaCache(ttl_seconds=ttl_seconds)
            else:
                try:
                    _cache_instance = RedisSchemaCache(redis_url=redis_url, ttl_seconds=ttl_seconds)
                    logger.info(f"Schema cache initialized: backend=redis, ttl={ttl_seconds}s")
                except NotImplementedError:
                    logger.warning("Redis cache not implemented yet, falling back to in-memory")
                    _cache_instance = InMemorySchemaCache(ttl_seconds=ttl_seconds)
        
        else:
            logger.warning(f"Unknown cache backend '{backend}', using in-memory")
            _cache_instance = InMemorySchemaCache(ttl_seconds=ttl_seconds)
        
        return _cache_instance


def reset_cache() -> None:
    """
    Reset the global cache instance.
    
    Useful for testing or when switching cache backends.
    """
    global _cache_instance
    with _cache_lock:
        if _cache_instance:
            _cache_instance.invalidate()
        _cache_instance = None
        logger.info("Global schema cache reset")