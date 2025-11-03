"""
Scout Runner for Async Catalog Building
Phase 1: Background catalog indexing with TTL and non-blocking startup.

Manages the async Scout Mode catalog building process:
- Background catalog building on startup
- TTL-based refresh scheduling
- Non-blocking operation (serve from cache while building)
- Health monitoring and metrics
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from mcp_server.catalog_store import CatalogStore
from mcp_server.catalog_builders.mssql import MSSQLCatalogBuilder

logger = logging.getLogger(__name__)


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

    def _build_catalog_sync(self) -> Dict[str, Any]:
        """
        Synchronous catalog building (runs in thread pool).

        Returns:
            Built catalog data
        """
        # For now, return a minimal catalog to avoid complex async issues
        # TODO: Properly implement sync catalog building
        logger.warning("Using minimal catalog - async catalog building not fully implemented")

        return {
            "metadata": {
                "database_type": "mssql",
                "build_timestamp": datetime.utcnow().isoformat(),
                "tables_count": 0,
                "views_count": 0,
                "relationships_count": 0,
                "note": "Minimal catalog - full build failed"
            },
            "tables": {},
            "views": {},
            "relationships": []
        }

    async def _build_catalog_async(self) -> bool:
        """
        Build catalog asynchronously in background.

        Returns:
            True if successful
        """
        build_start = datetime.utcnow()
        logger.info("🏗️ Starting background catalog build...")

        try:
            # Run catalog building in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            catalog_data = await loop.run_in_executor(
                self._executor,
                self._build_catalog_sync
            )

            # Store catalog
            success = self.store.store_catalog(catalog_data)

            if success:
                # Update stats
                build_duration = (datetime.utcnow() - build_start).total_seconds()
                self.build_count += 1
                self.last_build_duration = build_duration
                self.last_build_time = datetime.utcnow()

                logger.info(
                    f"✅ Catalog build completed in {build_duration:.1f}s, "
                    f"total builds: {self.build_count}"
                )
                return True
            else:
                logger.error("❌ Failed to store built catalog")
                return False

        except Exception as e:
            build_duration = (datetime.utcnow() - build_start).total_seconds()
            logger.error(f"❌ Catalog build failed after {build_duration:.1f}s: {e}")
            return False

    def _build_catalog_sync(self) -> Dict[str, Any]:
        """
        Synchronous catalog building (runs in thread pool).

        Returns:
            Built catalog data
        """
        # Create catalog builder
        builder = MSSQLCatalogBuilder(self.db_adapter)

        # Run synchronous catalog build
        # Note: This assumes db_adapter has sync methods or we wrap async ones
        # For now, we'll implement a sync version

        catalog = asyncio.run(builder.build_catalog())
        return catalog

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
