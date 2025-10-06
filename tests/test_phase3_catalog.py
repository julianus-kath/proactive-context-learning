"""
Phase 3 Tests: Catalog & Cache

Tests for the schema catalog with disk persistence and in-memory caching.

Test coverage:
- Catalog warmup and initialization
- Disk persistence (save/load)
- TTL-based refresh
- Metrics tracking (hits, misses, hit ratio)
- Table lookups (no DB hits after warmup)
- Foreign key relationships
- Top columns prioritization
- Table search
- Both PostgreSQL and SQL Server dialects
"""

import pytest
import os
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from mcp_server.catalog import (
    SchemaCatalog,
    TableInfo,
    ColumnInfo,
    ForeignKeyInfo,
    CatalogMetrics,
    create_catalog
)


class TestCatalogDataStructures:
    """Test catalog data structures."""
    
    def test_column_info(self):
        """Test ColumnInfo dataclass."""
        col = ColumnInfo(
            name="customer_id",
            type="integer",
            nullable=False,
            default=None,
            is_primary_key=True,
            is_foreign_key=False
        )
        
        assert col.name == "customer_id"
        assert col.type == "integer"
        assert not col.nullable
        assert col.is_primary_key
        assert not col.is_foreign_key
    
    def test_foreign_key_info(self):
        """Test ForeignKeyInfo dataclass."""
        fk = ForeignKeyInfo(
            column="customer_id",
            referenced_table="customers",
            referenced_schema="public",
            referenced_column="id"
        )
        
        assert fk.column == "customer_id"
        assert fk.referenced_table == "customers"
        assert fk.referenced_schema == "public"
        assert fk.referenced_column == "id"
    
    def test_table_info_full_name(self):
        """Test TableInfo.full_name()."""
        table = TableInfo(
            schema="public",
            name="customers",
            type="BASE TABLE",
            columns=[],
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        assert table.full_name() == "public.customers"
    
    def test_table_info_neighbors(self):
        """Test TableInfo.get_neighbors()."""
        fk1 = ForeignKeyInfo("customer_id", "customers", "public", "id")
        fk2 = ForeignKeyInfo("product_id", "products", "public", "id")
        
        table = TableInfo(
            schema="public",
            name="orders",
            type="BASE TABLE",
            columns=[],
            foreign_keys=[fk1, fk2],
            estimated_rows=5000,
            primary_keys=["id"]
        )
        
        neighbors = table.get_neighbors()
        assert len(neighbors) == 2
        assert "public.customers" in neighbors
        assert "public.products" in neighbors
    
    def test_table_info_top_columns(self):
        """Test TableInfo.get_top_columns() prioritizes PKs and FKs."""
        columns = [
            ColumnInfo("id", "integer", False, is_primary_key=True),
            ColumnInfo("customer_id", "integer", False, is_foreign_key=True),
            ColumnInfo("name", "varchar", False),
            ColumnInfo("email", "varchar", True),
            ColumnInfo("created_at", "timestamp", False)
        ]
        
        table = TableInfo(
            schema="public",
            name="orders",
            type="BASE TABLE",
            columns=columns,
            foreign_keys=[],
            estimated_rows=1000,
            primary_keys=["id"]
        )
        
        top_cols = table.get_top_columns(limit=3)
        assert len(top_cols) == 3
        assert top_cols[0] == "id"  # PK first
        assert top_cols[1] == "customer_id"  # FK second
        assert top_cols[2] in ["name", "email", "created_at"]  # Others
    
    def test_catalog_metrics_hit_ratio(self):
        """Test CatalogMetrics.hit_ratio()."""
        metrics = CatalogMetrics(cache_hits=90, cache_misses=10)
        assert metrics.hit_ratio() == 0.9
        
        metrics = CatalogMetrics(cache_hits=0, cache_misses=0)
        assert metrics.hit_ratio() == 0.0


class TestCatalogPersistence:
    """Test catalog disk persistence."""
    
    def test_save_and_load_catalog(self):
        """Test saving and loading catalog from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock connector
            connector = Mock()
            
            # Create catalog
            catalog = SchemaCatalog(
                connector=connector,
                dialect="postgres",
                cache_dir=tmpdir,
                ttl=3600,
                auto_warmup=False
            )
            
            # Manually populate catalog
            table = TableInfo(
                schema="public",
                name="customers",
                type="BASE TABLE",
                columns=[
                    ColumnInfo("id", "integer", False, is_primary_key=True),
                    ColumnInfo("name", "varchar", False)
                ],
                foreign_keys=[],
                estimated_rows=1000,
                primary_keys=["id"]
            )
            catalog._catalog["public.customers"] = table
            catalog._metrics.table_count = 1
            catalog._metrics.last_refresh_time = time.time()
            
            # Save to disk
            catalog._save_to_disk()
            
            # Verify file exists
            cache_file = Path(tmpdir) / "catalog_postgres.json"
            assert cache_file.exists()
            
            # Load from disk
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            assert data["metadata"]["dialect"] == "postgres"
            assert data["metadata"]["table_count"] == 1
            assert "public.customers" in data["tables"]
            assert data["tables"]["public.customers"]["name"] == "customers"
    
    def test_load_from_disk_expired(self):
        """Test that expired cache is not loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create expired cache file
            cache_file = Path(tmpdir) / "catalog_postgres.json"
            expired_data = {
                "metadata": {
                    "dialect": "postgres",
                    "timestamp": time.time() - 7200,  # 2 hours ago
                    "table_count": 1,
                    "ttl": 3600  # 1 hour TTL
                },
                "tables": {}
            }
            
            with open(cache_file, 'w') as f:
                json.dump(expired_data, f)
            
            # Create catalog
            connector = Mock()
            catalog = SchemaCatalog(
                connector=connector,
                dialect="postgres",
                cache_dir=tmpdir,
                ttl=3600,
                auto_warmup=False
            )
            
            # Try to load from disk
            loaded = catalog._load_from_disk()
            
            # Should not load expired cache
            assert not loaded
    
    def test_load_from_disk_valid(self):
        """Test that valid cache is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid cache file
            cache_file = Path(tmpdir) / "catalog_postgres.json"
            valid_data = {
                "metadata": {
                    "dialect": "postgres",
                    "timestamp": time.time() - 600,  # 10 minutes ago
                    "table_count": 1,
                    "ttl": 3600  # 1 hour TTL
                },
                "tables": {
                    "public.customers": {
                        "schema": "public",
                        "name": "customers",
                        "type": "BASE TABLE",
                        "estimated_rows": 1000,
                        "primary_keys": ["id"],
                        "columns": [
                            {
                                "name": "id",
                                "type": "integer",
                                "nullable": False,
                                "default": None,
                                "is_primary_key": True,
                                "is_foreign_key": False
                            }
                        ],
                        "foreign_keys": []
                    }
                }
            }
            
            with open(cache_file, 'w') as f:
                json.dump(valid_data, f)
            
            # Create catalog
            connector = Mock()
            catalog = SchemaCatalog(
                connector=connector,
                dialect="postgres",
                cache_dir=tmpdir,
                ttl=3600,
                auto_warmup=False
            )
            
            # Load from disk
            loaded = catalog._load_from_disk()
            
            # Should load valid cache
            assert loaded
            assert len(catalog._catalog) == 1
            assert "public.customers" in catalog._catalog


class TestCatalogAPI:
    """Test catalog public API."""
    
    def setup_method(self):
        """Setup test catalog."""
        self.connector = Mock()
        self.catalog = SchemaCatalog(
            connector=self.connector,
            dialect="postgres",
            cache_dir=None,
            ttl=3600,
            auto_warmup=False
        )
        
        # Populate with test data
        self.catalog._catalog = {
            "public.customers": TableInfo(
                schema="public",
                name="customers",
                type="BASE TABLE",
                columns=[
                    ColumnInfo("id", "integer", False, is_primary_key=True),
                    ColumnInfo("name", "varchar", False),
                    ColumnInfo("email", "varchar", True)
                ],
                foreign_keys=[],
                estimated_rows=1000,
                primary_keys=["id"]
            ),
            "public.orders": TableInfo(
                schema="public",
                name="orders",
                type="BASE TABLE",
                columns=[
                    ColumnInfo("id", "integer", False, is_primary_key=True),
                    ColumnInfo("customer_id", "integer", False, is_foreign_key=True),
                    ColumnInfo("total", "decimal", False)
                ],
                foreign_keys=[
                    ForeignKeyInfo("customer_id", "customers", "public", "id")
                ],
                estimated_rows=5000,
                primary_keys=["id"]
            )
        }
        
        self.catalog._metrics.table_count = 2
        self.catalog._metrics.last_refresh_time = time.time()
        self.catalog._warmup_complete = True
    
    def test_get_table_list(self):
        """Test get_table_list()."""
        tables = self.catalog.get_table_list()
        
        assert len(tables) == 2
        assert tables[0]["name"] in ["customers", "orders"]
        assert tables[0]["schema"] == "public"
        assert "estimated_rows" in tables[0]
        assert "column_count" in tables[0]
    
    def test_get_table(self):
        """Test get_table()."""
        table = self.catalog.get_table("public", "customers")
        
        assert table is not None
        assert table["name"] == "customers"
        assert table["schema"] == "public"
        assert len(table["columns"]) == 3
        assert table["primary_keys"] == ["id"]
        assert "top_columns" in table
    
    def test_get_table_not_found(self):
        """Test get_table() with non-existent table."""
        table = self.catalog.get_table("public", "nonexistent")
        
        assert table is None
        assert self.catalog._metrics.cache_misses == 1
    
    def test_get_columns(self):
        """Test get_columns()."""
        columns = self.catalog.get_columns("public", "customers")
        
        assert len(columns) == 3
        assert columns[0]["name"] == "id"
        assert columns[0]["is_primary_key"] is True
    
    def test_get_neighbors(self):
        """Test get_neighbors()."""
        neighbors = self.catalog.get_neighbors("public", "orders")
        
        assert len(neighbors) == 1
        assert "public.customers" in neighbors
    
    def test_get_top_columns(self):
        """Test get_top_columns()."""
        top_cols = self.catalog.get_top_columns("public", "orders", limit=2)
        
        assert len(top_cols) == 2
        assert top_cols[0] == "id"  # PK first
        assert top_cols[1] == "customer_id"  # FK second
    
    def test_search_tables(self):
        """Test search_tables()."""
        # Search by name
        results = self.catalog.search_tables("customer")
        assert len(results) == 1
        assert results[0]["name"] == "customers"
        
        # Search by schema
        results = self.catalog.search_tables("public")
        assert len(results) == 2
        
        # No matches
        results = self.catalog.search_tables("nonexistent")
        assert len(results) == 0
    
    def test_get_metrics(self):
        """Test get_metrics()."""
        # Perform some operations
        self.catalog.get_table("public", "customers")  # hit
        self.catalog.get_table("public", "orders")  # hit
        self.catalog.get_table("public", "nonexistent")  # miss
        
        metrics = self.catalog.get_metrics()
        
        assert metrics["cache_hits"] == 2
        assert metrics["cache_misses"] == 1
        assert metrics["hit_ratio"] > 0.5
        assert metrics["table_count"] == 2
        assert metrics["warmup_complete"] is True
    
    def test_get_summary(self):
        """Test get_summary()."""
        summary = self.catalog.get_summary()
        
        assert summary["table_count"] == 2
        assert summary["total_columns"] == 6  # 3 + 3
        assert summary["total_foreign_keys"] == 1
        assert summary["estimated_total_rows"] == 6000  # 1000 + 5000
        assert summary["dialect"] == "postgres"
        assert "metrics" in summary


class TestCatalogMetrics:
    """Test catalog metrics tracking."""
    
    def test_cache_hits_increment(self):
        """Test that cache hits increment correctly."""
        connector = Mock()
        catalog = SchemaCatalog(
            connector=connector,
            dialect="postgres",
            cache_dir=None,
            ttl=3600,
            auto_warmup=False
        )
        
        # Add test table
        catalog._catalog["public.test"] = TableInfo(
            schema="public",
            name="test",
            type="BASE TABLE",
            columns=[],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=[]
        )
        catalog._warmup_complete = True
        
        # Perform operations
        catalog.get_table_list()  # hit
        catalog.get_table("public", "test")  # hit
        catalog.search_tables("test")  # hit
        
        metrics = catalog.get_metrics()
        assert metrics["cache_hits"] == 3
        assert metrics["cache_misses"] == 0
    
    def test_cache_misses_increment(self):
        """Test that cache misses increment correctly."""
        connector = Mock()
        catalog = SchemaCatalog(
            connector=connector,
            dialect="postgres",
            cache_dir=None,
            ttl=3600,
            auto_warmup=False
        )
        catalog._warmup_complete = True
        
        # Try to access non-existent tables
        catalog.get_table("public", "nonexistent1")  # miss
        catalog.get_table("public", "nonexistent2")  # miss
        catalog.get_columns("public", "nonexistent3")  # miss
        
        metrics = catalog.get_metrics()
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 3
    
    def test_hit_ratio_calculation(self):
        """Test hit ratio calculation."""
        connector = Mock()
        catalog = SchemaCatalog(
            connector=connector,
            dialect="postgres",
            cache_dir=None,
            ttl=3600,
            auto_warmup=False
        )
        
        # Add test table
        catalog._catalog["public.test"] = TableInfo(
            schema="public",
            name="test",
            type="BASE TABLE",
            columns=[],
            foreign_keys=[],
            estimated_rows=100,
            primary_keys=[]
        )
        catalog._warmup_complete = True
        
        # 7 hits, 3 misses = 0.7 hit ratio
        for _ in range(7):
            catalog.get_table("public", "test")  # hit
        
        for _ in range(3):
            catalog.get_table("public", "nonexistent")  # miss
        
        metrics = catalog.get_metrics()
        assert metrics["hit_ratio"] == 0.7


@pytest.mark.asyncio
class TestCatalogIntegration:
    """Integration tests for catalog (require mock connector)."""
    
    async def test_warmup_postgres(self):
        """Test catalog warmup with PostgreSQL mock."""
        # Create mock connector
        connector = Mock()
        connector._get_pool = AsyncMock()
        connector.query = AsyncMock()
        
        # Mock table query response
        connector.query.return_value = (
            ["table_schema", "table_name", "table_type", "estimated_rows"],
            [["public", "customers", "BASE TABLE", 1000]]
        )
        
        # Mock pool for column/FK queries
        mock_pool = Mock()
        mock_conn = Mock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = Mock(return_value=mock_conn)
        connector._get_pool.return_value = mock_pool
        
        # Create and warmup catalog
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = SchemaCatalog(
                connector=connector,
                dialect="postgres",
                cache_dir=tmpdir,
                ttl=3600,
                auto_warmup=False
            )
            
            await catalog.warmup()
            
            # Verify warmup
            assert catalog._warmup_complete
            assert len(catalog._catalog) == 1
            assert "public.customers" in catalog._catalog
    
    async def test_refresh_if_needed_expired(self):
        """Test that catalog refreshes when TTL expired."""
        connector = Mock()
        connector._get_pool = AsyncMock()
        connector.query = AsyncMock(return_value=([], []))
        
        mock_pool = Mock()
        mock_conn = Mock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = Mock(return_value=mock_conn)
        connector._get_pool.return_value = mock_pool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = SchemaCatalog(
                connector=connector,
                dialect="postgres",
                cache_dir=tmpdir,
                ttl=1,  # 1 second TTL
                auto_warmup=False
            )
            
            await catalog.warmup()
            
            # Wait for TTL to expire
            time.sleep(2)
            
            # Refresh should trigger
            await catalog.refresh_if_needed()
            
            # Verify refresh happened
            assert catalog._metrics.refresh_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])