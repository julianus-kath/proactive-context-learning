"""
Health endpoint for MCP server with Scout Mode metrics.
Phase 1: Catalog health monitoring and metrics.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Global Scout Runner reference (set by server on startup)
_scout_runner_ref = None


def set_scout_runner(scout_runner):
    """
    Set the global Scout Runner reference for health monitoring.

    Args:
        scout_runner: ScoutRunner instance
    """
    global _scout_runner_ref
    _scout_runner_ref = scout_runner
    logger.info("✅ Scout Runner reference set for health monitoring")


async def get_health_status(db_manager=None) -> Dict[str, Any]:
    """
    Get comprehensive health status including Scout catalog metrics.

    Args:
        db_manager: Database manager (optional, for basic connectivity check)

    Returns:
        Health status dictionary
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0",
        "components": {}
    }

    try:
        # Database connectivity check
        db_healthy = False
        dialect: Optional[str] = None
        has_schema_catalog = False

        if db_manager:
            try:
                # Simple connectivity test
                test_result = await db_manager.fetch("SELECT 1 as test")
                db_healthy = len(test_result) > 0
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")

            # Inspect dialect and Phase 3 SchemaCatalog presence
            dialect = getattr(db_manager, "dialect", None)
            if isinstance(dialect, str):
                dialect = dialect.lower()
            has_schema_catalog = getattr(db_manager, "catalog", None) is not None

        health["components"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "connectivity": db_healthy,
            "dialect": dialect or "unknown",
        }

        # Scout / catalog health
        if _scout_runner_ref:
            # Full ScoutRunner-based catalog (primarily MSSQL, but supports Postgres too)
            scout_health = _scout_runner_ref.get_health_status()

            health["components"]["scout_catalog"] = {
                "status": "healthy" if scout_health.get("catalog_valid") else "building",
                "catalog_exists": scout_health.get("catalog_exists", False),
                "catalog_valid": scout_health.get("catalog_valid", False),
                "catalog_age_hours": scout_health.get("catalog_age_hours"),
                "catalog_ttl_hours": scout_health.get("catalog_ttl_hours"),
                "build_in_progress": scout_health.get("build_in_progress", False),
                "build_count": scout_health.get("build_count", 0),
                "last_build_duration": scout_health.get("last_build_duration", 0),
                "last_build_time": scout_health.get("last_build_time"),
                "compressed_size_mb": round(scout_health.get("compressed_size", 0) / (1024*1024), 2) if scout_health.get("compressed_size") else None,
                "compression_ratio": scout_health.get("compression_ratio"),
                "backend": "ScoutRunner",
            }

            # Overall status reflects catalog readiness when ScoutRunner is present
            if not scout_health.get("catalog_valid") and scout_health.get("build_in_progress"):
                health["status"] = "building_catalog"
            elif not scout_health.get("catalog_valid"):
                health["status"] = "catalog_unavailable"

        elif has_schema_catalog:
            # Phase 3 SchemaCatalog is available (e.g., Postgres dev mode)
            # Treat this as a healthy catalog backend even without ScoutRunner.
            summary: Dict[str, Any] = {}
            try:
                if hasattr(db_manager, "get_catalog_summary"):
                    summary = db_manager.get_catalog_summary() or {}
            except Exception as e:
                logger.warning(f"SchemaCatalog summary retrieval failed: {e}")

            table_count = (
                summary.get("table_count")
                or summary.get("tables")
                or summary.get("tables_count")
            )

            health["components"]["scout_catalog"] = {
                "status": "healthy",
                "catalog_exists": True,
                "catalog_valid": True,
                "backend": "SchemaCatalog",
                "dialect": dialect or "unknown",
                "table_count": table_count,
            }
            # Overall health remains driven by DB + generic status; do not downgrade

        else:
            # No ScoutRunner and no SchemaCatalog – catalog not initialized
            health["components"]["scout_catalog"] = {
                "status": "not_initialized",
                "catalog_exists": False,
                "catalog_valid": False,
            }
            # Only mark overall status as scout_not_initialized if database itself is reachable;
            # otherwise leave it as unhealthy/error.
            if db_healthy:
                health["status"] = "scout_not_initialized"

        # Cache hit metrics (if available)
        if _scout_runner_ref:
            # Could add cache hit statistics here in future
            pass

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health["status"] = "error"
        health["error"] = str(e)

    return health


async def get_health_summary() -> str:
    """
    Get a human-readable health summary.

    Returns:
        Formatted health summary string
    """
    health = await get_health_status()

    summary = f"🏥 MCP Server Health: {health['status'].upper()}\n\n"

    for component_name, component_health in health.get("components", {}).items():
        status = component_health.get("status", "unknown")
        status_icon = "✅" if status == "healthy" else "⚠️" if status == "building" else "❌"

        summary += f"{status_icon} {component_name}: {status}\n"

        if component_name == "scout_catalog":
            if component_health.get("catalog_valid"):
                age = component_health.get("catalog_age_hours", 0)
                ttl = component_health.get("catalog_ttl_hours", 0)
                summary += f"   📊 Catalog age: {age:.1f}h / {ttl}h TTL\n"
                if component_health.get("compressed_size_mb"):
                    summary += f"   📦 Size: {component_health.get('compressed_size_mb')}MB compressed\n"
            elif component_health.get("build_in_progress"):
                summary += f"   🏗️ Catalog build in progress...\n"

    summary += f"\n📅 Last updated: {health['timestamp']}"
    return summary
