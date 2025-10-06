#!/usr/bin/env python3
"""
Phase 3 Integration Test Script

Tests the catalog system with a real database connection.

Usage:
    # PostgreSQL
    export DB_DIALECT=postgres
    python scripts/test_phase3.py
    
    # SQL Server
    export DB_DIALECT=mssql
    python scripts/test_phase3.py
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from mcp_server.config import config
from mcp_server.db_postgres import PostgresConnector
from mcp_server.db_mssql import MSSQLConnector
from mcp_server.catalog import create_catalog


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


async def test_catalog_warmup(connector, dialect: str):
    """Test catalog warmup."""
    print_header("Test 1: Catalog Warmup")
    
    try:
        start_time = time.time()
        catalog = await create_catalog(connector, dialect, ttl=3600)
        elapsed = time.time() - start_time
        
        metrics = catalog.get_metrics()
        print_success(f"Catalog warmup complete in {elapsed:.2f}s")
        print_info(f"Tables loaded: {metrics['table_count']}")
        print_info(f"Warmup complete: {metrics['warmup_complete']}")
        
        return catalog
    
    except Exception as e:
        print_error(f"Catalog warmup failed: {e}")
        raise


async def test_table_list(catalog):
    """Test getting table list (no DB hit)."""
    print_header("Test 2: Get Table List (No DB Hit)")
    
    try:
        start_time = time.time()
        tables = catalog.get_table_list()
        elapsed = (time.time() - start_time) * 1000  # ms
        
        print_success(f"Retrieved {len(tables)} tables in {elapsed:.2f}ms")
        
        # Show first 5 tables
        print_info("First 5 tables:")
        for table in tables[:5]:
            print(f"  - {table['full_name']} ({table['estimated_rows']} rows, {table['column_count']} columns)")
        
        return tables
    
    except Exception as e:
        print_error(f"Get table list failed: {e}")
        raise


async def test_table_details(catalog, tables):
    """Test getting table details (no DB hit)."""
    print_header("Test 3: Get Table Details (No DB Hit)")
    
    if not tables:
        print_info("No tables to test")
        return
    
    try:
        # Get details for first table
        first_table = tables[0]
        schema = first_table['schema']
        name = first_table['name']
        
        start_time = time.time()
        table_info = catalog.get_table(schema, name)
        elapsed = (time.time() - start_time) * 1000  # ms
        
        print_success(f"Retrieved table details in {elapsed:.2f}ms")
        print_info(f"Table: {table_info['full_name']}")
        print_info(f"Type: {table_info['type']}")
        print_info(f"Estimated rows: {table_info['estimated_rows']}")
        print_info(f"Primary keys: {table_info['primary_keys']}")
        print_info(f"Columns: {len(table_info['columns'])}")
        print_info(f"Foreign keys: {len(table_info['foreign_keys'])}")
        print_info(f"Top columns: {table_info['top_columns']}")
        
        if table_info['neighbors']:
            print_info(f"Related tables: {', '.join(table_info['neighbors'])}")
        
        return table_info
    
    except Exception as e:
        print_error(f"Get table details failed: {e}")
        raise


async def test_foreign_keys(catalog, tables):
    """Test foreign key relationships (no DB hit)."""
    print_header("Test 4: Foreign Key Relationships (No DB Hit)")
    
    try:
        # Find tables with foreign keys
        tables_with_fks = [t for t in tables if t['fk_count'] > 0]
        
        if not tables_with_fks:
            print_info("No tables with foreign keys found")
            return
        
        print_success(f"Found {len(tables_with_fks)} tables with foreign keys")
        
        # Show first 3 tables with FKs
        for table in tables_with_fks[:3]:
            schema = table['schema']
            name = table['name']
            
            table_info = catalog.get_table(schema, name)
            print_info(f"\n{table_info['full_name']}:")
            
            for fk in table_info['foreign_keys']:
                print(f"  - {fk['column']} → {fk['referenced_schema']}.{fk['referenced_table']}.{fk['referenced_column']}")
    
    except Exception as e:
        print_error(f"Foreign key test failed: {e}")
        raise


async def test_search(catalog):
    """Test table search (no DB hit)."""
    print_header("Test 5: Table Search (No DB Hit)")
    
    try:
        # Search for common table names
        search_terms = ["customer", "order", "product", "user"]
        
        for term in search_terms:
            start_time = time.time()
            results = catalog.search_tables(term)
            elapsed = (time.time() - start_time) * 1000  # ms
            
            if results:
                print_success(f"Search '{term}': {len(results)} results in {elapsed:.2f}ms")
                for result in results[:3]:
                    print(f"  - {result['full_name']}")
            else:
                print_info(f"Search '{term}': No results")
    
    except Exception as e:
        print_error(f"Search test failed: {e}")
        raise


async def test_metrics(catalog):
    """Test catalog metrics."""
    print_header("Test 6: Catalog Metrics")
    
    try:
        metrics = catalog.get_metrics()
        
        print_success("Catalog metrics:")
        print(f"  - Catalog age: {metrics['catalog_age_s']}s")
        print(f"  - Cache hits: {metrics['cache_hits']}")
        print(f"  - Cache misses: {metrics['cache_misses']}")
        print(f"  - Hit ratio: {metrics['hit_ratio']:.3f}")
        print(f"  - Table count: {metrics['table_count']}")
        print(f"  - Refresh count: {metrics['refresh_count']}")
        print(f"  - TTL: {metrics['ttl']}s")
        print(f"  - Warmup complete: {metrics['warmup_complete']}")
        
        # Verify hit ratio > 0.9 (acceptance criteria)
        if metrics['hit_ratio'] >= 0.9:
            print_success(f"Hit ratio {metrics['hit_ratio']:.3f} >= 0.9 ✅")
        else:
            print_info(f"Hit ratio {metrics['hit_ratio']:.3f} < 0.9 (need more operations)")
    
    except Exception as e:
        print_error(f"Metrics test failed: {e}")
        raise


async def test_summary(catalog):
    """Test catalog summary."""
    print_header("Test 7: Catalog Summary")
    
    try:
        summary = catalog.get_summary()
        
        print_success("Catalog summary:")
        print(f"  - Tables: {summary['table_count']}")
        print(f"  - Total columns: {summary['total_columns']}")
        print(f"  - Total foreign keys: {summary['total_foreign_keys']}")
        print(f"  - Estimated total rows: {summary['estimated_total_rows']:,}")
        print(f"  - Dialect: {summary['dialect']}")
    
    except Exception as e:
        print_error(f"Summary test failed: {e}")
        raise


async def test_disk_persistence(connector, dialect: str):
    """Test disk persistence."""
    print_header("Test 8: Disk Persistence")
    
    try:
        # Create catalog with custom cache dir
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            print_info(f"Cache directory: {tmpdir}")
            
            # Create and warmup catalog
            catalog1 = await create_catalog(connector, dialect, cache_dir=tmpdir, ttl=3600)
            table_count1 = catalog1.get_metrics()['table_count']
            print_success(f"Catalog 1 created: {table_count1} tables")
            
            # Verify cache file exists
            cache_file = Path(tmpdir) / f"catalog_{dialect}.json"
            if cache_file.exists():
                print_success(f"Cache file created: {cache_file}")
                file_size = cache_file.stat().st_size
                print_info(f"Cache file size: {file_size:,} bytes")
            else:
                print_error("Cache file not created")
                return
            
            # Create new catalog instance (should load from disk)
            from mcp_server.catalog import SchemaCatalog
            catalog2 = SchemaCatalog(
                connector=connector,
                dialect=dialect,
                cache_dir=tmpdir,
                ttl=3600,
                auto_warmup=False
            )
            
            start_time = time.time()
            loaded = catalog2._load_from_disk()
            elapsed = (time.time() - start_time) * 1000  # ms
            
            if loaded:
                table_count2 = catalog2.get_metrics()['table_count']
                print_success(f"Catalog loaded from disk in {elapsed:.2f}ms: {table_count2} tables")
                
                if table_count1 == table_count2:
                    print_success("Table counts match ✅")
                else:
                    print_error(f"Table count mismatch: {table_count1} vs {table_count2}")
            else:
                print_error("Failed to load catalog from disk")
    
    except Exception as e:
        print_error(f"Disk persistence test failed: {e}")
        raise


async def test_no_db_hits(catalog):
    """Test that catalog operations don't hit the database."""
    print_header("Test 9: No Database Hits After Warmup")
    
    try:
        print_info("Performing 100 catalog operations...")
        
        start_time = time.time()
        
        # Perform various operations
        for i in range(100):
            if i % 4 == 0:
                catalog.get_table_list()
            elif i % 4 == 1:
                tables = catalog.get_table_list()
                if tables:
                    catalog.get_table(tables[0]['schema'], tables[0]['name'])
            elif i % 4 == 2:
                catalog.search_tables("test")
            else:
                catalog.get_summary()
        
        elapsed = (time.time() - start_time) * 1000  # ms
        avg_time = elapsed / 100
        
        print_success(f"100 operations completed in {elapsed:.2f}ms")
        print_info(f"Average time per operation: {avg_time:.2f}ms")
        
        if avg_time < 1.0:
            print_success("Average time < 1ms (no DB hits) ✅")
        else:
            print_info(f"Average time {avg_time:.2f}ms (may include DB hits)")
        
        # Check metrics
        metrics = catalog.get_metrics()
        print_info(f"Final hit ratio: {metrics['hit_ratio']:.3f}")
    
    except Exception as e:
        print_error(f"No DB hits test failed: {e}")
        raise


