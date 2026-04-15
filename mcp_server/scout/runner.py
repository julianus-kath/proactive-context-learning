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
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

from mcp_server.catalog.store import CatalogStore
from mcp_server.catalog.builders.mssql import MSSQLCatalogBuilder
from mcp_server.catalog.builders.postgres import PostgresCatalogBuilder
from mcp_server.scout.description_generator import (
    DescriptionGenerator,
    NullDescriptionGenerator,
    build_description_generator_from_env,
)
from mcp_server.scout.description_enricher import enrich_tables_with_descriptions

logger = logging.getLogger(__name__)


# ============================================================================
# SEMANTIC SEARCH HELPERS (from scout_mode.py)
# ============================================================================

class TableNameNormalizer:
    """Normalize table names for fuzzy matching."""

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize table name by removing schema prefix and lowercasing."""
        normalized = name.lower()
        # Only remove standard SQL schema prefix
        if normalized.startswith('dbo.'):
            normalized = normalized[4:]
        return normalized
    
    @staticmethod
    def extract_components(name: str) -> List[str]:
        """
        Extract components from camelCase/PascalCase names using general rules.

        Properly handles:
        - KHKStatVKKunden -> ["khk", "stat", "vk", "kunden"]
        - BSEinstellungen -> ["bs", "einstellungen"]
        - MAArtikel -> ["ma", "artikel"]
        - XMLParser -> ["xml", "parser"]
        """
        # Split on transitions using general CamelCase rules (no hardcoded prefixes)
        # 1. Insert _ before uppercase that follows lowercase (e.g., Stat_VK)
        split1 = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        # 2. Insert _ before last uppercase in a run when followed by lowercase
        #    (e.g., KHKStat -> KHK_Stat, VKKunden -> VK_Kunden)
        split2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', split1)

        # Split on _ and filter short components
        components = [c.lower() for c in split2.split('_') if len(c) >= 2]
        return components

    @staticmethod
    def safe_fuzzy_match(query: str, target: str) -> float:
        """
        Fuzzy match that prevents false suffix matches.

        Problem: "Bestellungen" matches "Einstellungen" (both end in "-stellungen")
        with similarity 0.833 - but these are completely different words!

        Solution: Require minimum prefix overlap before allowing fuzzy match.
        """
        query = query.lower()
        target = target.lower()

        # Exact substring is always a strong match
        if query in target:
            return 0.9

        # For fuzzy matching, require at least first 3 chars (or half the query) to appear
        # somewhere in the first half of target to prevent false suffix matches
        min_prefix_len = min(3, len(query) // 2 + 1)
        query_prefix = query[:min_prefix_len]
        target_check_region = target[:len(target) // 2 + min_prefix_len]

        if query_prefix not in target_check_region:
            # Prefix doesn't appear early in target - likely a false suffix match
            # Still allow very weak match if difflib score is extremely high
            base_ratio = difflib.SequenceMatcher(None, query, target).ratio()
            if base_ratio > 0.95:
                return base_ratio * 0.5  # Heavily penalize
            return 0.0

        # Prefix matches, safe to use normal fuzzy matching
        return difflib.SequenceMatcher(None, query, target).ratio()

    @staticmethod
    def get_component_match(query: str, name: str) -> float:
        """Check if query matches any component of the table name."""
        query_lower = query.lower()
        name_lower = name.lower()

        if query_lower in name_lower:
            return 0.85

        # Extract components properly from camelCase name
        components = TableNameNormalizer.extract_components(name)

        # Find best component match using safe fuzzy matching
        best_match = 0.0
        for component in components:
            # Use safe fuzzy match to prevent false suffix matches
            similarity = TableNameNormalizer.safe_fuzzy_match(query_lower, component)
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
        max_concurrent_builds: int = 1,
        description_generator: Optional[DescriptionGenerator] = None,
    ):
        """
        Initialize Scout Runner.

        Args:
            db_adapter: Database adapter for schema access
            catalog_dir: Directory for catalog storage
            ttl_hours: Catalog time-to-live in hours
            refresh_interval_hours: How often to check for refresh
            max_concurrent_builds: Max concurrent catalog builds
            description_generator: Optional SDG v2 description generator. If
                None, one is built from environment variables. Pass an explicit
                generator in tests or to pre-seed with a mock.
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

        # SDG v2: runtime-toggled semantic descriptions. A NullDescriptionGenerator
        # (default when SCOUT_DESCRIPTIONS_ENABLED is unset or false) stamps every
        # table with description="" and never calls any LLM — current behaviour
        # is preserved. An enabled generator enriches the catalog lazily the
        # first time get_catalog() is called after the catalog is available, and
        # the enriched catalog is then cached in-process for subsequent calls.
        self._description_generator: DescriptionGenerator = (
            description_generator
            if description_generator is not None
            else build_description_generator_from_env()
        )
        self._enriched_catalog: Optional[Dict[str, Any]] = None
        self._enrichment_done: bool = False

        logger.info(
            "✅ ScoutRunner initialized: TTL=%sh, refresh=%sh, descriptions=%s",
            ttl_hours,
            refresh_interval_hours,
            "on" if getattr(self._description_generator, "enabled", False) else "off",
        )

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
            builder = self._get_catalog_builder()
            catalog_data = await builder.build_catalog()

            # Store catalog
            success = self.store.store_catalog(catalog_data)

            if success:
                # Update stats
                build_duration = (datetime.utcnow() - build_start).total_seconds()
                self.build_count += 1
                self.last_build_duration = build_duration
                self.last_build_time = datetime.utcnow()

                # Fresh catalog → drop the in-process enriched copy so the next
                # get_catalog() call re-runs SDG enrichment.
                self.invalidate_enrichment_cache()

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

    def _get_catalog_builder(self):
        """
        Select appropriate catalog builder based on database dialect.

        Uses PostgresCatalogBuilder for postgres and MSSQLCatalogBuilder for mssql.
        """
        dialect = getattr(self.db_adapter, "dialect", None)
        if isinstance(dialect, str):
            dialect = dialect.lower()

        if dialect == "postgres":
            logger.info("📘 Using PostgresCatalogBuilder for Scout catalog")
            return PostgresCatalogBuilder(self.db_adapter)
        if dialect == "mssql":
            logger.info("📙 Using MSSQLCatalogBuilder for Scout catalog")
            return MSSQLCatalogBuilder(self.db_adapter)

        # Fallback: default to Postgres builder but log a warning
        logger.warning(f"Unknown dialect '{dialect}' in ScoutRunner; defaulting to PostgresCatalogBuilder")
        return PostgresCatalogBuilder(self.db_adapter)



    def get_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Get current catalog data, enriched with SDG v2 descriptions if enabled.

        When SCOUT_DESCRIPTIONS_ENABLED=true (or an explicit generator was
        injected in __init__), the first call after the catalog becomes
        available runs the generator over every table. The enriched catalog is
        then held in-process so subsequent calls are free.

        When disabled, returns the raw catalog from the store with
        description="" stamped on every table.
        """
        if self._enriched_catalog is not None:
            return self._enriched_catalog

        catalog = self.store.load_catalog()
        if catalog is None:
            return None

        tables = catalog.get("tables", []) or []
        gen = self._description_generator
        gen_kind = type(gen).__name__
        gen_enabled = bool(getattr(gen, "enabled", False))
        logger.info(
            "🔤 SDG enrichment START: generator=%s enabled=%s tables=%d",
            gen_kind, gen_enabled, len(tables),
        )
        try:
            written = enrich_tables_with_descriptions(tables, gen)
        except Exception as exc:
            logger.error("🔤 SDG enrichment FAILED: %s", exc)
            written = 0

        # Audit what actually landed on the catalog after enrichment so we
        # can see from the logs whether descriptions are present.
        non_empty = sum(
            1 for t in tables
            if isinstance(t, dict) and (t.get("description") or "").strip()
        )
        preview_table = next(
            (t for t in tables if isinstance(t, dict) and (t.get("description") or "").strip()),
            None,
        )
        if preview_table is not None:
            preview = (preview_table.get("description") or "")[:120].replace("\n", " ")
            logger.info(
                "🔤 SDG enrichment DONE: writes=%d non_empty=%d/%d preview[%s]=%r",
                written, non_empty, len(tables),
                preview_table.get("full_name"), preview,
            )
        else:
            logger.info(
                "🔤 SDG enrichment DONE: writes=%d non_empty=%d/%d (no descriptions present)",
                written, non_empty, len(tables),
            )

        self._enriched_catalog = catalog
        self._enrichment_done = True
        return self._enriched_catalog

    def invalidate_enrichment_cache(self) -> None:
        """Drop the in-process enriched catalog. Call after a fresh rebuild."""
        self._enriched_catalog = None
        self._enrichment_done = False

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
    
    def get_catalog_diagnostics(self) -> Dict[str, Any]:
        """
        Return detailed catalog diagnostics (coverage, freshness, alerts).
        """
        from mcp_server.scout.diagnostics import summarize_catalog
        return summarize_catalog(str(self.store.catalog_dir))
    
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

            # Split multi-word queries into tokens for matching
            # "Umsatz Kunden Bestellungen" -> ["umsatz", "kunden", "bestellungen"]
            query_tokens = [t.lower().strip() for t in query.split() if len(t.strip()) >= 3]
            if not query_tokens:
                # Fallback for short queries
                query_tokens = [query_lower] if query_lower else []

            for table in tables:
                full_name = table.get("full_name", "")
                name = table.get("name", "")
                schema = table.get("schema", "dbo")
                estimated_rows = table.get("estimated_rows", 0)
                table_type = table.get("type", "TABLE")
                columns = table.get("columns", [])

                name_lower = name.lower()
                full_name_lower = full_name.lower()
                normalized = TableNameNormalizer.normalize(name)

                # Extract table name components for matching
                table_components = TableNameNormalizer.extract_components(name)

                # Scoring system
                score = 0.0
                reasons = []
                matched_tokens = []

                # 1. Exact match (highest priority)
                if query_lower == name_lower or query_lower == normalized or query_lower in full_name_lower:
                    score = 1.0
                    reasons.append("Exact match")
                else:
                    # 2. Multi-token matching: count how many query tokens match
                    for token in query_tokens:
                        # Check direct substring match
                        if token in name_lower or token in full_name_lower:
                            matched_tokens.append(token)
                            continue

                        # Check component match with safe fuzzy matching
                        for component in table_components:
                            if TableNameNormalizer.safe_fuzzy_match(token, component) >= 0.8:
                                matched_tokens.append(token)
                                break

                    # Score based on token match ratio
                    if query_tokens and matched_tokens:
                        token_match_score = len(matched_tokens) / len(query_tokens)
                        score = max(score, token_match_score * 0.9)  # Scale to max 0.9
                        reasons.append(f"Token match: {len(matched_tokens)}/{len(query_tokens)} ({', '.join(matched_tokens)})")

                    # 3. Fallback: single-token fuzzy matching for simple queries
                    if len(query_tokens) == 1:
                        # Use safe fuzzy match to prevent false suffix matches
                        name_similarity = TableNameNormalizer.safe_fuzzy_match(query_lower, name_lower)
                        component_similarity = TableNameNormalizer.get_component_match(query, name)

                        best_fuzzy = max(name_similarity, component_similarity)
                        if best_fuzzy > score:
                            score = best_fuzzy
                            if score >= 0.7:
                                reasons.append(f"Fuzzy match: {score:.2f}")
                
                # 4. Column name matches (check all query tokens)
                col_matches = []
                for col in columns:
                    col_name = col.get("name", "").lower() if isinstance(col, dict) else str(col).lower()
                    for token in query_tokens:
                        if token in col_name:
                            col_matches.append(col_name)
                            break

                if col_matches:
                    score = max(score, 0.65)
                    reasons.append(f"Column match: {', '.join(col_matches[:3])}")

                # 5. Row count bonus (non-empty tables preferred)
                if estimated_rows and estimated_rows > 0:
                    score = min(1.0, score + 0.05)
                    reasons.append(f"{estimated_rows} rows")
                
                # Filter out empty tables unless they have very high relevance
                if estimated_rows == 0 and score < 0.8:
                    reasons.append("empty table (filtered)")
                    continue

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
