"""
Scout Runner: Consolidated Semantic Catalog Management
================================================================================
Manages the complete lifecycle of semantic table discovery:

CORE RESPONSIBILITIES:
1. Background catalog building with accurate row counts (via MSSQLCatalogBuilder)
2. Semantic search with fuzzy matching and description generation
3. TTL-based refresh scheduling with non-blocking operation
4. Health monitoring and metrics

ARCHITECTURE:
- Uses CatalogStore for compressed persistence (data/catalog/)
- Integrates MSSQLCatalogBuilder for accurate schema + row estimates
- Provides semantic search API for table discovery
- Runs async background refresh loop

KEY FIX: This consolidation ensures ALL tables (including KHKAdressen) are
         indexed with ACCURATE row counts, enabling proper ranking.
================================================================================
"""

import asyncio
import logging
import difflib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

from mcp_server.catalog_store import CatalogStore
from mcp_server.catalog_builders.mssql import MSSQLCatalogBuilder

logger = logging.getLogger(__name__)


# ============================================================================
# SEMANTIC SEARCH HELPERS (from scout_mode.py)
# ============================================================================

class TableNameNormalizer:
    """Normalize table names for fuzzy matching (handles German prefixes)."""
    
    PREFIXES = {
        'dbo.': '', 'vew': '', 'tbl': '', 'bs': '', 'vk': '',
        'kd': '', 'mat': '', 'obj': '', 'khk': ''
    }
    
    @staticmethod
    def normalize(name: str) -> str:
        """Normalize table name by removing prefixes and lowercasing."""
        normalized = name.lower()
        for prefix in TableNameNormalizer.PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        return normalized
    
    @staticmethod
    def get_component_match(query: str, name: str) -> float:
        """Check if query matches any component of the table name."""
        query_lower = query.lower()
        name_lower = name.lower()
        
        if query_lower in name_lower:
            return 0.85
        
        # Split camelCase/German compound words
        components = []
        current = ""
        for char in name:
            if char.isupper() or not char.isalpha():
                if current:
                    components.append(current.lower())
                current = ""
            else:
                current += char
        if current:
            components.append(current.lower())
        
        # Find best component match
        best_match = 0.0
        for component in components:
            similarity = difflib.SequenceMatcher(None, query_lower, component).ratio()
            best_match = max(best_match, similarity)
        
        return best_match


