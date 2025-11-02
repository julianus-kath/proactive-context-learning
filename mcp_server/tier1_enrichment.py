"""
Phase 9: Tier 1 Enrichment - Compute advanced metadata for better agent planning.

This module provides three enrichment capabilities:
1. ViewDependencyAnalyzer: Extract view dependencies, materialization status
2. FKCardinalityAnalyzer: Detect FK cardinality patterns (1:1, 1:N, N:N)
3. DomainClusterer: Identify business domains using FK graph + naming patterns

All analysis is cached-based (no live DB queries). Runs during Scout startup.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from mcp_server.catalog import (
    TableInfo,
    ColumnInfo,
    ForeignKeyInfo,
    ForeignKeyCardinality,
    ViewDependency,
    DomainMetadata,
)

logger = logging.getLogger(__name__)


# =====================================================
# 1. View Dependency Analyzer
# =====================================================

class ViewDependencyAnalyzer:
    """
    Analyzes view dependencies and materialization status.
    
    For each view, determines:
    - Which tables/views it depends on
    - Whether it's materialized (indexed view, computed column, etc.)
    - Materialization strategy type
    
    Optimizes query planning by:
    - Preferring materialized views (faster execution)
    - Avoiding redundant joins when view already includes logic
    """
    
    def __init__(self, catalog: Dict[str, TableInfo]):
        """
        Initialize analyzer.
        
        Args:
            catalog: Dict of table_name -> TableInfo
        """
        self.catalog = catalog
    
    def analyze_all_views(self) -> Dict[str, List[ViewDependency]]:
        """
        Analyze all views in the catalog.
        
        Returns:
            Dict mapping view full_name -> list of ViewDependency objects
        """
        view_deps = {}
        
        for full_name, table_info in self.catalog.items():
            # Only process views
            if table_info.type not in ('VIEW', 'MATERIALIZED VIEW'):
                continue
            
            deps = self._extract_view_dependencies(table_info)
            if deps:
                view_deps[full_name] = deps
        
        return view_deps
    
    def _extract_view_dependencies(self, view_info: TableInfo) -> List[ViewDependency]:
        """
        Extract dependencies for a single view by analyzing FK relationships.
        
        Note: In production MSSQL, you'd parse sys.sql_expression_dependencies.
        Here we use a heuristic: views that reference FK-related tables.
        
        Args:
            view_info: View table info
            
        Returns:
            List of ViewDependency objects
        """
        deps = []
        
        # Strategy: Check if view name suggests it includes specific tables
        # and infer dependencies from FK graph
        for fk in view_info.foreign_keys:
            dep = ViewDependency(
                view_name=view_info.name,
                view_schema=view_info.schema,
                depends_on_table=fk.referenced_table,
                depends_on_schema=fk.referenced_schema,
                dependency_type="table",
                is_materialized=self._detect_materialization(view_info),
                materialization_strategy=self._detect_materialization_strategy(view_info),
            )
            deps.append(dep)
        
        return deps
    
    def _detect_materialization(self, view_info: TableInfo) -> bool:
        """
        Detect if a view is materialized (indexed view, computed column, etc.).
        
        Heuristics:
        - View name contains 'mat', 'indexed', 'snapshot' -> materialized
        - High estimated_rows relative to dependency -> likely materialized
        - Type is 'MATERIALIZED VIEW' -> definitely materialized
        
        Args:
            view_info: View table info
            
        Returns:
            True if view is materialized
        """
        if view_info.type == 'MATERIALIZED VIEW':
            return True
        
        name_lower = view_info.name.lower()
        materialization_keywords = ['mat', 'indexed', 'snapshot', 'summary', 'cache']
        
        is_materialized = any(kw in name_lower for kw in materialization_keywords)
        
        return is_materialized
    
    def _detect_materialization_strategy(self, view_info: TableInfo) -> Optional[str]:
        """
        Detect the materialization strategy (indexed, computed, etc.).
        
        Args:
            view_info: View table info
            
        Returns:
            Strategy name or None
        """
        name_lower = view_info.name.lower()
        
        if 'indexed' in name_lower or 'index' in name_lower:
            return 'indexed'
        elif 'snapshot' in name_lower:
            return 'snapshot'
        elif 'summary' in name_lower:
            return 'summary'
        else:
            return None


# =====================================================
# 2. Foreign Key Cardinality Analyzer
# =====================================================

class FKCardinalityAnalyzer:
    """
    Analyzes foreign key cardinality patterns.
    
    Detects:
    - One-to-one relationships (unique constraint on FK column)
    - One-to-many relationships (typical FK)
    - Many-to-many relationships (junction tables)
    
    Optimizes join planning by:
    - Knowing which joins will preserve row count
    - Knowing which joins will multiply rows
    - Flagging many-to-many cases that need special handling
    """
    
    def __init__(self, catalog: Dict[str, TableInfo]):
        """
        Initialize analyzer.
        
        Args:
            catalog: Dict of table_name -> TableInfo
        """
        self.catalog = catalog
    
    def analyze_all_cardinalities(self) -> Dict[str, List[ForeignKeyCardinality]]:
        """
        Analyze cardinality for all foreign keys.
        
        Returns:
            Dict mapping table_name -> list of ForeignKeyCardinality objects
        """
        cardinalities = {}
        
        for full_name, table_info in self.catalog.items():
            if not table_info.foreign_keys:
                continue
            
            fk_cards = []
            for fk in table_info.foreign_keys:
                card = self._analyze_fk_cardinality(table_info, fk)
                fk_cards.append(card)
            
            if fk_cards:
                cardinalities[full_name] = fk_cards
        
        return cardinalities
    
    def _analyze_fk_cardinality(
        self,
        table_info: TableInfo,
        fk: ForeignKeyInfo
    ) -> ForeignKeyCardinality:
        """
        Analyze cardinality of a single foreign key.
        
        Heuristics used (in absence of unique constraints in catalog):
        - If FK column is also a PK or unique -> one-to-one
        - If table name suggests junction/bridge -> likely many-to-many
        - Otherwise -> one-to-many (default)
        
        Args:
            table_info: Table containing the FK
            fk: Foreign key info
            
        Returns:
            ForeignKeyCardinality object
        """
        cardinality_type = "one-to-many"  # Default
        ratio_estimate = None
        
        # Check if FK column is part of primary key -> likely one-to-one or many-to-many
        if fk.column in table_info.primary_keys:
            # If the entire PK is this FK, it's one-to-one
            if table_info.primary_keys == [fk.column]:
                cardinality_type = "one-to-one"
                ratio_estimate = 1.0
            else:
                # Part of composite PK -> likely many-to-many
                cardinality_type = "many-to-many"
        
        # Heuristic: table name suggests junction/bridge table
        table_name_lower = table_info.name.lower()
        junction_keywords = ['bridge', 'junction', 'link', 'mapping', 'assoc', 'rel']
        if any(kw in table_name_lower for kw in junction_keywords):
            cardinality_type = "many-to-many"
        
        # Estimate row ratio based on table sizes (heuristic)
        if table_info.estimated_rows > 0:
            ref_table = self.catalog.get(f"{fk.referenced_schema}.{fk.referenced_table}")
            if ref_table and ref_table.estimated_rows > 0:
                ratio_estimate = table_info.estimated_rows / ref_table.estimated_rows
        
        return ForeignKeyCardinality(
            column=fk.column,
            referenced_table=fk.referenced_table,
            referenced_schema=fk.referenced_schema,
            cardinality_type=cardinality_type,
            ratio_estimate=ratio_estimate,
        )


# =====================================================
# 3. Domain Clusterer
# =====================================================

class DomainClusterer:
    """
    Identifies business domains using FK graph analysis and naming patterns.
    
    Domains are business areas like:
    - Sales (Orders, OrderItems, Customers, Invoices)
    - Inventory (Products, Warehouses, StockLevels)
    - Purchasing (POs, Suppliers, PurchaseItems)
    - HR (Employees, Departments, Payroll)
    
    Optimizes query planning by:
    - Preferring tables from the same domain (higher join success rate)
    - Better ranking suggestions
    - Reducing ambiguity
    """
    
    # Domain keyword mappings
    DOMAIN_KEYWORDS = {
        'sales': ['order', 'invoice', 'customer', 'sale', 'transaction', 'payment'],
        'inventory': ['product', 'warehouse', 'stock', 'inventory', 'quantity', 'sku'],
        'purchasing': ['supplier', 'vendor', 'po', 'purchase', 'requisition'],
        'hr': ['employee', 'department', 'payroll', 'staff', 'personnel'],
        'finance': ['general ledger', 'account', 'cost center', 'budget', 'journal'],
        'manufacturing': ['bom', 'work order', 'routing', 'production', 'assembly'],
    }
    
    def __init__(self, catalog: Dict[str, TableInfo]):
        """
        Initialize clusterer.
        
        Args:
            catalog: Dict of table_name -> TableInfo
        """
        self.catalog = catalog
        self.fk_graph = self._build_fk_graph()
    
    def cluster_all_tables(self) -> Dict[str, DomainMetadata]:
        """
        Cluster all tables into business domains.
        
        Returns:
            Dict mapping table_name -> DomainMetadata
        """
        domains = {}
        
        for full_name, table_info in self.catalog.items():
            domain_meta = self._cluster_table(table_info)
            domains[full_name] = domain_meta
        
        return domains
    
    def _cluster_table(self, table_info: TableInfo) -> DomainMetadata:
        """
        Cluster a single table to a domain.
        
        Algorithm:
        1. Check table name against domain keywords (highest confidence)
        2. Check column names against domain keywords (medium confidence)
        3. Check FK neighbors' domains (lower confidence)
        4. Default to "General" domain
        
        Args:
            table_info: Table info to cluster
            
        Returns:
            DomainMetadata object
        """
        # Combine name and column names for analysis
        full_text = (table_info.name + " " + " ".join(col.name for col in table_info.columns)).lower()
        
        # Score each domain
        domain_scores = defaultdict(float)
        subject_tags_set = set()
        
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in full_text:
                    domain_scores[domain] += 1.0
                    subject_tags_set.add(keyword)
        
        # Check FK neighbors for domain hints
        neighbors_domains = self._get_neighbor_domains(table_info)
        for neighbor_domain in neighbors_domains:
            domain_scores[neighbor_domain] += 0.3
        
        # Determine best domain
        best_domain = max(domain_scores, default="General") if domain_scores else "General"
        confidence = domain_scores.get(best_domain, 0.0)
        
        # Normalize confidence to 0-1 range
        max_possible_score = 10.0  # Empirical max
        confidence = min(1.0, confidence / max_possible_score) if max_possible_score > 0 else 0.0
        
        # Get related domains (other domains this table connects to)
        related_domains = [d for d in domain_scores.keys() if d != best_domain]
        
        return DomainMetadata(
            table_name=table_info.name,
            table_schema=table_info.schema,
            domain_cluster=best_domain.capitalize(),
            domain_confidence=confidence,
            subject_tags=list(subject_tags_set)[:10],  # Top 10 tags
            related_domains=related_domains[:3] if related_domains else None,
        )
    
    def _build_fk_graph(self) -> Dict[str, Set[str]]:
        """
        Build a graph of FK relationships for domain propagation.
        
        Returns:
            Dict mapping table_name -> set of referenced table_names
        """
        graph = defaultdict(set)
        
        for full_name, table_info in self.catalog.items():
            for fk in table_info.foreign_keys:
                ref_full_name = f"{fk.referenced_schema}.{fk.referenced_table}"
                graph[full_name].add(ref_full_name)
                graph[ref_full_name].add(full_name)  # Bidirectional
        
        return graph
    
    def _get_neighbor_domains(self, table_info: TableInfo) -> List[str]:
        """
        Get domains of FK neighbors (for collaborative clustering).
        
        Args:
            table_info: Table info
            
        Returns:
            List of neighbor domains
        """
        neighbor_domains = []
        full_name = table_info.full_name()
        
        if full_name in self.fk_graph:
            for neighbor in list(self.fk_graph[full_name])[:3]:  # Top 3 neighbors
                if neighbor in self.catalog:
                    # Recursively get domain (limited depth)
                    neighbor_info = self.catalog[neighbor]
                    neighbor_text = (neighbor_info.name + " " + " ".join(col.name for col in neighbor_info.columns)).lower()
                    
                    for domain, keywords in self.DOMAIN_KEYWORDS.items():
                        if any(kw in neighbor_text for kw in keywords):
                            neighbor_domains.append(domain)
                            break
        
        return neighbor_domains


# =====================================================
# Main Enrichment Orchestrator
# =====================================================

class Tier1Enricher:
    """
    Orchestrates all Tier 1 enrichments on the catalog.
    
    Called during Scout startup to compute:
    - View dependencies and materialization info
    - FK cardinality patterns
    - Domain clustering
    
    Supports both TableInfo objects and dict-based catalogs.
    """
    
    def __init__(self, catalog: Dict):
        """
        Initialize enricher.
        
        Args:
            catalog: Dict of table_name -> TableInfo or dict-based catalog
        """
        self.catalog = catalog
        self._is_dict_based = self._detect_format()
    
    def _detect_format(self) -> bool:
        """Detect if catalog is dict-based or TableInfo-based."""
        if not self.catalog:
            return True  # Default to dict format
        
        first_value = next(iter(self.catalog.values()), None)
        if first_value is None:
            return True
        
        # Check if it's a dict or TableInfo
        return isinstance(first_value, dict)
    
    def enrich(self) -> Dict:
        """
        Enrich all tables with Tier 1 metadata.
        
        Returns:
            Updated catalog with enriched metadata
        """
        logger.info("🚀 Starting Tier 1 enrichment...")
        
        try:
            if self._is_dict_based:
                return self._enrich_dict_catalog()
            else:
                return self._enrich_tableinfo_catalog()
        
        except Exception as e:
            logger.error(f"❌ Tier 1 enrichment failed: {e}")
            raise
    
    def _enrich_dict_catalog(self) -> Dict:
        """Enrich dict-based catalog (from Scout)."""
        # Convert dict catalog to TableInfo-like structure for analysis
        tableinfo_catalog = self._dict_to_tableinfo_catalog()
        
        # Run enrichment
        view_deps_by_view = self._analyze_view_deps_dict(tableinfo_catalog)
        fk_cards_by_table = self._analyze_fk_cards_dict(tableinfo_catalog)
        domains_by_table = self._cluster_domains_dict(tableinfo_catalog)
        
        logger.info(f"   ✓ Analyzed {len(view_deps_by_view)} views")
        logger.info(f"   ✓ Analyzed cardinality for {len(fk_cards_by_table)} tables")
        logger.info(f"   ✓ Clustered {len(domains_by_table)} tables into business domains")
        
        # Apply enrichment to original dict catalog
        for full_name, table_dict in self.catalog.items():
            # Add view dependencies
            if full_name in view_deps_by_view:
                table_dict['view_dependencies'] = [asdict(d) for d in view_deps_by_view[full_name]]
            
            # Add FK cardinality
            if full_name in fk_cards_by_table:
                table_dict['fk_cardinality'] = [asdict(c) for c in fk_cards_by_table[full_name]]
            
            # Add domain metadata
            if full_name in domains_by_table:
                table_dict['domain_metadata'] = asdict(domains_by_table[full_name])
                # Mark materialization status
                table_dict['is_materialized_view'] = 'MATERIALIZED VIEW' in str(table_dict.get('type', ''))
        
        logger.info("✅ Tier 1 enrichment complete")
        return self.catalog
    
    def _enrich_tableinfo_catalog(self) -> Dict:
        """Enrich TableInfo-based catalog."""
        view_analyzer = ViewDependencyAnalyzer(self.catalog)
        view_deps_by_view = view_analyzer.analyze_all_views()
        logger.info(f"   ✓ Analyzed {len(view_deps_by_view)} views")
        
        fk_analyzer = FKCardinalityAnalyzer(self.catalog)
        fk_cards_by_table = fk_analyzer.analyze_all_cardinalities()
        logger.info(f"   ✓ Analyzed cardinality for {len(fk_cards_by_table)} tables")
        
        clusterer = DomainClusterer(self.catalog)
        domains_by_table = clusterer.cluster_all_tables()
        logger.info(f"   ✓ Clustered {len(domains_by_table)} tables into business domains")
        
        # Apply enrichment to TableInfo objects
        for full_name, table_info in self.catalog.items():
            if full_name in view_deps_by_view:
                table_info.view_dependencies = view_deps_by_view[full_name]
            
            if full_name in fk_cards_by_table:
                table_info.fk_cardinality = fk_cards_by_table[full_name]
            
            if full_name in domains_by_table:
                table_info.domain_metadata = domains_by_table[full_name]
        
        logger.info("✅ Tier 1 enrichment complete")
        return self.catalog
    
    def _dict_to_tableinfo_catalog(self) -> Dict[str, TableInfo]:
        """Convert dict-based catalog to TableInfo format for analysis."""
        tableinfo_catalog = {}
        
        for full_name, table_dict in self.catalog.items():
            # Reconstruct TableInfo from dict
            columns = [
                ColumnInfo(
                    name=col.get('name', ''),
                    type=col.get('type', 'unknown'),
                    nullable=col.get('nullable', True),
                    is_primary_key=col.get('is_primary_key', False),
                    is_foreign_key=col.get('is_foreign_key', False),
                    role_hints=col.get('role_hints'),
                )
                for col in table_dict.get('columns', [])
            ]
            
            foreign_keys = [
                ForeignKeyInfo(
                    column=fk.get('column', ''),
                    referenced_table=fk.get('referenced_table', ''),
                    referenced_schema=fk.get('referenced_schema', 'dbo'),
                    referenced_column=fk.get('referenced_column', ''),
                )
                for fk in table_dict.get('foreign_keys', [])
            ]
            
            table_info = TableInfo(
                schema=table_dict.get('schema', 'dbo'),
                name=table_dict.get('name', ''),
                type=table_dict.get('type', 'BASE TABLE'),
                columns=columns,
                foreign_keys=foreign_keys,
                estimated_rows=table_dict.get('estimated_rows', 0),
                primary_keys=table_dict.get('primary_keys', []),
            )
            
            tableinfo_catalog[full_name] = table_info
        
        return tableinfo_catalog
    
    def _analyze_view_deps_dict(self, tableinfo_catalog: Dict) -> Dict:
        """Analyze view dependencies on TableInfo catalog."""
        analyzer = ViewDependencyAnalyzer(tableinfo_catalog)
        return analyzer.analyze_all_views()
    
    def _analyze_fk_cards_dict(self, tableinfo_catalog: Dict) -> Dict:
        """Analyze FK cardinalities on TableInfo catalog."""
        analyzer = FKCardinalityAnalyzer(tableinfo_catalog)
        return analyzer.analyze_all_cardinalities()
    
    def _cluster_domains_dict(self, tableinfo_catalog: Dict) -> Dict:
        """Cluster domains on TableInfo catalog."""
        clusterer = DomainClusterer(tableinfo_catalog)
        return clusterer.cluster_all_tables()