"""
Phase 3: Catalog & Cache - Server-side schema catalog with disk persistence.

This module provides a comprehensive schema catalog that:
- Fetches schema metadata, foreign keys, and row estimates on warmup
- Persists catalog to disk (JSON) for fast startup
- Holds catalog in memory with TTL-based refresh
- Provides quick lookups without hitting the database
- Tracks metrics: catalog_age_s, cache_hits, cache_misses

Architecture alignment:
- Proxy-only separation: No business logic, just data caching
- Database abstraction: Works with both PostgreSQL and SQL Server
- Read-only, safe queries: Only SELECT queries for metadata
- JSON as single data format: Catalog stored and returned as JSON
- Security & privacy: No sensitive data in catalog
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """Column metadata."""
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    role_hints: Optional[List[str]] = None  # Phase 1: Scout Mode v2 semantic roles


@dataclass
class ForeignKeyInfo:
    """Foreign key relationship."""
    column: str
    referenced_table: str
    referenced_schema: str
    referenced_column: str


@dataclass
class ForeignKeyCardinality:
    """Foreign key cardinality metadata (Tier 1 Enhancement)."""
    column: str
    referenced_table: str
    referenced_schema: str
    cardinality_type: str  # "one-to-one", "one-to-many", "many-to-many"
    ratio_estimate: Optional[float] = None  # Estimated ratio (e.g., 1.5 means average 1.5 rows per parent)


@dataclass
class ViewDependency:
    """View dependency metadata (Tier 1 Enhancement)."""
    view_name: str
    view_schema: str
    depends_on_table: str
    depends_on_schema: str
    dependency_type: str  # "table", "view"
    is_materialized: bool = False
    materialization_strategy: Optional[str] = None  # "indexed", "computed", etc.


@dataclass
class DomainMetadata:
    """Domain/subject area metadata (Tier 1 Enhancement)."""
    table_name: str
    table_schema: str
    domain_cluster: str  # e.g., "Sales", "Inventory", "Purchasing", "HR"
    domain_confidence: float  # 0.0 to 1.0
    subject_tags: List[str]  # e.g., ["financial", "transactions", "customer-facing"]
    related_domains: Optional[List[str]] = None  # Other domains this table connects to


@dataclass
class TableInfo:
    """Comprehensive table metadata."""
    schema: str
    name: str
    type: str  # 'BASE TABLE', 'VIEW', etc.
    columns: List[ColumnInfo]
    foreign_keys: List[ForeignKeyInfo]
    estimated_rows: int
    primary_keys: List[str]
    # Tier 1 Enhancements
    fk_cardinality: Optional[List[ForeignKeyCardinality]] = None
    view_dependencies: Optional[List[ViewDependency]] = None
    domain_metadata: Optional[DomainMetadata] = None
    is_materialized_view: bool = False  # For views: True if materialized/indexed
    view_materialization_strategy: Optional[str] = None  # "indexed", "computed", etc.
    
    def full_name(self) -> str:
        """Get fully qualified table name."""
        return f"{self.schema}.{self.name}"
    
    def get_neighbors(self) -> Set[str]:
        """Get set of related table names via foreign keys."""
        neighbors = set()
        for fk in self.foreign_keys:
            neighbors.add(f"{fk.referenced_schema}.{fk.referenced_table}")
        return neighbors
    
    def get_top_columns(self, limit: int = 5) -> List[str]:
        """Get top N column names (prioritize PKs and FKs)."""
        top_cols = []
        
        # Add primary keys first
        for col in self.columns:
            if col.is_primary_key and len(top_cols) < limit:
                top_cols.append(col.name)
        
        # Add foreign keys next
        for col in self.columns:
            if col.is_foreign_key and col.name not in top_cols and len(top_cols) < limit:
                top_cols.append(col.name)
        
        # Fill remaining with other columns
        for col in self.columns:
            if col.name not in top_cols and len(top_cols) < limit:
                top_cols.append(col.name)
        
        return top_cols


@dataclass
class CatalogMetrics:
    """Catalog performance metrics."""
    catalog_age_s: Optional[float] = None
    cache_hits: int = 0
    cache_misses: int = 0
    last_refresh_time: Optional[float] = None
    refresh_count: int = 0
    table_count: int = 0
    
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class SchemaCatalog:
    """
    Server-side schema catalog with disk persistence and in-memory caching.
    
    Features:
    - Warmup: Fetch schema metadata, FKs, and row estimates on first call
    - Persistence: Save catalog to disk as JSON
    - Caching: Hold catalog in memory with TTL-based refresh
    - Metrics: Track cache hits, misses, age, and hit ratio
    - Fast lookups: No database hits after warmup
    
    Supports both PostgreSQL and SQL Server dialects.
    """
    
    def __init__(
        self,
        connector,
        dialect: str,
        cache_dir: Optional[str] = None,
        ttl: int = 360000,
        auto_warmup: bool = True
    ):
        """
        Initialize schema catalog.
        
        Args:
            connector: Database connector (PostgresConnector or MSSQLConnector)
            dialect: Database dialect ('postgres' or 'mssql')
            cache_dir: Directory for catalog cache files (default: ./cache)
            ttl: Time-to-live for catalog in seconds (default: 3600 = 1 hour)
            auto_warmup: Automatically warmup on initialization (default: True)
        """
        self.connector = connector
        self.dialect = dialect.lower()
        self.ttl = ttl
        
        # Setup cache directory
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.cache_file = self.cache_dir / f"catalog_{self.dialect}.json"
        
        # In-memory catalog
        self._catalog: Dict[str, TableInfo] = {}  # key: schema.table
        self._metrics = CatalogMetrics()
        self._warmup_complete = False
        
        logger.info(f"SchemaCatalog initialized for {dialect} (TTL: {ttl}s, cache: {self.cache_file})")
        
        # Auto-warmup if requested
        if auto_warmup:
            # Note: warmup is async, so we can't call it here
            # The caller should call warmup() after initialization
            logger.info("Auto-warmup enabled - call warmup() to initialize catalog")
    
    async def warmup(self, force_refresh: bool = False) -> None:
        """
        Warmup the catalog by loading from disk or fetching from database.
        
        Args:
            force_refresh: Force refresh from database even if cache exists
        """
        # Try to load from disk first
        if not force_refresh and self._load_from_disk():
            logger.info("✅ Catalog loaded from disk cache")
            self._warmup_complete = True
            return
        
        # Fetch from database
        logger.info("🔄 Warming up catalog from database...")
        start_time = time.time()
        
        try:
            # Fetch schema metadata
            await self._fetch_catalog()
            
            # Save to disk
            self._save_to_disk()
            
            elapsed = time.time() - start_time
            self._metrics.last_refresh_time = time.time()
            self._metrics.refresh_count += 1
            self._metrics.table_count = len(self._catalog)
            self._warmup_complete = True
            
            logger.info(f"✅ Catalog warmup complete: {self._metrics.table_count} tables in {elapsed:.2f}s")
        
        except Exception as e:
            logger.error(f"❌ Catalog warmup failed: {e}")
            raise
    
    async def _fetch_catalog(self) -> None:
        """Fetch comprehensive catalog from database."""
        if self.dialect == "postgres":
            await self._fetch_postgres_catalog()
        elif self.dialect == "mssql":
            await self._fetch_mssql_catalog()
        else:
            raise ValueError(f"Unsupported dialect: {self.dialect}")
    
    async def _fetch_postgres_catalog(self) -> None:
        """Fetch catalog from PostgreSQL."""
        # Get all tables with basic info
        tables_query = """
        SELECT 
            t.table_schema,
            t.table_name,
            t.table_type,
            COALESCE(c.reltuples::bigint, 0) as estimated_rows
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        LEFT JOIN pg_namespace n ON n.nspname = t.table_schema AND c.relnamespace = n.oid
        WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY t.table_schema, t.table_name
        """
        
        columns, rows = await self.connector.query(tables_query, limit=10000)
        
        for row in rows:
            schema_name = row[0]
            table_name = row[1]
            table_type = row[2]
            estimated_rows = row[3] if len(row) > 3 else 0
            
            # Get columns with PK/FK info
            table_columns = await self._fetch_postgres_columns(schema_name, table_name)
            
            # Get foreign keys
            foreign_keys = await self._fetch_postgres_foreign_keys(schema_name, table_name)
            
            # Get primary keys
            primary_keys = await self._fetch_postgres_primary_keys(schema_name, table_name)
            
            # Mark PK and FK columns
            for col in table_columns:
                col.is_primary_key = col.name in primary_keys
                col.is_foreign_key = any(fk.column == col.name for fk in foreign_keys)
            
            # Create table info
            table_info = TableInfo(
                schema=schema_name,
                name=table_name,
                type=table_type,
                columns=table_columns,
                foreign_keys=foreign_keys,
                estimated_rows=estimated_rows,
                primary_keys=primary_keys
            )
            
            self._catalog[table_info.full_name()] = table_info
    
    async def _fetch_postgres_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """Fetch columns for a PostgreSQL table."""
        query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """
        
        try:
            pool = await self.connector._get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetch(query, schema, table)
                
                columns = []
                for record in result:
                    columns.append(ColumnInfo(
                        name=record['column_name'],
                        type=record['data_type'],
                        nullable=record['is_nullable'] == 'YES',
                        default=record['column_default']
                    ))
                
                return columns
        
        except Exception as e:
            logger.warning(f"Could not fetch columns for {schema}.{table}: {e}")
            return []
    
    async def _fetch_postgres_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        """Fetch foreign keys for a PostgreSQL table."""
        query = """
        SELECT
            kcu.column_name,
            ccu.table_schema AS referenced_schema,
            ccu.table_name AS referenced_table,
            ccu.column_name AS referenced_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = $1
            AND tc.table_name = $2
        """
        
        try:
            pool = await self.connector._get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetch(query, schema, table)
                
                foreign_keys = []
                for record in result:
                    foreign_keys.append(ForeignKeyInfo(
                        column=record['column_name'],
                        referenced_schema=record['referenced_schema'],
                        referenced_table=record['referenced_table'],
                        referenced_column=record['referenced_column']
                    ))
                
                return foreign_keys
        
        except Exception as e:
            logger.warning(f"Could not fetch foreign keys for {schema}.{table}: {e}")
            return []
    
    async def _fetch_postgres_primary_keys(self, schema: str, table: str) -> List[str]:
        """Fetch primary key columns for a PostgreSQL table."""
        query = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = $1
            AND tc.table_name = $2
        ORDER BY kcu.ordinal_position
        """
        
        try:
            pool = await self.connector._get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetch(query, schema, table)
                return [record['column_name'] for record in result]
        
        except Exception as e:
            logger.warning(f"Could not fetch primary keys for {schema}.{table}: {e}")
            return []
    
    async def _fetch_mssql_catalog(self) -> None:
        """Fetch catalog from SQL Server."""
        # Get all tables with row estimates
        tables_query = """
        SELECT 
            s.name AS schema_name,
            t.name AS table_name,
            CASE 
                WHEN t.type = 'U' THEN 'BASE TABLE'
                WHEN t.type = 'V' THEN 'VIEW'
                ELSE 'OTHER'
            END AS table_type,
            COALESCE(SUM(p.rows), 0) AS estimated_rows
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        GROUP BY s.name, t.name, t.type
        ORDER BY s.name, t.name
        """
        
        columns, rows = await self.connector.query(tables_query, limit=10000)
        
        for row in rows:
            schema_name = row[0]
            table_name = row[1]
            table_type = row[2]
            # Convert Decimal (from pyodbc/SQL Server) to int
            estimated_rows = int(row[3]) if row[3] else 0
            
            # Get columns with PK/FK info
            table_columns = await self._fetch_mssql_columns(schema_name, table_name)
            
            # Get foreign keys
            foreign_keys = await self._fetch_mssql_foreign_keys(schema_name, table_name)
            
            # Get primary keys
            primary_keys = await self._fetch_mssql_primary_keys(schema_name, table_name)
            
            # Mark PK and FK columns
            for col in table_columns:
                col.is_primary_key = col.name in primary_keys
                col.is_foreign_key = any(fk.column == col.name for fk in foreign_keys)
            
            # Create table info
            table_info = TableInfo(
                schema=schema_name,
                name=table_name,
                type=table_type,
                columns=table_columns,
                foreign_keys=foreign_keys,
                estimated_rows=estimated_rows,
                primary_keys=primary_keys
            )
            
            self._catalog[table_info.full_name()] = table_info
    
    async def _fetch_mssql_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """Fetch columns for a SQL Server table."""
        query = """
        SELECT 
            c.name AS column_name,
            t.name AS data_type,
            c.is_nullable,
            dc.definition AS column_default
        FROM sys.columns c
        INNER JOIN sys.tables tb ON c.object_id = tb.object_id
        INNER JOIN sys.schemas s ON tb.schema_id = s.schema_id
        INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        WHERE s.name = ? AND tb.name = ?
        ORDER BY c.column_id
        """
        
        try:
            col_columns, col_rows = await self.connector.query(
                query,
                params=[schema, table],  # Use list for positional params
                limit=1000
            )
            
            columns = []
            for row in col_rows:
                columns.append(ColumnInfo(
                    name=row[0],
                    type=row[1],
                    nullable=bool(row[2]),
                    default=row[3]
                ))
            
            return columns
        
        except Exception as e:
            logger.warning(f"Could not fetch columns for {schema}.{table}: {e}")
            return []
    
    async def _fetch_mssql_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        """Fetch foreign keys for a SQL Server table."""
        query = """
        SELECT 
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
            SCHEMA_NAME(ref_t.schema_id) AS referenced_schema,
            OBJECT_NAME(fkc.referenced_object_id) AS referenced_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
        FROM sys.foreign_key_columns fkc
        INNER JOIN sys.tables t ON fkc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.tables ref_t ON fkc.referenced_object_id = ref_t.object_id
        WHERE s.name = ? AND t.name = ?
        """
        
        try:
            col_columns, col_rows = await self.connector.query(
                query,
                params=[schema, table],  # Use list for positional params
                limit=1000
            )
            
            foreign_keys = []
            for row in col_rows:
                foreign_keys.append(ForeignKeyInfo(
                    column=row[0],
                    referenced_schema=row[1],
                    referenced_table=row[2],
                    referenced_column=row[3]
                ))
            
            return foreign_keys
        
        except Exception as e:
            logger.warning(f"Could not fetch foreign keys for {schema}.{table}: {e}")
            return []
    
    async def _fetch_mssql_primary_keys(self, schema: str, table: str) -> List[str]:
        """Fetch primary key columns for a SQL Server table."""
        query = """
        SELECT c.name AS column_name
        FROM sys.indexes i
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        INNER JOIN sys.tables t ON i.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE i.is_primary_key = 1
            AND s.name = ? AND t.name = ?
        ORDER BY ic.key_ordinal
        """
        
        try:
            col_columns, col_rows = await self.connector.query(
                query,
                params=[schema, table],  # Use list for positional params
                limit=100
            )
            
            return [row[0] for row in col_rows]
        
        except Exception as e:
            logger.warning(f"Could not fetch primary keys for {schema}.{table}: {e}")
            return []
    
    def _save_to_disk(self) -> None:
        """Save catalog to disk as JSON."""
        try:
            # Convert catalog to JSON-serializable format
            catalog_data = {
                "metadata": {
                    "dialect": self.dialect,
                    "timestamp": time.time(),
                    "table_count": len(self._catalog),
                    "ttl": self.ttl
                },
                "tables": {}
            }
            
            for full_name, table_info in self._catalog.items():
                catalog_data["tables"][full_name] = {
                    "schema": table_info.schema,
                    "name": table_info.name,
                    "type": table_info.type,
                    "estimated_rows": table_info.estimated_rows,
                    "primary_keys": table_info.primary_keys,
                    "columns": [asdict(col) for col in table_info.columns],
                    "foreign_keys": [asdict(fk) for fk in table_info.foreign_keys]
                }
            
            # Write to disk
            with open(self.cache_file, 'w') as f:
                json.dump(catalog_data, f, indent=2)
            
            logger.info(f"✅ Catalog saved to disk: {self.cache_file}")
        
        except Exception as e:
            logger.error(f"Failed to save catalog to disk: {e}")
    
    def _load_from_disk(self) -> bool:
        """
        Load catalog from disk if available and not expired.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.cache_file.exists():
            logger.info("No disk cache found")
            return False
        
        try:
            with open(self.cache_file, 'r') as f:
                catalog_data = json.load(f)
            
            # Check if cache is expired
            metadata = catalog_data.get("metadata", {})
            timestamp = metadata.get("timestamp", 0)
            age = time.time() - timestamp
            
            if age > self.ttl:
                logger.info(f"Disk cache expired (age: {age:.1f}s > TTL: {self.ttl}s)")
                return False
            
            # Load tables
            self._catalog.clear()
            for full_name, table_data in catalog_data.get("tables", {}).items():
                # Reconstruct ColumnInfo objects
                columns = [ColumnInfo(**col) for col in table_data.get("columns", [])]
                
                # Reconstruct ForeignKeyInfo objects
                foreign_keys = [ForeignKeyInfo(**fk) for fk in table_data.get("foreign_keys", [])]
                
                # Create TableInfo
                table_info = TableInfo(
                    schema=table_data["schema"],
                    name=table_data["name"],
                    type=table_data["type"],
                    columns=columns,
                    foreign_keys=foreign_keys,
                    estimated_rows=table_data.get("estimated_rows", 0),
                    primary_keys=table_data.get("primary_keys", [])
                )
                
                self._catalog[full_name] = table_info
            
            # Update metrics
            self._metrics.catalog_age_s = age
            self._metrics.table_count = len(self._catalog)
            
            logger.info(f"✅ Catalog loaded from disk: {len(self._catalog)} tables (age: {age:.1f}s)")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load catalog from disk: {e}")
            return False
    
    async def refresh_if_needed(self) -> None:
        """Refresh catalog if TTL expired."""
        if not self._warmup_complete:
            await self.warmup()
            return
        
        # Check if refresh needed
        if self._metrics.last_refresh_time is None:
            await self.warmup(force_refresh=True)
            return
        
        age = time.time() - self._metrics.last_refresh_time
        if age > self.ttl:
            logger.info(f"Catalog TTL expired (age: {age:.1f}s > TTL: {self.ttl}s), refreshing...")
            await self.warmup(force_refresh=True)
    
    # === Public API ===
    
    def get_table_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all tables with basic info including columns.

        Returns:
            List of dicts with schema, name, type, estimated_rows, columns
        """
        self._metrics.cache_hits += 1

        return [
            {
                "schema": table.schema,
                "name": table.name,
                "full_name": table.full_name(),
                "type": table.type,
                "estimated_rows": table.estimated_rows,
                "column_count": len(table.columns),
                "fk_count": len(table.foreign_keys),
                # Include column data for search ranking and SQL generation
                "columns": [
                    {"name": col.name, "type": col.type, "is_primary_key": col.is_primary_key, "is_foreign_key": col.is_foreign_key}
                    for col in table.columns[:30]  # Limit to 30 columns for performance
                ]
            }
            for table in self._catalog.values()
        ]
    
    def get_table(self, schema: str, table: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific table.
        
        Args:
            schema: Schema name
            table: Table name
        
        Returns:
            Table info dict or None if not found
        """
        full_name = f"{schema}.{table}"
        table_info = self._catalog.get(full_name)
        
        if table_info is None:
            self._metrics.cache_misses += 1
            return None
        
        self._metrics.cache_hits += 1
        
        return {
            "schema": table_info.schema,
            "name": table_info.name,
            "full_name": table_info.full_name(),
            "type": table_info.type,
            "estimated_rows": table_info.estimated_rows,
            "primary_keys": table_info.primary_keys,
            "columns": [asdict(col) for col in table_info.columns],
            "foreign_keys": [asdict(fk) for fk in table_info.foreign_keys],
            "neighbors": list(table_info.get_neighbors()),
            "top_columns": table_info.get_top_columns()
        }
    
    def get_columns(self, schema: str, table: str) -> List[Dict[str, Any]]:
        """
        Get columns for a specific table.
        
        Args:
            schema: Schema name
            table: Table name
        
        Returns:
            List of column info dicts
        """
        full_name = f"{schema}.{table}"
        table_info = self._catalog.get(full_name)
        
        if table_info is None:
            self._metrics.cache_misses += 1
            return []
        
        self._metrics.cache_hits += 1
        return [asdict(col) for col in table_info.columns]
    
    def get_neighbors(self, schema: str, table: str) -> List[str]:
        """
        Get related tables via foreign keys.
        
        Args:
            schema: Schema name
            table: Table name
        
        Returns:
            List of related table names (schema.table format)
        """
        full_name = f"{schema}.{table}"
        table_info = self._catalog.get(full_name)
        
        if table_info is None:
            self._metrics.cache_misses += 1
            return []
        
        self._metrics.cache_hits += 1
        return list(table_info.get_neighbors())
    
    def get_top_columns(self, schema: str, table: str, limit: int = 5) -> List[str]:
        """
        Get top N columns for a table (prioritize PKs and FKs).
        
        Args:
            schema: Schema name
            table: Table name
            limit: Number of columns to return
        
        Returns:
            List of column names
        """
        full_name = f"{schema}.{table}"
        table_info = self._catalog.get(full_name)
        
        if table_info is None:
            self._metrics.cache_misses += 1
            return []
        
        self._metrics.cache_hits += 1
        return table_info.get_top_columns(limit)
    
    def search_tables(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for tables by name (case-insensitive).
        
        Args:
            query: Search query
        
        Returns:
            List of matching table info dicts
        """
        self._metrics.cache_hits += 1
        
        query_lower = query.lower()
        matches = []
        
        for table in self._catalog.values():
            if (query_lower in table.name.lower() or 
                query_lower in table.schema.lower() or
                query_lower in table.full_name().lower()):
                matches.append({
                    "schema": table.schema,
                    "name": table.name,
                    "full_name": table.full_name(),
                    "type": table.type,
                    "estimated_rows": table.estimated_rows
                })
        
        return matches
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get catalog metrics.
        
        Returns:
            Dict with catalog_age_s, cache_hits, cache_misses, hit_ratio, etc.
        """
        # Update catalog age
        if self._metrics.last_refresh_time is not None:
            self._metrics.catalog_age_s = time.time() - self._metrics.last_refresh_time
        
        return {
            "catalog_age_s": round(self._metrics.catalog_age_s, 1) if self._metrics.catalog_age_s else None,
            "cache_hits": self._metrics.cache_hits,
            "cache_misses": self._metrics.cache_misses,
            "hit_ratio": round(self._metrics.hit_ratio(), 3),
            "table_count": self._metrics.table_count,
            "refresh_count": self._metrics.refresh_count,
            "ttl": self.ttl,
            "warmup_complete": self._warmup_complete
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get catalog summary with statistics.
        
        Returns:
            Dict with table count, column count, FK count, etc.
        """
        total_columns = sum(len(table.columns) for table in self._catalog.values())
        total_fks = sum(len(table.foreign_keys) for table in self._catalog.values())
        total_rows = sum(table.estimated_rows for table in self._catalog.values())
        
        return {
            "table_count": len(self._catalog),
            "total_columns": total_columns,
            "total_foreign_keys": total_fks,
            "estimated_total_rows": total_rows,
            "dialect": self.dialect,
            "metrics": self.get_metrics()
        }


# === Convenience functions ===

async def create_catalog(
    connector,
    dialect: str,
    cache_dir: Optional[str] = None,
    ttl: int = 3600
) -> SchemaCatalog:
    """
    Create and warmup a schema catalog.
    
    Args:
        connector: Database connector
        dialect: Database dialect ('postgres' or 'mssql')
        cache_dir: Cache directory (optional)
        ttl: Time-to-live in seconds (default: 3600)
    
    Returns:
        Initialized SchemaCatalog
    """
    catalog = SchemaCatalog(
        connector=connector,
        dialect=dialect,
        cache_dir=cache_dir,
        ttl=ttl,
        auto_warmup=False
    )
    
    await catalog.warmup()
    return catalog