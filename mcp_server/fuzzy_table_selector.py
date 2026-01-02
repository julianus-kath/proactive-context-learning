"""
Fuzzy Table Selector: Intelligent table discovery for autonomous query generation.

Phase 7 Enhancement:
- Smart hybrid matching: fuzzy for German/non-English, exact for others
- Ranked results with confidence scoring
- Relations traversal via foreign keys
- Session-level caching to avoid archive searches
- Fallback to on-demand search if Scout Mode unavailable

Usage:
    selector = FuzzyTableSelector(db_adapter)
    await selector.find_tables("Offene Lieferungen")
    # Returns top matches with confidence scores
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TableMatch:
    """A table match with confidence score and ranking."""
    full_name: str  # "schema.table"
    table_name: str
    schema: str
    confidence: float  # 0.0 to 1.0
    match_type: str  # "exact", "fuzzy", "component", "column", "related"
    reason: str  # Human-readable explanation
    column_matches: List[str] = None  # If matched by column
    related_via: Optional[str] = None  # If matched via FK relationship
    
    def is_primary_match(self) -> bool:
        """High confidence match (>= 0.72)."""
        return self.confidence >= 0.72
    
    def is_secondary_match(self) -> bool:
        """Lower confidence but still relevant (0.60-0.72)."""
        return 0.60 <= self.confidence < 0.72


class SessionTableCache:
    """Session-level cache for table searches to avoid archive lookups."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize session cache.
        
        Args:
            ttl_seconds: Time-to-live for cached searches
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[List[TableMatch], float]] = {}
    
    def get(self, query: str) -> Optional[List[TableMatch]]:
        """Get cached results if available and fresh."""
        if query in self._cache:
            results, timestamp = self._cache[query]
            age = datetime.now().timestamp() - timestamp
            if age < self.ttl_seconds:
                logger.info(f"📦 Session cache hit for '{query}' (age: {age:.1f}s)")
                return results
            else:
                del self._cache[query]
        return None
    
    def set(self, query: str, results: List[TableMatch]):
        """Cache search results."""
        self._cache[query] = (results, datetime.now().timestamp())
        logger.info(f"📦 Session cache set for '{query}' ({len(results)} results)")
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()