class ScoutRunner:
    """
    Asynchronous catalog builder and manager for Scout Mode.

    Features:
    - Background catalog building (non-blocking startup)
    - TTL-based refresh scheduling
    - Health metrics and monitoring
    - Graceful fallback to stale cache during rebuilds
    """

    def __init__(
        self,
        db_adapter,
        catalog_dir: str = "data/catalog",
        ttl_hours: int = 24 * 7,  # 7 days
        refresh_interval_hours: int = 24,  # Check daily
        max_concurrent_builds: int = 1
    ):
        """
        Initialize Scout Runner.

        Args:
            db_adapter: Database adapter for schema access
            catalog_dir: Directory for catalog storage
            ttl_hours: Catalog time-to-live in hours
            refresh_interval_hours: How often to check for refresh
            max_concurrent_builds: Max concurrent catalog builds
        """
        self.db_adapter = db_adapter
        self.store = CatalogStore(catalog_dir=catalog_dir, ttl_hours=ttl_hours)
        self.ttl_hours = ttl_hours
        self.refresh_interval_hours = refresh_interval_hours
        self.max_concurrent_builds = max_concurrent_builds

        # State
        self._running = False
        self._build_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_builds)
        self._last_refresh_check = datetime.min

        # Stats
        self.build_count = 0
        self.last_build_duration = 0.0
        self.last_build_time: Optional[datetime] = None

        logger.info(f"✅ ScoutRunner initialized: TTL={ttl_hours}h, refresh={refresh_interval_hours}h")

    async def start(self) -> None:
        """
        Start the Scout Runner background tasks.

        This is non-blocking - starts background catalog building if needed.
        """
        if self._running:
            logger.warning("ScoutRunner already running")
            return

        self._running = True
        logger.info("🚀 Starting Scout Runner...")

        # Start background refresh checker
        asyncio.create_task(self._refresh_loop())

        # Check if immediate build needed
        if self._should_build_catalog():
            logger.info("📦 Catalog missing or expired, starting background build...")
            self._build_task = asyncio.create_task(self._build_catalog_async())
        else:
            logger.info("✅ Catalog is fresh, no build needed")

    async def stop(self) -> None:
        """
        Stop the Scout Runner and cleanup.
        """
        logger.info("🛑 Stopping Scout Runner...")
        self._running = False

        if self._build_task and not self._build_task.done():
            self._build_task.cancel()
            try:
                await self._build_task
            except asyncio.CancelledError:
                pass

        self._executor.shutdown(wait=True)
        logger.info("✅ ScoutRunner stopped")

    async def _refresh_loop(self) -> None:
        """
        Background loop that checks for catalog refresh needs.
        """
        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval_hours * 3600)  # Convert hours to seconds

                if not self._running:
                    break

                if self._should_build_catalog():
                    logger.info("🔄 Catalog TTL expired, starting refresh build...")
                    if not self._build_task or self._build_task.done():
                        self._build_task = asyncio.create_task(self._build_catalog_async())
                    else:
                        logger.debug("Build already in progress, skipping")

            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

    def _should_build_catalog(self) -> bool:
        """
        Check if catalog should be built/refreshed.

        Returns:
            True if build is needed
        """
        # Check if catalog exists and is valid
        if not self.store.is_valid():
            return True

        # Check if it's time for a refresh check (don't check too often)
        now = datetime.utcnow()
        time_since_last_check = (now - self._last_refresh_check).total_seconds() / 3600

        if time_since_last_check < self.refresh_interval_hours:
            return False

        self._last_refresh_check = now

        # Check TTL
        age_hours = self.store.get_age_hours()
        if age_hours is None:
            return True

        return age_hours >= self.ttl_hours

    async def _build_catalog_async(self) -> bool:
        """
        Build catalog asynchronously.

        Returns:
            True if successful
        """
        build_start = datetime.utcnow()
        logger.info("🏗️ Starting catalog build...")

        try:
            # Create catalog builder
            builder = MSSQLCatalogBuilder(self.db_adapter)

            # Build catalog directly (no thread pool needed since we're already async)
            catalog_data = await builder.build_catalog()

            # Store catalog
            success = self.store.store_catalog(catalog_data)

            if success:
                # Update stats
                build_duration = (datetime.utcnow() - build_start).total_seconds()
                self.build_count += 1
                self.last_build_duration = build_duration
                self.last_build_time = datetime.utcnow()

                metadata = catalog_data.get("metadata", {})
                tables_count = metadata.get("tables_count", 0)
                views_count = metadata.get("views_count", 0)

                logger.info(
                    f"✅ Catalog build completed in {build_duration:.1f}s, "
                    f"{tables_count} tables, {views_count} views"
                )

                return True
            else:
                logger.error("❌ Catalog storage failed")
                return False

        except Exception as e:
            build_duration = (datetime.utcnow() - build_start).total_seconds()
            logger.error(f"❌ Catalog build failed after {build_duration:.1f}s: {e}")
            return False



    def get_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Get current catalog data.

        Returns:
            Catalog dict if available, None otherwise
        """
        return self.store.load_catalog()

    def force_refresh(self) -> bool:
        """
        Force immediate catalog refresh.

        Returns:
            True if refresh started
        """
        if self._build_task and not self._build_task.done():
            logger.warning("Build already in progress")
            return False

        logger.info("🔄 Forcing catalog refresh...")
        self._build_task = asyncio.create_task(self._build_catalog_async())
        return True

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status and metrics.

        Returns:
            Health status dictionary
        """
        catalog_stats = self.store.get_stats()

        return {
            "scout_running": self._running,
            "catalog_exists": catalog_stats["exists"],
            "catalog_valid": catalog_stats["valid"],
            "catalog_age_hours": catalog_stats["age_hours"],
            "catalog_ttl_hours": catalog_stats["ttl_hours"],
            "build_in_progress": self._build_task is not None and not self._build_task.done(),
            "build_count": self.build_count,
            "last_build_duration": self.last_build_duration,
            "last_build_time": self.last_build_time.isoformat() if self.last_build_time else None,
            "compressed_size": catalog_stats["compressed_size"],
            "compression_ratio": catalog_stats["compression_ratio"]
        }

    def is_ready(self) -> bool:
        """
        Check if Scout is ready (has valid catalog).

        Returns:
            True if catalog is available and valid
        """
        return self.store.is_valid()
    
    # ========================================================================
    # SEMANTIC SEARCH API (consolidated from scout_mode.py)
    # ========================================================================
    
    def search(self, query: str, top_k: int = 10, intent_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Semantic search for tables using fuzzy matching and intent awareness.
        
        This is the PRIMARY search method used by discovery agents.
        
        Args:
            query: Search query (e.g., "kunde", "customer", "adressen")
            top_k: Number of results to return
            intent_data: Optional intent information for ranking boost
        
        Returns:
            List of matching tables with metadata, sorted by relevance
        """
        try:
            catalog = self.get_catalog()
            if not catalog:
                logger.warning("Scout catalog not available for search")
                return []
            
            tables = catalog.get("tables", [])
            if not tables:
                logger.warning("Scout catalog contains no tables")
                return []
            
            results = []
            query_lower = query.lower()
            
            # Extract intent info for ranking boost
            intent_entities = []
            intent_operations = []
            if intent_data:
                intent_entities = [str(e).lower() for e in (intent_data.get("primary_entities") or [])]
                intent_entities += [str(e).lower() for e in (intent_data.get("secondary_entities") or [])]
                intent_operations = [str(op).lower() for op in (intent_data.get("metrics") or [])]
            
            for table in tables:
                full_name = table.get("full_name", "")
                name = table.get("name", "")
                schema = table.get("schema", "dbo")
                estimated_rows = table.get("estimated_rows", 0)
                table_type = table.get("type", "TABLE")
                columns = table.get("columns", [])
                
                name_lower = name.lower()
                normalized = TableNameNormalizer.normalize(name)
                
                # Scoring system
                score = 0.0
                reasons = []
                
                # 1. Exact match (highest priority)
                if query_lower == name_lower or query_lower == normalized or query_lower in full_name.lower():
                    score = 1.0
                    reasons.append("Exact match")
                else:
                    # 2. Fuzzy name match
                    name_similarity = difflib.SequenceMatcher(None, query_lower, name_lower).ratio()
                    
                    # 3. Component match (for German compound words)
                    component_similarity = TableNameNormalizer.get_component_match(query, name)
                    
                    score = max(name_similarity, component_similarity)
                    
                    if score >= 0.7:
                        reasons.append(f"Fuzzy match: {score:.2f}")
                
                # 4. Column name matches
                col_matches = []
                for col in columns:
                    col_name = col.get("name", "").lower() if isinstance(col, dict) else str(col).lower()
                    if query_lower in col_name:
                        col_matches.append(col_name)
                
                if col_matches:
                    score = max(score, 0.65)
                    reasons.append(f"Column match: {', '.join(col_matches[:3])}")
                
                # 5. CRITICAL: Apply archive/admin/config penalties
                # This ensures junk tables are de-ranked
                penalty_tokens = [
                    'archiv', 'archive', 'berecht', 'berechtigung', 'permission',
                    'rechte', 'user', 'users', 'benutzer', 'rolle', 'role',
                    'config', 'konfiguration', 'belegart', 'belegnummer', 'log', 'audit'
                ]
                is_junk = any(tok in name_lower or tok in full_name.lower() for tok in penalty_tokens)
                if is_junk:
                    score = max(0.0, score - 0.7)
                    reasons.append("Archive/admin penalty")
                
                # 6. Intent-aware boosting
                if intent_operations and intent_entities:
                    # Customer count intent: boost master address/customer tables
                    if "count" in intent_operations and any(e in ["kunde", "kunden", "customer", "customers"] for e in intent_entities):
                        if any(tok in name_lower for tok in ["khkadressen", "adressen", "adresse", "kunde", "kunden", "customer"]) and not is_junk:
                            score = min(1.0, score + 0.6)
                            reasons.append("Customer master boost")
                    
                    # Revenue/sum intent: STRONG boost for sales transaction tables, penalize non-sales
                    elif any(op in ["sum", "total", "revenue"] for op in intent_operations):
                        # STRONG boost for actual sales/invoice tables
                        if any(tok in name_lower for tok in ["vkposition", "rechnungsposition", "position", "rechnung", "rechnungen", "vkbeleg", "vkbelege", "invoice", "invoices", "order", "orders", "umsatz", "faktura"]) and not is_junk:
                            # Extra boost if "position" or "rechnung" (core sales tables)
                            if any(tok in name_lower for tok in ["vkposition", "rechnungsposition", "rechnung", "rechnungen", "invoice"]):
                                score = min(1.0, score + 0.8)
                                reasons.append("CORE sales transaction boost")
                            else:
                                score = min(1.0, score + 0.5)
                                reasons.append("Sales transaction boost")
                        # PENALIZE dispatch/project/warehouse tables for revenue queries
                        elif any(tok in name_lower for tok in ["dispo", "dispatch", "projekt", "project", "lager", "warehouse", "verursacher"]):
                            score = max(0.0, score - 0.4)
                            reasons.append("Non-sales table penalty")
                
                # 7. Row count bonus (non-empty tables preferred)
                if estimated_rows and estimated_rows > 0:
                    score = min(1.0, score + 0.05)
                    reasons.append(f"{estimated_rows} rows")
                
                # Only include tables with meaningful score
                if score >= 0.3:
                    results.append({
                        "full_name": full_name,
                        "name": name,
                        "schema": schema,
                        "type": table_type,
                        "estimated_rows": estimated_rows,
                        "column_count": len(columns),
                        "relevance_score": score,
                        "reasons": reasons,
                        "columns": columns[:10]  # Include first 10 columns
                    })
            
            # Sort by score descending
            results.sort(key=lambda x: (-x["relevance_score"], -x.get("estimated_rows", 0), x["full_name"]))
            
            # Return top_k
            final_results = results[:top_k]
            
            if final_results:
                logger.info(f"🔍 Scout search '{query}' found {len(final_results)} results, top score: {final_results[0]['relevance_score']:.3f}")
            else:
                logger.warning(f"🔍 Scout search '{query}' found no results")
            
            return final_results
            
        except Exception as e:
            logger.error(f"Scout search failed for '{query}': {e}")
            import traceback
            traceback.print_exc()
            return []
