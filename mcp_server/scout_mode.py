"""
Scout Mode: Autonomous startup discovery with semantic indexing.

Phase 7 Enhancement:
- Runs on server startup to index database schema
- Builds semantic catalog with table metadata
- Creates fuzzy matching index for table discovery
- Caches results to disk for fast subsequent startups
- Falls back to on-demand search if catalog unavailable

Architecture:
- Lazy initialization: Scout Mode runs async during startup, doesn't block
- Semantic indexing: Uses string similarity (Levenshtein distance)
- German name handling: Strips prefixes (dbo., vew, tbl, BS, VK)
- Hybrid matching: Exact match (1.0), fuzzy (0.72+), runners-up (0.60-0.72)
"""

import os
import json
import logging
import time
import difflib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TableSearchResult:
    """Result from table search."""
    table_name: str
    full_name: str
    schema: str
    similarity: float  # 0.0 to 1.0
    reason: str  # "exact", "fuzzy", "prefix_match", etc.
    column_matches: List[str] = None  # Matching columns


class TableNameNormalizer:
    """Normalize table names for fuzzy matching (handles German prefixes)."""
    
    # German/SQL prefixes to strip
    PREFIXES = {
        'dbo.': '',      # SQL Server schema prefix
        'vew': '',       # View prefix
        'tbl': '',       # Table prefix
        'bs': '',        # German prefix (Bestand, Stamm)
        'vk': '',        # German prefix (Verkauf)
        'kd': '',        # German prefix (Kunde/Customer)
        'mat': '',       # German prefix (Material)
        'obj': '',       # Generic prefix
    }
    
    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize a table name by removing common prefixes and lowercasing.
        
        Args:
            name: Table name (e.g., "BSOffeneVKLieferungen")
            
        Returns:
            Normalized name (e.g., "offenelieferungen")
        """
        normalized = name.lower()
        
        # Strip known prefixes
        for prefix, replacement in TableNameNormalizer.PREFIXES.items():
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):] + replacement
        
        return normalized
    
    @staticmethod
    def get_component_match(query: str, name: str) -> float:
        """
        Check if query matches any component of the table name.
        E.g., "Offene" matches "BSOffeneVKLieferungen"
        """
        query_lower = query.lower()
        name_lower = name.lower()
        
        # Check if query is substring
        if query_lower in name_lower:
            return 0.85
        
        # Check each word component
        components = []
        current = ""
        for char in name_lower:
            if char.isupper() or not char.isalpha():
                if current:
                    components.append(current)
                current = ""
            else:
                current += char
        if current:
            components.append(current)
        
        # Find best component match
        best_match = 0.0
        for component in components:
            similarity = difflib.SequenceMatcher(None, query_lower, component).ratio()
            if similarity > best_match:
                best_match = similarity
        
        return best_match


class SemanticCatalogBuilder:
    """Build semantic catalog with fuzzy matching index."""
    
    def __init__(self, cache_dir: str = "cache", ttl_days: int = 7):
        """
        Initialize the Scout Mode builder.
        
        Args:
            cache_dir: Directory to store catalog cache
            ttl_days: Time-to-live for cached catalog (in days)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        self.catalog_path = self.cache_dir / "scout_catalog.json"
        self.index_path = self.cache_dir / "scout_index.json"
    
    async def scout(self, db_adapter, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Run Scout Mode: build semantic catalog and index.
        
        Args:
            db_adapter: DatabaseAdapter instance
            force_rebuild: Force rebuild even if cache is valid
            
        Returns:
            Scout report with metrics
        """
        start_time = time.time()
        report = {
            "phase": "Scout Mode",
            "status": "starting",
            "timestamp": datetime.now().isoformat(),
            "total_time_ms": 0,
            "tables_indexed": 0,
            "cache_used": False,
            "errors": []
        }
        
        try:
            # Check if cache is valid
            if not force_rebuild and self._is_cache_valid():
                logger.info("📚 Scout Mode: Using valid cached catalog")
                cached_catalog = self._load_cached_catalog()
                report["status"] = "success"
                report["cache_used"] = True
                report["tables_indexed"] = len(cached_catalog.get("tables", []))
                report["total_time_ms"] = int((time.time() - start_time) * 1000)
                return report
            
            logger.info("🔍 Scout Mode: Building semantic catalog...")
            
            # Get tables from database
            if not hasattr(db_adapter, 'catalog') or not db_adapter.catalog:
                logger.warning("⚠️ Scout Mode: Catalog not available, using connector")
                tables = await db_adapter.connector.get_table_list()
            else:
                tables = db_adapter.catalog.get_table_list()
            
            if not tables:
                raise RuntimeError("No tables found in database")
            
            # Build semantic index
            catalog = self._build_catalog(tables, db_adapter)
            index = self._build_fuzzy_index(catalog)
            
            # Cache the results
            self._save_catalog(catalog, index)
            
            report["status"] = "success"
            report["tables_indexed"] = len(catalog["tables"])
            report["total_time_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"✅ Scout Mode: Indexed {len(catalog['tables'])} tables in {report['total_time_ms']}ms")
            
        except Exception as e:
            report["status"] = "error"
            report["errors"].append(str(e))
            logger.error(f"❌ Scout Mode failed: {e}")
        
        return report
    
    def _build_catalog(self, tables: List[Any], db_adapter=None) -> Dict[str, Any]:
        """Build semantic catalog from table list with type metadata for ranking."""
        catalog = {
            "version": "1.1",  # Updated version for semantic metadata
            "built_at": datetime.now().isoformat(),
            "tables": [],
            "search_index": {}
        }
        
        for table in tables:
            # ✅ Access as dict, not object
            schema = table['schema']
            name = table['name']
            full_name = table['full_name']
            
            table_info = {
                "name": name,
                "schema": schema,
                "full_name": full_name,
                "type": table['type'],
                "estimated_rows": table['estimated_rows'],
                "column_count": table.get('column_count', 0),
                "columns": [],
                "primary_keys": [],
                "foreign_keys": [],
                # 🆕 Phase 7.1: Semantic metadata for ranking
                "numeric_columns": [],
                "date_columns": [],
                "text_columns": [],
                "fk_count": 0
            }
            
            # Try to fetch full table details for columns and foreign keys
            try:
                if db_adapter and hasattr(db_adapter, 'catalog') and db_adapter.catalog:
                    full_table = db_adapter.catalog.get_table(schema, name)
                    if full_table:
                        # ✅ Now working with full dict that includes columns
                        table_info["columns"] = full_table.get('columns', [])
                        table_info["primary_keys"] = full_table.get('primary_keys', [])
                        table_info["foreign_keys"] = full_table.get('foreign_keys', [])
                        
                        # 🆕 Index columns by type for semantic ranking
                        table_info["fk_count"] = len(full_table.get('foreign_keys', []))
                        
                        numeric_types = {'int', 'float', 'decimal', 'numeric', 'bigint', 'smallint', 'money', 'real'}
                        date_types = {'date', 'datetime', 'datetime2', 'timestamp', 'time'}
                        text_types = {'varchar', 'text', 'nvarchar', 'char', 'string'}
                        
                        for col in table_info["columns"]:
                            col_type = col.get('type', '').lower()
                            col_name = col.get('name', '')
                            
                            if any(t in col_type for t in numeric_types):
                                table_info["numeric_columns"].append(col_name)
                            if any(t in col_type for t in date_types):
                                table_info["date_columns"].append(col_name)
                            if any(t in col_type for t in text_types):
                                table_info["text_columns"].append(col_name)
            except Exception as e:
                logger.warning(f"Could not fetch full details for {full_name}: {e}")
            
            catalog["tables"].append(table_info)
        
        return catalog
    
    def _build_fuzzy_index(self, catalog: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build fuzzy matching index for tables and columns."""
        index = {
            "table_names": {},
            "column_names": {},
            "normalized_names": {}
        }
        
        for table in catalog["tables"]:
            full_name = table["full_name"]
            short_name = table["name"]
            
            # Add to index with normalization
            normalized = TableNameNormalizer.normalize(short_name)
            index["table_names"][full_name] = short_name
            index["normalized_names"][normalized] = full_name
            
            # Index column names
            for col in table["columns"]:
                col_name = col["name"].lower()
                if col_name not in index["column_names"]:
                    index["column_names"][col_name] = []
                index["column_names"][col_name].append(full_name)
        
        return index
    
    def search(self, query: str, top_k: int = 5) -> List[TableSearchResult]:
        """
        Search for tables using fuzzy matching.
        
        Args:
            query: Search query (table name or keyword)
            top_k: Number of results to return
            
        Returns:
            List of matching tables sorted by relevance
        """
        try:
            catalog = self._load_cached_catalog()
            if not catalog:
                logger.warning("Scout catalog not available")
                return []
            
            results = []
            query_lower = query.lower()
            
            for table in catalog.get("tables", []):
                full_name = table["full_name"]
                short_name = table["name"].lower()
                normalized = TableNameNormalizer.normalize(table["name"])
                
                # Exact match (highest priority)
                if query_lower == short_name or query_lower == normalized:
                    results.append(TableSearchResult(
                        table_name=table["name"],
                        full_name=full_name,
                        schema=table["schema"],
                        similarity=1.0,
                        reason="exact"
                    ))
                    continue
                
                # Fuzzy name match
                name_similarity = difflib.SequenceMatcher(None, query_lower, short_name).ratio()
                
                # Component match (for German names)
                component_similarity = TableNameNormalizer.get_component_match(query, table["name"])
                
                best_name_similarity = max(name_similarity, component_similarity)
                
                # Column name match
                col_matches = []
                for col in table["columns"]:
                    if query_lower in col["name"].lower():
                        col_matches.append(col["name"])
                
                # Calculate overall similarity
                if best_name_similarity >= 0.60 or col_matches:
                    # Boost score if there are column matches
                    if col_matches:
                        best_name_similarity = max(best_name_similarity, 0.65)
                    
                    reason = "fuzzy"
                    if component_similarity > name_similarity:
                        reason = "component_match"
                    if col_matches:
                        reason = "column_match"
                    
                    results.append(TableSearchResult(
                        table_name=table["name"],
                        full_name=full_name,
                        schema=table["schema"],
                        similarity=best_name_similarity,
                        reason=reason,
                        column_matches=col_matches
                    ))
            
            # Sort by similarity (descending)
            results.sort(key=lambda x: (-x.similarity, x.table_name))
            
            # Apply thresholds: 0.72+ primary, 0.60-0.72 runners-up
            primary = [r for r in results if r.similarity >= 0.72]
            runners_up = [r for r in results if 0.60 <= r.similarity < 0.72]
            
            # Return top_k from combined list
            return (primary + runners_up)[:top_k]
            
        except Exception as e:
            logger.error(f"Scout search failed: {e}")
            return []
    
    def _save_catalog(self, catalog: Dict[str, Any], index: Dict[str, Any]):
        """Save catalog and index to disk."""
        try:
            with open(self.catalog_path, 'w') as f:
                json.dump(catalog, f, indent=2)
            
            with open(self.index_path, 'w') as f:
                json.dump(index, f, indent=2)
            
            logger.info(f"✅ Scout catalog saved to {self.catalog_path}")
        except Exception as e:
            logger.error(f"Failed to save scout catalog: {e}")
    
    def _load_cached_catalog(self) -> Optional[Dict[str, Any]]:
        """Load cached catalog from disk."""
        try:
            if self.catalog_path.exists():
                with open(self.catalog_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached catalog: {e}")
        
        return None
    
    def _is_cache_valid(self) -> bool:
        """Check if cached catalog is still valid."""
        if not self.catalog_path.exists():
            return False
        
        try:
            file_time = self.catalog_path.stat().st_mtime
            current_time = time.time()
            age_days = (current_time - file_time) / (24 * 3600)
            
            return age_days < self.ttl_days
        except Exception as e:
            logger.warning(f"Failed to check cache validity: {e}")
            return False


# Global Scout instance
_scout_instance: Optional[SemanticCatalogBuilder] = None


def get_scout_instance(cache_dir: str = "cache") -> SemanticCatalogBuilder:
    """Get or create Scout Mode instance."""
    global _scout_instance
    if _scout_instance is None:
        _scout_instance = SemanticCatalogBuilder(cache_dir=cache_dir)
    return _scout_instance


async def run_scout_mode(db_adapter, cache_dir: str = "cache", force_rebuild: bool = False) -> Dict[str, Any]:
    """
    Run Scout Mode: build semantic catalog on startup.
    
    This is safe to run during server startup and doesn't block.
    If catalog is already cached and valid, it returns immediately.
    """
    scout = get_scout_instance(cache_dir)
    return await scout.scout(db_adapter, force_rebuild=force_rebuild)