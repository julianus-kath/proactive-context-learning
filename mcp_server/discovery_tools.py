"""
Phase 4: MCP Discovery Tools - Paged, searchable, and drillable schema discovery.

This module provides catalog-backed discovery tools that:
- Return paged summaries instead of full schema dumps
- Support keyword search across tables
- Provide targeted drill-downs for specific tables
- Use O(1) catalog lookups (no DB hits after warmup)
- Include rate limiting and response caching

Architecture alignment:
- Proxy-only separation: No business logic, just data retrieval
- Database abstraction: Works with catalog (both PostgreSQL and SQL Server)
- Read-only, safe queries: Only reads from catalog (no DB queries)
- JSON as single data format: All responses are JSON
- Security & privacy: No sensitive data exposed
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from functools import lru_cache
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    """Pagination metadata."""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass
class TableSummary:
    """Lightweight table summary for list views."""
    schema: str
    name: str
    full_name: str
    type: str
    estimated_rows: int
    column_count: int
    has_foreign_keys: bool
    has_primary_keys: bool


@dataclass
class DiscoveryResponse:
    """Standard response envelope for discovery tools."""
    ok: bool
    data: Any
    page_info: Optional[PageInfo] = None
    execution_time_ms: float = 0.0
    cached: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
    retry_after: Optional[float] = None  # Phase 6: Exponential backoff header
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "ok": self.ok,
            "data": self.data,
            "execution_time_ms": self.execution_time_ms,
            "cached": self.cached
        }
        
        if self.page_info:
            result["page_info"] = asdict(self.page_info)
        
        if self.error:
            result["error"] = self.error
            result["error_code"] = self.error_code
            
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        
        return result


class ResponseCache:
    """Simple in-memory response cache with TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize response cache.
        
        Args:
            ttl_seconds: Time-to-live for cached responses (default: 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate cache key from tool name and arguments."""
        # Sort arguments for consistent hashing
        args_str = json.dumps(arguments, sort_keys=True)
        key_str = f"{tool_name}:{args_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[DiscoveryResponse]:
        """Get cached response if available and not expired."""
        key = self._make_key(tool_name, arguments)
        
        if key in self._cache:
            response, timestamp = self._cache[key]
            age = time.time() - timestamp
            
            if age < self.ttl_seconds:
                self._hits += 1
                # Mark as cached
                response.cached = True
                return response
            else:
                # Expired, remove from cache
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, tool_name: str, arguments: Dict[str, Any], response: DiscoveryResponse):
        """Cache a response."""
        key = self._make_key(tool_name, arguments)
        self._cache[key] = (response, time.time())
    
    def clear(self):
        """Clear all cached responses."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_ratio = self._hits / total if total > 0 else 0.0
        
        return {
            "cache_size": len(self._cache),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_ratio": hit_ratio,
            "ttl_seconds": self.ttl_seconds
        }


class RateLimiter:
    """Simple token bucket rate limiter."""
    
    def __init__(self, requests_per_second: float = 10.0, burst_size: int = 20):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_second: Average requests per second allowed
            burst_size: Maximum burst size (tokens in bucket)
        """
        self.rate = requests_per_second
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_update = time.time()
        self._total_requests = 0
        self._throttled_requests = 0
    
    def allow_request(self) -> Tuple[bool, Optional[float]]:
        """
        Check if request is allowed.
        
        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        self._total_requests += 1
        
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, None
        else:
            self._throttled_requests += 1
            # Calculate retry after time
            retry_after = (1.0 - self.tokens) / self.rate
            return False, retry_after
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        throttle_ratio = self._throttled_requests / self._total_requests if self._total_requests > 0 else 0.0
        
        return {
            "rate_limit_rps": self.rate,
            "burst_size": self.burst_size,
            "current_tokens": self.tokens,
            "total_requests": self._total_requests,
            "throttled_requests": self._throttled_requests,
            "throttle_ratio": throttle_ratio
        }


class DiscoveryTools:
    """
    Phase 4 discovery tools backed by Phase 3 catalog.
    
    Provides paged, searchable, and drillable schema discovery without hitting the database.
    """
    
    # Global response cache and rate limiter
    _response_cache = ResponseCache(ttl_seconds=300)  # 5 minutes
    _rate_limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
    
    @staticmethod
    async def list_tables(
        db_adapter,
        page: int = 1,
        page_size: int = 25,
        schema: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> DiscoveryResponse:
        """
        List tables with pagination and optional filtering.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            page: Page number (1-indexed)
            page_size: Number of items per page (max: 100)
            schema: Filter by schema name (optional)
            pattern: Filter by table name pattern (optional, case-insensitive)
        
        Returns:
            DiscoveryResponse with paged table summaries
        """
        start_time = time.time()
        
        # Check rate limit
        allowed, retry_after = DiscoveryTools._rate_limiter.allow_request()
        if not allowed:
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after:.2f} seconds.",
                error_code="RATE_LIMIT_EXCEEDED",
                retry_after=retry_after,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Check cache
        cache_key_args = {"page": page, "page_size": page_size, "schema": schema, "pattern": pattern}
        cached_response = DiscoveryTools._response_cache.get("list_tables", cache_key_args)
        if cached_response:
            return cached_response
        
        try:
            # Validate parameters
            page = max(1, page)
            page_size = min(max(1, page_size), 100)  # Cap at 100
            
            # Get catalog
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog not initialized",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            catalog = db_adapter.catalog
            
            # Get all tables from catalog
            all_tables = catalog.get_table_list()
            
            # Apply filters
            filtered_tables = []
            for table in all_tables:
                # Schema filter (table is a dict, not an object)
                if schema and table['schema'].lower() != schema.lower():
                    continue
                
                # Pattern filter (case-insensitive)
                if pattern and pattern.lower() not in table['name'].lower():
                    continue
                
                # Create summary
                summary = TableSummary(
                    schema=table['schema'],
                    name=table['name'],
                    full_name=table['full_name'],
                    type=table['type'],
                    estimated_rows=table['estimated_rows'],
                    column_count=table.get('column_count', 0),
                    has_foreign_keys=table.get('fk_count', 0) > 0,
                    has_primary_keys=False  # Not available in list_tables
                )
                filtered_tables.append(summary)
            
            # Calculate pagination
            total_items = len(filtered_tables)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
            
            # Ensure page is within bounds
            page = min(page, total_pages)
            
            # Get page slice
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_tables = filtered_tables[start_idx:end_idx]
            
            # Create page info
            page_info = PageInfo(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
            # Convert to dict
            data = {
                "tables": [asdict(t) for t in page_tables],
                "filters": {
                    "schema": schema,
                    "pattern": pattern
                }
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            response = DiscoveryResponse(
                ok=True,
                data=data,
                page_info=page_info,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
            # Cache response
            DiscoveryTools._response_cache.set("list_tables", cache_key_args, response)
            
            return response
            
        except Exception as e:
            logger.error(f"list_tables failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def search_tables(
        db_adapter,
        query: str,
        page: int = 1,
        page_size: int = 25
    ) -> DiscoveryResponse:
        """
        Search tables by keyword (table name, schema, or column names).
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            query: Search query (case-insensitive)
            page: Page number (1-indexed)
            page_size: Number of items per page (max: 100)
        
        Returns:
            DiscoveryResponse with ranked search results
        """
        start_time = time.time()
        
        # Check rate limit
        allowed, retry_after = DiscoveryTools._rate_limiter.allow_request()
        if not allowed:
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after:.2f} seconds.",
                error_code="RATE_LIMIT_EXCEEDED",
                retry_after=retry_after,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Check cache
        cache_key_args = {"query": query, "page": page, "page_size": page_size}
        cached_response = DiscoveryTools._response_cache.get("search_tables", cache_key_args)
        if cached_response:
            return cached_response
        
        try:
            # Validate parameters
            if not query or not query.strip():
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Search query is required",
                    error_code="EMPTY_QUERY",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            query = query.strip().lower()
            page = max(1, page)
            page_size = min(max(1, page_size), 100)
            
            # Get catalog
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog not initialized",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            catalog = db_adapter.catalog
            
            # Use catalog's search_tables method
            matching_tables = catalog.search_tables(query)
            
            # Create summaries with relevance scores
            results = []
            for table in matching_tables:
                # table is a dict with: schema, name, full_name, type, estimated_rows
                # Calculate relevance score
                score = 0
                
                # Exact table name match (highest priority)
                query_lower = query.lower()
                table_name_lower = table['name'].lower()
                if query_lower == table_name_lower:
                    score += 100
                elif query_lower in table_name_lower:
                    score += 50
                
                # Schema match
                if query_lower in table['schema'].lower():
                    score += 20
                
                # Try to fetch full table details for column-level matching
                matched_columns = []
                try:
                    full_table = catalog.get_table(table['schema'], table['name'])
                    if full_table and 'columns' in full_table:
                        # Column name matches
                        for col in full_table['columns']:
                            col_name_lower = col.get('name', '').lower()
                            if query_lower == col_name_lower:
                                score += 30
                            elif query_lower in col_name_lower:
                                score += 10
                            
                            # Column type matches
                            col_type_lower = col.get('type', '').lower()
                            if query_lower in col_type_lower:
                                score += 5
                            
                            # Track matched columns
                            if query_lower in col_name_lower or query_lower in col_type_lower:
                                matched_columns.append(col_name_lower)
                except Exception as col_error:
                    logger.warning(f"Could not fetch column details for {table['schema']}.{table['name']}: {col_error}")
                
                summary = {
                    "schema": table['schema'],
                    "name": table['name'],
                    "full_name": table['full_name'],
                    "type": table['type'],
                    "estimated_rows": table['estimated_rows'],
                    "column_count": table.get('column_count', 0),
                    "has_foreign_keys": False,  # Not available in search results
                    "has_primary_keys": False,  # Not available in search results
                    "relevance_score": score,
                    "matched_columns": matched_columns[:5]  # Top 5 matched columns
                }
                results.append(summary)
            
            # Sort by relevance score (descending)
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Calculate pagination
            total_items = len(results)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
            page = min(page, total_pages)
            
            # Get page slice
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_results = results[start_idx:end_idx]
            
            # Create page info
            page_info = PageInfo(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
            data = {
                "query": query,
                "results": page_results
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            response = DiscoveryResponse(
                ok=True,
                data=data,
                page_info=page_info,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
            # Cache response
            DiscoveryTools._response_cache.set("search_tables", cache_key_args, response)
            
            return response
            
        except Exception as e:
            logger.error(f"search_tables failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def describe_table(
        db_adapter,
        table_name: str,
        include_sample: bool = False
    ) -> DiscoveryResponse:
        """
        Get detailed information about a specific table.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            table_name: Fully qualified table name (schema.table) or just table name
            include_sample: Whether to include sample data (requires DB query)
        
        Returns:
            DiscoveryResponse with table details
        """
        start_time = time.time()
        
        # Check rate limit
        allowed, retry_after = DiscoveryTools._rate_limiter.allow_request()
        if not allowed:
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after:.2f} seconds.",
                error_code="RATE_LIMIT_EXCEEDED",
                retry_after=retry_after,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Check cache (only if not including sample data)
        cache_key_args = {"table_name": table_name, "include_sample": include_sample}
        if not include_sample:
            cached_response = DiscoveryTools._response_cache.get("describe_table", cache_key_args)
            if cached_response:
                return cached_response
        
        try:
            # Validate parameters
            if not table_name or not table_name.strip():
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Table name is required",
                    error_code="EMPTY_TABLE_NAME",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            table_name = table_name.strip()
            
            # Get catalog
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog not initialized",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            catalog = db_adapter.catalog
            
            # Parse table name (schema.table or just table)
            if '.' in table_name:
                schema, name = table_name.split('.', 1)
            else:
                # Try to find table in any schema
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t.name.lower() == table_name.lower()]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Table '{table_name}' not found",
                        error_code="TABLE_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                if len(matching) > 1:
                    schemas = [t.schema for t in matching]
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Ambiguous table name '{table_name}'. Found in schemas: {', '.join(schemas)}. Please specify schema.table",
                        error_code="AMBIGUOUS_TABLE_NAME",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0].schema
                name = matching[0].name
            
            # Get table from catalog
            table = catalog.get_table(schema, name)
            
            if not table:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"Table '{schema}.{name}' not found",
                    error_code="TABLE_NOT_FOUND",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Build response data
            data = {
                "schema": table.schema,
                "name": table.name,
                "full_name": table.full_name(),
                "type": table.type,
                "estimated_rows": table.estimated_rows,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "nullable": col.nullable,
                        "default": col.default,
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key
                    }
                    for col in table.columns
                ],
                "primary_keys": table.primary_keys,
                "foreign_keys": [
                    {
                        "column": fk.column,
                        "referenced_table": fk.referenced_table,
                        "referenced_schema": fk.referenced_schema,
                        "referenced_column": fk.referenced_column,
                        "referenced_full_name": f"{fk.referenced_schema}.{fk.referenced_table}"
                    }
                    for fk in table.foreign_keys
                ],
                "top_columns": table.get_top_columns(limit=10)
            }
            
            # Include sample data if requested (requires DB query)
            if include_sample:
                try:
                    sample_query = f"SELECT * FROM {table.full_name()} LIMIT 5"
                    sample_rows = await db_adapter.fetch(sample_query, limit=5)
                    data["sample_data"] = sample_rows
                except Exception as e:
                    logger.warning(f"Failed to fetch sample data for {table.full_name()}: {e}")
                    data["sample_data"] = None
                    data["sample_error"] = str(e)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            response = DiscoveryResponse(
                ok=True,
                data=data,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
            # Cache response (only if not including sample data)
            if not include_sample:
                DiscoveryTools._response_cache.set("describe_table", cache_key_args, response)
            
            return response
            
        except Exception as e:
            logger.error(f"describe_table failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def list_relations(
        db_adapter,
        table_name: str
    ) -> DiscoveryResponse:
        """
        Get relationships (neighbors) for a specific table.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            table_name: Fully qualified table name (schema.table) or just table name
        
        Returns:
            DiscoveryResponse with related tables and join columns
        """
        start_time = time.time()
        
        # Check rate limit
        allowed, retry_after = DiscoveryTools._rate_limiter.allow_request()
        if not allowed:
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after:.2f} seconds.",
                error_code="RATE_LIMIT_EXCEEDED",
                retry_after=retry_after,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Check cache
        cache_key_args = {"table_name": table_name}
        cached_response = DiscoveryTools._response_cache.get("list_relations", cache_key_args)
        if cached_response:
            return cached_response
        
        try:
            # Validate parameters
            if not table_name or not table_name.strip():
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Table name is required",
                    error_code="EMPTY_TABLE_NAME",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            table_name = table_name.strip()
            
            # Get catalog
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog not initialized",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            catalog = db_adapter.catalog
            
            # Parse table name
            if '.' in table_name:
                schema, name = table_name.split('.', 1)
            else:
                # Try to find table in any schema
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t.name.lower() == table_name.lower()]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Table '{table_name}' not found",
                        error_code="TABLE_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                if len(matching) > 1:
                    schemas = [t.schema for t in matching]
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Ambiguous table name '{table_name}'. Found in schemas: {', '.join(schemas)}",
                        error_code="AMBIGUOUS_TABLE_NAME",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0].schema
                name = matching[0].name
            
            # Get neighbors from catalog
            neighbors = catalog.get_neighbors(schema, name)
            
            if neighbors is None:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"Table '{schema}.{name}' not found",
                    error_code="TABLE_NOT_FOUND",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Build response data
            data = {
                "table": f"{schema}.{name}",
                "neighbor_count": len(neighbors),
                "neighbors": neighbors
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            response = DiscoveryResponse(
                ok=True,
                data=data,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
            # Cache response
            DiscoveryTools._response_cache.set("list_relations", cache_key_args, response)
            
            return response
            
        except Exception as e:
            logger.error(f"list_relations failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get statistics for response cache and rate limiter."""
        return {
            "response_cache": DiscoveryTools._response_cache.get_stats(),
            "rate_limiter": DiscoveryTools._rate_limiter.get_stats()
        }
    
    @staticmethod
    def clear_cache():
        """Clear response cache."""
        DiscoveryTools._response_cache.clear()