class FuzzyTableSelector:
    """
    Intelligent table selector using Scout Mode and discovery tools.
    
    Provides autonomous table discovery without requiring user clarification.
    """
    
    def __init__(self, db_adapter, cache_ttl_seconds: int = 300):
        """
        Initialize the table selector.
        
        Args:
            db_adapter: DatabaseAdapter instance
            cache_ttl_seconds: Session cache TTL
        """
        self.db_adapter = db_adapter
        self.session_cache = SessionTableCache(ttl_seconds=cache_ttl_seconds)
        self.scout_mode = None
        
        # Try to load Scout Mode if available
        try:
            from mcp_server.scout_mode import get_scout_instance
            self.scout_mode = get_scout_instance()
        except Exception as e:
            logger.warning(f"Scout Mode not available: {e}")
    
    async def find_tables(
        self,
        user_query: str,
        top_k: int = 5,
        use_cache: bool = True
    ) -> List[TableMatch]:
        """
        Find tables matching a user query with fuzzy matching.
        
        Strategy:
        1. Check session cache
        2. Try Scout Mode semantic search
        3. Fallback to on-demand discovery tools
        4. Traverse relationships for context
        
        Args:
            user_query: User's description of desired table
            top_k: Number of top matches to return
            use_cache: Whether to use session cache
            
        Returns:
            List of matching tables ranked by confidence
        """
        logger.info(f"🔍 Finding tables for: '{user_query}'")
        
        # Check session cache first
        if use_cache:
            cached = self.session_cache.get(user_query)
            if cached is not None:
                return cached[:top_k]
        
        matches = []
        
        try:
            # Strategy 1: Try Scout Mode (semantic search)
            if self.scout_mode:
                scout_matches = self.scout_mode.search(user_query, top_k=top_k * 2)
                if scout_matches:
                    matches.extend([
                        TableMatch(
                            full_name=m.full_name,
                            table_name=m.table_name,
                            schema=m.schema,
                            confidence=m.similarity,
                            match_type=m.reason,
                            reason=f"Scout Mode {m.reason} match",
                            column_matches=m.column_matches
                        )
                        for m in scout_matches
                    ])
                    logger.info(f"✅ Scout Mode found {len(scout_matches)} matches")
            
            # Strategy 2: Fallback to on-demand discovery tools
            if not matches or len(matches) < top_k:
                fallback_matches = await self._search_discovery_tools(user_query, top_k * 2)
                matches.extend(fallback_matches)
                if fallback_matches:
                    logger.info(f"✅ Discovery tools found {len(fallback_matches)} matches")
            
            # Deduplicate and sort
            unique_matches = {}
            for match in matches:
                if match.full_name not in unique_matches:
                    unique_matches[match.full_name] = match
                else:
                    # Keep highest confidence
                    if match.confidence > unique_matches[match.full_name].confidence:
                        unique_matches[match.full_name] = match
            
            matches = list(unique_matches.values())
            matches.sort(key=lambda x: (-x.confidence, x.table_name))
            
            # Limit to top_k
            matches = matches[:top_k]
            
            # Cache the results
            if use_cache:
                self.session_cache.set(user_query, matches)
            
            logger.info(f"✅ Found {len(matches)} table matches for '{user_query}'")
            for match in matches:
                logger.info(f"   • {match.full_name}: {match.confidence:.2f} ({match.match_type})")
            
            return matches
            
        except Exception as e:
            logger.error(f"❌ Error finding tables: {e}")
            return []
    
    async def _search_discovery_tools(
        self,
        query: str,
        top_k: int = 5
    ) -> List[TableMatch]:
        """
        Fallback: Use MCP discovery tools to search for tables.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of matching tables
        """
        try:
            from mcp_server.discovery_tools import DiscoveryTools
            
            # Call search_tables discovery tool
            response = await DiscoveryTools.search_tables(
                db_adapter=self.db_adapter,
                keyword=query,
                page=1,
                page_size=top_k
            )
            
            if not response.ok:
                logger.warning(f"Discovery tools search failed: {response.error}")
                return []
            
            matches = []
            if response.data and "tables" in response.data:
                for table in response.data["tables"]:
                    matches.append(TableMatch(
                        full_name=table.get("full_name"),
                        table_name=table.get("name"),
                        schema=table.get("schema"),
                        confidence=0.65,  # Lower confidence for fallback
                        match_type="discovery_tool",
                        reason="Found via discovery tools"
                    ))
            
            return matches
            
        except Exception as e:
            logger.error(f"Discovery tools search error: {e}")
            return []
    
    async def get_related_tables(self, table_name: str, max_depth: int = 1) -> List[TableMatch]:
        """
        Get tables related to a given table via foreign keys.
        
        Args:
            table_name: Fully qualified table name (schema.table)
            max_depth: Maximum relationship depth to traverse
            
        Returns:
            List of related tables
        """
        try:
            from mcp_server.discovery_tools import DiscoveryTools
            
            relations = await DiscoveryTools.list_relations(
                db_adapter=self.db_adapter,
                table_name=table_name
            )
            
            if not relations.ok:
                logger.warning(f"Failed to get relations for {table_name}")
                return []
            
            related_tables = []
            if relations.data and "relations" in relations.data:
                for relation in relations.data["relations"]:
                    related_tables.append(TableMatch(
                        full_name=relation.get("target_table"),
                        table_name=relation.get("target_table").split(".")[-1],
                        schema=relation.get("target_table").split(".")[0],
                        confidence=0.8,  # High confidence for direct relations
                        match_type="related_fk",
                        reason=f"Related via foreign key on {relation.get('source_column')}",
                        related_via=relation.get("source_column")
                    ))
            
            logger.info(f"Found {len(related_tables)} related tables for {table_name}")
            return related_tables
            
        except Exception as e:
            logger.error(f"Failed to get related tables: {e}")
            return []
    
    def clear_session_cache(self):
        """Clear session-level cache (useful between conversations)."""
        self.session_cache.clear()
        logger.info("🧹 Session cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.session_cache._cache),
            "entries": list(self.session_cache._cache.keys())
        }


# Global selector instance
_selector_instance: Optional[FuzzyTableSelector] = None


def get_table_selector(db_adapter) -> FuzzyTableSelector:
    """Get or create a fuzzy table selector instance."""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = FuzzyTableSelector(db_adapter)
    return _selector_instance


async def find_best_table(
    db_adapter,
    user_mention: str,
    top_k: int = 3
) -> Optional[str]:
    """
    Convenience function: Find the best matching table for a user mention.
    
    Args:
        db_adapter: DatabaseAdapter instance
        user_mention: User's table name mention or description
        top_k: Number of candidates to consider
        
    Returns:
        Fully qualified table name (schema.table) or None
    """
    selector = get_table_selector(db_adapter)
    matches = await selector.find_tables(user_mention, top_k=top_k)
    
    if matches and matches[0].is_primary_match():
        return matches[0].full_name
    
    return None