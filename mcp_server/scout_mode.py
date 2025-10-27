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

# Phase 1: Scout Mode v2 - Column Role Enricher
try:
    from mcp_server.column_enricher import ColumnRoleEnricher
except ImportError:
    ColumnRoleEnricher = None
    logger.warning("⚠️ ColumnRoleEnricher not available, column role tagging disabled")

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


class SemanticDescriptionGenerator:
    """
    Generate semantic descriptions for tables based on structure analysis.
    
    Analyzes table metadata (name, columns, foreign keys, data types) to create
    human-readable descriptions that help the agent understand table purpose.
    
    Examples:
    - "Stores customer profile information including contact details"
    - "Records sales transactions with amounts and dates"
    - "Hub table connecting orders to line items and products"
    """
    
    # Domain keywords mapped to common table purposes
    DOMAIN_KEYWORDS = {
        'customer': 'customer management',
        'client': 'customer management',
        'order': 'sales/transactions',
        'sale': 'sales/transactions',
        'invoice': 'financial/billing',
        'payment': 'financial/billing',
        'product': 'inventory/catalog',
        'inventory': 'inventory/stock',
        'warehouse': 'inventory/stock',
        'supplier': 'procurement',
        'vendor': 'procurement',
        'employee': 'human resources',
        'staff': 'human resources',
        'address': 'contact information',
        'contact': 'contact information',
        'phone': 'contact information',
        'email': 'contact information',
        'log': 'audit/history',
        'history': 'audit/history',
        'transaction': 'financial/transactions',
        'ledger': 'financial/accounting',
        'budget': 'financial/planning',
        'report': 'reporting/analytics',
        'metric': 'reporting/analytics',
        'config': 'system configuration',
        'setting': 'system configuration',
    }
    
    # Common column name patterns
    COLUMN_PATTERNS = {
        'amount': 'financial amount',
        'price': 'pricing information',
        'quantity': 'quantity/count',
        'date': 'temporal data',
        'time': 'temporal data',
        'created': 'audit timestamp',
        'modified': 'audit timestamp',
        'status': 'status/state',
        'code': 'coded identifier',
        'name': 'text identifier',
        'description': 'descriptive text',
        'comment': 'descriptive text',
        'note': 'descriptive text',
    }
    
    @staticmethod
    def _extract_domain_keywords(table_name: str, columns: List[Dict]) -> List[str]:
        """Extract domain keywords from table and column names."""
        keywords = []
        
        # Check table name
        name_lower = table_name.lower()
        for keyword, domain in SemanticDescriptionGenerator.DOMAIN_KEYWORDS.items():
            if keyword in name_lower:
                keywords.append(domain)
        
        # Check column names
        if columns:
            col_names = ' '.join([col.get('name', '').lower() for col in columns])
            for keyword, domain in SemanticDescriptionGenerator.DOMAIN_KEYWORDS.items():
                if keyword in col_names and domain not in keywords:
                    keywords.append(domain)
        
        return list(set(keywords))  # Deduplicate
    
    @staticmethod
    def _characterize_table(table_info: Dict[str, Any]) -> str:
        """
        Characterize table based on data type composition.
        
        Returns a descriptive phrase about the table's nature.
        """
        numeric_count = len(table_info.get('numeric_columns', []))
        date_count = len(table_info.get('date_columns', []))
        text_count = len(table_info.get('text_columns', []))
        fk_count = table_info.get('fk_count', 0)
        col_count = table_info.get('column_count', 0)
        
        characteristics = []
        
        # Analyze composition
        if fk_count > 5:
            characteristics.append("hub/junction table")
        elif fk_count > 2:
            characteristics.append("relational table")
        
        if numeric_count > col_count * 0.5:
            characteristics.append("financial/analytical data")
        
        if date_count > col_count * 0.3:
            characteristics.append("temporal data")
        
        if text_count > col_count * 0.5:
            characteristics.append("descriptive/categorical data")
        
        return ', '.join(characteristics) if characteristics else "data table"
    
    @staticmethod
    def generate_description(table_info: Dict[str, Any]) -> str:
        """
        Generate a semantic description for a table.
        
        Args:
            table_info: Table metadata dict with name, columns, foreign_keys, etc.
            
        Returns:
            Human-readable description (1-2 sentences)
        """
        name = table_info.get('name', 'Unknown')
        columns = table_info.get('columns', [])
        fk_count = table_info.get('fk_count', 0)
        
        # Extract domain keywords
        domains = SemanticDescriptionGenerator._extract_domain_keywords(name, columns)
        
        # Characterize the table
        characteristics = SemanticDescriptionGenerator._characterize_table(table_info)
        
        # Build description
        parts = []
        
        # Main purpose
        if domains:
            parts.append(f"Stores {', '.join(domains[:2])} information")
        else:
            parts.append(f"Contains {characteristics}")
        
        # Additional context
        context_parts = []
        
        # Check for common column types
        col_names_str = ' '.join([col.get('name', '').lower() for col in columns]).lower()
        
        if any(word in col_names_str for word in ['amount', 'price', 'total', 'cost']):
            context_parts.append("with financial amounts")
        
        if any(word in col_names_str for word in ['date', 'time', 'created', 'modified']):
            context_parts.append("with temporal tracking")
        
        if fk_count > 0:
            context_parts.append(f"connected to {fk_count} other table(s)")
        
        if context_parts:
            parts.append(' '.join(context_parts))
        
        description = ' '.join(parts).rstrip('.')
        return description[:150]  # Cap at 150 chars


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
                "uri": f"table://{schema}/{name}",  # 🆕 Semantic URI for agent reference
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
                "fk_count": 0,
                "description": ""  # 🆕 Will be filled after fetching columns
            }
            
            # Try to fetch full table details for columns and foreign keys
            try:
                if db_adapter and hasattr(db_adapter, 'catalog') and db_adapter.catalog:
                    full_table = db_adapter.catalog.get_table(schema, name)
                    if full_table:
                        # ✅ Now working with full dict that includes columns
                        columns = full_table.get('columns', [])
                        
                        # Ensure columns are in dict format (not dataclass objects)
                        columns_list = []
                        for col in columns:
                            if isinstance(col, dict):
                                columns_list.append(col)
                            elif hasattr(col, '__dataclass_fields__'):
                                from dataclasses import asdict
                                columns_list.append(asdict(col))
                            else:
                                logger.warning(f"Unexpected column format for {full_name}: {type(col)}")
                                columns_list.append({'name': str(col), 'type': 'unknown'})
                        
                        table_info["columns"] = columns_list
                        table_info["primary_keys"] = full_table.get('primary_keys', [])
                        
                        # Ensure foreign_keys are in dict format
                        fk_list = []
                        for fk in full_table.get('foreign_keys', []):
                            if isinstance(fk, dict):
                                fk_list.append(fk)
                            elif hasattr(fk, '__dataclass_fields__'):
                                from dataclasses import asdict
                                fk_list.append(asdict(fk))
                            else:
                                fk_list.append({'column': str(fk), 'referenced_table': 'unknown'})
                        
                        table_info["foreign_keys"] = fk_list
                        
                        # 🆕 Phase 1: Enrich columns with role hints (German/English fuzzy matching)
                        if ColumnRoleEnricher:
                            try:
                                enricher = ColumnRoleEnricher(use_llm=False)  # Pure fuzzy for now
                                table_info["columns"] = enricher.enrich_columns(
                                    table_info["columns"],
                                    fk_list
                                )
                            except Exception as e:
                                logger.debug(f"Column role enrichment failed for {full_name}: {e}")
                        
                        # 🆕 Index columns by type for semantic ranking
                        table_info["fk_count"] = len(fk_list)
                        
                        numeric_types = {'int', 'float', 'decimal', 'numeric', 'bigint', 'smallint', 'money', 'real'}
                        date_types = {'date', 'datetime', 'datetime2', 'timestamp', 'time'}
                        text_types = {'varchar', 'text', 'nvarchar', 'char', 'string'}
                        
                        for col in table_info["columns"]:
                            try:
                                col_type = str(col.get('type', '')).lower() if isinstance(col, dict) else str(col).lower()
                                col_name = str(col.get('name', '')) if isinstance(col, dict) else str(col)
                                
                                if any(t in col_type for t in numeric_types):
                                    table_info["numeric_columns"].append(col_name)
                                if any(t in col_type for t in date_types):
                                    table_info["date_columns"].append(col_name)
                                if any(t in col_type for t in text_types):
                                    table_info["text_columns"].append(col_name)
                            except Exception as col_error:
                                logger.debug(f"Could not process column type for {full_name}: {col_error}")
            except Exception as e:
                logger.warning(f"Could not fetch full details for {full_name}: {e}")
            
            # 🆕 Generate semantic description based on table structure
            try:
                table_info["description"] = SemanticDescriptionGenerator.generate_description(table_info)
            except Exception as e:
                logger.debug(f"Could not generate description for {full_name}: {e}")
                table_info["description"] = f"Table {name}"  # Fallback
            
            catalog["tables"].append(table_info)
        
        return catalog
    
    def _build_fuzzy_index(self, catalog: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build fuzzy matching index for tables, columns, and descriptions."""
        index = {
            "table_names": {},
            "column_names": {},
            "normalized_names": {},
            "description_keywords": {}  # 🆕 For semantic search
        }
        
        for table in catalog["tables"]:
            full_name = table["full_name"]
            short_name = table["name"]
            description = table.get("description", "")
            
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
            
            # 🆕 Extract keywords from description for semantic search
            if description:
                # Split description into keywords
                keywords = description.lower().split()
                for keyword in keywords:
                    if len(keyword) > 2:  # Ignore short words
                        clean_keyword = keyword.strip('.,;:')
                        if clean_keyword not in index["description_keywords"]:
                            index["description_keywords"][clean_keyword] = []
                        if full_name not in index["description_keywords"][clean_keyword]:
                            index["description_keywords"][clean_keyword].append(full_name)
        
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
                
                # 🆕 Description match (semantic search)
                description = table.get("description", "").lower()
                description_similarity = 0.0
                if description and query_lower in description:
                    # Boost if query appears in description
                    description_similarity = 0.70
                elif description:
                    # Try fuzzy match on description
                    description_similarity = difflib.SequenceMatcher(None, query_lower, description).ratio() * 0.5
                
                best_name_similarity = max(best_name_similarity, description_similarity)
                
                # Calculate overall similarity
                if best_name_similarity >= 0.60 or col_matches or description_similarity >= 0.5:
                    # Boost score if there are column matches
                    if col_matches:
                        best_name_similarity = max(best_name_similarity, 0.65)
                    
                    reason = "fuzzy"
                    if component_similarity > name_similarity:
                        reason = "component_match"
                    if col_matches:
                        reason = "column_match"
                    if description_similarity > best_name_similarity * 0.8:  # 🆕 Description match was primary
                        reason = "description_match"
                    
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
            # Ensure all objects are JSON serializable
            catalog = self._make_json_serializable(catalog)
            index = self._make_json_serializable(index)
            
            with open(self.catalog_path, 'w') as f:
                json.dump(catalog, f, indent=2, default=str)
            
            with open(self.index_path, 'w') as f:
                json.dump(index, f, indent=2, default=str)
            
            logger.info(f"✅ Scout catalog saved to {self.catalog_path}")
        except Exception as e:
            logger.error(f"Failed to save scout catalog: {e}")
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """
        Recursively convert objects to JSON-serializable format.
        
        Converts dataclasses, objects with __dict__, and other non-serializable types
        to dictionaries or strings.
        """
        if obj is None:
            return None
        
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        if isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        
        # Handle dataclasses
        if hasattr(obj, '__dataclass_fields__'):
            from dataclasses import asdict
            return self._make_json_serializable(asdict(obj))
        
        # Handle objects with __dict__
        if hasattr(obj, '__dict__'):
            return self._make_json_serializable(obj.__dict__)
        
        # Fallback to string representation
        return str(obj)
    
    def _load_cached_catalog(self) -> Optional[Dict[str, Any]]:
        """Load cached catalog from disk."""
        try:
            if self.catalog_path.exists():
                try:
                    with open(self.catalog_path, 'r') as f:
                        return json.load(f)
                except json.JSONDecodeError as je:
                    logger.error(f"Scout catalog JSON is malformed: {je}")
                    logger.error(f"Catalog path: {self.catalog_path}")
                    # Try to salvage by deleting the corrupted cache
                    try:
                        self.catalog_path.unlink()
                        logger.info("Deleted corrupted scout catalog cache")
                    except Exception as delete_error:
                        logger.error(f"Could not delete corrupted cache: {delete_error}")
                    return None
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