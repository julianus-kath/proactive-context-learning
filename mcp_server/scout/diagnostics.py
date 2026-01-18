"""
Scout catalog diagnostics utilities.

Provides structured summaries of the persisted Scout catalog so we can quickly
verify freshness, metadata coverage, and ranking readiness without manually
inspecting the compressed JSON files.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from mcp_server.catalog.store import CatalogStore


def _as_sequence(collection: Any) -> List[Dict[str, Any]]:
    """Normalize catalog entities to a list of dictionaries."""
    if isinstance(collection, dict):
        return list(collection.values())
    if isinstance(collection, list):
        return [item for item in collection if isinstance(item, dict)]
    return []


def _coverage(
    entities: Sequence[Dict[str, Any]],
    key: str,
    predicate,
) -> float:
    """Compute coverage ratio for a given key using predicate."""
    if not entities:
        return 0.0
    covered = sum(1 for entity in entities if predicate(entity.get(key)))
    return covered / len(entities)


def summarize_catalog(catalog_dir: str = "data/catalog") -> Dict[str, Any]:
    """
    Summarize scout catalog health and metadata coverage.

    Args:
        catalog_dir: Directory containing catalog files.

    Returns:
        Diagnostic dictionary with coverage ratios, freshness, and flags.
    """
    store = CatalogStore(catalog_dir=catalog_dir)
    metadata = store.get_metadata()
    stats = store.get_stats()
    catalog = store.load_catalog()

    if not catalog:
        reason = "catalog_missing"
        if stats.get("exists") and not stats.get("valid"):
            reason = "catalog_expired"
        return {
            "ok": False,
            "reason": reason,
            "metadata": metadata,
            "stats": stats,
            "catalog_dir": str(store.catalog_dir),
        }

    tables = _as_sequence(catalog.get("tables"))
    views = _as_sequence(catalog.get("views"))
    relationships = catalog.get("relationships") or []
    relationships_count = len(relationships) if isinstance(relationships, list) else len(relationships.keys())

    table_coverage = {
        "has_columns": _coverage(tables, "columns", lambda v: bool(v)),
        "has_column_count": _coverage(tables, "column_count", lambda v: isinstance(v, (int, float))),
        "has_estimated_rows": _coverage(tables, "estimated_rows", lambda v: v is not None),
        "has_fk_count": _coverage(tables, "fk_count", lambda v: v is not None),
    }

    view_coverage = {
        "has_columns": _coverage(views, "columns", lambda v: bool(v)),
        "has_role_coverage": _coverage(views, "role_coverage", lambda v: v is not None),
        "has_business_analysis": _coverage(views, "business_analysis", lambda v: bool(v)),
    }

    tables_missing_columns = [
        table.get("full_name", table.get("name"))
        for table in tables
        if not table.get("columns")
    ]
    tables_missing_estimates = [
        table.get("full_name", table.get("name"))
        for table in tables
        if table.get("estimated_rows") in (None, 0)
    ]
    views_missing_role = [
        view.get("full_name", view.get("name"))
        for view in views
        if view.get("role_coverage") is None
    ]

    issues: List[str] = []
    recommendations: List[str] = []

    if stats.get("valid") is False:
        issues.append("Catalog exists but expired (TTL exceeded).")
        recommendations.append("Trigger Scout catalog rebuild before answering discovery requests.")

    if table_coverage["has_columns"] < 0.8:
        issues.append("Less than 80% of tables expose column metadata.")
        recommendations.append("Ensure catalog builder fetches columns for every table (permissions / catalog builder health).")

    if table_coverage["has_estimated_rows"] < 0.6:
        issues.append("Row estimates missing for a large portion of tables.")
        recommendations.append("Consider enabling row-count probes or caching sampled counts for ranking.")

    if view_coverage["has_role_coverage"] < 0.6:
        issues.append("Role coverage missing on most views (views-first ranking may degrade).")
        recommendations.append("Audit view classification heuristics or re-run catalog build with required permissions.")

    if not issues and stats.get("valid"):
        recommendations.append("Scout catalog looks healthy; no immediate action required.")

    overview = {
        "tables": len(tables),
        "views": len(views),
        "relationships": relationships_count,
        "catalog_age_hours": stats.get("age_hours"),
        "catalog_ttl_hours": stats.get("ttl_hours"),
        "catalog_version": metadata.get("version") if metadata else None,
    }

    return {
        "ok": True,
        "catalog_dir": str(store.catalog_dir),
        "metadata": metadata,
        "stats": stats,
        "overview": overview,
        "table_coverage": table_coverage,
        "view_coverage": view_coverage,
        "tables_missing_columns": tables_missing_columns[:10],
        "tables_missing_row_estimates": tables_missing_estimates[:10],
        "views_missing_role_coverage": views_missing_role[:10],
        "issues": issues,
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    import json
    summary = summarize_catalog()
    print(json.dumps(summary, indent=2, ensure_ascii=False))