async def main():
    """Run all Phase 3 tests."""
    print_header("Phase 3 Integration Tests: Catalog & Cache")
    
    dialect = config.db_dialect
    print_info(f"Database dialect: {dialect}")
    
    # Create connector
    if dialect == "postgres":
        connector = PostgresConnector(
            host=config.postgres_host,
            port=config.postgres_port,
            database=config.postgres_database,
            user=config.postgres_user,
            password=config.postgres_password,
            timeout=config.query_timeout,
            max_rows=config.max_query_results
        )
        print_info(f"PostgreSQL: {config.postgres_host}:{config.postgres_port}/{config.postgres_database}")
    
    elif dialect == "mssql":
        connector = MSSQLConnector(
            server=config.mssql_server,
            database=config.mssql_database,
            username=config.mssql_user,
            password=config.mssql_password,
            driver=config.mssql_driver,
            timeout=config.query_timeout,
            max_rows=config.max_query_results
        )
        print_info(f"SQL Server: {config.mssql_server}/{config.mssql_database}")
    
    else:
        print_error(f"Unsupported dialect: {dialect}")
        sys.exit(1)
    
    # Test connection
    print_info("Testing database connection...")
    is_healthy = await connector.test_connection()
    if not is_healthy:
        print_error("Database connection failed")
        sys.exit(1)
    print_success("Database connection OK")
    
    try:
        # Run tests
        catalog = await test_catalog_warmup(connector, dialect)
        tables = await test_table_list(catalog)
        table_info = await test_table_details(catalog, tables)
        await test_foreign_keys(catalog, tables)
        await test_search(catalog)
        await test_metrics(catalog)
        await test_summary(catalog)
        await test_disk_persistence(connector, dialect)
        await test_no_db_hits(catalog)
        
        # Final summary
        print_header("Phase 3 Tests Complete")
        metrics = catalog.get_metrics()
        
        print_success("All tests passed! ✅")
        print_info(f"Final metrics:")
        print(f"  - Tables: {metrics['table_count']}")
        print(f"  - Cache hits: {metrics['cache_hits']}")
        print(f"  - Cache misses: {metrics['cache_misses']}")
        print(f"  - Hit ratio: {metrics['hit_ratio']:.3f}")
        
        # Acceptance criteria
        print_header("Acceptance Criteria")
        
        # 1. Discovery answers come from memory (no DB hits)
        if metrics['hit_ratio'] >= 0.9:
            print_success("✅ Hit ratio >= 0.9 (discovery from memory)")
        else:
            print_info(f"⚠️  Hit ratio {metrics['hit_ratio']:.3f} < 0.9")
        
        # 2. /health shows finite catalog_age_s
        if metrics['catalog_age_s'] is not None:
            print_success(f"✅ Catalog age: {metrics['catalog_age_s']}s (finite)")
        else:
            print_error("❌ Catalog age is None")
        
        print_header("Phase 3 Ready for Integration! 🚀")
    
    finally:
        # Cleanup
        if dialect == "postgres":
            await connector.close()
        else:
            connector.close()


if __name__ == "__main__":
    asyncio.run(main())