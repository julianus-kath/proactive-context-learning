"""
MCP Discovery Tools - Paged, searchable, and drillable schema discovery.

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
from decimal import Decimal
from datetime import datetime, date

logger = logging.getLogger(__name__)


def convert_row_to_json_serializable(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert database row to JSON-serializable format (handle Decimal, datetime, etc.)."""
    result = {}
    for key, value in row.items():
        if value is None:
            result[key] = None
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, (datetime, date)):
            result[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
        else:
            result[key] = value
    return result


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
        pattern: Optional[str] = None,
        include_empty: bool = False,
        min_rows: int = 1,
    ) -> DiscoveryResponse:
        """
        List tables with pagination and optional filtering.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            page: Page number (1-indexed)
            page_size: Number of items per page (max: 100)
            schema: Filter by schema name (optional)
            pattern: Filter by table name pattern (optional, case-insensitive)
            include_empty: Include tables with zero rows when True (default False)
            min_rows: Minimum estimated rows to include when include_empty=False (default 1)
        
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
        cache_key_args = {"page": page, "page_size": page_size, "schema": schema, "pattern": pattern, "include_empty": include_empty, "min_rows": min_rows}
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
            threshold = 0 if include_empty else max(int(min_rows or 1), 1)

            # Stats: count candidates and empty tables before thresholding
            total_candidates = 0
            empty_candidates = 0

            for table in all_tables:
                # Schema filter (table is a dict, not an object)
                if schema and table['schema'].lower() != schema.lower():
                    continue
                
                # Pattern filter (case-insensitive)
                if pattern and pattern.lower() not in table['name'].lower():
                    continue
                
                # Count candidate and empties (pre-threshold)
                est = int(table.get('estimated_rows') or 0)
                total_candidates += 1
                if est == 0:
                    empty_candidates += 1

                # Estimated rows filter (apply threshold)
                if est < threshold:
                    continue
                
                # Create summary
                summary = TableSummary(
                    schema=table['schema'],
                    name=table['name'],
                    full_name=table['full_name'],
                    type=table['type'],
                    estimated_rows=est,
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
                    "pattern": pattern,
                    "include_empty": include_empty,
                    "min_rows": threshold,
                },
                "stats": {
                    "total_candidates": total_candidates,
                    "empty_candidates": empty_candidates,
                    "empty_ratio": (empty_candidates / total_candidates) if total_candidates > 0 else 0.0
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
        Search tables by query using Phase 2 semantic ranking (ADR-0015).
        
        Uses multi-signal scoring to rank tables:
        1. Entity matching (table/column names)
        2. Type compatibility (numeric for aggregates, date for trends)
        3. Fuzzy matching (typo tolerance)
        4. Foreign key connectivity
        5. Table size
        
        Returns top-k tables <100ms from catalog cache with detailed reasoning.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            query: Search query (natural language, e.g., "show me customers")
            page: Page number (1-indexed)
            page_size: Number of items per page (max: 100)
        
        Returns:
            DiscoveryResponse with semantically ranked search results:
            - relevance_score: 0.0-1.0 confidence
            - reasons: List of scoring signals that contributed to rank
            - estimated_rows: Cached row count
            - fk_count: Foreign key count (connectedness indicator)
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
            
            query = query.strip()
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
            
            # Phase 2: Rank tables using semantic scoring (LLM already parsed intent upstream)
            rank_start = time.time()
            results = []
            
            try:
                # ARCHITECTURE FIX (Phase 9):
                # DO NOT parse intent here. Intent parsing is handled by LangGraph IntentParserAgent.
                # MCP is a pure tool layer that receives already-parsed keywords from LangGraph.
                # This prevents double intent parsing and the plural entity bug.
                
                from mcp_server.tools.table_ranker import TableRanker
                
                # MCP search tools receive keywords/entities from caller
                # For backward compatibility: if not provided, use query as-is (no re-parsing)
                logger.debug(f"Searching for tables matching query: '{query}'")
                
                # Step 1: Load all tables from catalog (O(1) disk read, cached in memory)
                all_tables = catalog.get_table_list()
                
                # Step 2: Rank all tables using multi-signal scoring
                # NOTE: We pass query terms as-is, no intent parsing at MCP layer
                ranker = TableRanker()
                
                # Extract keywords from query for basic ranking (no semantic re-parsing)
                # These should ideally come from LangGraph, but we keep minimal fallback here
                query_terms = query.lower().split()
                query_entities = [t.strip(',.!?;:') for t in query_terms if len(t.strip(',.!?;:')) > 2]
                
                # Heuristic ops from query for better ranking (sum/revenue detection)
                ops: List[str] = []
                if any(tok in query_entities for tok in [
                    'umsatz','revenue','verkauf','vk','rechnung','invoice','order','position','beleg','faktura','sum'
                ]):
                    ops.append('sum')
                
                ranked_tables = ranker.rank_tables(
                    tables=all_tables,
                    entities=query_entities,  # Simple tokenization, NO semantic parsing
                    intent_operations=ops,  # Minimal op hinting to improve ranking
                    catalog_adapter=catalog
                )
                
                rank_duration = (time.time() - rank_start) * 1000
                logger.info(f"Ranked {len(all_tables)} tables in {rank_duration:.1f}ms for query '{query}'")
                
                # Step 4: Convert to API response format
                # PHASE 2 FIX: Only include tables with meaningful scores (>0.0)
                # This prevents LLM confusion from irrelevant results
                for ranked_table in ranked_tables:
                    if ranked_table.score <= 0.0:
                        # Skip tables with zero relevance - they add noise
                        continue

                    summary = {
                        "schema": ranked_table.schema,
                        "name": ranked_table.name,
                        "full_name": ranked_table.full_name,
                        "type": "TABLE",
                        "estimated_rows": ranked_table.estimated_rows or 0,
                        "column_count": ranked_table.column_count or 0,
                        "fk_count": ranked_table.fk_count or 0,
                        "has_foreign_keys": (ranked_table.fk_count or 0) > 0,
                        "has_primary_keys": False,  # Would need to fetch from catalog if needed
                        "relevance_score": ranked_table.score,  # 0.0-1.0 confidence
                        "reasons": ranked_table.reasons,  # Why this table was ranked high
                        "columns": ranked_table.columns or [],  # All column names for SQL generation
                        "matched_columns": ranked_table.matched_columns or []  # Columns matching query
                    }
                    results.append(summary)
                
                # Post-filter/reorder for revenue-like queries: prefer sales-like, avoid archives/address-only
                if 'sum' in ops or any(tok in query_entities for tok in ['umsatz','revenue','verkauf','vk','rechnung','invoice','order','position','beleg','faktura']):
                    def looks_sales(x: Dict[str, Any]) -> bool:
                        n = (x.get('full_name') or x.get('name') or '').lower()
                        return any(t in n for t in ['vk','verkauf','rechnung','rechnungs','beleg','belege','position','positionen','umsatz','invoice','order','faktura'])
                    def is_archive(x: Dict[str, Any]) -> bool:
                        n = (x.get('full_name') or x.get('name') or '').lower()
                        return ('archiv' in n) or ('archive' in n)
                    def is_address_only(x: Dict[str, Any]) -> bool:
                        n = (x.get('full_name') or x.get('name') or '').lower()
                        return any(t in n for t in ['adresse','adressen','address','kontakt','contacts','khkadressen']) and not looks_sales(x)
                    sales = [r for r in results if looks_sales(r)]
                    non_sales = [r for r in results if not looks_sales(r)]
                    # Drop archives first
                    non_archive_sales = [r for r in sales if not is_archive(r)] or sales
                    non_archive_rest = [r for r in non_sales if not is_archive(r)] or non_sales
                    # Push address-only to the end
                    non_address_rest = [r for r in non_archive_rest if not is_address_only(r)]
                    address_only = [r for r in non_archive_rest if is_address_only(r)]
                    # Prefer non-empty first
                    def rank_block(block: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                        return sorted(block, key=lambda r: ((r.get('estimated_rows') or 0) > 0, r.get('relevance_score', 0.0)), reverse=True)
                    results = rank_block(non_archive_sales) + rank_block(non_address_rest) + rank_block(address_only)
            except Exception as ranking_error:
                logger.warning(f"Phase 2 ranking failed, falling back to basic search: {ranking_error}")
                
                # Fallback: Basic catalog search (for edge cases)
                matching_tables = catalog.search_tables(query)
                
                for table in matching_tables:
                    # Calculate basic relevance score
                    score = 0
                    query_lower = query.lower()
                    table_name_lower = table['name'].lower()
                    reasons = []
                    
                    if query_lower == table_name_lower:
                        score = 1.0
                        reasons.append("Exact match")
                    elif query_lower in table_name_lower:
                        score = 0.8
                        reasons.append("Name contains query")
                    elif table_name_lower.startswith(query_lower):
                        score = 0.7
                        reasons.append("Name starts with query")
                    else:
                        score = 0.5
                        reasons.append("Name partially matches query")
                    
                    summary = {
                        "schema": table['schema'],
                        "name": table['name'],
                        "full_name": table['full_name'],
                        "type": table['type'],
                        "estimated_rows": table.get('estimated_rows', 0),
                        "column_count": table.get('column_count', 0),
                        "fk_count": table.get('fk_count', 0),
                        "has_foreign_keys": False,
                        "has_primary_keys": False,
                        "relevance_score": score,
                        "reasons": reasons,
                        "matched_columns": []
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
                # Try to find table in any schema (get_table_list returns dicts)
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t["name"].lower() == table_name.lower()]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Table '{table_name}' not found",
                        error_code="TABLE_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                if len(matching) > 1:
                    schemas = [t["schema"] for t in matching]
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Ambiguous table name '{table_name}'. Found in schemas: {', '.join(schemas)}. Please specify schema.table",
                        error_code="AMBIGUOUS_TABLE_NAME",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0]["schema"]
                name = matching[0]["name"]
            
            # Get table from catalog (returns a dict, not a dataclass object)
            table = catalog.get_table(schema, name)
            
            if not table:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"Table '{schema}.{name}' not found",
                    error_code="TABLE_NOT_FOUND",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Build response data (catalog.get_table() already returns dict with properly serialized columns and fks)
            # Also augment foreign keys with referenced_full_name for downstream consumers.
            fk_list = table.get("foreign_keys", []) or []
            for fk in fk_list:
                try:
                    fk["referenced_full_name"] = f"{fk.get('referenced_schema')}.{fk.get('referenced_table')}"
                except Exception:
                    fk["referenced_full_name"] = None

            data = {
                "schema": table["schema"],
                "name": table["name"],
                "full_name": table["full_name"],
                "type": table["type"],
                "estimated_rows": table["estimated_rows"],
                "columns": table.get("columns", []),  # Already properly serialized from catalog
                "primary_keys": table.get("primary_keys", []),
                "foreign_keys": fk_list,  # Already properly serialized from catalog, augmented with referenced_full_name
                "top_columns": table.get("top_columns", []),  # Already a list of strings
                "neighbors": table.get("neighbors", []),  # Already a list of strings
                # SDG v2: business-level description; empty string when disabled.
                "description": table.get("description", "") or "",
            }

            # Enrich with role_hints, time_col_candidates, and measure_suggestions (catalog-derived only)
            try:
                # Validate columns structure before processing
                columns = data.get("columns", [])
                if not isinstance(columns, list):
                    logger.warning(f"⚠️ columns is not a list, it's {type(columns).__name__}: {str(columns)[:100]}")
                    columns = []
                    data["columns"] = columns
                
                # 🆕 FIX: Ensure all elements in columns are dicts, not other types
                validated_columns = []
                for col in columns:
                    if isinstance(col, dict):
                        validated_columns.append(col)
                    else:
                        logger.warning(f"⚠️ Column element is not a dict, skipping: {type(col).__name__}")
                if validated_columns != columns:
                    logger.warning(f"⚠️ Filtered {len(columns) - len(validated_columns)} non-dict column elements")
                    columns = validated_columns
                    data["columns"] = columns
                
                fk_map = {}
                foreign_keys = data.get("foreign_keys", [])
                if isinstance(foreign_keys, list):
                    for fk in foreign_keys:
                        try:
                            if isinstance(fk, dict):  # 🆕 Validate FK is a dict
                                fk_map[fk.get("column")] = f"{fk.get('referenced_schema')}.{fk.get('referenced_table')}"
                        except Exception as fk_err:
                            logger.debug(f"Skipping FK processing: {fk_err}")
                            continue

                def infer_role_hints(col: dict) -> list:
                    if not isinstance(col, dict):
                        logger.warning(f"⚠️ col is not a dict, it's {type(col).__name__}")
                        return []
                    
                    name = str(col.get("name", "")).lower()
                    dtype = str(col.get("type", "")).lower()
                    hints: list[str] = []

                    # id / pk
                    if col.get("is_primary_key") or name == "id" or name.endswith("_id"):
                        hints.append("id")

                    # fk
                    if col.get("is_foreign_key") or name.endswith("_id"):
                        target = fk_map.get(col.get("name"))
                        if target:
                            hints.append(f"fk_to:{target}")

                    # date-like
                    if any(k in name for k in ["date", "time", "timestamp", "created", "updated"]) or \
                       any(k in dtype for k in ["date", "time", "timestamp"]):
                        hints.append("date")

                    # amount-like
                    if any(k in name for k in ["amount", "total", "price", "revenue", "cost", "subtotal", "grand_total", "sales"]):
                        hints.append("amount")

                    # quantity-like
                    if any(k in name for k in ["qty", "quantity", "units", "count", "qnty"]):
                        hints.append("quantity")

                    # status-like
                    if any(k in name for k in ["status", "state", "flag"]):
                        hints.append("status")

                    # email
                    if "email" in name:
                        hints.append("email")

                    # de-dup while preserving order
                    return list(dict.fromkeys(hints))

                # Apply role_hints to columns (with strict type checking)
                for col in columns:
                    if isinstance(col, dict):
                        col["role_hints"] = infer_role_hints(col)

                # Time column candidates (top 5)
                data["time_col_candidates"] = [
                    c.get("name") for c in columns
                    if isinstance(c, dict) and isinstance(c.get("role_hints"), list) and "date" in c.get("role_hints")
                ][:5]

                # Measure suggestions
                def find_cols(keywords: list[str]) -> list[str]:
                    return [
                        c.get("name") for c in columns
                        if isinstance(c, dict) and any(k in str(c.get("name", "")).lower() for k in keywords)
                    ]

                price_like = find_cols(["unit_price", "price", "line_amount", "amount"])
                qty_like = find_cols(["qty", "quantity", "units", "count"])
                amount_like = find_cols(["amount", "total", "revenue", "cost", "subtotal", "grand_total", "sales"])

                measure_suggestions: list[dict] = []
                if price_like and qty_like:
                    measure_suggestions.append({
                        "name": "revenue",
                        "expr": f"{price_like[0]}*{qty_like[0]}",
                        "agg": "SUM"
                    })
                # Simple SUMs for standalone amount-like columns
                for col_name in amount_like:
                    measure_suggestions.append({
                        "name": f"sum_{col_name}",
                        "expr": col_name,
                        "agg": "SUM"
                    })

                data["measure_suggestions"] = measure_suggestions[:5]
            except Exception as enrich_err:
                # Non-fatal: enrichment best-effort only
                logger.warning(f"describe_table enrichment error (non-fatal): {enrich_err}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Include sample data if requested (requires DB query)
            if include_sample:
                try:
                    sample_query = f"SELECT * FROM {data['full_name']} LIMIT 5"
                    sample_rows = await db_adapter.fetch(sample_query, limit=5)
                    # Convert rows to JSON-serializable format (handles Decimal, datetime, etc.)
                    data["sample_data"] = [convert_row_to_json_serializable(row) for row in sample_rows]
                except Exception as e:
                    logger.warning(f"Failed to fetch sample data for {data.get('full_name')}: {e}")
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
            
            # Parse table name (get_table_list returns dicts)
            if '.' in table_name:
                schema, name = table_name.split('.', 1)
            else:
                # Try to find table in any schema
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t["name"].lower() == table_name.lower()]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Table '{table_name}' not found",
                        error_code="TABLE_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                if len(matching) > 1:
                    schemas = [t["schema"] for t in matching]
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Ambiguous table name '{table_name}'. Found in schemas: {', '.join(schemas)}",
                        error_code="AMBIGUOUS_TABLE_NAME",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0]["schema"]
                name = matching[0]["name"]
            
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
    
    # =====================================================
    # Tier 1 Enhancement Tools
    # =====================================================
    
    @staticmethod
    async def get_view_dependencies(
        db_adapter,
        view_name: str
    ) -> DiscoveryResponse:
        """
        Get view dependencies and materialization status (Tier 1 Enhancement).
        
        Helps agents understand:
        - Which tables/views this view depends on
        - Whether the view is materialized (indexed, snapshot, etc.)
        - Performance implications of using this view
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            view_name: Fully qualified view name (schema.view) or just view name
        
        Returns:
            DiscoveryResponse with view dependencies and materialization info
        """
        start_time = time.time()
        
        try:
            if not view_name or not view_name.strip():
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="View name is required",
                    error_code="EMPTY_VIEW_NAME",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            view_name = view_name.strip()
            
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
            
            # Parse view name
            if '.' in view_name:
                schema, name = view_name.split('.', 1)
            else:
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t["name"].lower() == view_name.lower() and t["type"] in ('VIEW', 'MATERIALIZED VIEW')]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"View '{view_name}' not found",
                        error_code="VIEW_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                if len(matching) > 1:
                    schemas = [t["schema"] for t in matching]
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Ambiguous view name '{view_name}'. Found in schemas: {', '.join(schemas)}",
                        error_code="AMBIGUOUS_VIEW_NAME",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0]["schema"]
                name = matching[0]["name"]
            
            # Get view from catalog
            view_dict = catalog.get_table(schema, name)
            
            if not view_dict:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"View '{schema}.{name}' not found",
                    error_code="VIEW_NOT_FOUND",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            if view_dict.get('type') not in ('VIEW', 'MATERIALIZED VIEW'):
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"'{schema}.{name}' is not a view",
                    error_code="NOT_A_VIEW",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Extract view dependency info
            # Accept both legacy and new builder shapes
            raw_deps = view_dict.get('view_dependencies') or view_dict.get('dependencies') or []
            dependencies = []
            for d in raw_deps:
                # New builder shape: {schema, name, type, ...}
                if isinstance(d, dict):
                    depends_on_schema = d.get('depends_on_schema') or d.get('schema') or 'dbo'
                    depends_on_table = d.get('depends_on_table') or d.get('name') or d.get('entity_name')
                    dep_type = d.get('dependency_type') or d.get('type')
                    dependencies.append({
                        'depends_on_schema': depends_on_schema,
                        'depends_on_table': depends_on_table,
                        'dependency_type': dep_type,
                        'type': d.get('type')
                    })
                else:
                    # String full_name fallback like 'dbo.Table'
                    try:
                        parts = str(d).split('.')
                        depends_on_schema = parts[0] if len(parts) > 1 else 'dbo'
                        depends_on_table = parts[1] if len(parts) > 1 else parts[0]
                        dependencies.append({
                            'depends_on_schema': depends_on_schema,
                            'depends_on_table': depends_on_table,
                            'dependency_type': 'table'
                        })
                    except Exception:
                        continue
            is_materialized = view_dict.get('is_materialized_view', False)
            materialization_strategy = view_dict.get('view_materialization_strategy')
            
            data = {
                "view": f"{schema}.{name}",
                "type": view_dict.get('type'),
                "is_materialized": is_materialized,
                "materialization_strategy": materialization_strategy,
                "dependencies": [
                    {
                        "depends_on": f"{d.get('depends_on_schema', 'dbo')}.{d.get('depends_on_table')}",
                        "dependency_type": d.get('dependency_type', 'table'),
                        "type": d.get('type'),
                    }
                    for d in dependencies
                ],
                "dependency_count": len(dependencies),
                "estimated_rows": view_dict.get('estimated_rows', 0),
                "column_count": view_dict.get('column_count', 0),
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return DiscoveryResponse(
                ok=True,
                data=data,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"get_view_dependencies failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def get_fk_cardinality(
        db_adapter,
        table_name: str
    ) -> DiscoveryResponse:
        """
        Get foreign key cardinality patterns for a table (Tier 1 Enhancement).
        
        Helps agents understand:
        - Which FKs are 1:1 (no row multiplication)
        - Which FKs are 1:N (typical case)
        - Which FKs are N:N (many-to-many)
        - Estimated join ratios
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            table_name: Fully qualified table name (schema.table) or just table name
        
        Returns:
            DiscoveryResponse with FK cardinality information
        """
        start_time = time.time()
        
        try:
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
                all_tables = catalog.get_table_list()
                matching = [t for t in all_tables if t["name"].lower() == table_name.lower()]
                
                if not matching:
                    return DiscoveryResponse(
                        ok=False,
                        data=None,
                        error=f"Table '{table_name}' not found",
                        error_code="TABLE_NOT_FOUND",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                schema = matching[0]["schema"]
                name = matching[0]["name"]
            
            # Get table from catalog
            table_dict = catalog.get_table(schema, name)
            
            if not table_dict:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error=f"Table '{schema}.{name}' not found",
                    error_code="TABLE_NOT_FOUND",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Extract FK cardinality info
            fk_cardinality = table_dict.get('fk_cardinality', []) or []
            
            data = {
                "table": f"{schema}.{name}",
                "fk_cardinalities": [
                    {
                        "column": c.get('column'),
                        "references": f"{c.get('referenced_schema', 'dbo')}.{c.get('referenced_table')}",
                        "cardinality_type": c.get('cardinality_type', 'one-to-many'),
                        "ratio_estimate": c.get('ratio_estimate'),
                    }
                    for c in fk_cardinality
                ],
                "cardinality_count": len(fk_cardinality),
                "one_to_one_count": sum(1 for c in fk_cardinality if c.get('cardinality_type') == 'one-to-one'),
                "one_to_many_count": sum(1 for c in fk_cardinality if c.get('cardinality_type') == 'one-to-many'),
                "many_to_many_count": sum(1 for c in fk_cardinality if c.get('cardinality_type') == 'many-to-many'),
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return DiscoveryResponse(
                ok=True,
                data=data,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"get_fk_cardinality failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def get_domain_clusters(
        db_adapter,
    ) -> DiscoveryResponse:
        """
        Get business domain clusters (Tier 1 Enhancement).
        
        Helps agents understand:
        - Which domain each table belongs to (Sales, Inventory, HR, etc.)
        - Related domains within a table's domain
        - Domain confidence scores
        
        Returns:
            DiscoveryResponse with domain cluster information for all tables
        """
        start_time = time.time()
        
        # Check cache
        cache_key_args = {}
        cached_response = DiscoveryTools._response_cache.get("get_domain_clusters", cache_key_args)
        if cached_response:
            return cached_response
        
        try:
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
            all_tables = catalog.get_table_list()
            
            # Extract domain info from each table
            domain_clusters = {}
            
            for table_dict in all_tables:
                schema = table_dict.get('schema', 'dbo')
                name = table_dict.get('name', '')
                domain_meta = table_dict.get('domain_metadata', {})
                
                if domain_meta:
                    domain = domain_meta.get('domain_cluster', 'General')
                    
                    if domain not in domain_clusters:
                        domain_clusters[domain] = {
                            "domain": domain,
                            "tables": [],
                            "table_count": 0,
                        }
                    
                    domain_clusters[domain]["tables"].append({
                        "table": f"{schema}.{name}",
                        "confidence": domain_meta.get('domain_confidence', 0.0),
                        "subject_tags": domain_meta.get('subject_tags', []),
                        "related_domains": domain_meta.get('related_domains', []),
                    })
                    domain_clusters[domain]["table_count"] += 1
            
            data = {
                "domain_count": len(domain_clusters),
                "domains": list(domain_clusters.values()),
            }
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            response = DiscoveryResponse(
                ok=True,
                data=data,
                execution_time_ms=execution_time_ms,
                cached=False
            )
            
            # Cache response
            DiscoveryTools._response_cache.set("get_domain_clusters", cache_key_args, response)
            
            return response
            
        except Exception as e:
            logger.error(f"get_domain_clusters failed: {e}")
            return DiscoveryResponse(
                ok=False,
                data=None,
                error=str(e),
                error_code="INTERNAL_ERROR",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def get_column_index(
        db_adapter,
        table_names: List[str]
    ) -> DiscoveryResponse:
        """
        Get structured column lists for multiple tables (Phase 7.1).
        
        Prevents column hallucination by providing exact, enumerated column names
        from Scout Catalog. This allows the LLM to reference only real columns.
        
        Args:
            db_adapter: DatabaseAdapter instance with catalog
            table_names: List of table names to get columns for
        
        Returns:
            DiscoveryResponse with format: {
                "dbo.Table1": ["Id", "Name", "Amount"],
                "dbo.Table2": ["OrderId", "Total"],
                "non_existent_table": null  # To indicate table not found
            }
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not table_names or not isinstance(table_names, list):
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="table_names must be a non-empty list",
                    error_code="VALIDATION_FAILED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Check catalog
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog not initialized",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            catalog = db_adapter.catalog
            
            # Validate catalog is an instance, not a class
            if isinstance(catalog, type):
                logger.error(f"Catalog is a class type, not an instance: {catalog}")
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog is a class, not an instance",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Additional validation: ensure catalog has required methods
            if not hasattr(catalog, 'get_table') or not callable(getattr(catalog, 'get_table')):
                logger.error(f"Catalog missing get_table method or it's not callable")
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog missing required get_table method",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            if not hasattr(catalog, 'get_table_list') or not callable(getattr(catalog, 'get_table_list')):
                logger.error(f"Catalog missing get_table_list method or it's not callable")
                return DiscoveryResponse(
                    ok=False,
                    data=None,
                    error="Catalog missing required get_table_list method",
                    error_code="CATALOG_NOT_INITIALIZED",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            column_index = {}
            
            # Extract columns for each table (O(1) per table from in-memory catalog)
            for table_name in table_names:
                try:
                    # Parse table name (handle both "schema.table" and just "table" formats)
                    if '.' in table_name:
                        schema, name = table_name.split('.', 1)
                        if not schema or not name:
                            logger.debug(f"Invalid table name format: {table_name}")
                            column_index[table_name] = None
                            continue
                        
                        # Ensure we're calling as an instance method with correct signature
                        if not isinstance(schema, str) or not isinstance(name, str):
                            logger.warning(f"Invalid argument types for get_table: schema={type(schema)}, name={type(name)}")
                            column_index[table_name] = None
                            continue
                        
                        table_info = catalog.get_table(schema, name)
                    else:
                        # Try to find table in any schema
                        try:
                            all_tables = catalog.get_table_list()
                        except Exception as list_err:
                            logger.warning(f"Error calling catalog.get_table_list(): {list_err}")
                            column_index[table_name] = None
                            continue
                        
                        matching = [t for t in all_tables if t.get("name", "").lower() == table_name.lower()]
                        if matching:
                            # Warn if ambiguous (found in multiple schemas)
                            if len(matching) > 1:
                                schemas = [t.get('schema', '?') for t in matching]
                                logger.warning(f"Ambiguous table '{table_name}': found in schemas {schemas}, using first")
                            schema = matching[0].get("schema", "")
                            name = matching[0].get("name", "")
                            if not schema or not name:
                                logger.warning(f"Matched table has missing schema or name: {matching[0]}")
                                column_index[table_name] = None
                                continue
                            table_info = catalog.get_table(schema, name)
                        else:
                            table_info = None
                except Exception as table_err:
                    logger.warning(f"Error retrieving table info for '{table_name}': {table_err}")
                    import traceback
                    logger.debug(f"Stack trace: {traceback.format_exc()}")
                    table_info = None
                
                if table_info:
                    # Extract column names with validation
                    columns_data = table_info.get('columns', [])
                    if not isinstance(columns_data, list):
                        logger.warning(f"Table {table_name}: columns is {type(columns_data).__name__}, expected list")
                        column_index[table_name] = None
                        continue

                    # Validate each column entry is a dict with 'name' key
                    validated_cols = []
                    for col in columns_data:
                        if isinstance(col, dict) and 'name' in col:
                            validated_cols.append(col['name'])
                        else:
                            logger.warning(f"Table {table_name}: invalid column format {type(col).__name__}, skipping")

                    fqtn = table_info.get('full_name', table_name)
                    column_index[fqtn] = validated_cols
                    if validated_cols:
                        logger.debug(f"✓ {fqtn}: {len(validated_cols)} columns")
                    else:
                        logger.warning(f"⚠️ {fqtn}: no valid columns found")
                else:
                    # Table not found - indicate with null
                    column_index[table_name] = None
                    logger.debug(f"✗ {table_name}: not found in catalog")
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return DiscoveryResponse(
                ok=True,
                data=column_index,
                execution_time_ms=execution_time_ms,
                cached=False
            )
        
        except Exception as e:
            import traceback
            logger.error(f"get_column_index failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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